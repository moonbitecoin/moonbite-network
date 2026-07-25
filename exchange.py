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

from swap_verifier import VERIFIER_STATES

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

# --- Phase 2a: atomic-swap settlement coordination ------------------------- #
# The server COORDINATES the HTLC hand-off and (from Phase 2b) VERIFIES it
# on-chain; it never custodies coins or keys. Phase 2a records only the public
# swap parameters and the parties' self-reported funding txids and advances a
# state machine. On-chain verification, preimage extraction, the 'redeemed'/
# 'settled' transitions, and price discovery all arrive in Phase 2b/2c — until
# then a swap can progress no further than 'both_locked' and last_price stays
# null (no trade is considered settled without independent on-chain proof).
SWAP_STATES = (
    "swap_init",     # HTLC parameters registered; nothing funded yet
    "base_funded",   # MBITE-leg HTLC funding txid reported (unverified)
    "quote_funded",  # quote-leg HTLC funding txid reported (unverified)
    "both_locked",   # both legs' funding txids reported (awaiting 2b verify)
)

# Phase 2b bolts the on-chain-verified tail onto the machine. These transitions
# are driven ONLY by swap_verifier reading confirmed chain data — never by a
# caller's report. See swap_verifier.VERIFIER_STATES for the definitions.
ALL_SWAP_STATES = SWAP_STATES + VERIFIER_STATES

# Columns swap_verifier is permitted to write back (whitelist: the status/txids/
# preimage/confs/assurance it independently derives from chain data). Guards the
# dynamic UPDATE in apply_swap_verification against arbitrary column writes.
_VERIFIER_WRITABLE = frozenset(
    {
        "status", "preimage", "base_redeem_txid", "quote_redeem_txid",
        "base_confs", "quote_confs", "settled_at", "quote_assurance",
    }
)

# Swaps the verifier still needs to watch (everything before a terminal state).
_VERIFIABLE_STATES = ("both_locked", "quote_redeemed", "base_redeemed")

