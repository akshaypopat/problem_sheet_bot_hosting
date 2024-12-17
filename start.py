import discord
from discord import app_commands
from discord.ext import commands
import pandas as pd
from datetime import datetime
from jinja2 import Template
import json
import asyncio
import os
import dropbox
import random
import string
import csv
import matplotlib.pyplot as plt
from io import BytesIO
import matplotlib.dates as mdates
from get_new_dropbox_access_token import refresh_access_token

token = os.getenv("TOKEN_DISCORD")
if token is None:
    print("DISCORD_TOKEN environment variable not set!")
else:
    print("Bot token is set successfully!")

db_token = refresh_access_token()
if db_token is None:
    print("Couldn't get Dropbox access token!")
else:
    print("Dropbox token is set successfully!")

# Bot setup
intents = discord.Intents.all()
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Helper functions
def load_progress_data():
    global progress_data
    try:
        with open("progress_data.json", "r") as file:
            loaded_data = json.load(file)
            progress_data = {int(user_id): v for user_id, v in loaded_data.items()}

    except FileNotFoundError:
        print("progress_data.json not found. Starting empty leaderboard.")
        progress_data = {}

def load_from_dropbox(dropbox_path, local_path, db_token):
    dbx = dropbox.Dropbox(db_token)
    try:
        metadata, response = dbx.files_download(dropbox_path)
        with open(local_path, "wb") as file:
            file.write(response.content)
        print(f"File downloaded successfully to {local_path}")
    except dropbox.exceptions.ApiError as e:
        print(f"Dropbox API error while downloading: {e}")

def save_to_dropbox(file_path, dropbox_path, db_token):
    """Save a file to Dropbox and also create a backup with a random filename."""
    dbx = dropbox.Dropbox(db_token)
    with open(file_path, 'rb') as file:
        try:
            # Save to primary path
            dbx.files_upload(file.read(), dropbox_path, mode=dropbox.files.WriteMode("overwrite"))
            print(f"File uploaded successfully to {dropbox_path}")
        except dropbox.exceptions.ApiError as e:
            print(f"Dropbox API error for {dropbox_path}: {e}")
        
        # Create a backup with a random filename
        random_backup_path = f"/{generate_random_filename()}_{dropbox_path[1::]}"
        file.seek(0)  # Reset file pointer to the beginning
        try:
            dbx.files_upload(file.read(), random_backup_path, mode=dropbox.files.WriteMode("overwrite"))
            print(f"Backup file uploaded successfully to {random_backup_path}")
        except dropbox.exceptions.ApiError as e:
            print(f"Dropbox API error for backup {random_backup_path}: {e}")

def get_user_log_file(user_id):
    return f"{user_id}_logs.csv"

