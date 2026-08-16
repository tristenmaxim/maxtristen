import os
from typing import Optional

import markdown
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

import auth
import db

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


def require_wallet(request: Request) -> str:
    token = request.cookies.get(auth.COOKIE_NAME)
    wallet = auth.require_wallet_from_cookie(token)
    if wallet is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return wallet


def optional_wallet(request: Request) -> Optional[str]:
    token = request.cookies.get(auth.COOKIE_NAME)
    return auth.require_wallet_from_cookie(token)


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
        key=auth.COOKIE_NAME, value=token, httponly=True, samesite="lax",
        secure=auth.COOKIE_SECURE, max_age=auth.SESSION_TTL_SECONDS,
    )
    return {"wallet": wallet}


@app.post("/api/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token:
        db.delete_session(token)
    response.delete_cookie(auth.COOKIE_NAME)
    return {"ok": True}


@app.get("/api/auth/me")
async def auth_me(wallet: str = Depends(require_wallet)):
    return {"wallet": wallet}


class PostIn(BaseModel):
    title: str
    body_markdown: str
    published: bool = False


class PostPatch(BaseModel):
    title: Optional[str] = None
    body_markdown: Optional[str] = None
    published: Optional[bool] = None


@app.get("/api/posts")
async def list_posts(wallet: Optional[str] = Depends(optional_wallet)):
    return db.list_posts(include_drafts=wallet is not None)


@app.get("/api/posts/{post_id}")
async def get_post(post_id: int, wallet: Optional[str] = Depends(optional_wallet)):
    post = db.get_post(post_id)
    if post is None or (not post["published"] and wallet is None):
        raise HTTPException(status_code=404, detail="not found")
    post["body_html"] = markdown.markdown(post["body_markdown"])
    return post


@app.post("/api/posts")
async def create_post(body: PostIn, wallet: str = Depends(require_wallet)):
    post_id = db.create_post(body.title, body.body_markdown, body.published)
    return {"id": post_id}


@app.put("/api/posts/{post_id}")
async def update_post(post_id: int, body: PostPatch, wallet: str = Depends(require_wallet)):
    if db.get_post(post_id) is None:
        raise HTTPException(status_code=404, detail="not found")
    fields = {k: v for k, v in body.dict().items() if v is not None}
    db.update_post(post_id, **fields)
    return {"ok": True}


@app.delete("/api/posts/{post_id}")
async def delete_post(post_id: int, wallet: str = Depends(require_wallet)):
    if db.get_post(post_id) is None:
        raise HTTPException(status_code=404, detail="not found")
    db.delete_post(post_id)
    return {"ok": True}


@app.get("/")
async def serve_index():
    return FileResponse("../frontend/index.html")


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Blog API"}
