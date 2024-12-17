import requests
import base64
import os

APP_KEY = os.getenv("DROPBOX_APP_KEY")
APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")

# Dropbox API endpoint for refreshing tokens
TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"

def refresh_access_token():
    # Prepare the HTTP Basic Authentication header
    credentials = f"{APP_KEY}:{APP_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # Data for the POST request
    data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
    }

    # Send the POST request
    response = requests.post(TOKEN_URL, headers=headers, data=data)

    # Check the response
    if response.status_code == 200:
        new_tokens = response.json()
        print("Token Expires In:", new_tokens["expires_in"], "seconds")
        return new_tokens["access_token"]
    else:
        print("Error refreshing access token:", response.text)
        return None