def append_to_user_log(user_id, date, sheet_number, module, progress, comment):
    log_file = get_user_log_file(user_id)
    is_new_file = not os.path.exists(log_file)
    
    with open(log_file, mode='a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if is_new_file:
            writer.writerow(["Date", "Sheet Number", "Module", "Progress", "Comment"])
        writer.writerow([date, sheet_number, module, progress, comment])

def save_user_logs(user_id, username):
    """Save the user's logs to Dropbox using their username."""
    log_file = get_user_log_file(user_id)
    if os.path.exists(log_file):
        dropbox_path = f"/{username}.csv"  # Dropbox path based on username
        try:
            save_to_dropbox(log_file, dropbox_path, db_token)
        except:
            db_token = refresh_access_token()
            save_to_dropbox(log_file, dropbox_path, db_token)
    else:
        print(f"No logs found for user_id {user_id}, skipping Dropbox upload.")

def save_progress_data():
    with open("progress_data.json", "w") as file:
        json.dump(progress_data, file)

def generate_random_filename():
    """Generate a random 20-character string for backup filenames."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=20))

def update_progress(user_id, week, module, progress, comment):
    week = str(week)
    if user_id not in progress_data:
        progress_data[user_id] = {}
    if week not in progress_data[user_id]:
        progress_data[user_id][week] = {m: 0 for m in modules}
    
    current_progress = progress_data[user_id][week].get(module, 0)
    new_progress = min(current_progress + progress, 100)
    new_progress = max(new_progress, 0)
    progress_data[user_id][week][module] = new_progress
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Logged progress: {progress}")
    print(f"new_progress = {new_progress}")
    print(f"current_progress = {current_progress}")
    print(f"new_progress - current_progress = {new_progress - current_progress}")
    append_to_user_log(user_id, date, week, module, new_progress - current_progress, comment)

def get_user_progress(user_id):
    print(progress_data)
    print([type(userid) for userid in progress_data.keys()])
    return progress_data.get(user_id, {})

def generate_html_table(user_id, weeks, selected_modules):
    user_progress = get_user_progress(user_id)
    data = []
    for week in weeks:
        row = [
            user_progress.get(week, {}).get(module, 0)  # Default to 0 if no progress logged
            for module in selected_modules
        ]
        data.append(row)

    # Create a DataFrame
    df = pd.DataFrame(data, index=weeks, columns=selected_modules)

    # Round values to the nearest integer
    df = df.round(0).astype(int)

    # Generate heatmap HTML
    template = Template(
        """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <style>
                table {
                    border-collapse: collapse;
                    width: 100%;
                }
                th, td {
                    border: 1px solid black;
                    text-align: center;
                    padding: 8px;
                }
            </style>
        </head>
        <body>
            <h2>Progress Heatmap</h2>
            {{ table_html }}
        </body>
        </html>
        """
    )
    styled_table = df.style.background_gradient(cmap="coolwarm_r", axis=None)
    table_html = styled_table.to_html()
    return template.render(table_html=table_html)

async def save_periodically():
    while True:
        await asyncio.sleep(600)  # Wait for 10 minutes
        save_progress_data()  # Save data
        try:
            save_to_dropbox("progress_data.json", "/progress_data.json", db_token)
        except:
            db_token = refresh_access_token()
            save_to_dropbox("progress_data.json", "/progress_data.json", db_token)
        print("Progress data saved.")

load_progress_data()
modules = [
    "Analysis 2",
    "Linear Algebra and Numerical Analysis",
    "Multivariable Calculus and Differential Equations",
    "Groups and Rings",
    "Lebesgue Measure and Integration",
    "Network Science",
    "Partial Differential Equations in Action",
    "Probability for Statistics",
    "Statistical Modelling 1",
    "Principles of Programming"
]

# Commands
@bot.command()
async def log(ctx, sheet_number: int, module: str, progress: float):
    sheet_number = str(sheet_number)
    if module not in modules:
        await ctx.send(f"Invalid module. Choose from: {', '.join(modules)}")
        return

    # Check if progress is between 0 and 100
    if progress > 100:
        await ctx.send("Progress must be between 0 and 100!")
        return
    
    update_progress(ctx.author.id, sheet_number, module, progress)
    await ctx.send(f"Progress updated for {ctx.author.name}: Sheet number {sheet_number}, {module}, +{progress}%!")

@bot.command()
async def leaderboard(ctx, sheet_number: int):
    sheet_number = str(sheet_number)
    save_progress_data() # Remove later
    try:
        save_to_dropbox("progress_data.json", "/progress_data.json", db_token) # Remove later
    except:
        db_token = refresh_access_token()
        save_to_dropbox("progress_data.json", "/progress_data.json", db_token) # Remove later 
    leaderboard = []
    print(progress_data)

    for user_id, user_data in progress_data.items():
        total_progress = sum(user_data.get(sheet_number, {}).values())
        leaderboard.append((user_id, total_progress))

    leaderboard.sort(key=lambda x: x[1], reverse=True)
    print(leaderboard)
    leaderboard_message = "Leaderboard:\n"
    for rank, (user_id, total) in enumerate(leaderboard, start=1):
        user = await bot.fetch_user(user_id)
        leaderboard_message += f"{rank}. {user.name} - {total}\n"

    await ctx.send(f"```{leaderboard_message}```")

@bot.command()
async def myprogress(ctx):
    progress = get_user_progress(ctx.author.id)
    progress_message = "Your Progress:\n"

    for sheet_number, modules_progress in progress.items():
        progress_message += f"Sheet number {sheet_number}:\n"
        for module, percentage in modules_progress.items():
            progress_message += f"  {module}: {percentage}%\n"

    await ctx.send(f"```{progress_message}```")

@bot.command()
async def export(ctx, sheets: str, modules: str = None):
    user_id = ctx.author.id
    try:
        sheets = [sheet.strip() for sheet in sheets.split(",")]
    except ValueError:
        await ctx.send(
            "Invalid sheet numbers format. Use a comma-separated list, e.g., `1,2,3`."
        )
        return

    selected_modules = (
        [module.strip() for module in modules.split(",")] if modules else modules
    )
    if selected_modules:
        for module in selected_modules:
            if module not in modules:
                await ctx.send(
                    f"Invalid module: {module}. Choose from: {', '.join(modules)}"
                )
                return
    else:
        selected_modules = modules  # Default to all modules

    try:
        html_content = generate_html_table(user_id, sheets, selected_modules)
        with open("progress.html", "w") as f:
            f.write(html_content)
        await ctx.send(file=discord.File("progress.html"))
    except Exception as e:
        print(f"Error exporting progress: {e}")
        await ctx.send("Failed to export progress. Please try again.")

@bot.tree.command(name="log", description="Log your progress on a problem sheet")
@app_commands.describe(
    sheet_number="The sheet number (e.g., 1, 2, 3)",
    module="The module you're working on (choose from options)",
    progress="The percentage of progress you made"
)
async def log(interaction: discord.Interaction, sheet_number: int, module: str, progress: float, comment: str = ""):
    sheet_number = str(sheet_number)
    if module not in modules:
        await interaction.response.send_message(f"Invalid module. Choose from: {', '.join(modules)}")
        return

    update_progress(interaction.user.id, sheet_number, module, progress, comment)
    save_user_logs(interaction.user.id, interaction.user.name)
    await interaction.response.send_message(f"Progress updated for {interaction.user.name}: Sheet {sheet_number}, {module}, +{progress}%!\n\n{comment}")

@log.autocomplete('module')
async def module_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=module, value=module)
        for module in modules if current.lower() in module.lower()
    ]

@bot.tree.command(name="leaderboard", description="See the problem sheet leaderboards")
@app_commands.describe(
    sheet_number="The sheet number (e.g., 1, 2, 3)",
    module="The module to filter by (choose from options)"
)
async def leaderboard(interaction: discord.Interaction, sheet_number: int = None, module: str = None):
    leaderboard_prefix = ""
    if sheet_number:
        sheet_number = str(sheet_number)
        leaderboard_prefix += "Sheet " + sheet_number + ' '
    if module:
        leaderboard_prefix += module + ' '
    leaderboard = []
    

    if module and (module not in modules):
        await interaction.response.send_message(
            f"Invalid module. Choose from: {', '.join(modules)}"
        )
        return

    # Calculate leaderboard
    for user_id, user_data in progress_data.items():
        if sheet_number:
            print(f"We have sheet_number: sheet_number = {sheet_number}") # Remove later
        if module:
            print(f"We have module: module = {module}")
        if sheet_number is None:
            print("sheet_number is None")

        if sheet_number and module:  # Specific sheet and module
            total_points = user_data.get(sheet_number, {}).get(module, 0)
        elif sheet_number:  # Specific sheet
            total_points = sum(user_data.get(sheet_number, {}).values())
        elif module:  # Specific module
            print(progress_data) # Remove later
            print([sheet_data.get(module, 0) for sheet_data in user_data.values()]) # Remove later
            total_points = sum(
                sheet_data.get(module, 0) for sheet_data in user_data.values()
            )
        else:  # All sheets and modules
            total_points = sum(
                module_points for sheet_data in user_data.values() for module_points in sheet_data.values()
            )

        leaderboard.append((user_id, total_points))

    # Sort leaderboard by total points
    leaderboard.sort(key=lambda x: x[1], reverse=True)

    # Format leaderboard message
    leaderboard_message = leaderboard_prefix + "Leaderboard:\n"
    for rank, (user_id, total) in enumerate(leaderboard, start=1):
        user = await bot.fetch_user(user_id)
        leaderboard_message += f"{rank}. {user.name} - {total}\n"

    await interaction.response.send_message(f"```{leaderboard_message}```")

@leaderboard.autocomplete('module')
async def module_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=module, value=module)
        for module in modules if current.lower() in module.lower()
    ]

@bot.tree.command(name="export", description="Export your progress as an HTML table")
@app_commands.describe(
    sheets="Comma-separated list of sheet numbers (optional, defaults to all sheets you've logged)",
    selected_modules="Comma-separated list of modules (optional, defaults to logged modules)"
)
async def export(interaction: discord.Interaction, sheets: str = "", selected_modules: str = ""):
    user_id = interaction.user.id

    # Get user's progress data
    user_progress = get_user_progress(user_id)

    # Infer all sheets if none are provided
    if not sheets.strip():
        sheets = list(user_progress.keys())
        if not sheets:
            await interaction.response.send_message(
                "You have no progress logged, so there's nothing to export."
            )
            return
    else:
        try:
            sheets = [sheet.strip() for sheet in sheets.split(",")]
        except ValueError:
            await interaction.response.send_message(
                "Invalid sheet numbers format. Use a comma-separated list, e.g., `1,2,3`."
            )
            return

    # Infer modules if none are provided
    if not selected_modules.strip():
        # Find all modules with progress > 0 for the user
        selected_modules = list({
            module
            for sheet_data in user_progress.values()
            for module, progress in sheet_data.items()
            if progress > 0
        })
        if not selected_modules:
            await interaction.response.send_message(
                "You have no progress logged for any modules, so there's nothing to export."
            )
            return
    else:
        selected_modules = [module.strip() for module in selected_modules.split(",")]
        for module in selected_modules:
            if module not in modules:
                await interaction.response.send_message(
                    f"Invalid module: {module}. Choose from: {', '.join(modules)}"
                )
                return

    # Generate and send HTML table
    try:
        html_content = generate_html_table(user_id, sheets, selected_modules)
        with open("progress.html", "w") as f:
            f.write(html_content)

        await interaction.response.send_message(
            "Here's your exported progress!",
            file=discord.File("progress.html")
        )
    except Exception as e:
        print(f"Error exporting progress: {e}")
        await interaction.response.send_message(
            "Failed to export progress. Please try again."
        )

@bot.tree.command(name="alllogs", description="Export all of your logs as a CSV file")
async def alllogs(interaction: discord.Interaction):
    user_id = interaction.user.id
    log_file = get_user_log_file(user_id)

    if not os.path.exists(log_file):
        await interaction.response.send_message("You have no logs to export.")
        return

    await interaction.response.send_message(
        "Here are all your logs!",
        file=discord.File(log_file)
    )

@bot.tree.command(name="race", description="Show progress race across users with a line graph.")
@app_commands.describe(
    sheets="Filter by sheet number (e.g., 1, 2, 3) (comma separated)",
    module="Filter by module (choose from options)",
    start_date="Filter data from this date onwards (YYYY-MM-DD)"
)
async def race(interaction: discord.Interaction, sheets: str = "", module: str = None, start_date: str = None):
    # Convert sheets input into a list
    sheets = [sheet.strip() for sheet in sheets.split(',')] if sheets else None

    # Parse start_date
    if start_date:
        try:
            start_date = pd.to_datetime(start_date)
        except ValueError:
            await interaction.response.send_message("Invalid `start_date` format. Please use YYYY-MM-DD.", ephemeral=True)
            return

    # Initialize a dictionary to store user progress over time
    user_data = {}

    # Get the current time for the end dummy point
    current_time = datetime.now()

    # Loop through all CSV files in the directory
    for file in os.listdir():
        if file.endswith(".csv"):
            user_id = os.path.splitext(file)[0].partition('_')[0]  # Extract user ID from file name

            try:
                # Read the CSV file
                df = pd.read_csv(file)

                # Filter by sheet and/or module if applicable
                if sheets:
                    df = df[df["Sheet Number"].astype(str).isin(sheets)]
                if module:
                    df = df[df["Module"] == module]

                # Ensure 'Date' is datetime and filter by start_date if provided
                df["Date"] = pd.to_datetime(df["Date"])
                if start_date:
                    df = df[df["Date"] >= start_date]

                # Group progress by date
                df = df.groupby("Date")["Progress"].sum().cumsum().reset_index()

                # Add dummy point for the start (progress=0 at the first log time)
                start_time = df["Date"].min()
                if not start_time:
                    continue  # Skip if there's no valid data after filtering
                df = pd.concat([
                    pd.DataFrame({"Date": [start_time], "Progress": [0]}),
                    df
                ], ignore_index=True)

                # Add dummy point for the end (progress=cumulative progress at current time)
                current_progress = df["Progress"].iloc[-1]
                df = pd.concat([
                    df,
                    pd.DataFrame({"Date": [current_time], "Progress": [current_progress]})
                ], ignore_index=True)

                # Store user progress
                user_data[user_id] = df
            except Exception as e:
                print(f"Error reading file {file}: {e}")

    # Plotting the data
    plt.figure(figsize=(10, 6))
    for user_id, df in user_data.items():
        # Fetch user's display name
        user = await bot.fetch_user(int(user_id))
        display_name = user.display_name if user else user_id

        # Plot the user's progress
        plt.plot(df["Date"], df["Progress"], label=display_name)

    plt.title("Progress Race")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Progress (%)")

    # Set x-axis ticks to display daily labels
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())  # Display every day
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%b %d, %Y'))  # Format as 'Jan 01, 2022'
    plt.xticks(rotation=45)  # Rotate labels to avoid overlap

    plt.tight_layout()

    plt.legend(title="Users")
    plt.grid()

    # Save plot to a BytesIO object
    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close()

    # Send the image
    await interaction.response.send_message(file=discord.File(fp=buffer, filename="progress_race.png"))

@race.autocomplete('module')
async def module_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=module, value=module)
        for module in modules if current.lower() in module.lower()
    ]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    # Sync commands with Discord
    await bot.tree.sync()
    try:
        load_from_dropbox("/progress_data.json", "progress_data.json", db_token)
    except:
        db_token = refresh_access_token()
        load_from_dropbox("/progress_data.json", "progress_data.json", db_token) 
    load_progress_data()
    print("Commands synced.")
    bot.loop.create_task(save_periodically())

# Run the bot
bot.run(token)
