"""MoonBite community forum — a small SQLite-backed discussion board.

Threaded discussions with free-text display names (no accounts, no passwords).
The server stores raw text only; every value is HTML-escaped at render time by
Jinja's autoescaping, so stored posts can never inject markup into a page.

Storage is a single SQLite file (MOONBITE_FORUM_DB, default ``forum.db``). On an
ephemeral filesystem (e.g. Railway) the file resets on redeploy; on the droplet
it persists. SQLite is stdlib, so this adds no dependency. WAL mode lets the
read-heavy board tolerate concurrent gunicorn workers.
"""

from __future__ import annotations

import os
import sqlite3
import time
from typing import Optional

# --- limits (also enforced client-side, but the server is the source of truth) #
MAX_TITLE = 120
MAX_AUTHOR = 40
MAX_BODY = 8000
MIN_BODY = 1
DEFAULT_AUTHOR = "anon"

_DB_PATH = os.environ.get("MOONBITE_FORUM_DB", "").strip() or "forum.db"


def _connect() -> sqlite3.Connection:
    """Open a short-lived connection with the schema guaranteed to exist.

    Each request opens and closes its own connection; WAL mode keeps concurrent
    readers from blocking on a writer. `CREATE TABLE IF NOT EXISTS` makes first
    use self-initialising, so there is no separate migration step to forget.
    """
    conn = sqlite3.connect(_DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS threads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            author      TEXT    NOT NULL,
            body        TEXT    NOT NULL,
            created_at  INTEGER NOT NULL,
            bumped_at   INTEGER NOT NULL,
            reply_count INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS replies (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id  INTEGER NOT NULL,
            author     TEXT    NOT NULL,
            body       TEXT    NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
        )"""
    )
    return conn


def _clean(value, *, field: str, maxlen: int, minlen: int = 0, default: str | None = None) -> str:
    """Validate one user-supplied text field: coerce, strip, bound its length.

    Raises ValueError on empty required fields or overrun so the route can turn
    it into a clean 400 (mirrors the exchange/merchants modules' convention).
    """
    text = str(value or "").strip()
    if not text and default is not None:
        text = default
    if len(text) < minlen or not text:
        raise ValueError(f"{field} is required")
    if len(text) > maxlen:
        raise ValueError(f"{field} must be {maxlen} characters or fewer")
    return text


def _iso(ts: int) -> str:
    """Human-readable UTC stamp for display (e.g. '2026-07-26 14:30 UTC')."""
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(ts))


def _thread_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "author": row["author"],
        "body": row["body"],
        "created_at": row["created_at"],
        "created_display": _iso(row["created_at"]),
        "bumped_at": row["bumped_at"],
        "bumped_display": _iso(row["bumped_at"]),
        "reply_count": row["reply_count"],
    }


def _reply_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "thread_id": row["thread_id"],
        "author": row["author"],
        "body": row["body"],
        "created_at": row["created_at"],
        "created_display": _iso(row["created_at"]),
    }


def create_thread(title, author, body) -> dict:
    """Open a new discussion thread. Returns the stored thread dict."""
    title = _clean(title, field="Title", maxlen=MAX_TITLE, minlen=1)
    author = _clean(author, field="Name", maxlen=MAX_AUTHOR, default=DEFAULT_AUTHOR)
    body = _clean(body, field="Message", maxlen=MAX_BODY, minlen=MIN_BODY)
    now = int(time.time())
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO threads (title, author, body, created_at, bumped_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (title, author, body, now, now),
        )
        thread_id = cur.lastrowid
        row = conn.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()
    return _thread_row(row)


def list_threads(limit: int = 20, offset: int = 0) -> dict:
    """Return a page of threads, most-recently-active first, plus the total."""
    limit = max(1, min(int(limit), 50))
    offset = max(0, int(offset))
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM threads").fetchone()["n"]
        rows = conn.execute(
            "SELECT * FROM threads ORDER BY bumped_at DESC, id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return {
        "threads": [_thread_row(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_thread(thread_id: int) -> Optional[dict]:
    """Return one thread with its replies (oldest first), or None if missing."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()
        if row is None:
            return None
        replies = conn.execute(
            "SELECT * FROM replies WHERE thread_id = ? ORDER BY created_at ASC, id ASC",
            (thread_id,),
        ).fetchall()
    thread = _thread_row(row)
    thread["replies"] = [_reply_row(r) for r in replies]
    return thread


def add_reply(thread_id: int, author, body) -> dict:
    """Append a reply to a thread and bump it. Raises ValueError if no thread."""
    author = _clean(author, field="Name", maxlen=MAX_AUTHOR, default=DEFAULT_AUTHOR)
    body = _clean(body, field="Reply", maxlen=MAX_BODY, minlen=MIN_BODY)
    now = int(time.time())
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM threads WHERE id = ?", (thread_id,)
        ).fetchone()
        if exists is None:
            raise ValueError("thread not found")
        cur = conn.execute(
            "INSERT INTO replies (thread_id, author, body, created_at) VALUES (?, ?, ?, ?)",
            (thread_id, author, body, now),
        )
        reply_id = cur.lastrowid
        conn.execute(
            "UPDATE threads SET reply_count = reply_count + 1, bumped_at = ? WHERE id = ?",
            (now, thread_id),
        )
        row = conn.execute("SELECT * FROM replies WHERE id = ?", (reply_id,)).fetchone()
    return _reply_row(row)
