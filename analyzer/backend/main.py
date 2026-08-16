import os
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

import auth
import db
import pipeline
import telegram

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[auth.SITE_BASE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory="../frontend/assets"), name="assets")


@app.on_event("startup")
def startup():
    db.init_db()
    os.makedirs(pipeline.FILES_DIR, exist_ok=True)


def require_wallet(request: Request) -> str:
    token = request.cookies.get("session")
    wallet = auth.require_wallet_from_cookie(token)
    if wallet is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return wallet


@app.get("/api/auth/nonce")
async def auth_nonce():
    return {"nonce": auth.issue_nonce()}


@app.post("/api/auth/verify")
async def auth_verify(request: Request, response: Response):
    body = await request.json()
    try:
        wallet = auth.verify_siwe(body["message"], body["signature"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    if wallet not in auth.ALLOWED_WALLETS:
        raise HTTPException(status_code=403, detail="wallet not allowed")

    token = auth.create_session(wallet)
    response.set_cookie(
        key="session", value=token, httponly=True, samesite="lax",
        secure=auth.COOKIE_SECURE, max_age=auth.SESSION_TTL_SECONDS,
    )
    return {"wallet": wallet}


@app.post("/api/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get("session")
    if token:
        db.delete_session(token)
    response.delete_cookie("session")
    return {"ok": True}


@app.get("/api/auth/me")
async def auth_me(wallet: str = Depends(require_wallet)):
    return {"wallet": wallet}


@app.post("/api/telegram/link-code")
async def telegram_link_code(wallet: str = Depends(require_wallet)):
    return {"code": auth.issue_link_code(wallet), "bot_username": os.getenv("TELEGRAM_BOT_USERNAME", "")}


@app.post("/api/entries")
async def create_entry(
    background_tasks: BackgroundTasks,
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    wallet: str = Depends(require_wallet),
):
    if not url and not file:
        raise HTTPException(status_code=400, detail="provide either url or file")
    if url and file:
        raise HTTPException(status_code=400, detail="provide only one of url or file")

    if file:
        entry_id = db.create_entry(wallet_address=wallet, source_type="web_upload")
        ext = os.path.splitext(file.filename or "")[1] or ".mp4"
        dest_path = os.path.join(pipeline.FILES_DIR, f"{entry_id}{ext}")
        os.makedirs(pipeline.FILES_DIR, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(await file.read())
        db.update_entry(entry_id, file_path=dest_path)
    else:
        entry_id = db.create_entry(wallet_address=wallet, source_type="url", source_ref=url)

    background_tasks.add_task(pipeline.process_entry, entry_id)
    return {"id": entry_id}


@app.get("/api/entries")
async def list_entries(wallet: str = Depends(require_wallet)):
    return db.list_entries(wallet_address=wallet)


@app.get("/api/entries/{entry_id}")
async def get_entry(entry_id: int, wallet: str = Depends(require_wallet)):
    entry = db.get_entry_for_wallet(entry_id, wallet_address=wallet)
    if entry is None:
        raise HTTPException(status_code=404, detail="not found")
    return entry


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    update = await request.json()
    parsed = telegram.parse_update(update)
    if parsed is None:
        return {"ok": True}

    wallet = parsed["wallet_address"]

    if parsed["source_type"] == "telegram_video":
        entry_id = db.create_entry(wallet_address=wallet, source_type="telegram_video",
                                    source_ref=parsed["file_id"], telegram_chat_id=parsed["chat_id"])
        os.makedirs(pipeline.FILES_DIR, exist_ok=True)
        dest_path = os.path.join(pipeline.FILES_DIR, f"{entry_id}.mp4")
        telegram.download_telegram_file(parsed["file_id"], dest_path)
        db.update_entry(entry_id, file_path=dest_path)
    else:
        entry_id = db.create_entry(wallet_address=wallet, source_type="url",
                                    source_ref=parsed["url"], telegram_chat_id=parsed["chat_id"])

    telegram.send_message(parsed["chat_id"], "Обрабатываю…")
    background_tasks.add_task(pipeline.process_entry, entry_id)
    return {"ok": True}


@app.get("/")
async def serve_index():
    return FileResponse("../frontend/index.html")


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Analyzer API"}
