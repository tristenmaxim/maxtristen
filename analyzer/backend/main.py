import os
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

import db
import pipeline
import telegram

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory="../frontend/assets"), name="assets")


@app.on_event("startup")
def startup():
    db.init_db()
    os.makedirs(pipeline.FILES_DIR, exist_ok=True)


@app.post("/api/entries")
async def create_entry(
    background_tasks: BackgroundTasks,
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    if not url and not file:
        raise HTTPException(status_code=400, detail="provide either url or file")
    if url and file:
        raise HTTPException(status_code=400, detail="provide only one of url or file")

    if file:
        entry_id = db.create_entry(source_type="web_upload")
        ext = os.path.splitext(file.filename or "")[1] or ".mp4"
        dest_path = os.path.join(pipeline.FILES_DIR, f"{entry_id}{ext}")
        os.makedirs(pipeline.FILES_DIR, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(await file.read())
        db.update_entry(entry_id, file_path=dest_path)
    else:
        entry_id = db.create_entry(source_type="url", source_ref=url)

    background_tasks.add_task(pipeline.process_entry, entry_id)
    return {"id": entry_id}


@app.get("/api/entries")
async def list_entries():
    return db.list_entries()


@app.get("/api/entries/{entry_id}")
async def get_entry(entry_id: int):
    entry = db.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="not found")
    return entry


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    update = await request.json()
    parsed = telegram.parse_update(update)
    if parsed is None:
        return {"ok": True}

    if parsed["source_type"] == "telegram_video":
        entry_id = db.create_entry(source_type="telegram_video", source_ref=parsed["file_id"],
                                    telegram_chat_id=parsed["chat_id"])
        os.makedirs(pipeline.FILES_DIR, exist_ok=True)
        dest_path = os.path.join(pipeline.FILES_DIR, f"{entry_id}.mp4")
        telegram.download_telegram_file(parsed["file_id"], dest_path)
        db.update_entry(entry_id, file_path=dest_path)
    else:
        entry_id = db.create_entry(source_type="url", source_ref=parsed["url"],
                                    telegram_chat_id=parsed["chat_id"])

    telegram.send_message(parsed["chat_id"], "Обрабатываю…")
    background_tasks.add_task(pipeline.process_entry, entry_id)
    return {"ok": True}


@app.get("/")
async def serve_index():
    return FileResponse("../frontend/index.html")


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Analyzer API"}
