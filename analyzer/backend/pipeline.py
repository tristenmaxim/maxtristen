import os
import time

import httpx

import db
import gemini
import telegram

DOWNLOADER_URL = os.getenv("DOWNLOADER_URL", "http://127.0.0.1:8003")
FILES_DIR = os.getenv("ANALYZER_FILES_DIR", os.path.join(os.path.dirname(__file__), ".local-data", "files"))


def _download_via_downloader_service(entry_id: int, url: str) -> str:
    resp = httpx.post(f"{DOWNLOADER_URL}/download", json={"url": url}, timeout=30)
    resp.raise_for_status()
    video_id = resp.json()["videoId"]

    while True:
        progress = httpx.get(f"{DOWNLOADER_URL}/progress/{video_id}", timeout=10).json()
        if progress["status"] == "complete":
            break
        if progress["status"] == "error":
            raise RuntimeError(f"downloader failed: {progress.get('message')}")
        time.sleep(2)

    dest_path = os.path.join(FILES_DIR, f"{entry_id}.mp4")
    with httpx.stream("GET", f"{DOWNLOADER_URL}/download/{video_id}", timeout=120) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    return dest_path


def process_entry(entry_id: int) -> None:
    os.makedirs(FILES_DIR, exist_ok=True)
    row = db.get_entry(entry_id)
    if row is None:
        return

    try:
        file_path = row["file_path"]
        if not file_path:
            db.update_entry(entry_id, status="downloading")
            file_path = _download_via_downloader_service(entry_id, row["source_ref"])
            db.update_entry(entry_id, file_path=file_path)

        db.update_entry(entry_id, status="transcribing")
        transcript = gemini.transcribe(file_path)
        db.update_entry(entry_id, status="done", transcript=transcript)
    except Exception as e:
        db.update_entry(entry_id, status="error", error_message=str(e))
    finally:
        row = db.get_entry(entry_id)
        if row and row["telegram_chat_id"]:
            if row["status"] == "done":
                telegram.send_message(row["telegram_chat_id"], row["transcript"], entry_id=entry_id)
            else:
                telegram.send_message(row["telegram_chat_id"], f"Ошибка: {row['error_message']}")
