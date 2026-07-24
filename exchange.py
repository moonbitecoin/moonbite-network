"""MoonBite internal exchange — non-custodial order book.

This module stores *order intents* only: a public offer to trade MBITE against a
quote asset (LTC, BTC, or a USD stablecoin). It NEVER holds coins, private keys,
or user balances. Settlement happens off this server via an atomic (HTLC) swap
directly between the two parties' wallets — see settle_hint() for the hand-off.

Because the server only matchmakes and never custodies funds, it stays a piece of
software rather than a money transmitter. Keep it that way: do not add deposit,
withdrawal, or fiat handling here.
"""

from __future__ import annotations

import hmac
import secrets
import sqlite3
import threading
import time
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

# Pairs we support first. MBITE is always the base; the quote is what you pay/receive.
# "ease" is an honest note surfaced in the UI: LTC/BTC swap natively with MoonBite
# (shared Bitcoin script family); the stablecoin needs a smart-contract HTLC leg.
SUPPORTED_PAIRS = {
    "MBITE/LTC": {"quote": "LTC", "ease": "native", "quote_decimals": 8},
    "MBITE/BTC": {"quote": "BTC", "ease": "native", "quote_decimals": 8},
    "MBITE/USDT": {"quote": "USDT", "ease": "contract", "quote_decimals": 6},
}

SIDES = ("buy", "sell")  # buy = want MBITE (pay quote); sell = give MBITE (want quote)

# Basic anti-abuse: cap simultaneously-open orders per MBITE address.
MAX_OPEN_ORDERS_PER_ADDRESS = 20

_DB_PATH = Path(__file__).with_name("exchange.db")
_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id            TEXT PRIMARY KEY,
                side          TEXT NOT NULL,
                pair          TEXT NOT NULL,
                price         TEXT NOT NULL,   -- quote per 1 MBITE, decimal string
                amount        TEXT NOT NULL,   -- MBITE amount, decimal string
                mbite_address TEXT NOT NULL,   -- maker's MBITE receive/send address
                quote_address TEXT NOT NULL,   -- maker's address on the quote chain
                status        TEXT NOT NULL DEFAULT 'open',
                created_at    INTEGER NOT NULL,
                cancel_token  TEXT             -- secret; returned once to the maker
            )
            """
        )
        # Migration for databases created before cancel_token existed.
        cols = {r["name"] for r in _conn.execute("PRAGMA table_info(orders)")}
        if "cancel_token" not in cols:
            _conn.execute("ALTER TABLE orders ADD COLUMN cancel_token TEXT")
        # Migration: record the crossing counter-order when a match is found.
        if "matched_with" not in cols:
            _conn.execute("ALTER TABLE orders ADD COLUMN matched_with TEXT")
        _conn.commit()
    return _conn


def _public(order: Optional[dict]) -> Optional[dict]:
    """Strip the secret cancel_token from any order shown on a read path."""
    if order is not None:
        order.pop("cancel_token", None)
    return order


def _pos_decimal(value, field: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{field} must be a number")
    if d <= 0:
        raise ValueError(f"{field} must be greater than zero")
    if d != d.quantize(Decimal(1)) and len(d.as_tuple().digits) > 20:
        raise ValueError(f"{field} has too many digits")
    return d


def _clean_address(value, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is required")
    v = value.strip()
    # Deliberately loose: we never spend from these, we only display them so the
    # counterparty knows where to send. Reject only clearly-bogus input.
    if not (6 <= len(v) <= 120) or any(c.isspace() for c in v):
        raise ValueError(f"{field} does not look like a valid address")
    return v


def create_order(
    side: str,
    pair: str,
    price,
    amount,
    mbite_address: str,
    quote_address: str,
) -> dict:
    """Validate and store a public order intent. Returns the stored order."""
    if side not in SIDES:
        raise ValueError("side must be 'buy' or 'sell'")
    if pair not in SUPPORTED_PAIRS:
        raise ValueError(f"unsupported pair: {pair}")
    price_d = _pos_decimal(price, "price")
    amount_d = _pos_decimal(amount, "amount")
    mbite = _clean_address(mbite_address, "MBITE address")
    quote = _clean_address(quote_address, f"{SUPPORTED_PAIRS[pair]['quote']} address")

    with _lock:
        conn = _connect()
        open_count = conn.execute(
            "SELECT COUNT(*) AS n FROM orders WHERE mbite_address = ? AND status = 'open'",
            (mbite,),
        ).fetchone()["n"]
        if open_count >= MAX_OPEN_ORDERS_PER_ADDRESS:
            raise ValueError(
                f"too many open orders for this address (max {MAX_OPEN_ORDERS_PER_ADDRESS})"
            )
        order_id = uuid.uuid4().hex
        cancel_token = secrets.token_urlsafe(24)
        conn.execute(
            """INSERT INTO orders
               (id, side, pair, price, amount, mbite_address, quote_address,
                status, created_at, cancel_token)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
            (
                order_id,
                side,
                pair,
                format(price_d, "f"),
                format(amount_d, "f"),
                mbite,
                quote,
                int(time.time()),
                cancel_token,
            ),
        )
        conn.commit()
    # A newly-posted order may cross an existing resting order. If it does, flag
    # both as 'matched' so the two makers can settle off-server. This is pure
    # matchmaking: no funds are held or moved — settlement is a manual HTLC swap.
    match = _try_match(order_id)

    # Return the token ONCE, only to the maker who created the order. It is the
    # secret proof-of-ownership required to cancel; it is never shown again.
    order = get_order(order_id)
    order["cancel_token"] = cancel_token
    if match is not None:
        order["matched_with"] = match
    return order