# Safety invariant: the party who redeems second must hold the longer refund
# window, so the base (MBITE) timelock must exceed the quote timelock by at
# least this margin. Locktimes are unix timestamps (seconds).
MIN_TIMELOCK_GAP_SECONDS = 6 * 60 * 60  # 6 hours

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
        # Phase 2a: atomic-swap settlement coordination. One row per matched
        # order pair. Holds only PUBLIC swap parameters — no keys, no coins. The
        # redeem/preimage/confs/settled_at columns are populated later by the
        # on-chain verifier (Phase 2b/2c); in 2a they stay null/zero.
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS swaps (
                swap_id            TEXT PRIMARY KEY,
                buy_order_id       TEXT NOT NULL,
                sell_order_id      TEXT NOT NULL,
                pair               TEXT NOT NULL,
                price              TEXT NOT NULL,   -- agreed execution (maker) price
                amount             TEXT NOT NULL,   -- swappable MBITE = min(buy, sell)
                hashlock           TEXT NOT NULL UNIQUE,  -- SHA256(preimage); anti-replay
                base_recipient_pk  TEXT NOT NULL,   -- who claims the MBITE leg (hex)
                base_refund_pk     TEXT NOT NULL,   -- who refunds the MBITE leg (hex)
                quote_recipient_pk TEXT NOT NULL,   -- who claims the quote leg (hex)
                quote_refund_pk    TEXT NOT NULL,   -- who refunds the quote leg (hex)
                base_locktime      INTEGER NOT NULL,-- unix seconds; > quote_locktime
                quote_locktime     INTEGER NOT NULL,-- unix seconds
                base_htlc_txid     TEXT,            -- reported funding tx, MBITE leg
                quote_htlc_txid    TEXT,            -- reported funding tx, quote leg
                base_redeem_txid   TEXT,            -- filled by verifier (2b)
                quote_redeem_txid  TEXT,            -- filled by verifier (2b)
                preimage           TEXT,            -- extracted once public on-chain (2b)
                base_confs         INTEGER NOT NULL DEFAULT 0,
                quote_confs        INTEGER NOT NULL DEFAULT 0,
                status             TEXT NOT NULL DEFAULT 'swap_init',
                created_at         INTEGER NOT NULL,
                settled_at         INTEGER          -- set only when fully verified (2c)
            )
            """
        )
        # Phase 2b migration: records HOW a settlement's quote leg was verified —
        # 'node' (full-node read, fully trustless) vs 'explorer' (N-of-M explorer
        # agreement, lower assurance). Surfaced so the UI never overstates trust.
        swap_cols = {r["name"] for r in _conn.execute("PRAGMA table_info(swaps)")}
        if "quote_assurance" not in swap_cols:
            _conn.execute("ALTER TABLE swaps ADD COLUMN quote_assurance TEXT")
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
    if not d.is_finite():  # reject NaN / Infinity / -Infinity before any comparison
        raise ValueError(f"{field} must be a finite number")
    if d <= 0:
        raise ValueError(f"{field} must be greater than zero")
    # Bound magnitude/precision without quantize() (which throws on huge
    # exponents like 1e400): adjusted() is the power of the leading digit,
    # as_tuple().exponent < 0 counts fractional places.
    if d.adjusted() > 20 or d.as_tuple().exponent < -20:
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


# --------------------------------------------------------------------------- #
# Phase 2a: atomic-swap settlement coordination
#
# These functions record the HTLC hand-off for a matched order pair and track
# self-reported funding, advancing a small state machine. They perform NO
# on-chain verification and move NO funds — that is Phase 2b/2c. A swap cannot
# progress past 'both_locked' here, and nothing is ever marked 'settled', so
# price discovery (last_price) is untouched. The parameters recorded are all
# public (hashlock, pubkeys, timelocks, txids); no secret or key is accepted.
# --------------------------------------------------------------------------- #


def _hexish(value, field: str, min_len: int, max_len: int) -> str:
    """Validate a lowercase hex string (optional 0x prefix) of a bounded length."""
    if not isinstance(value, str):
        raise ValueError(f"{field} is required")
    v = value.strip().lower()
    if v.startswith("0x"):
        v = v[2:]
    if not (min_len <= len(v) <= max_len) or any(c not in "0123456789abcdef" for c in v):
        raise ValueError(f"{field} must be hex of {min_len}-{max_len} chars")
    return v


def _authorize_order(conn, order_id: str, cancel_token) -> dict:
    """Return the order row iff the cancel_token proves ownership, else raise.

    Reuses the per-order secret minted at creation: a caller proves they own one
    side of the matched pair by presenting that order's cancel_token. The address
    is public and so cannot serve as the secret.
    """
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        raise ValueError("order not found")
    stored = row["cancel_token"] or ""
    provided = (cancel_token or "").strip()
    if not stored or not hmac.compare_digest(stored, provided):
        raise ValueError("invalid or missing cancel token")
    return dict(row)


def get_swap(order_id: str) -> Optional[dict]:
    """Return the swap coordinating settlement for a matched order, or None.

    A read path: no secret to strip (every stored field is public). Callable by
    anyone, since the swap parameters are the public hand-off both parties need.
    """
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT * FROM swaps WHERE buy_order_id = ? OR sell_order_id = ?",
            (order_id, order_id),
        ).fetchone()
    return dict(row) if row else None


def init_swap(
    order_id: str,
    cancel_token,
    hashlock,
    base_recipient_pk,
    base_refund_pk,
    quote_recipient_pk,
    quote_refund_pk,
    base_locktime,
    quote_locktime,
) -> dict:
    """Register the HTLC hand-off for a matched order pair (Phase 2a).

    Records only PUBLIC swap parameters so both legs can later be verified
    on-chain (Phase 2b). Never accepts a private key or preimage; never moves
    funds. Auth: the caller proves they own one side via its cancel_token.
    """
    with _lock:
        conn = _connect()
        order = _authorize_order(conn, order_id, cancel_token)
        if order["status"] != "matched":
            raise ValueError(f"order is {order['status']}, not matched")
        counter_id = order.get("matched_with")
        counter_row = conn.execute(
            "SELECT * FROM orders WHERE id = ?", (counter_id,)
        ).fetchone()
        if counter_row is None:
            raise ValueError("counterparty order not found")
        counter = dict(counter_row)

        # At most one swap per order pair (either party may have started it).
        existing = conn.execute(
            "SELECT 1 FROM swaps WHERE buy_order_id IN (?, ?) OR sell_order_id IN (?, ?)",
            (order_id, counter_id, order_id, counter_id),
        ).fetchone()
        if existing is not None:
            raise ValueError("a swap already exists for this order pair")

        # Hashlock: SHA256 digest (32 bytes = 64 hex). Must be globally fresh.
        h = _hexish(hashlock, "hashlock", 64, 64)
        if conn.execute("SELECT 1 FROM swaps WHERE hashlock = ?", (h,)).fetchone():
            raise ValueError("hashlock already used; use a fresh secret")

        # Pubkeys / pubkey-hashes: hex, 20-byte hash (40) up to uncompressed (130).
        b_recip = _hexish(base_recipient_pk, "base_recipient_pubkey", 40, 130)
        b_refund = _hexish(base_refund_pk, "base_refund_pubkey", 40, 130)
        q_recip = _hexish(quote_recipient_pk, "quote_recipient_pubkey", 40, 130)
        q_refund = _hexish(quote_refund_pk, "quote_refund_pubkey", 40, 130)

        try:
            b_lock = int(base_locktime)
            q_lock = int(quote_locktime)
        except (TypeError, ValueError):
            raise ValueError("locktimes must be integers (unix seconds)")
        if b_lock <= 0 or q_lock <= 0:
            raise ValueError("locktimes must be positive")
        if q_lock >= b_lock:
            raise ValueError("quote_locktime must be earlier than base_locktime")
        if b_lock - q_lock < MIN_TIMELOCK_GAP_SECONDS:
            raise ValueError(
                "timelock gap too small; base must exceed quote by "
                f">= {MIN_TIMELOCK_GAP_SECONDS} seconds"
            )

        # Resolve buy/sell sides and the agreed execution terms. Trades execute at
        # the resting (maker = earlier-created) order's price; the swappable size
        # is the smaller of the two orders (no partial-fill accounting here).
        if order["side"] == "buy":
            buy, sell = order, counter
        else:
            buy, sell = counter, order
        # The maker is the resting order that was crossed. created_at is only
        # second-resolution, so same-second matches tie; break the tie by rowid
        # (insertion order), which the resting order always wins.
        maker_id = conn.execute(
            "SELECT id FROM orders WHERE id IN (?, ?) "
            "ORDER BY created_at ASC, rowid ASC LIMIT 1",
            (order["id"], counter["id"]),
        ).fetchone()["id"]
        price = order["price"] if maker_id == order["id"] else counter["price"]
        amount = min(Decimal(buy["amount"]), Decimal(sell["amount"]))

        swap_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO swaps
               (swap_id, buy_order_id, sell_order_id, pair, price, amount,
                hashlock, base_recipient_pk, base_refund_pk,
                quote_recipient_pk, quote_refund_pk, base_locktime, quote_locktime,
                status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'swap_init',?)""",
            (
                swap_id, buy["id"], sell["id"], order["pair"], price,
                format(amount, "f"), h, b_recip, b_refund, q_recip, q_refund,
                b_lock, q_lock, int(time.time()),
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM swaps WHERE swap_id = ?", (swap_id,)
        ).fetchone()
    return dict(row)


