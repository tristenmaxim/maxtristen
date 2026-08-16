import os
import sqlite3
from typing import Optional

DB_PATH = os.getenv("BLOG_DB_PATH", os.path.join(os.path.dirname(__file__), ".local-data", "blog.db"))

_UPDATABLE_FIELDS = {"title", "body_markdown", "published"}


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                title          TEXT NOT NULL,
                body_markdown  TEXT NOT NULL,
                published      INTEGER NOT NULL DEFAULT 0,
                created_at     TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token          TEXT PRIMARY KEY,
                wallet_address TEXT NOT NULL,
                created_at     TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at     TEXT NOT NULL
            )
            """
        )


def create_post(title: str, body_markdown: str, published: bool) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO posts (title, body_markdown, published) VALUES (?, ?, ?)",
            (title, body_markdown, int(published)),
        )
        return cur.lastrowid


def update_post(post_id: int, **fields) -> None:
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValueError(f"cannot update fields: {unknown}")
    if not fields:
        return
    if "published" in fields:
        fields["published"] = int(fields["published"])
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with _connect() as conn:
        conn.execute(
            f"UPDATE posts SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            (*fields.values(), post_id),
        )


def delete_post(post_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))


def get_post(post_id: int) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        return dict(row) if row else None


def list_posts(include_drafts: bool) -> list[dict]:
    with _connect() as conn:
        query = "SELECT id, title, published, created_at, updated_at FROM posts"
        if not include_drafts:
            query += " WHERE published = 1"
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]


def create_session(token: str, wallet_address: str, ttl_seconds: int) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, wallet_address, expires_at) VALUES (?, ?, datetime('now', ?))",
            (token, wallet_address, f"+{ttl_seconds} seconds"),
        )


def get_session(token: str) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT wallet_address FROM sessions WHERE token = ? AND expires_at > datetime('now')",
            (token,),
        ).fetchone()
        return row["wallet_address"] if row else None


def delete_session(token: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
