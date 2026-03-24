from agents.cleaner import clean_transcript
from agents.extractor import extract_structured
from agents.updater import update_state
from agents.summarizer import summarize_call
from agents.reporter import write_meeting_row
from agents.drive_matcher import find_matching_drive_file   # <-- UPDATED IMPORT

SPREADSHEET_ID = "1b5WzbTaVC1LftK1jYeQNvOB3KGMc1S3Rh7p6TGNjUKk"


def load_transcript_from_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def process_transcript(file_path: str):

    print("\n=== LOADING TRANSCRIPT ===")
    raw_transcript = load_transcript_from_file(file_path)

    print("\n=== CLEANING TRANSCRIPT ===")
    cleaned = clean_transcript(raw_transcript)

    print("\n=== EXTRACTING STRUCTURED DATA ===")
    extracted = extract_structured(cleaned, transcript_path)

    print("\n=== GENERATING SUMMARY OF CALL ===")
    summary_of_call = summarize_call(cleaned, extracted)

    print("\n=== UPDATING STATE (STATELESS) ===")
    state = update_state(extracted)

    print("\n=== MATCHING TRANSCRIPT FILE IN GOOGLE DRIVE ===")
    drive_link = find_matching_drive_file(file_path)

    print("\n=== WRITING ROW TO GOOGLE SHEET ===")
    report = write_meeting_row(summary_of_call, extracted, drive_link, SPREADSHEET_ID)

    print("\n=== DONE ===")
    return {
        "cleaned": cleaned,
        "extracted": extracted,
        "summary_of_call": summary_of_call,
        "drive_link": drive_link,
        "report": report
    }


if __name__ == "__main__":
    transcript_path = "transcripts/ 2026_03_02 17_30 – Transcript.docx.txt"

    result = process_transcript(transcript_path)

    print("\n=== CLEANED TRANSCRIPT ===\n", result["cleaned"])
    print("\n=== STRUCTURED OUTPUT ===\n", result["extracted"])
    print("\n=== SUMMARY OF CALL ===\n", result["summary_of_call"])
    print("\n=== DRIVE LINK ===\n", result["drive_link"])
    print("\n=== REPORT ===\n", result["report"])