def report_funding(order_id: str, cancel_token, leg: str, txid) -> dict:
    """Record a self-reported HTLC funding txid for one leg (Phase 2a).

    Stores the report and advances the state machine to base_funded / quote_funded
    / both_locked. It does NOT verify the tx on-chain — that is Phase 2b — and it
    never treats a report as settlement. Auth: the order's cancel_token.
    """
    if leg not in ("base", "quote"):
        raise ValueError("leg must be 'base' or 'quote'")
    tx = _hexish(txid, "txid", 64, 64)
    with _lock:
        conn = _connect()
        _authorize_order(conn, order_id, cancel_token)
        row = conn.execute(
            "SELECT * FROM swaps WHERE buy_order_id = ? OR sell_order_id = ?",
            (order_id, order_id),
        ).fetchone()
        if row is None:
            raise ValueError("no swap for this order; call swap/init first")
        if row["status"] not in ("swap_init", "base_funded", "quote_funded"):
            raise ValueError(f"swap is {row['status']}; cannot report funding")
        # `col` is chosen from string literals, never from user input — safe.
        col = "base_htlc_txid" if leg == "base" else "quote_htlc_txid"
        conn.execute(
            f"UPDATE swaps SET {col} = ? WHERE swap_id = ?", (tx, row["swap_id"])
        )
        cur = conn.execute(
            "SELECT base_htlc_txid, quote_htlc_txid FROM swaps WHERE swap_id = ?",
            (row["swap_id"],),
        ).fetchone()
        if cur["base_htlc_txid"] and cur["quote_htlc_txid"]:
            new_status = "both_locked"
        elif cur["base_htlc_txid"]:
            new_status = "base_funded"
        else:
            new_status = "quote_funded"
        conn.execute(
            "UPDATE swaps SET status = ? WHERE swap_id = ?",
            (new_status, row["swap_id"]),
        )
        conn.commit()
        final = conn.execute(
            "SELECT * FROM swaps WHERE swap_id = ?", (row["swap_id"],)
        ).fetchone()
    return dict(final)


