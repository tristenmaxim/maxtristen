import os
import time
import tempfile
import shutil

import httpx

import db
import gemini
import telegram
import library
import notion_store

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

    page_id = None
    page_url = None
    try:
        if notion_store.TOKEN and notion_store.DATABASE:
            source_url = row['source_ref'] if row['source_type'] == 'url' else None
            page_id, page_url = row.get('notion_page_id'), row.get('notion_url')
            if not page_id:
                page = notion_store.create_entry(source_url, library.source_for(source_url))
                page_id, page_url = page['id'], page['url']
                db.update_entry(entry_id, notion_page_id=page_id, notion_url=page_url)
        file_path = row["file_path"]
        text = ''
        extra_files = []
        tempdir = tempfile.TemporaryDirectory(prefix='meaningly-')
        if row['source_type'] == 'url' and library.source_for(row['source_ref']) in ('X', 'Instagram'):
            fetch = library.tweet if library.source_for(row['source_ref']) == 'X' else library.instagram
            text, extra_files = fetch(row['source_ref'], tempdir.name)
            original_dir = os.path.join(FILES_DIR, f'{entry_id}-originals')
            os.makedirs(original_dir, exist_ok=True)
            for i, item in enumerate(extra_files):
                target = os.path.join(original_dir, os.path.basename(item))
                shutil.copyfile(item, target)
                extra_files[i] = target
            videos = [p for p in extra_files if p.endswith('.mp4')]
            if videos:
                file_path = videos[0]
        elif not file_path:
            db.update_entry(entry_id, status="downloading")
            file_path = _download_via_downloader_service(entry_id, row["source_ref"])
            db.update_entry(entry_id, file_path=file_path)

        transcript = ''
        if file_path:
            db.update_entry(entry_id, status="transcribing")
            transcript = gemini.transcribe(file_path)
            for extra in [p for p in extra_files if p.endswith('.mp4') and p != file_path]:
                transcript += '\n\n' + gemini.transcribe(extra)
        if not text and not transcript and not extra_files:
            raise ValueError('Не удалось получить содержимое публикации')
        if page_id:
            images = [p for p in extra_files if p.endswith(('.jpg', '.jpeg', '.png', '.webp'))]
            analysis_error = None
            try:
                title, summary, tags = library.describe('\n\n'.join(x for x in (text, transcript) if x), images)
            except Exception as error:
                analysis_error = error
            if text:
                notion_store.append_text(page_id, 'Текст публикации', text)
            if transcript:
                notion_store.append_text(page_id, 'Расшифровка', transcript)
            files = extra_files or ([file_path] if file_path else [])
            library.upload_media(page_id, files, tempdir.name)
            if analysis_error:
                raise analysis_error
            notion_store.update_entry(page_id, title, summary, tags, 'Готово', library.source_for(source_url))
        transcript = transcript or text or 'Сохранено изображение.'
        db.update_entry(entry_id, status="done", transcript=transcript, error_message=None)
    except Exception as e:
        db.update_entry(entry_id, status="error", error_message=str(e))
        if page_id:
            try:
                notion_store.update_entry(page_id, 'Ошибка обработки', str(e), [], 'Ошибка')
            except Exception:
                pass
    finally:
        row = db.get_entry(entry_id)
        if row and row["telegram_chat_id"]:
            if row["status"] == "done":
                telegram.send_message(row["telegram_chat_id"], row["transcript"], entry_id=entry_id)
                if page_url:
                    telegram.send_message(row["telegram_chat_id"], f'Сохранено в Notion: {page_url}')
            else:
                telegram.send_message(row["telegram_chat_id"], f"Ошибка обработки. {('Карточка в Notion: ' + page_url) if page_url else ''}")
