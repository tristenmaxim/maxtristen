import os
import time
import math

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
import httpx

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
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
            return response.text or ''
        except genai_errors.ServerError as e:
            last_error = e
    raise last_error


def transcribe_youtube(url, duration=None, cached=None, on_part=None):
    cached = cached or {}
    total = float(duration) if duration else None
    segmented = total is not None and total > 600
    starts = range(0, math.ceil(total), 600) if segmented else [0]
    parts = []
    for start in starts:
        end = min(start + 600, total) if segmented else total
        if start in cached:
            text = cached[start]
        else:
            kwargs = {'file_data': types.FileData(file_uri=url)}
            if segmented:
                kwargs['video_metadata'] = types.VideoMetadata(start_offset=f'{start}s', end_offset=f'{end:g}s')
            prompt = ('Listen to the audio and transcribe every spoken word verbatim in the original language. '
                      'Include timestamps relative to the original full video. Label speakers when distinguishable. Do not summarize.')
            response = generate(contents=[types.Part(**kwargs), prompt], config=types.GenerateContentConfig(temperature=0.2))
            candidates = getattr(response, 'candidates', None) or []
            if candidates:
                reason = getattr(candidates[0], 'finish_reason', None)
                if reason and str(reason).rsplit('.', 1)[-1] != 'STOP':
                    raise RuntimeError(f'Не удалось получить полный фрагмент YouTube: {reason}')
            feedback = getattr(response, 'prompt_feedback', None)
            block_reason = getattr(feedback, 'block_reason', None) if feedback else None
            if block_reason and str(block_reason).rsplit('.', 1)[-1] not in ('UNSPECIFIED', 'BLOCK_REASON_UNSPECIFIED'):
                raise RuntimeError('Google отклонил обработку фрагмента YouTube')
            text = (response.text or '').strip() or '[Речь в этом фрагменте не распознана или отсутствует]'
            if on_part:
                on_part(start, text)
        if segmented:
            def stamp(seconds):
                seconds = int(seconds)
                return f'{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}'
            parts.append(f'Фрагмент {stamp(start)}–{stamp(end)}\n{text}')
        else:
            parts.append(text)
    return '\n\n'.join(parts)
