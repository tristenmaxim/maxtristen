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

    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        progress_response = httpx.get(f"{DOWNLOADER_URL}/progress/{video_id}", timeout=10)
        progress_response.raise_for_status()
        progress = progress_response.json()
        if progress["status"] == "complete":
            break
        if progress["status"] == "error":
            raise RuntimeError(f"downloader failed: {progress.get('message')}")
        time.sleep(2)
    else:
        raise TimeoutError('Превышено время скачивания')

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

    if notion_store.TOKEN and notion_store.DATABASE:
        source_url = row['source_ref'] if row['source_type'] == 'url' else None
        page_id, page_url = row.get('notion_page_id'), row.get('notion_url')
        if not page_id:
            page = notion_store.create_entry(source_url, library.source_for(source_url))
            page_id, page_url = page['id'], page['url']
            db.update_entry(entry_id, notion_page_id=page_id, notion_url=page_url)
        else:
            notion_store.set_status(page_id, 'Обработка')
    else:
        page_id = None

    with tempfile.TemporaryDirectory(prefix='meaningly-') as tempdir:
        file_path = row['file_path']
        text = ''
        extra_files = []
        if row['source_type'] == 'url' and library.source_for(row['source_ref']) in ('X', 'Instagram'):
            fetch = library.tweet if library.source_for(row['source_ref']) == 'X' else library.instagram
            text, extra_files = fetch(row['source_ref'], tempdir)
            original_dir = os.path.join(FILES_DIR, f'{entry_id}-originals')
            os.makedirs(original_dir, exist_ok=True)
            for i, item in enumerate(extra_files):
                target = os.path.join(original_dir, os.path.basename(item))
                shutil.copyfile(item, target)
                extra_files[i] = target
            videos = [p for p in extra_files if p.endswith('.mp4')]
            if videos:
                file_path = videos[0]
        elif not file_path and row['source_type'] == 'telegram_video':
            db.update_entry(entry_id, status='downloading')
            file_path = os.path.join(FILES_DIR, f'{entry_id}.mp4')
            telegram.download_telegram_file(row['source_ref'], file_path)
            db.update_entry(entry_id, file_path=file_path)
        elif not file_path:
            db.update_entry(entry_id, status="downloading")
            file_path = _download_via_downloader_service(entry_id, row["source_ref"])
            db.update_entry(entry_id, file_path=file_path)

        transcript = row.get('transcript') or ''
        if file_path and not transcript:
            db.update_entry(entry_id, status="transcribing")
            transcript = gemini.transcribe(file_path)
            for extra in [p for p in extra_files if p.endswith('.mp4') and p != file_path]:
                transcript += '\n\n' + gemini.transcribe(extra)
            db.update_entry(entry_id, transcript=transcript)
        if not text and not transcript and not extra_files:
            raise ValueError('Не удалось получить содержимое публикации')
        if page_id:
            images = [p for p in extra_files if p.endswith(('.jpg', '.jpeg', '.png', '.webp'))]
            analysis_error = None
            try:
                title, summary, tags = library.describe('\n\n'.join(x for x in (text, transcript) if x), images)
            except Exception as error:
                analysis_error = error
            if text and not row['saved_text']:
                notion_store.append_text(page_id, 'Текст публикации', text)
                db.update_entry(entry_id, saved_text=1)
            if transcript and not row['saved_transcript']:
                notion_store.append_text(page_id, 'Расшифровка', transcript)
                db.update_entry(entry_id, saved_transcript=1)
            files = extra_files or ([file_path] if file_path else [])
            library.upload_media(page_id, files, tempdir, saved=row['saved_media'],
                                 on_saved=lambda count: db.update_entry(entry_id, saved_media=count))
            if analysis_error:
                raise analysis_error
            notion_store.update_entry(page_id, title, summary, tags, 'Готово', library.source_for(source_url))
        transcript = transcript or text or 'Сохранено изображение.'
        db.update_entry(entry_id, status="done", transcript=transcript, error_message=None)
