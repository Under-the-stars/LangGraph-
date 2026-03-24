from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import os

FOLDER_ID = "1egkMQZRQgf6y4spgRG2jUbmaTGJEBEdw"

def get_drive_service():
    creds = Credentials.from_service_account_file(
        "service_account.json",
        scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return build("drive", "v3", credentials=creds)


def find_matching_drive_file(local_path: str) -> str:
    """
    Matches the Drive file EXACTLY to the .docx.txt filename.
    """

    service = get_drive_service()

    # Example: "Mensa FT - FSCP process overview_Part 1.docx.txt"
    filename = os.path.basename(local_path)

    # We now match EXACTLY this filename in Drive
    base_name = filename

    query = f"'{FOLDER_ID}' in parents and name = '{base_name}'"

    results = service.files().list(
        q=query,
        fields="files(id, name)"
    ).execute()

    files = results.get("files", [])

    if not files:
        raise FileNotFoundError(
            f"No matching Drive file found for: {base_name}"
        )

    file_id = files[0]["id"]

    return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
