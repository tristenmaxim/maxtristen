import os
import sqlite3
from typing import Optional

DB_PATH = os.getenv("ANALYZER_DB_PATH", os.path.join(os.path.dirname(__file__), ".local-data", "analyzer.db"))

_UPDATABLE_FIELDS = {"status", "error_message", "transcript", "file_path", "notion_page_id", "notion_url", "saved_text", "saved_transcript", "saved_visual_text", "saved_media"}


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
        columns = {r[1] for r in conn.execute('PRAGMA table_info(entries)')}
        migrating_queue = 'job_state' not in columns
        for column in ('notion_page_id', 'notion_url'):
            if column not in columns:
                conn.execute(f'ALTER TABLE entries ADD COLUMN {column} TEXT')
        for column, definition in (
            ('job_state', 'TEXT'), ('attempts', 'INTEGER NOT NULL DEFAULT 0'),
            ('next_attempt', 'TEXT'), ('saved_text', 'INTEGER NOT NULL DEFAULT 0'),
            ('saved_transcript', 'INTEGER NOT NULL DEFAULT 0'), ('saved_visual_text', 'INTEGER NOT NULL DEFAULT 0'),
            ('saved_media', 'INTEGER NOT NULL DEFAULT 0'),
        ):
            if column not in columns:
                conn.execute(f'ALTER TABLE entries ADD COLUMN {column} {definition}')
        if migrating_queue:
            conn.execute("UPDATE entries SET job_state = 'pending', status = 'queued' WHERE status IN ('queued', 'downloading', 'transcribing')")
        conn.execute('CREATE TABLE IF NOT EXISTS telegram_updates (update_id INTEGER PRIMARY KEY)')
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
                  telegram_chat_id: Optional[int] = None, file_path: Optional[str] = None,
                  queued: bool = False) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO entries (wallet_address, source_type, source_ref, telegram_chat_id, file_path, job_state) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (wallet_address, source_type, source_ref, telegram_chat_id, file_path, 'pending' if queued else None),
        )
        return cur.lastrowid


def enqueue(entry_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE entries SET job_state = 'pending', status = 'queued', next_attempt = NULL WHERE id = ?", (entry_id,))


def enqueue_telegram_urls(wallet: str, urls: list, chat_id: int, update_id: Optional[int]) -> tuple:
    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if update_id is not None:
            if conn.execute('INSERT OR IGNORE INTO telegram_updates(update_id) VALUES (?)', (update_id,)).rowcount == 0:
                return 0, 0, True
        added = duplicates = 0
        for url in dict.fromkeys(urls):
            existing = conn.execute(
                "SELECT id, job_state FROM entries WHERE wallet_address = ? AND source_type = 'url' AND source_ref = ? "
                "AND (job_state IN ('pending', 'running', 'failed') OR (status = 'done' AND notion_url IS NOT NULL)) "
                "ORDER BY CASE WHEN status = 'done' THEN 0 WHEN job_state IN ('pending', 'running') THEN 1 ELSE 2 END, id DESC LIMIT 1",
                (wallet, url),
            ).fetchone()
            if existing:
                if existing['job_state'] == 'failed':
                    conn.execute("UPDATE entries SET job_state = 'pending', status = 'queued', attempts = 0, next_attempt = NULL, telegram_chat_id = ? WHERE id = ?", (chat_id, existing['id']))
                    added += 1
                    continue
                duplicates += 1
                continue
            conn.execute("INSERT INTO entries(wallet_address, source_type, source_ref, telegram_chat_id, job_state) VALUES (?, 'url', ?, ?, 'pending')", (wallet, url, chat_id))
            added += 1
        return added, duplicates, False


def enqueue_telegram_file(wallet: str, file_id: str, chat_id: int, update_id: Optional[int]) -> bool:
    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if update_id is not None:
            if conn.execute('INSERT OR IGNORE INTO telegram_updates(update_id) VALUES (?)', (update_id,)).rowcount == 0:
                return False
        conn.execute("INSERT INTO entries(wallet_address, source_type, source_ref, telegram_chat_id, job_state) VALUES (?, 'telegram_video', ?, ?, 'pending')", (wallet, file_id, chat_id))
        return True


def recover_jobs() -> None:
    with _connect() as conn:
        conn.execute("UPDATE entries SET job_state = 'done', next_attempt = NULL WHERE job_state = 'running' AND status = 'done'")
        conn.execute("UPDATE entries SET job_state = 'pending', status = 'queued', next_attempt = NULL, attempts = MAX(attempts - 1, 0) WHERE job_state = 'running'")


def claim_job() -> Optional[dict]:
    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute("SELECT id FROM entries WHERE job_state = 'pending' AND (next_attempt IS NULL OR next_attempt <= datetime('now')) ORDER BY id LIMIT 1").fetchone()
        if row is None:
            return None
        conn.execute("UPDATE entries SET job_state = 'running', attempts = attempts + 1, updated_at = datetime('now') WHERE id = ?", (row['id'],))
        return dict(conn.execute('SELECT * FROM entries WHERE id = ?', (row['id'],)).fetchone())


def finish_job(entry_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE entries SET job_state = 'done', next_attempt = NULL WHERE id = ?", (entry_id,))


def retry_job(entry_id: int, error: str, delay: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE entries SET job_state = 'pending', status = 'queued', error_message = ?, next_attempt = datetime('now', ?), updated_at = datetime('now') WHERE id = ?", (error, f'+{delay} seconds', entry_id))


def fail_job(entry_id: int, error: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE entries SET job_state = 'failed', status = 'error', error_message = ?, updated_at = datetime('now') WHERE id = ?", (error, entry_id))


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


def find_saved_url(wallet_address: str, url: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT notion_url FROM entries WHERE wallet_address = ? AND source_type = 'url' AND source_ref = ? AND status = 'done' AND notion_url IS NOT NULL ORDER BY id DESC LIMIT 1",
            (wallet_address, url),
        ).fetchone()
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
