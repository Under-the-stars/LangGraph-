from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, START, END

from agents.cleaner import clean_transcript
from agents.drive_matcher import find_matching_drive_file
from agents.extractor import extract_structured
from agents.summarizer import summarize_call
from agents.updater import update_state
from agents.reporter import write_meeting_row


# ============================================================
#                   STATE DEFINITION
# ============================================================

class PipelineState(TypedDict, total=False):
    # Inputs
    file_path: str
    spreadsheet_id: str

    # Loaded transcript
    raw_text: str

    # Intermediate
    clean_text: str
    extracted: Dict[str, Any]
    summary_of_call: str
    updated_state: Dict[str, Any]
    drive_link: str

    # Final
    report_status: Dict[str, Any]

    # Extractor loop fields
    extractor_valid: bool
    extractor_retry_count: int

    # Updater loop fields (NEW)
    updator_valid: bool
    updator_retry_count: int


# ============================================================
#                   NODE IMPLEMENTATIONS
# ============================================================

def loader_node(state: PipelineState) -> PipelineState:
    file_path = state["file_path"]
    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()
    return {"raw_text": raw_text}


def cleaner_node(state: PipelineState) -> PipelineState:
    clean_text = clean_transcript(state["raw_text"])
    return {"clean_text": clean_text}


def extractor_node(state: PipelineState) -> PipelineState:
    extracted = extract_structured(state["clean_text"], state["file_path"])
    return {"extracted": extracted}


# ============================================================
#                   STRICT EXTRACTOR VALIDATOR
# ============================================================

REQUIRED_KEYS = {
    "tasks": list,
    "decisions": list,
    "risks": list,
    "updates": list,
    "action_items": list,
    "attendees": list,
    "next_steps": list,
    "meeting_date": str,
    "meeting_time": str,
}

def extractor_validator_node(state: PipelineState) -> PipelineState:
    data = state.get("extracted")

    # Must be dict
    if not isinstance(data, dict):
        return {"extractor_valid": False}

    # Required keys + types
    for key, expected_type in REQUIRED_KEYS.items():
        if key not in data:
            return {"extractor_valid": False}
        if not isinstance(data[key], expected_type):
            return {"extractor_valid": False}

    # Strict mode: lists must NOT be empty
    if len(data["tasks"]) == 0:
        return {"extractor_valid": False}
    if len(data["attendees"]) == 0:
        return {"extractor_valid": False}
    if len(data["next_steps"]) == 0:
        return {"extractor_valid": False}

    # Structure checks
    for t in data["tasks"]:
        if not isinstance(t, dict) or "task" not in t or "owner" not in t:
            return {"extractor_valid": False}

    for ns in data["next_steps"]:
        if not isinstance(ns, dict) or "task" not in ns or "owner" not in ns:
            return {"extractor_valid": False}

    for ai in data["action_items"]:
        if not isinstance(ai, dict) or "text" not in ai or "owner" not in ai:
            return {"extractor_valid": False}

    return {"extractor_valid": True}


# ============================================================
#                   EXTRACTOR RETRY LOGIC
# ============================================================

MAX_RETRIES = 3

def extractor_retry_logic_node(state: PipelineState) -> PipelineState:
    if state.get("extractor_valid"):
        return {"next": "summarizer"}

    retry_count = state.get("extractor_retry_count", 0) + 1

    if retry_count >= MAX_RETRIES:
        raise ValueError("Extractor failed after 3 retries")

    return {
        "extractor_retry_count": retry_count,
        "next": "extractor"
    }


# ============================================================
#                   REMAINING NODES (UNCHANGED)
# ============================================================

def summarizer_node(state: PipelineState) -> PipelineState:
    summary = summarize_call(state["clean_text"], state["extracted"])
    return {"summary_of_call": summary}


def updator_node(state: PipelineState) -> PipelineState:
    updated_state = update_state(state["extracted"])
    return {"updated_state": updated_state}


def drive_matcher_node(state: PipelineState) -> PipelineState:
    drive_link = find_matching_drive_file(state["file_path"])
    return {"drive_link": drive_link}


def reporter_node(state: PipelineState) -> PipelineState:
    report_status = write_meeting_row(
        summary_of_call=state["summary_of_call"],
        extracted=state["extracted"],
        drive_link=state["drive_link"],
        spreadsheet_id=state["spreadsheet_id"],
    )
    return {"report_status": report_status}


# ============================================================
#                   MINIMAL UPDATER VALIDATOR (NEW)
# ============================================================

