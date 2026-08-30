"""The Wall — a public, chain-verified registry of first blocks.

Every miner who finds a block may put one entry on the Wall and receives a
permanent ordinal ("certificate #47 of forever"). The ordinal is the whole
point: it cannot be bought, only taken earlier.

Why this is not a guestbook: `add()` refuses any entry whose address has not
actually been paid a coinbase on this chain. The caller supplies a verifier
that answers "how many blocks has this address mined?" from the chain itself,
so a claim that never happened cannot reach the Wall. Handles are free text and
are stored raw — the renderer is responsible for escaping them.

Storage mirrors forum.py / worldcup.py: stdlib sqlite3, one short-lived
connection per call, WAL for concurrent gunicorn workers, and
`CREATE TABLE IF NOT EXISTS` so first use self-initialises. The file lives at
MOONBITE_WALL_DB (default ``wall.db``); on an ephemeral filesystem it resets on
redeploy, on the droplet it persists.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from typing import Callable, Optional

from storage import data_path

# Lands on the mounted volume when there is one, beside the code when
# there is not. MOONBITE_WALL_DB still overrides both.
_DB_PATH = data_path("wall.db", "MOONBITE_WALL_DB")

MAX_HANDLE = 24
MAX_ADDRESS = 128
MAX_HEIGHT = 100_000_000

# Handles are shown publicly, so keep them to a boring, unambiguous set: no
# control characters, no direction overrides, nothing that can be mistaken for
# markup even if a future renderer forgets to escape.
_HANDLE_RE = re.compile(r"^[A-Za-z0-9 ._\-]{1,24}$")
_ADDR_RE = re.compile(r"^[A-Za-z0-9]{8,128}$")

DEFAULT_HANDLE = "anonymous"


def _connect() -> sqlite3.Connection:
    """Open a short-lived connection with the schema guaranteed to exist."""
    conn = sqlite3.connect(_DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS certificates (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            address    TEXT    NOT NULL UNIQUE,
            handle     TEXT    NOT NULL,
            country    TEXT,
            height     INTEGER NOT NULL,
            reward     REAL    NOT NULL,
            created_at INTEGER NOT NULL
        )"""
    )
    return conn


def _clean_handle(handle: Optional[str]) -> str:
    handle = (handle or "").strip()
    if not handle:
        return DEFAULT_HANDLE
    if not _HANDLE_RE.match(handle):
        raise ValueError("Handle may use letters, numbers, spaces, dot, dash or underscore")
    return handle


def _clean_address(address: Optional[str]) -> str:
    address = (address or "").strip()
    if not _ADDR_RE.match(address):
        raise ValueError("Invalid address")
    return address


def _clean_country(country: Optional[str]) -> Optional[str]:
    country = (country or "").strip().upper()
    if not country:
        return None
    if len(country) != 2 or not country.isalpha():
        raise ValueError("Invalid country code")
    return country


def add(
    address: str,
    handle: Optional[str],
    country: Optional[str],
    height: int,
    reward: float,
    verify_blocks: Callable[[str], int],
) -> dict:
    """Place one chain-verified certificate on the Wall.

    `verify_blocks(address)` must return the number of blocks that address has
    actually been paid on-chain; zero means the claim is refused. One entry per
    address — calling again returns the existing certificate rather than
    minting a second ordinal, so numbers stay honest.
    """
    address = _clean_address(address)
    handle = _clean_handle(handle)
    country = _clean_country(country)
    try:
        height = int(height)
        reward = float(reward)
    except (TypeError, ValueError):
        raise ValueError("Invalid block data")
    if not (0 <= height <= MAX_HEIGHT) or not (0 < reward <= 1_000_000):
        raise ValueError("Invalid block data")

    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT id, handle, country, height, reward, created_at "
            "FROM certificates WHERE address = ?",
            (address,),
        ).fetchone()
        if existing is not None:
            row = dict(existing)
            row["new"] = False
            return row

        # The Wall is only worth anything if every entry is real.
        if verify_blocks(address) < 1:
            raise ValueError("No block has been mined to this address yet")

        now = int(time.time())
        with conn:
            cur = conn.execute(
                "INSERT INTO certificates (address, handle, country, height, reward, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (address, handle, country, height, reward, now),
            )
        return {
            "id": cur.lastrowid,
            "handle": handle,
            "country": country,
            "height": height,
            "reward": reward,
            "created_at": now,
            "new": True,
        }
    finally:
        conn.close()


def lookup(address: Optional[str]) -> Optional[dict]:
    """Return this address's certificate, or None if it has never claimed one."""
    try:
        address = _clean_address(address)
    except ValueError:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, handle, country, height, reward, created_at "
            "FROM certificates WHERE address = ?",
            (address,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def recent(limit: int = 60, offset: int = 0) -> dict:
    """Newest certificates first, plus the total ever issued."""
    limit = max(1, min(int(limit or 60), 200))
    offset = max(0, int(offset or 0))
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, handle, country, height, reward, created_at "
            "FROM certificates ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS c FROM certificates").fetchone()["c"]
    finally:
        conn.close()
    return {"certificates": [dict(r) for r in rows], "total": total}
