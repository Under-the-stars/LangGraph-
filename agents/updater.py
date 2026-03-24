import json
from pathlib import Path

STATE_FILE = Path("state/project_state.json")

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"tasks": [], "decisions": [], "risks": []}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def update_state(extracted):
    return extracted

    # merge tasks
    for t in extracted["tasks"]:
        state["tasks"].append(t)

    # merge decisions
    state["decisions"].extend(extracted["decisions"])

    # merge risks
    state["risks"].extend(extracted["risks"])

    save_state(state)
    return state
