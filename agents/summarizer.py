from .client import client

def summarize_call(clean_text: str, extracted: dict) -> str:
    """
    Produces a concise, high-level summary of the meeting.
    This becomes the 'Summary of Call' column in the sheet.
    """

    prompt = f"""
    You are an expert meeting summarizer.

    Summarize the following cleaned transcript into a concise,
    clear, high-level summary of the call. Focus on the main
    discussion points, decisions, and direction.

    Cleaned Transcript:
    {clean_text}
    """

    response = client.chat.completions.create(
        model="meta/llama-3.1-70b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content.strip()


def generate_overall_summary(previous_overall: str, current_summary: str) -> str:
    """
    Creates a rewritten, concise, high-level overall project summary.
    Uses ONLY:
    - previous overall summary
    - current summary of call
    """

    # If this is the first meeting, overall summary = summary of call
    if not previous_overall or previous_overall.strip() == "":
        return current_summary.strip()

    prompt = f"""
    You are an expert project manager.

    Your job is to maintain a concise, high-level “Overall Summary” of the project.

    Rewrite the overall summary so that it reflects the entire project so far.
    Do NOT simply append or merge text.
    Instead, synthesize the key themes, decisions, progress, risks, and direction of the project.

    Your output must be:
    - concise
    - coherent
    - readable
    - high-level
    - suitable for an executive
    - updated with the latest meeting’s information

    Previous Overall Summary:
    {previous_overall}

    Latest Summary of Call:
    {current_summary}

    Produce the updated Overall Summary below:
    """

    response = client.chat.completions.create(
        model="meta/llama-3.1-70b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content.strip()
