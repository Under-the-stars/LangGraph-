from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from .summarizer import generate_overall_summary

MASTER_SHEET_NAME = "langgraph dry run"
PROJECT_ID = 1

def get_sheet_service():
    creds = Credentials.from_service_account_file(
        "service_account.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds).spreadsheets()

def get_last_overall_summary(service, spreadsheet_id):
    result = service.values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{MASTER_SHEET_NAME}!D2:D"
    ).execute()
    values = result.get("values", [])
    return values[-1][0] if values else ""

def write_meeting_row(summary_of_call, extracted, drive_link, spreadsheet_id):
    service = get_sheet_service()

    # Ensure sheet exists
    try:
        service.values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{MASTER_SHEET_NAME}!A1:A1"
        ).execute()
    except:
        service.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": MASTER_SHEET_NAME}}}]}
        ).execute()

    # Write headers if missing
    header_check = service.values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{MASTER_SHEET_NAME}!A1:J1"
    ).execute()

    if "values" not in header_check:
        headers = [
            "Project ID", "Meeting Date", "Meeting Time", "Overall Summary",
            "Summary of Call", "Main Points", "Transcript Link",
            "Next Steps", "Action Items", "Attendees"
        ]
        service.values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{MASTER_SHEET_NAME}!A1:J1",
            valueInputOption="RAW",
            body={"values": [headers]}
        ).execute()

    previous_overall = get_last_overall_summary(service, spreadsheet_id)
    updated_overall = generate_overall_summary(previous_overall, summary_of_call)

    # Format tasks
    formatted_tasks = []
    for t in extracted.get("tasks", []):
        if isinstance(t, dict):
            text = t.get("task", "")
            owner = t.get("owner", "")
            if owner:
                formatted_tasks.append(f"{text} (Owner: {owner})")
            else:
                formatted_tasks.append(text)
        else:
            formatted_tasks.append(str(t))

    # Format next steps
    formatted_next_steps = []
    for ns in extracted.get("next_steps", []):
        if isinstance(ns, dict):
            text = ns.get("task", "")
            owner = ns.get("owner", "")
            if owner:
                formatted_next_steps.append(f"{text} (Owner: {owner})")
            else:
                formatted_next_steps.append(text)
        else:
            formatted_next_steps.append(str(ns))

    # Format action items
    formatted_actions = []
    for a in extracted.get("action_items", []):
        if isinstance(a, dict):
            text = a.get("text", "")
            owner = a.get("owner", "")
            if owner:
                formatted_actions.append(f"{text} (Owner: {owner})")
            else:
                formatted_actions.append(text)
        else:
            formatted_actions.append(str(a))

    row = [
        PROJECT_ID,
        extracted.get("meeting_date"),
        extracted.get("meeting_time"),
        updated_overall,
        summary_of_call,
        "\n".join(formatted_tasks),
        drive_link,
        "\n".join(formatted_next_steps),
        "\n".join(formatted_actions),
        ", ".join(extracted.get("attendees", []))
    ]

    service.values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{MASTER_SHEET_NAME}!A:J",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]}
    ).execute()

    return {"status": "success", "written_row": row}
