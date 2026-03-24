from .client import client
import json
import re
from datetime import datetime

def extract_structured(clean_text: str, file_path: str) -> dict:
    """
    clean_text: cleaned transcript
    file_path: original transcript path (for raw date/time extraction)
    """

    # -------------------------
    # LOAD RAW TRANSCRIPT
    # -------------------------
    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # -------------------------
    # MODEL PROMPT
    # -------------------------
    prompt = f"""
    You are an expert project analyst.

    Extract ALL structured information needed to populate a meeting log.

    You MUST extract the following fields:

    1. tasks:
        - Extract tasks as structured objects
        - Format each task as:
            {{"task": "<task text>", "owner": "<explicit owner or empty string>"}}
        - Only assign an owner if the transcript explicitly names one
        - If no owner is mentioned, owner = ""

    2. decisions:
        - Any decisions made during the meeting

    3. risks:
        - Any risks, blockers, concerns, or uncertainties

    4. updates:
        - Status updates
        - Progress updates
        - Work completed or in progress

    5. action_items:
        - Leave this empty; action items will be generated programmatically

    6. attendees:
        - List of unique speaker names

    7. next_steps:
        - Tasks that imply future action
        - Format each as:
            {{"task": "<task text>", "owner": "<explicit owner or empty string>"}}

    8. meeting_date:
        - Leave blank; will be extracted from raw transcript

    9. meeting_time:
        - Leave blank; will be extracted from raw transcript

    Return ONLY valid JSON in this exact format:

    {{
        "tasks": [],
        "decisions": [],
        "risks": [],
        "updates": [],
        "action_items": [],
        "attendees": [],
        "next_steps": [],
        "meeting_date": "",
        "meeting_time": ""
    }}

    Cleaned Transcript:
    {clean_text}
    """

    # -------------------------
    # CALL MODEL
    # -------------------------
    response = client.chat.completions.create(
        model="meta/llama-3.1-70b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )

    json_text = response.choices[0].message.content

    print("=== RAW MODEL OUTPUT ===")
    print(json_text)

    # -------------------------
    # CLEAN MODEL OUTPUT
    # -------------------------
    json_text = json_text.replace("```json", "").replace("```", "").strip()
    if "{" in json_text:
        json_text = json_text[json_text.index("{"):]
    if "}" in json_text:
        json_text = json_text[:json_text.rindex("}") + 1]

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        raise ValueError("Model did not return valid JSON. Cleaned text was:\n" + json_text)

    # -------------------------
    # DATE EXTRACTION (RAW)
    # -------------------------
    date_patterns = [
    # 9 January 2026
    r"\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}",

    # January 9 2026 or January 9, 2026
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*\d{4}",

    # 2026-01-09 (ISO)
    r"\d{4}-\d{2}-\d{2}",

    # 2026/01/09 (NEW — slash format)
    r"\d{4}/\d{2}/\d{2}"
]


    found_date = None
    for pattern in date_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            found_date = match.group(0)
            break

    if found_date:
        cleaned = (
            found_date.replace("st", "")
                      .replace("nd", "")
                      .replace("rd", "")
                      .replace("th", "")
        )
        parsed_date = None
        for fmt in ["%d %B %Y", "%B %d %Y", "%Y-%m-%d", "%Y/%m/%d"]:
            try:
                parsed_date = datetime.strptime(cleaned, fmt)
                break
            except:
                continue
        if parsed_date:
            data["meeting_date"] = parsed_date.strftime("%Y-%m-%d")
    else:
        data["meeting_date"] = ""

    # -------------------------
    # TIME EXTRACTION (RAW)
    # -------------------------
    time_patterns = [
        r"\b\d{1,2}:\d{2}\s*(AM|PM|am|pm)\b",
        r"\b\d{1,2}:\d{2}\b",
        r"\b\d{1,2}\s*(AM|PM|am|pm)\b",
    ]

    found_time = None
    for pattern in time_patterns:
        match = re.search(pattern, raw_text)
        if match:
            found_time = match.group(0)
            break

    if found_time:
        t = found_time.strip().lower().replace(" ", "")
        try:
            dt = datetime.strptime(t, "%I:%M%p")
            data["meeting_time"] = dt.strftime("%I:%M %p")
        except:
            try:
                dt = datetime.strptime(t, "%H:%M")
                data["meeting_time"] = dt.strftime("%I:%M %p")
            except:
                data["meeting_time"] = ""
    else:
        data["meeting_time"] = ""

    # -------------------------
    # STRUCTURE TASKS
    # -------------------------
    structured_tasks = []
    for t in data.get("tasks", []):
        if isinstance(t, dict):
            structured_tasks.append(t)
        else:
            structured_tasks.append({"task": t, "owner": ""})
    data["tasks"] = structured_tasks

    # -------------------------
    # STRUCTURE NEXT STEPS
    # -------------------------
    structured_next = []
    for ns in data.get("next_steps", []):
        if isinstance(ns, dict):
            structured_next.append(ns)
        else:
            structured_next.append({"task": ns, "owner": ""})
    data["next_steps"] = structured_next

    # -------------------------
    # HIGH-PRIORITY ACTION ITEM EXTRACTION
    # -------------------------
    priority_keywords = [
        "will", "need to", "should", "must", "please", "can you", "could you",
        "let's", "follow up", "confirm", "share", "prepare", "review",
        "discuss", "finalize", "complete", "send", "to do"
    ]

    action_items = []

    def is_high_priority(text: str) -> bool:
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in priority_keywords)

    # Extract from tasks
    for t in data["tasks"]:
        if is_high_priority(t["task"]):
            action_items.append({"text": t["task"], "owner": t["owner"]})

    # Extract from next_steps
    for ns in data["next_steps"]:
        if is_high_priority(ns["task"]):
            action_items.append({"text": ns["task"], "owner": ns["owner"]})

    data["action_items"] = action_items

    # -------------------------
    # UNIQUE ATTENDEES
    # -------------------------
    if "attendees" in data:
        data["attendees"] = list(set(data["attendees"]))

    return data
