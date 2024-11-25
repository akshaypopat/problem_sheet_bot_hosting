import discord
from discord import app_commands
from discord.ext import commands
import pandas as pd
from jinja2 import Template
import json
import asyncio
import os

"""
Discord bot that tracks problem sheet progress.
"""

token = os.getenv("DISCORD_TOKEN")
if token is None:
    print("DISCORD_TOKEN environment variable not set!")
else:
    print("Bot token is set successfully!")

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
        progress_data = {}

def save_progress_data():
    with open("progress_data.json", "w") as file:
        json.dump(progress_data, file)

def update_progress(user_id, week, module, progress):
    week = str(week)
    if user_id not in progress_data:
        progress_data[user_id] = {}
    if week not in progress_data[user_id]:
        progress_data[user_id][week] = {m: 0 for m in modules}
    
    current_progress = progress_data[user_id][week].get(module, 0)
    new_progress = min(current_progress + progress, 100)
    new_progress = max(new_progress, 0)
    progress_data[user_id][week][module] = new_progress

def get_user_progress(user_id):
    print(progress_data) # Remove later
    print([type(userid) for userid in progress_data.keys()]) # Remove later
    return progress_data.get(user_id, {})

def generate_html_table(user_id, weeks, selected_modules):
    user_progress = get_user_progress(user_id)
    data = []

    for week in weeks:
        row = [
            user_progress.get(week, {}).get(module, 0)  # Match string week keys
            for module in selected_modules
        ]
        data.append(row)

    df = pd.DataFrame(data, index=weeks, columns=selected_modules)
    
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
        print("Progress data saved.")

# Mock database
load_progress_data()
modules = [
    "Analysis 2",
    "Linear Algebra and Numerical Analysis",
    "Multivariable Calculus and Differential Equations",
    "Groups and Rings",
    "Probability for Statistics",
    "Principles of Programming",
]

# Commands
@bot.command()
async def log(ctx, week: int, module: str, progress: float):
    week = str(week)
    if module not in modules:
        await ctx.send(f"Invalid module. Choose from: {', '.join(modules)}")
        return

    # Check if progress is between 0 and 100
    if progress > 100:
        await ctx.send("Progress must be between 0 and 100!")
        return
    
    update_progress(ctx.author.id, week, module, progress)
    await ctx.send(f"Progress updated for {ctx.author.name}: Week {week}, {module}, +{progress}%!")

@bot.command()
async def leaderboard(ctx, week: int):
    week = str(week)
    save_progress_data() # Remove later
    leaderboard = []
    print(progress_data) # Remove later

    for user_id, user_data in progress_data.items():
        total_progress = sum(user_data.get(week, {}).values())
        leaderboard.append((user_id, total_progress))

    leaderboard.sort(key=lambda x: x[1], reverse=True)
    print(leaderboard) # Remove later
    leaderboard_message = "Leaderboard:\n"
    for rank, (user_id, total) in enumerate(leaderboard, start=1):
        user = await bot.fetch_user(user_id)
        leaderboard_message += f"{rank}. {user.name} - {total}\n"

    await ctx.send(f"```{leaderboard_message}```")

@bot.command()
async def myprogress(ctx):
    progress = get_user_progress(ctx.author.id)
    progress_message = "Your Progress:\n"

    for week, modules_progress in progress.items():
        progress_message += f"Week {week}:\n"
        for module, percentage in modules_progress.items():
            progress_message += f"  {module}: {percentage}%\n"

    await ctx.send(f"```{progress_message}```")

@bot.command()
async def export(ctx, weeks: str, modules: str = None):
    user_id = ctx.author.id
    try:
        weeks = [week.strip() for week in weeks.split(",")]
    except ValueError:
        await ctx.send(
            "Invalid weeks format. Use a comma-separated list, e.g., `1,2,3`."
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
        html_content = generate_html_table(user_id, weeks, selected_modules)
        with open("progress.html", "w") as f:
            f.write(html_content)
        await ctx.send(file=discord.File("progress.html"))
    except Exception as e:
        print(f"Error exporting progress: {e}")
        await ctx.send("Failed to export progress. Please try again.")

@bot.tree.command(name="log", description="Log your progress on a problem sheet")
@app_commands.describe(
    week="The week number (e.g., 1, 2, 3)",
    module="The module you're working on (choose from options)",
    progress="The percentage of progress you made"
)
async def log(interaction: discord.Interaction, week: int, module: str, progress: float):
    week = str(week)
    if module not in modules:
        await interaction.response.send_message(f"Invalid module. Choose from: {', '.join(modules)}")
        return

    update_progress(interaction.user.id, week, module, progress)
    await interaction.response.send_message(f"Progress updated for {interaction.user.name}: Week {week}, {module}, +{progress}%!")

@log.autocomplete('module')
async def module_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=module, value=module)
        for module in modules if current.lower() in module.lower()
    ]

@bot.tree.command(name="leaderboard", description="See the problem sheet leaderboards")
@app_commands.describe(
    week="The week number (e.g., 1, 2, 3)",
    module="The module to filter by (choose from options)"
)
async def leaderboard(interaction: discord.Interaction, week: int = None, module: str = None):
    if week:
        week = str(week)
    leaderboard = []

    if module and (module not in modules):
        await interaction.response.send_message(
            f"Invalid module. Choose from: {', '.join(modules)}"
        )
        return

    # Calculate leaderboard
    for user_id, user_data in progress_data.items():
        print("gamma") # Remove later
        if week: # Remove later
            print(f"We have week: week = {week}") # Remove later
        if module: # Remove later
            print(f"We have module: module = {module}") # Remove later
        if week is None: # Remove later
            print("Week is None") # Remove later
        if week and module:  # Specific week and module
            total_points = user_data.get(week, {}).get(module, 0)
        elif week:  # Specific week
            total_points = sum(user_data.get(week, {}).values())
        elif module:  # Specific module
            print(progress_data) # Remove later
            print([week_data.get(module, 0) for week_data in user_data.values()]) # Remove later
            total_points = sum(
                week_data.get(module, 0) for week_data in user_data.values()
            )
        else:  # All weeks and modules
            total_points = sum(
                module_points for week_data in user_data.values() for module_points in week_data.values()
            )

        leaderboard.append((user_id, total_points))

    # Sort leaderboard by total points
    leaderboard.sort(key=lambda x: x[1], reverse=True)

    # Format leaderboard message
    leaderboard_message = "Leaderboard:\n"
    for rank, (user_id, total) in enumerate(leaderboard, start=1):
        user = await bot.fetch_user(user_id)
        leaderboard_message += f"{rank}. {user.name} - {total}\n"

    await interaction.response.send_message(f"```{leaderboard_message}```")

@leaderboard.autocomplete("module")
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
    print("Commands synced.")
    bot.loop.create_task(save_periodically())

# Run the bot
bot.run(token)
