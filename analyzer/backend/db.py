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
                wallet_address   TEXT NOT NULL,
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_accounts (
                telegram_user_id INTEGER PRIMARY KEY,
                wallet_address   TEXT NOT NULL,
                linked_at        TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


def create_entry(wallet_address: str, source_type: str, source_ref: Optional[str] = None,
                  telegram_chat_id: Optional[int] = None, file_path: Optional[str] = None) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO entries (wallet_address, source_type, source_ref, telegram_chat_id, file_path) "
            "VALUES (?, ?, ?, ?, ?)",
            (wallet_address, source_type, source_ref, telegram_chat_id, file_path),
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


def get_entry_for_wallet(entry_id: int, wallet_address: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM entries WHERE id = ? AND wallet_address = ?", (entry_id, wallet_address)
        ).fetchone()
        return dict(row) if row else None


def list_entries(wallet_address: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, source_type, source_ref, status, error_message,
                   substr(transcript, 1, 300) AS transcript_preview,
                   created_at, updated_at
            FROM entries WHERE wallet_address = ? ORDER BY created_at DESC
            """,
            (wallet_address,),
        ).fetchall()
        return [dict(r) for r in rows]


def create_session(token: str, wallet_address: str, ttl_seconds: int) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, wallet_address, expires_at) "
            "VALUES (?, ?, datetime('now', ?))",
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


def link_telegram(telegram_user_id: int, wallet_address: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO telegram_accounts (telegram_user_id, wallet_address) VALUES (?, ?) "
            "ON CONFLICT(telegram_user_id) DO UPDATE SET wallet_address = excluded.wallet_address",
            (telegram_user_id, wallet_address),
        )


def get_wallet_for_telegram(telegram_user_id: int) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT wallet_address FROM telegram_accounts WHERE telegram_user_id = ?", (telegram_user_id,)
        ).fetchone()
        return row["wallet_address"] if row else None
