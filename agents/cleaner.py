from .client import client
import re

def clean_transcript(raw_text: str) -> str:
    prompt = f"""
    Clean and normalize the following meeting transcript.

    Your tasks:
    - Detect and translate ANY Hindi (including Devanagari script) into clear English.
    - Normalize Hinglish (Hindi written in English letters) into proper English.
    - Fix grammar, punctuation, and sentence structure.
    - Expand shorthand and incomplete phrases.
    - Remove filler words ("um", "uh", "like", "you know").
    - Preserve the original meaning and speaker intent.
    - Keep speaker names EXACTLY as they appear.
    - Do NOT summarize or shorten content.
    - Rewrite line-by-line in clean, fluent English.
    - Ignore timestamps such as "0:23", "12:45", "1:02:33" — they will be removed later.

    Transcript:
    {raw_text}
    """

    # --- LLM CLEANING ---
    response = client.chat.completions.create(
        model="meta/llama-3.1-70b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )

    cleaned_text = response.choices[0].message.content

    # --- POST-PROCESSING CLEANUP (regex) ---
    # Remove timestamps like 0:23, 12:45, 1:02:33
    cleaned_text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", "", cleaned_text)

    # Normalize speaker labels: "Madhu   " → "Madhu:"
    cleaned_text = re.sub(r"([A-Za-z][A-Za-z .()-]{1,40})\s{2,}", r"\1: ", cleaned_text)

    # Ensure speaker labels appear on new lines
    cleaned_text = re.sub(r"\s*([A-Za-z][A-Za-z .()-]{1,40}:)", r"\n\1", cleaned_text)

    # Remove extra spaces
    cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text)

    # Remove accidental double newlines
    cleaned_text = re.sub(r"\n{2,}", "\n", cleaned_text)

    return cleaned_text.strip()