UPDATOR_REQUIRED_KEYS = {
    "tasks": list,
    "decisions": list,
    "risks": list,
    "updates": list,
    "action_items": list,
    "attendees": list,
    "next_steps": list,
    "meeting_date": str,
    "meeting_time": str,
}

def updator_validator_node(state: PipelineState) -> PipelineState:
    updated = state.get("updated_state")

    # Must be dict
    if not isinstance(updated, dict):
        return {"updator_valid": False}

    # Required keys + types
    for key, expected_type in UPDATOR_REQUIRED_KEYS.items():
        if key not in updated:
            return {"updator_valid": False}
        if not isinstance(updated[key], expected_type):
            return {"updator_valid": False}

    # Minimal validator: allow empty lists, no strict checks
    return {"updator_valid": True}


# ============================================================
#                   UPDATER RETRY LOGIC (NEW)
# ============================================================

MAX_UPDATOR_RETRIES = 3

def updator_retry_logic_node(state: PipelineState) -> PipelineState:
    if state.get("updator_valid"):
        return {"next": "drive_matcher"}

    retry_count = state.get("updator_retry_count", 0) + 1

    if retry_count >= MAX_UPDATOR_RETRIES:
        raise ValueError("Updater failed after 3 retries")

    return {
        "updator_retry_count": retry_count,
        "next": "updator"
    }


# ============================================================
#                   GRAPH CONSTRUCTION
# ============================================================

def build_pipeline_graph():
    graph = StateGraph(PipelineState)

    # Register nodes
    graph.add_node("loader", loader_node)
    graph.add_node("cleaner", cleaner_node)
    graph.add_node("extractor", extractor_node)

    # Extractor loop nodes
    graph.add_node("extractor_validator", extractor_validator_node)
    graph.add_node("extractor_retry_logic", extractor_retry_logic_node)

    graph.add_node("summarizer", summarizer_node)
    graph.add_node("updator", updator_node)

    # Updater loop nodes (NEW)
    graph.add_node("updator_validator", updator_validator_node)
    graph.add_node("updator_retry_logic", updator_retry_logic_node)

    graph.add_node("drive_matcher", drive_matcher_node)
    graph.add_node("reporter", reporter_node)

    # Flow
    graph.add_edge(START, "loader")
    graph.add_edge("loader", "cleaner")
    graph.add_edge("cleaner", "extractor")

    # Extractor loop
    graph.add_edge("extractor", "extractor_validator")
    graph.add_edge("extractor_validator", "extractor_retry_logic")

    graph.add_conditional_edges(
        "extractor_retry_logic",
        lambda state: state["next"],
        {
            "extractor": "extractor",
            "summarizer": "summarizer",
        }
    )

    # Summarizer → Updater
    graph.add_edge("summarizer", "updator")

    # Updater loop (NEW)
    graph.add_edge("updator", "updator_validator")
    graph.add_edge("updator_validator", "updator_retry_logic")

    graph.add_conditional_edges(
        "updator_retry_logic",
        lambda state: state["next"],
        {
            "updator": "updator",
            "drive_matcher": "drive_matcher",
        }
    )

    # Continue pipeline
    graph.add_edge("drive_matcher", "reporter")
    graph.add_edge("reporter", END)

    return graph.compile()


# ============================================================
#                   PIPELINE ENTRYPOINT
# ============================================================

def run_pipeline(
    file_path: str,
    spreadsheet_id: str,
) -> PipelineState:
    app = build_pipeline_graph()

    initial_state: PipelineState = {
        "file_path": file_path,
        "spreadsheet_id": spreadsheet_id,
    }

    final_state: PipelineState = app.invoke(initial_state)
    return final_state


# ============================================================
#                   COMMAND-LINE EXECUTION
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m agents.langgraph_pipeline <transcript_path>")
        sys.exit(1)

    transcript_path = sys.argv[1]
    spreadsheet_id = "1b5WzbTaVC1LftK1jYeQNvOB3KGMc1S3Rh7p6TGNjUKk"

    result = run_pipeline(
        file_path=transcript_path,
        spreadsheet_id=spreadsheet_id,
    )

    print("\n=== CLEANED TRANSCRIPT ===\n", result.get("clean_text"))
    print("\n=== STRUCTURED OUTPUT ===\n", result.get("extracted"))
    print("\n=== SUMMARY OF CALL ===\n", result.get("summary_of_call"))
    print("\n=== DRIVE LINK ===\n", result.get("drive_link"))
    print("\n=== REPORT STATUS ===\n", result.get("report_status"))
