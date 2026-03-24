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


# ============================================================
#                   NODE IMPLEMENTATIONS
# ============================================================

def loader_node(state: PipelineState) -> PipelineState:
    """
    Loads transcript text from file_path.
    Mirrors: raw_transcript = load_transcript_from_file(file_path)
    """
    file_path = state["file_path"]
    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()
    return {"raw_text": raw_text}


def cleaner_node(state: PipelineState) -> PipelineState:
    """
    clean_transcript(raw_text)
    """
    clean_text = clean_transcript(state["raw_text"])
    return {"clean_text": clean_text}


def extractor_node(state: PipelineState) -> PipelineState:
    """
    extract_structured(clean_text, file_path)
    """
    extracted = extract_structured(state["clean_text"], state["file_path"])
    return {"extracted": extracted}


def summarizer_node(state: PipelineState) -> PipelineState:
    """
    summarize_call(clean_text, extracted)
    """
    summary = summarize_call(state["clean_text"], state["extracted"])
    return {"summary_of_call": summary}


def updator_node(state: PipelineState) -> PipelineState:
    """
    update_state(extracted)  # stateless
    """
    updated_state = update_state(state["extracted"])
    return {"updated_state": updated_state}


def drive_matcher_node(state: PipelineState) -> PipelineState:
    """
    find_matching_drive_file(file_path)
    """
    drive_link = find_matching_drive_file(state["file_path"])
    return {"drive_link": drive_link}


def reporter_node(state: PipelineState) -> PipelineState:
    """
    write_meeting_row(summary_of_call, extracted, drive_link, spreadsheet_id)
    """
    report_status = write_meeting_row(
        summary_of_call=state["summary_of_call"],
        extracted=state["extracted"],
        drive_link=state["drive_link"],
        spreadsheet_id=state["spreadsheet_id"],
    )
    return {"report_status": report_status}


# ============================================================
#                   GRAPH CONSTRUCTION
# ============================================================

def build_pipeline_graph():
    graph = StateGraph(PipelineState)

    # Register nodes
    graph.add_node("loader", loader_node)
    graph.add_node("cleaner", cleaner_node)
    graph.add_node("extractor", extractor_node)
    graph.add_node("summarizer", summarizer_node)
    graph.add_node("updator", updator_node)
    graph.add_node("drive_matcher", drive_matcher_node)
    graph.add_node("reporter", reporter_node)

    # EXACT flow of your real pipeline
    graph.add_edge(START, "loader")
    graph.add_edge("loader", "cleaner")
    graph.add_edge("cleaner", "extractor")
    graph.add_edge("extractor", "summarizer")
    graph.add_edge("summarizer", "updator")
    graph.add_edge("updator", "drive_matcher")
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
    """
    This mirrors main.py logic exactly.
    """
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
