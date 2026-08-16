import os
import time

from google import genai
from google.genai import types

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

_client = genai.Client(api_key=GEMINI_API_KEY)

TRANSCRIBE_PROMPT = (
    "Transcribe this video in full. Include timecodes (mm:ss) at natural breaks, "
    "and label distinct speakers as 'Speaker 1:', 'Speaker 2:', etc. "
    "Output only the transcript, no preamble."
)


def transcribe(file_path: str) -> str:
    uploaded = _client.files.upload(file=file_path)
    while uploaded.state.name == "PROCESSING":
        time.sleep(3)
        uploaded = _client.files.get(name=uploaded.name)
    if uploaded.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini file upload failed: state={uploaded.state.name}")

    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[uploaded, TRANSCRIBE_PROMPT],
        config=types.GenerateContentConfig(temperature=0.2),
    )
    return response.text
