"""MoonBite Mining World Cup — a country-by-country community scoreboard.

Miners declare which country they mine for and receive a permanent ordinal
("the 47th miner from Pakistan"). Countries are ranked by enlisted miners and
by self-reported blocks.

Honesty model — this is deliberately NOT presented as a chain metric:
  * A coinbase transaction carries no country, so per-country block counts
    cannot be derived from consensus data. Both numbers here are declared by
    miners themselves.
  * Enlistment is deduplicated by a client-generated token, which stops casual
    double-counting but is not Sybil-proof. The page says so in plain text.
Presenting self-reported figures as verified chain data would be the exact kind
of claim this project refuses to make elsewhere, so it is not made here either.

Storage is a single SQLite file (MOONBITE_WORLDCUP_DB, default
``worldcup.db``), mirroring forum.py: stdlib only, WAL mode for concurrent
gunicorn workers, and `CREATE TABLE IF NOT EXISTS` so first use self-initialises.
On an ephemeral filesystem (Railway) the file resets on redeploy; on the
droplet it persists.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from typing import Optional

_DB_PATH = os.environ.get("MOONBITE_WORLDCUP_DB", "").strip() or "worldcup.db"

MAX_TOKEN = 64
MAX_BLOCKS = 1_000_000  # a self-report above this is nonsense; clamp it

# ISO 3166-1 alpha-2. An allowlist keeps junk codes out of the standings and
# bounds the flag rendering to real regional-indicator pairs.
VALID_CODES = frozenset("""
AD AE AF AG AI AL AM AO AR AT AU AW AZ BA BB BD BE BF BG BH BI BJ BM BN BO BR
BS BT BW BY BZ CA CD CF CG CH CI CL CM CN CO CR CU CV CY CZ DE DJ DK DM DO DZ
EC EE EG ER ES ET FI FJ FM FO FR GA GB GD GE GH GI GL GM GN GQ GR GT GW GY HK
HN HR HT HU ID IE IL IM IN IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW
KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MG MH MK ML MM MN MO MR MT
MU MV MW MX MY MZ NA NE NG NI NL NO NP NR NZ OM PA PE PF PG PH PK PL PR PS PT
PW PY QA RO RS RU RW SA SB SC SD SE SG SI SK SL SM SN SO SR SS ST SV SY SZ TD
TG TH TJ TL TM TN TO TR TT TV TW TZ UA UG US UY UZ VA VC VE VN VU WS XK YE ZA
ZM ZW
""".split())

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _connect() -> sqlite3.Connection:
    """Open a short-lived connection with the schema guaranteed to exist."""
    conn = sqlite3.connect(_DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS countries (
            code       TEXT    PRIMARY KEY,
            miners     INTEGER NOT NULL DEFAULT 0,
            blocks     INTEGER NOT NULL DEFAULT 0,
            first_at   INTEGER,
            updated_at INTEGER
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS enlistments (
            token      TEXT    PRIMARY KEY,
            code       TEXT    NOT NULL,
            ordinal    INTEGER NOT NULL,
            blocks     INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_enlist_code ON enlistments(code)")
    return conn


def _clean_code(code: Optional[str]) -> str:
    code = (code or "").strip().upper()
    if code not in VALID_CODES:
        raise ValueError("Unknown country code")
    return code


def _clean_token(token: Optional[str]) -> str:
    token = (token or "").strip()
    if not _TOKEN_RE.match(token):
        raise ValueError("Invalid token")
    return token


def enlist(token: str, code: str, blocks: int = 0) -> dict:
    """Register (or refresh) one miner for a country.

    Idempotent per token: calling again keeps the original ordinal and country
    so a miner's number never silently changes, and only refreshes the
    self-reported block count. Returns this miner's standing.
    """
    token = _clean_token(token)
    code = _clean_code(code)
    blocks = max(0, min(int(blocks or 0), MAX_BLOCKS))
    now = int(time.time())

    conn = _connect()
    try:
        with conn:
            row = conn.execute(
                "SELECT code, ordinal, blocks FROM enlistments WHERE token = ?",
                (token,),
            ).fetchone()

            if row is not None:
                # Existing miner: only the block self-report may move.
                delta = blocks - row["blocks"]
                if delta:
                    conn.execute(
                        "UPDATE enlistments SET blocks = ? WHERE token = ?",
                        (blocks, token),
                    )
                    conn.execute(
                        "UPDATE countries SET blocks = MAX(0, blocks + ?), "
                        "updated_at = ? WHERE code = ?",
                        (delta, now, row["code"]),
                    )
                return {
                    "code": row["code"],
                    "ordinal": row["ordinal"],
                    "blocks": blocks,
                    "new": False,
                }

            conn.execute(
                "INSERT INTO countries (code, miners, blocks, first_at, updated_at) "
                "VALUES (?, 0, 0, ?, ?) ON CONFLICT(code) DO NOTHING",
                (code, now, now),
            )
            conn.execute(
                "UPDATE countries SET miners = miners + 1, blocks = blocks + ?, "
                "updated_at = ? WHERE code = ?",
                (blocks, now, code),
            )
            # Read back rather than using RETURNING: that needs SQLite 3.35+,
            # and the deploy images may ship older. Still atomic — the
            # surrounding `with conn` holds the write transaction.
            ordinal = conn.execute(
                "SELECT miners FROM countries WHERE code = ?", (code,)
            ).fetchone()["miners"]
            conn.execute(
                "INSERT INTO enlistments (token, code, ordinal, blocks, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (token, code, ordinal, blocks, now),
            )
            return {"code": code, "ordinal": ordinal, "blocks": blocks, "new": True}
    finally:
        conn.close()


def lookup(token: Optional[str]) -> Optional[dict]:
    """Return this miner's existing standing, or None if never enlisted."""
    try:
        token = _clean_token(token)
    except ValueError:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT code, ordinal, blocks FROM enlistments WHERE token = ?",
            (token,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def standings() -> dict:
    """Full ranking, best first, plus totals.

    Ranked by miners then blocks: before mainnet the only honest signal is how
    many people showed up, so that leads.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT code, miners, blocks, first_at FROM countries "
            "WHERE miners > 0 ORDER BY miners DESC, blocks DESC, first_at ASC"
        ).fetchall()
    finally:
        conn.close()

    table = [
        {
            "rank": i + 1,
            "code": r["code"],
            "miners": r["miners"],
            "blocks": r["blocks"],
        }
        for i, r in enumerate(rows)
    ]
    return {
        "countries": table,
        "total_countries": len(table),
        "total_miners": sum(r["miners"] for r in table),
        "total_blocks": sum(r["blocks"] for r in table),
    }