# --------------------------------------------------------------------------- #
# Phase 2b: on-chain verification hand-off.
#
# The verifier (swap_verifier.py) READS the chains and independently decides how
# far a swap has genuinely progressed. exchange.py stays the sole DB owner: it
# hands the verifier the swaps that still need watching and applies the verified
# result. Only a swap the verifier drives to 'settled' marks its two orders
# 'settled' — the single event that lets _last_trade_price (and thus last_price)
# reflect a real, on-chain-proven trade. No caller can reach these transitions.
# --------------------------------------------------------------------------- #


def list_swaps_for_verification() -> list:
    """Return swaps still awaiting on-chain progress (non-terminal, funded)."""
    with _lock:
        conn = _connect()
        placeholders = ",".join("?" for _ in _VERIFIABLE_STATES)
        rows = conn.execute(
            f"SELECT * FROM swaps WHERE status IN ({placeholders})",
            _VERIFIABLE_STATES,
        ).fetchall()
    return [dict(r) for r in rows]


def apply_swap_verification(swap_id: str, updates: dict) -> Optional[dict]:
    """Persist the verifier's independently-derived findings for one swap.

    Only whitelisted, verifier-owned columns may be written. If the swap reaches
    'settled', both underlying orders are marked 'settled' in the SAME
    transaction so price discovery and settlement flip atomically. A no-op
    ``updates`` leaves the row untouched.
    """
    clean = {k: v for k, v in (updates or {}).items() if k in _VERIFIER_WRITABLE}
    if not clean:
        return get_swap_by_id(swap_id)
    if clean.get("status") is not None and clean["status"] not in ALL_SWAP_STATES:
        raise ValueError(f"illegal swap status: {clean['status']}")

    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT * FROM swaps WHERE swap_id = ?", (swap_id,)
        ).fetchone()
        if row is None:
            raise ValueError("no such swap")

        assignments = ", ".join(f"{col} = ?" for col in clean)  # cols are whitelisted
        conn.execute(
            f"UPDATE swaps SET {assignments} WHERE swap_id = ?",
            (*clean.values(), swap_id),
        )
        if clean.get("status") == "settled":
            # Atomically record the executed trade on both orders so the pair's
            # last_price finally reflects an on-chain-proven fill.
            conn.execute(
                "UPDATE orders SET status = 'settled' WHERE id IN (?, ?)",
                (row["buy_order_id"], row["sell_order_id"]),
            )
        conn.commit()
        final = conn.execute(
            "SELECT * FROM swaps WHERE swap_id = ?", (swap_id,)
        ).fetchone()
    return dict(final)


def get_swap_by_id(swap_id: str) -> Optional[dict]:
    """Fetch a swap by its primary key (verifier/introspection helper)."""
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT * FROM swaps WHERE swap_id = ?", (swap_id,)
        ).fetchone()
    return dict(row) if row else None
