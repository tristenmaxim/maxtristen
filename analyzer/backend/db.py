import os
import sqlite3
from typing import Optional

DB_PATH = os.getenv("ANALYZER_DB_PATH", os.path.join(os.path.dirname(__file__), ".local-data", "analyzer.db"))

_UPDATABLE_FIELDS = {"status", "error_message", "transcript", "file_path"}


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
            CREATE TABLE IF NOT EXISTS entries (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type      TEXT NOT NULL CHECK (source_type IN ('url', 'telegram_video', 'web_upload')),
                source_ref       TEXT,
                telegram_chat_id INTEGER,
                file_path        TEXT,
                status           TEXT NOT NULL DEFAULT 'queued'
                                 CHECK (status IN ('queued','downloading','transcribing','done','error')),
                error_message    TEXT,
                transcript       TEXT,
                created_at       TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


def create_entry(source_type: str, source_ref: Optional[str] = None,
                  telegram_chat_id: Optional[int] = None, file_path: Optional[str] = None) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO entries (source_type, source_ref, telegram_chat_id, file_path) VALUES (?, ?, ?, ?)",
            (source_type, source_ref, telegram_chat_id, file_path),
        )
        return cur.lastrowid


def update_entry(entry_id: int, **fields) -> None:
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValueError(f"cannot update fields: {unknown}")
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with _connect() as conn:
        conn.execute(
            f"UPDATE entries SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            (*fields.values(), entry_id),
        )


def get_entry(entry_id: int) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
        return dict(row) if row else None


def list_entries() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, source_type, source_ref, status, error_message,
                   substr(transcript, 1, 300) AS transcript_preview,
                   created_at, updated_at
            FROM entries ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
