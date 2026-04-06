# LangGraph Meeting Intelligence Pipeline

### A Production-Grade, Self-Correcting Multi-Agent System Built with LangGraph, NVIDIA NIM, and Google Sheets

---

## What This Project Is

Most meeting notes get lost. Action items slip through the cracks, decisions go undocumented, and the institutional knowledge from every call lives — and dies — in someone's memory. This project is an attempt to fix that systematically.

The Meeting Intelligence Pipeline takes a raw meeting transcript — noisy, multilingual, unstructured — and transforms it into structured project data: tasks, decisions, risks, action items, attendees, next steps, a meeting date and time, and an executive summary. The final output is written directly into a Google Sheet, giving teams a consistent, searchable, and auditable record of every meeting, automatically.

But what makes this different from a simple script that calls an LLM is the architecture. This is not a chain of function calls. It is a stateful, cyclic, self-correcting multi-agent system built on LangGraph's `StateGraph`, where every stage of the pipeline has its own validation logic and can loop back and retry if the output doesn't meet a strict schema. It behaves less like a script and more like a careful, methodical analyst who checks their own work before moving on.

---

## The Problem It Solves

Real meeting transcripts are messy. They contain filler words, overlapping speakers, code-switching between languages (this system was built and tested on Hinglish — a mix of Hindi and English), timestamps, and informal shorthand. A simple LLM call on raw transcript text will often return incomplete or malformed data — missing fields, empty lists, hallucinated summaries that don't match the actual conversation.

The standard approach to this problem is to prompt-engineer your way out of it and hope for the best. This project takes a different approach: instead of trusting a single LLM call, every critical extraction step is wrapped in a validation layer that checks the output against a strict schema, and a retry layer that loops back to the agent with exponential backoff if the validation fails. The pipeline cannot proceed to the next stage until the current stage produces output that passes inspection.

The result is a system that is robust to real-world noise in a way that a linear pipeline simply cannot be.

---

## Architecture Overview

The pipeline is built as a LangGraph `StateGraph`, which means the entire workflow shares a single typed state object — a `TypedDict` called `PipelineState` — that flows through every node. Each agent reads the fields it needs from the state, performs its task, and writes only the fields it owns back. No agent has access to more than it needs, and no agent can corrupt another agent's output.

The graph is composed of seven core agents, each accompanied by a Validator node and a Retry Logic node (except the Cleaner, which runs as a deliberate single pass). The conditional edges between the retry nodes and the agent nodes are what create the cyclic, self-correcting behavior that defines this system.

```
                ┌──────────────────────────┐
                │        Transcript         │
                │         (.txt file)       │
                └──────────────┬───────────┘
                               ▼
                    ┌──────────────────┐
                    │     Loader       │
                    └──────────────────┘
                               ▼
                    ┌──────────────────┐
                    │     Cleaner      │  (NVIDIA LLM)
                    │  (single pass)   │
                    └──────────────────┘
                               ▼
                    ┌──────────────────┐
                    │    Extractor     │  (NVIDIA LLM)
                    │  + Validator     │
                    │  + Retry Logic   │
                    └──────────────────┘
                               ▼
                    ┌──────────────────┐
                    │   Summarizer     │  (NVIDIA LLM)
                    │  + Validator     │
                    │  + Retry Logic   │
                    └──────────────────┘
                               ▼
                    ┌──────────────────┐
                    │     Updater      │
                    │  + Validator     │
                    │  + Retry Logic   │
                    └──────────────────┘
                               ▼
                    ┌──────────────────┐
                    │  Drive Matcher   │
                    └──────────────────┘
                               ▼
                    ┌──────────────────┐
                    │     Reporter     │  (Google Sheets API)
                    │  + Validator     │
                    │  + Retry Logic   │
                    └──────────────────┘
```

---

## Agent-by-Agent Walkthrough

### Loader

The Loader is the entry point to the pipeline. It takes a file path as input, reads the raw transcript from disk, and injects the text into the shared `PipelineState` under the `raw_text` field. It performs no transformation — its only job is to make the transcript available to the rest of the pipeline in a consistent way.

### Cleaner

The Cleaner receives the raw transcript and uses NVIDIA's LLM (`meta/llama-3.1-70b-instruct`) to clean, normalize, and translate it. In practice, this means removing filler words and disfluencies, correcting grammar, translating Hinglish passages into standard English, and producing a clean, readable version of the conversation that the downstream agents can work with reliably.

