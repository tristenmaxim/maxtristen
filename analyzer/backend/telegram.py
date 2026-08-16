import os
from typing import Optional

import httpx

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")

TELEGRAM_ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID")
if not TELEGRAM_ALLOWED_USER_ID:
    raise ValueError("TELEGRAM_ALLOWED_USER_ID not found in environment variables")
TELEGRAM_ALLOWED_USER_ID = int(TELEGRAM_ALLOWED_USER_ID)

SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://maxtristen.com")

API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
FILE_BASE = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}"

MAX_MESSAGE_LEN = 4000


def send_message(chat_id: int, text: str, entry_id: Optional[int] = None) -> None:
    if len(text) > MAX_MESSAGE_LEN:
        link = f"{SITE_BASE_URL}/analyzer/#entry-{entry_id}" if entry_id else f"{SITE_BASE_URL}/analyzer/"
        text = text[:MAX_MESSAGE_LEN] + f"\n\n… обрезано, полностью тут: {link}"
    httpx.post(f"{API_BASE}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)


def get_file_download_url(file_id: str) -> str:
    resp = httpx.get(f"{API_BASE}/getFile", params={"file_id": file_id}, timeout=10)
    resp.raise_for_status()
    file_path = resp.json()["result"]["file_path"]
    return f"{FILE_BASE}/{file_path}"


def download_telegram_file(file_id: str, dest_path: str) -> None:
    url = get_file_download_url(file_id)
    with httpx.stream("GET", url, timeout=60) as resp:
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)


def parse_update(update: dict) -> Optional[dict]:
    message = update.get("message")
    if not message:
        return None
    from_id = message.get("from", {}).get("id")
    if from_id != TELEGRAM_ALLOWED_USER_ID:
        return None

    chat_id = message["chat"]["id"]

    video = message.get("video") or message.get("document")
    if video:
        return {"chat_id": chat_id, "source_type": "telegram_video", "file_id": video["file_id"]}

    text = (message.get("text") or "").strip()
    if text.startswith("http://") or text.startswith("https://"):
        return {"chat_id": chat_id, "source_type": "url", "url": text}

    return None
