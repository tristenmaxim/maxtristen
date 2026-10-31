import os
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
import httpx

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.8-flash")

_client = genai.Client(api_key=GEMINI_API_KEY, http_options=types.HttpOptions(timeout=90000))

TRANSCRIBE_PROMPT = (
    "Transcribe the audio in this audio or video file in full. Include timecodes (mm:ss) at natural breaks, "
    "and label distinct speakers as 'Speaker 1:', 'Speaker 2:', etc. "
    "Output only the transcript, no preamble."
)


def generate(contents, config):
    models = list(dict.fromkeys((GEMINI_MODEL, GEMINI_FALLBACK_MODEL, 'gemini-3.1-flash-lite')))
    for index, model in enumerate(models):
        try:
            return _client.models.generate_content(model=model, contents=contents, config=config)
        except (genai_errors.ServerError, httpx.TimeoutException):
            if index == len(models) - 1:
                raise
        except genai_errors.ClientError as error:
            if error.code != 429 or index == len(models) - 1:
                raise


def transcribe(file_path: str) -> str:
    uploaded = _client.files.upload(file=file_path)
    while uploaded.state.name == "PROCESSING":
        time.sleep(3)
        uploaded = _client.files.get(name=uploaded.name)
    if uploaded.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini file upload failed: state={uploaded.state.name}")

    last_error = None
    for attempt, backoff in enumerate((0, 10, 30)):
        if backoff:
            time.sleep(backoff)
        try:
            response = generate(
                contents=[uploaded, TRANSCRIBE_PROMPT],
                config=types.GenerateContentConfig(temperature=0.2),
            )
            return response.text
        except genai_errors.ServerError as e:
            last_error = e
    raise last_error
