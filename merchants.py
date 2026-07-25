"""MoonBite merchant adoption layer — non-custodial "Accept MBITE" rails.

This module stores a merchant *directory* (businesses that voluntarily accept
MBITE) and the *invoices* they raise. It NEVER holds coins, keys, or balances.

A payment is detected the way a watch-only wallet does it: we look at the chain
for coins that landed on the merchant's own address. The customer pays directly,
wallet-to-wallet; the server only *observes* that it happened and marks the
invoice paid. Keep it that way — do not add custody, escrow, or fiat handling.

Payment verification is deliberately injected (`received_lookup`) so this module
stays decoupled from any particular node. In this demo the web app wires it to
the local educational node; in production it points at the MoonBite node.
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
import time
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Optional

# Categories a merchant can pick. Kept small and honest — no fake taxonomy.
CATEGORIES = ("goods", "services", "food", "digital", "donation", "other")

# App unit: base units per coin. The educational chain uses 100; the production
# Litecoin-fork node uses 1e8 (sats). Configurable so a production deployment can
# match its chain's precision (set MOONBITE_UNITS_PER_COIN=100000000) while the
# in-process demo keeps 100. The invoiced amount and the injected received_lookup
# MUST share this basis — that pairing is wired in web_app.py.
UNITS_PER_COIN = int(os.environ.get("MOONBITE_UNITS_PER_COIN", "100"))

# An invoice is payable for this long, then it expires (seconds).
DEFAULT_INVOICE_TTL = 60 * 60  # 1 hour

# Anti-spam: cap directory size churn per address.
MAX_MERCHANTS_PER_ADDRESS = 3

_URL_RE = re.compile(r"^https?://[^\s]{3,200}$", re.IGNORECASE)

_DB_PATH = Path(__file__).with_name("merchants.db")
_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None

# A callable(address:str) -> int (received base units, monotonic over chain life).
ReceivedLookup = Callable[[str], int]


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS merchants (
                id            TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                url           TEXT NOT NULL DEFAULT '',
                category      TEXT NOT NULL,
                mbite_address TEXT NOT NULL,
                blurb         TEXT NOT NULL DEFAULT '',
                created_at    INTEGER NOT NULL
            )
            """
        )
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id             TEXT PRIMARY KEY,
                merchant_id    TEXT,
                address        TEXT NOT NULL,
                amount         TEXT NOT NULL,   -- MBITE, decimal string
                amount_units   INTEGER NOT NULL,-- base units for on-chain check
                memo           TEXT NOT NULL DEFAULT '',
                status         TEXT NOT NULL DEFAULT 'pending',
                baseline_units INTEGER NOT NULL,-- received at address when raised
                created_at     INTEGER NOT NULL,
                expires_at     INTEGER NOT NULL,
                paid_at        INTEGER
            )
            """
        )
        _conn.commit()
    return _conn


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #
def _clean_text(value, field: str, lo: int, hi: int, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    v = value.strip()
    if required and len(v) < lo:
        raise ValueError(f"{field} must be at least {lo} characters")
    if len(v) > hi:
        raise ValueError(f"{field} must be at most {hi} characters")
    return v


def _clean_address(value, validate: Optional[Callable[[str], bool]]) -> str:
    if not isinstance(value, str):
        raise ValueError("MBITE address is required")
    v = value.strip()
    if not (6 <= len(v) <= 120) or any(c.isspace() for c in v):
        raise ValueError("MBITE address does not look valid")
    # When the caller supplies an address validator (the app's own format), use
    # it so invoices raised against this address can actually be auto-verified.
    if validate is not None and not validate(v):
        raise ValueError("MBITE address failed checksum validation")
    return v


def _pos_amount(value) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("amount must be a number")
    if d <= 0:
        raise ValueError("amount must be greater than zero")
    return d


def _amount_units(d: Decimal) -> int:
    # Convert a MBITE amount to the chain's integer base units.
    return int((d * UNITS_PER_COIN).to_integral_value())


# --------------------------------------------------------------------------- #
# Merchant directory
# --------------------------------------------------------------------------- #
def add_merchant(
    name,
    category,
    mbite_address,
    url="",
    blurb="",
    address_validator: Optional[Callable[[str], bool]] = None,
) -> dict:
    """Register a merchant that voluntarily accepts MBITE. Returns the record."""
    name_c = _clean_text(name, "name", 2, 60)
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of: {', '.join(CATEGORIES)}")
    addr = _clean_address(mbite_address, address_validator)
    url_c = _clean_text(url, "url", 0, 200, required=False)
    if url_c and not _URL_RE.match(url_c):
        raise ValueError("url must start with http:// or https://")
    blurb_c = _clean_text(blurb, "blurb", 0, 160, required=False)

    with _lock:
        conn = _connect()
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM merchants WHERE mbite_address = ?", (addr,)
        ).fetchone()["n"]
        if n >= MAX_MERCHANTS_PER_ADDRESS:
            raise ValueError("too many listings for this address")
        mid = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO merchants (id, name, url, category, mbite_address, blurb, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (mid, name_c, url_c, category, addr, blurb_c, int(time.time())),
        )
        conn.commit()
    return get_merchant(mid)


def get_merchant(merchant_id: str) -> Optional[dict]:
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT * FROM merchants WHERE id = ?", (merchant_id,)
        ).fetchone()
    return dict(row) if row else None


def list_merchants(category: Optional[str] = None) -> list[dict]:
    with _lock:
        conn = _connect()
        if category is not None and category not in CATEGORIES:
            raise ValueError("unknown category")
        if category:
            rows = conn.execute(
                "SELECT * FROM merchants WHERE category = ? ORDER BY created_at DESC",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM merchants ORDER BY created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Invoices (non-custodial payment requests)
# --------------------------------------------------------------------------- #
def build_pay_uri(address: str, amount: Decimal, memo: str = "") -> str:
    """A BIP21-style MoonBite payment URI a wallet can parse into a prefilled send."""
    uri = f"moonbite:{address}?amount={format(amount, 'f')}"
    if memo:
        # keep it URL-safe-ish; wallets treat label as display text
        label = re.sub(r"[^\w \-.,]", "", memo)[:60].replace(" ", "%20")
        if label:
            uri += f"&label={label}"
    return uri


def create_invoice(
    address,
    amount,
    received_lookup: ReceivedLookup,
    merchant_id: Optional[str] = None,
    memo: str = "",
    ttl: int = DEFAULT_INVOICE_TTL,
    address_validator: Optional[Callable[[str], bool]] = None,
) -> dict:
    """Raise a payment request against a merchant address. Non-custodial.

    We snapshot how much the address has *already* received so that only a NEW
    inbound payment of at least `amount` marks this specific invoice paid.
    """
    addr = _clean_address(address, address_validator)
    amt = _pos_amount(amount)
    memo_c = _clean_text(memo, "memo", 0, 140, required=False)
    baseline = int(received_lookup(addr))

    now = int(time.time())
    inv_id = uuid.uuid4().hex
    with _lock:
        conn = _connect()
        conn.execute(
            """INSERT INTO invoices
               (id, merchant_id, address, amount, amount_units, memo, status,
                baseline_units, created_at, expires_at, paid_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, NULL)""",
            (
                inv_id,
                merchant_id,
                addr,
                format(amt, "f"),
                _amount_units(amt),
                memo_c,
                baseline,
                now,
                now + int(ttl),
            ),
        )
        conn.commit()
    return invoice_status(inv_id, received_lookup)


def _settle_invoice(inv: dict, received_now: int, now: int) -> dict:
    """Given a fresh on-chain reading, transition one pending invoice and persist.

    Pure observation: a NEW inbound total of at least the invoiced amount (over
    the baseline snapshotted at creation) flips 'pending' -> 'paid'; a lapsed TTL
    flips it -> 'expired'. Terminal invoices are never re-touched. Returns the
    invoice enriched with the live payment view.
    """
    paid_units = max(0, received_now - inv["baseline_units"])
    new_status = inv["status"]
    paid_at = inv["paid_at"]
    if inv["status"] == "pending":
        if paid_units >= inv["amount_units"]:
            new_status = "paid"
            paid_at = now
        elif now > inv["expires_at"]:
            new_status = "expired"

    if new_status != inv["status"]:
        with _lock:
            conn = _connect()
            conn.execute(
                "UPDATE invoices SET status = ?, paid_at = ? WHERE id = ?",
                (new_status, paid_at, inv["id"]),
            )
            conn.commit()
        inv["status"] = new_status
        inv["paid_at"] = paid_at

    amt = Decimal(inv["amount"])
    return {
        **inv,
        "paid_units": paid_units,
        "received_now": received_now,
        "seconds_left": max(0, inv["expires_at"] - now),
        "pay_uri": build_pay_uri(inv["address"], amt, inv["memo"]),
    }


def invoice_status(invoice_id: str, received_lookup: ReceivedLookup) -> dict:
    """Return an invoice with a *fresh* payment check against the chain."""
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT * FROM invoices WHERE id = ?", (invoice_id,)
        ).fetchone()
        if row is None:
            raise ValueError("invoice not found")
        inv = dict(row)

    return _settle_invoice(inv, int(received_lookup(inv["address"])), int(time.time()))


def list_invoices(
    received_lookup: ReceivedLookup, merchant_id: Optional[str] = None
) -> list[dict]:
    """Return a merchant's invoices, each with a fresh chain-payment check.

    A shop dashboard's read view: newest first, optionally scoped to one
    merchant. Every returned invoice is passed through the same observation as
    invoice_status, so simply listing also advances any that have been paid or
    have expired since last seen.
    """
    with _lock:
        conn = _connect()
        if merchant_id:
            rows = conn.execute(
                "SELECT * FROM invoices WHERE merchant_id = ? ORDER BY created_at DESC",
                (merchant_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM invoices ORDER BY created_at DESC"
            ).fetchall()
    now = int(time.time())
    # Cache lookups per address so a shop with many invoices hits the chain once
    # per distinct address, not once per invoice.
    seen: dict = {}
    out = []
    for r in rows:
        inv = dict(r)
        addr = inv["address"]
        if addr not in seen:
            seen[addr] = int(received_lookup(addr))
        out.append(_settle_invoice(inv, seen[addr], now))
    return out


def poll_pending_invoices(received_lookup: ReceivedLookup) -> dict:
    """Sweep every still-pending invoice once, advancing paid/expired ones.

    The automation behind "auto-mark an invoice paid": a shop (or a timer) calls
    this to reconcile all open invoices against the chain in a single pass,
    instead of polling each invoice by hand. Non-custodial and idempotent — it
    only observes and records; it never moves funds. Returns a small summary.
    """
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT * FROM invoices WHERE status = 'pending'"
        ).fetchall()
    now = int(time.time())
    seen: dict = {}
    paid, expired = [], []
    for r in rows:
        inv = dict(r)
        addr = inv["address"]
        if addr not in seen:
            seen[addr] = int(received_lookup(addr))
        settled = _settle_invoice(inv, seen[addr], now)
        if settled["status"] == "paid":
            paid.append(settled["id"])
        elif settled["status"] == "expired":
            expired.append(settled["id"])
    return {
        "checked": len(rows),
        "paid": paid,
        "expired": expired,
        "addresses_scanned": len(seen),
    }