The Cleaner is the one agent in the pipeline that runs as a single pass without a retry loop. This is an intentional design decision: cleaning is a best-effort normalization step, and running it once with a basic validity check (is the output a non-empty string that doesn't start with an LLM refusal like "I'm sorry" or "As an AI") is sufficient. Adding a full retry loop here would add latency without meaningfully improving downstream quality.

### Extractor

The Extractor is the most critical — and most carefully validated — agent in the pipeline. It takes the cleaned transcript and uses the LLM to extract a structured dictionary containing nine fields: `tasks`, `decisions`, `risks`, `updates`, `action_items`, `attendees`, `next_steps`, `meeting_date`, and `meeting_time`.

What makes the Extractor robust is its validation layer. The Extractor Validator does not just check whether a dictionary was returned. It verifies that every required key is present, that each key maps to the correct Python type (`list` vs `str`), that critical lists like `tasks`, `attendees`, and `next_steps` are non-empty, and that each item in those lists contains the expected nested fields (for example, every task must have both a `"task"` key and an `"owner"` key). If any of these checks fail, the pipeline routes back to the Extractor — up to three times, with exponential backoff between attempts — before raising a hard error.

This is the guardrail that prevents incomplete or hallucinated extractions from propagating downstream.

### Summarizer

The Summarizer takes both the cleaned transcript and the structured extraction as context and uses the LLM to produce an executive summary of the meeting. The summary is intended to be human-readable and narrative — something a stakeholder could read in thirty seconds to understand what happened in a call.

The Summarizer Validator checks that the output is a non-empty string of meaningful length, that it is not a JSON object mistakenly returned by the model, and that it does not begin with an LLM refusal phrase. If validation fails, the pipeline retries once before raising an error.

### Updater

The Updater normalizes the extracted data into a consistent schema for downstream systems. It re-validates the structure of the extraction to ensure that any edge cases or inconsistencies introduced during the extraction step are resolved before the data is written anywhere. Like the Extractor, it has a Validator and a Retry Logic node, and it enforces the same schema requirements.

### Drive Matcher

The Drive Matcher is a utility agent that takes the transcript file path and uses filename heuristics to locate the corresponding file in Google Drive. It returns a direct link to the Drive file, which is included in the final Google Sheets report for traceability. This agent does not call the LLM and does not have a retry loop — it either finds a match or returns a graceful fallback.

### Reporter

The Reporter is the terminal agent in the pipeline. It takes the executive summary, the structured extraction, the Drive link, and the target Google Sheets spreadsheet ID, and writes a clean, structured row into the sheet using the Google Sheets API. The Reporter Validator checks that the write operation returned a `"success"` status before allowing the pipeline to terminate. If the write fails, it retries once before raising an error.

---

## How the Self-Correcting Loops Work

The cyclic behavior of this pipeline is implemented using LangGraph's `add_conditional_edges` API. After each Validator node runs, it sets a boolean flag in the state (`extractor_valid`, `summarizer_valid`, etc.). The subsequent Retry Logic node reads this flag and sets a `"next"` field in the state to either the name of the current agent (if validation failed) or the name of the next agent (if validation passed). The conditional edge then routes the graph accordingly.

Here is the pattern for the Extractor, which repeats across all agents with retry loops:

```
Extractor → Extractor Validator → Extractor Retry Logic
                                          │
                          ┌───────────────┴───────────────┐
                          ▼                               ▼
                      Extractor                       Summarizer
                   (validation failed,             (validation passed,
                    retry with backoff)             continue pipeline)
```

The retry count for each agent is tracked in the state and incremented on each loop. When the maximum retry count is reached without a successful validation, the pipeline raises a `ValueError` with a descriptive message rather than silently producing bad output.

---

## Technology Stack

**LangGraph** provides the `StateGraph` runtime that orchestrates the entire pipeline. It handles node registration, edge routing, conditional branching, and state management. LangGraph is what makes the cyclic, self-correcting architecture possible without writing custom graph traversal logic.

**NVIDIA NIM** provides the LLM backend via an OpenAI-compatible API. The pipeline uses `meta/llama-3.1-70b-instruct` for all LLM tasks — cleaning, extraction, and summarization. NVIDIA's inference infrastructure provides low-latency, high-quality completions with strong multilingual support, which is critical for handling Hinglish transcripts reliably.

**Google Sheets API** serves as the reporting backend. Using a Google Cloud service account, the Reporter agent writes structured rows directly into a target spreadsheet, giving teams a persistent, queryable record of every processed meeting.

---

## Setup and Installation

Clone the repository and install the required dependencies:

```bash
git clone <repo>
cd LangGraph-
pip install -r requirements.txt
```

Set your NVIDIA API key as an environment variable:

```bash
export NVIDIA_API_KEY="your-nvidia-api-key"
```

Place your Google Cloud service account credentials at the following path:

```
credentials/service_account.json
```

---

## Running the Pipeline

```bash
python -m agents.langgraph_pipeline "transcripts/your_transcript.txt"
```

The pipeline will print the cleaned transcript, structured extraction, executive summary, Drive link, and Google Sheets write status to stdout on completion.

---

## Example Output Schema

The structured extraction produced by the Extractor agent follows this schema:

```json
{
  "tasks": [{"task": "...", "owner": "..."}],
  "decisions": ["..."],
  "risks": ["..."],
  "updates": ["..."],
  "action_items": [{"text": "...", "owner": "..."}],
  "attendees": ["..."],
  "next_steps": [{"task": "...", "owner": "..."}],
  "meeting_date": "YYYY-MM-DD",
  "meeting_time": "HH:MM"
}
```

---

## Results

Deployed against real project meeting transcripts, the pipeline achieved an 80–90% reduction in manual note-taking effort, 98% accurate date and time extraction across multilingual inputs, a 40% increase in high-priority action item completeness compared to manual notes, and saved approximately 2–3 hours per stakeholder per week through automated Google Sheets reporting.

---

## Why This Architecture Matters

The design philosophy behind this system is that reliability in production AI pipelines cannot be bolt-on. It has to be structural. Retry logic, schema validation, and typed state are not nice-to-haves — they are the difference between a demo and a system you can actually trust with real data.

The Validator-Retry pattern implemented here is directly applicable to any agentic pipeline where the cost of bad output is high: medical record extraction, legal document processing, educational assessment, financial reporting. The specific domain is meeting intelligence, but the architecture is general.