def _try_match(order_id: str) -> Optional[str]:
    """If `order_id` crosses a resting opposite order, mark both 'matched'.

    A buy (bid) crosses a sell (ask) when the bid price >= the ask price. We pick
    the best price for the incoming taker (lowest ask for a buyer / highest bid
    for a seller), breaking ties by oldest resting order (price-time priority).
    Returns the counter-order id if matched, else None. Never routes funds.
    """
    with _lock:
        conn = _connect()
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row is None or row["status"] != "open":
            return None
        taker = dict(row)
        taker_price = Decimal(taker["price"])
        if taker["side"] == "buy":
            # Want the cheapest ask we can afford (ask price <= our bid).
            candidates = conn.execute(
                """SELECT * FROM orders
                   WHERE pair = ? AND side = 'sell' AND status = 'open'
                     AND id != ? AND mbite_address != ?
                   ORDER BY CAST(price AS REAL) ASC, created_at ASC""",
                (taker["pair"], order_id, taker["mbite_address"]),
            ).fetchall()
            counter = next(
                (c for c in candidates if Decimal(c["price"]) <= taker_price), None
            )
        else:
            # Selling: want the highest bid at or above our ask.
            candidates = conn.execute(
                """SELECT * FROM orders
                   WHERE pair = ? AND side = 'buy' AND status = 'open'
                     AND id != ? AND mbite_address != ?
                   ORDER BY CAST(price AS REAL) DESC, created_at ASC""",
                (taker["pair"], order_id, taker["mbite_address"]),
            ).fetchall()
            counter = next(
                (c for c in candidates if Decimal(c["price"]) >= taker_price), None
            )
        if counter is None:
            return None
        conn.execute(
            "UPDATE orders SET status = 'matched', matched_with = ? WHERE id = ?",
            (counter["id"], order_id),
        )
        conn.execute(
            "UPDATE orders SET status = 'matched', matched_with = ? WHERE id = ?",
            (order_id, counter["id"]),
        )
        conn.commit()
        return counter["id"]


def list_orders(pair: Optional[str] = None, status: str = "open") -> dict:
    """Return the order book for a pair, split into bids (buys) and asks (sells)."""
    with _lock:
        conn = _connect()
        if pair is not None and pair not in SUPPORTED_PAIRS:
            raise ValueError(f"unsupported pair: {pair}")
        params = [status]
        query = "SELECT * FROM orders WHERE status = ?"
        if pair is not None:
            query += " AND pair = ?"
            params.append(pair)
        rows = [_public(dict(r)) for r in conn.execute(query, params).fetchall()]

    bids = sorted(
        (r for r in rows if r["side"] == "buy"),
        key=lambda r: Decimal(r["price"]),
        reverse=True,  # highest buy price first
    )
    asks = sorted(
        (r for r in rows if r["side"] == "sell"),
        key=lambda r: Decimal(r["price"]),  # lowest sell price first
    )
    last_price = _last_trade_price(pair) if pair else None
    return {"pair": pair, "bids": bids, "asks": asks, "last_price": last_price}


def get_order(order_id: str) -> Optional[dict]:
    with _lock:
        conn = _connect()
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return _public(dict(row)) if row else None


def cancel_order(order_id: str, cancel_token: str) -> dict:
    """Cancel an open order.

    Authorization is the secret `cancel_token` minted at creation and returned
    only to the maker — NOT the MBITE address, which is public in the order book
    and so cannot serve as a secret.
    """
    with _lock:
        conn = _connect()
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            raise ValueError("order not found")
        if row["status"] != "open":
            raise ValueError(f"order is already {row['status']}")
        stored = row["cancel_token"] or ""
        provided = (cancel_token or "").strip()
        if not stored or not hmac.compare_digest(stored, provided):
            raise ValueError("invalid or missing cancel token")
        conn.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
        conn.commit()
    return get_order(order_id)


def _last_trade_price(pair: str) -> Optional[str]:
    """Most recent settled trade price for a pair — the internal price discovery."""
    conn = _connect()
    row = conn.execute(
        "SELECT price FROM orders WHERE pair = ? AND status = 'settled' "
        "ORDER BY created_at DESC LIMIT 1",
        (pair,),
    ).fetchone()
    return row["price"] if row else None


def settle_hint(order_id: str) -> dict:
    """Return the atomic-swap hand-off instructions for a matched order.

    NOTE (Phase 2): the actual HTLC atomic-swap execution engine is not built yet.
    This returns the addresses both parties need so they can perform the swap with
    an external atomic-swap tool. Wiring an automated, trustless HTLC coordinator is
    the next milestone; until then settlement is a guided/manual step. We must not
    pretend the swap is automatic, and we must never route funds through the server.
    """
    order = get_order(order_id)
    if order is None:
        raise ValueError("order not found")
    quote = SUPPORTED_PAIRS[order["pair"]]["quote"]
    counterparty = None
    if order.get("matched_with"):
        counter = get_order(order["matched_with"])
        if counter is not None:
            counterparty = {
                "order_id": counter["id"],
                "side": counter["side"],
                "price": counter["price"],
                "amount": counter["amount"],
                "mbite_address": counter["mbite_address"],
                "quote_address": counter["quote_address"],
            }
    return {
        "order": order,
        "swap": {
            "mechanism": "HTLC atomic swap (non-custodial)",
            "base_asset": "MBITE",
            "quote_asset": quote,
            "maker_mbite_address": order["mbite_address"],
            "maker_quote_address": order["quote_address"],
            "counterparty": counterparty,
            "status": "manual",
            "note": (
                "Automated HTLC swap coordination is not yet implemented (Phase 2). "
                "Perform the swap directly wallet-to-wallet using an atomic-swap tool. "
                "The server never holds either side's coins."
            ),
        },
    }
