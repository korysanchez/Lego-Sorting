import dropbox
import requests
from dropbox.files import WriteMode
import os
import re

# Read API keys
keys = []
with open("./keys", "r") as file:
    keys = [file.readline().strip() for _ in range(6)]
REFRESH_TOKEN = keys[3]
APP_KEY = keys[4]
APP_SECRET = keys[5]

ACCESS_TOKEN = None


def get_access_token(depth):
    global ACCESS_TOKEN

    if ACCESS_TOKEN is None:
        # Use the refresh token to get a new access token
        token_url = 'https://api.dropboxapi.com/oauth2/token'
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': REFRESH_TOKEN,
            'client_id': APP_KEY,
            'client_secret': APP_SECRET,
        }

        response = requests.post(token_url, data=data)
        tokens = response.json()

        if 'access_token' in tokens:
            ACCESS_TOKEN = tokens['access_token']
            print(f"{'  ' * depth}        Access token refreshed!")
        else:
            print(f"{'  ' * depth}        Error refreshing access token: {tokens}")
            exit(0)
            return None

    return ACCESS_TOKEN


def sanitize_path(path):
    sanitized_path = re.sub(r'[<>:"|?*]', '', path)  # Remove invalid characters
    sanitized_path = sanitized_path.replace('\\', '/')  # forward slashes for dropbox
    #sanitized_path = re.sub(r'\s+', '_', sanitized_path)  # Replace spaces with underscores

    # Ensure the path starts with a forward slash
    if not sanitized_path.startswith('/'):
        sanitized_path = '/' + sanitized_path

    return sanitized_path


def upload_to_dropbox(file_path, destination_path, depth):
    print(f"{'  ' * depth}    Dropbox:")
    
    access_token = get_access_token(depth)
    if access_token is None:
        print(f"{'  ' * depth}        ERROR WITH ACCESS KEY")
        return None
    dbx = dropbox.Dropbox(ACCESS_TOKEN)

    destination_path = sanitize_path(destination_path)

    # Check if the file already exists in Dropbox
    try:
        dbx.files_get_metadata(destination_path)
        print(f"{'  ' * depth}        File already exists, fetching shared link.")
        shared_link = dbx.sharing_create_shared_link(destination_path).url
        return shared_link.replace("?dl=0", "?raw=1")
    except dropbox.exceptions.ApiError as e:
        pass
    
    # Create folders in Dropbox if they don't exist
    folder_path = os.path.dirname(destination_path)
    try:
        dbx.files_create_folder_v2(folder_path)
    except dropbox.exceptions.ApiError as e:
        # Ignore if the folder already exists
        if e.error.is_path() and e.error.get_path().is_conflict():
            pass
        else:
            print(f"Error creating folder: {e}")
            return None

    # Read the file and upload it
    with open(file_path, 'rb') as file:
        try:
            dbx.files_upload(file.read(), destination_path, mode=WriteMode('overwrite'))
            print(f"{'  ' * depth}        Successful upload!")
        except Exception as e:
            print(f"Error uploading file: {e}")
            return None

    # Create a shared link
    try:
        shared_link = dbx.sharing_create_shared_link(destination_path).url
        # Modify the link to directly download the file
        return shared_link.replace("?dl=0", "?raw=1")
    except Exception as e:
        print(f"Error creating shared link: {e}")
        return None