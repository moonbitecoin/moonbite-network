"""MoonBite wallet history and address book — transaction tracking and contact management.

Transaction History:
  Tracks send/receive transactions per user session with on-chain details (block height,
  confirmations, status). Every transaction is immutable once recorded; only the memo
  can be edited. User can add private memos to any transaction for record-keeping.

Address Book:
  Stores labeled contact addresses per user session. Each contact tracks usage stats
  (times sent, last sent timestamp) to help the user identify frequent recipients.
  Labels are unique per session to prevent duplicate contact names.

Both tables are filtered by user_session_id for per-visitor isolation, matching the
forum and merchants pattern. SQLite with WAL mode for concurrent reads across
gunicorn workers.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import time
import uuid
from typing import Optional

_DB_PATH = os.environ.get("MOONBITE_WALLET_HISTORY_DB", "").strip() or "wallet_history.db"


def get_connection() -> sqlite3.Connection:
    """Open a short-lived connection with WAL mode and FK constraints enabled.

    Each request opens and closes its own connection; WAL mode keeps concurrent
    readers from blocking on a writer. `CREATE TABLE IF NOT EXISTS` makes first
    use self-initialising.
    """
    conn = sqlite3.connect(_DB_PATH, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_schema():
    """Initialize transaction, address book, accounts, preferences, and account_addresses tables if they don't exist."""
    conn = get_connection()
    try:
        # Transaction table: tracks all send/receive activity
        conn.execute(
            """CREATE TABLE IF NOT EXISTS transactions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_session_id TEXT NOT NULL,
                account_id      TEXT,
                txid            TEXT NOT NULL,
                direction       TEXT NOT NULL,  -- 'send' or 'receive'
                amount_units    INTEGER NOT NULL,
                fee_units       INTEGER NOT NULL DEFAULT 0,
                from_address    TEXT NOT NULL,
                to_address      TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',  -- pending, confirmed, failed
                block_height    INTEGER,
                confirmations   INTEGER NOT NULL DEFAULT 0,
                timestamp       INTEGER NOT NULL,
                confirmed_at    INTEGER,
                memo            TEXT NOT NULL DEFAULT '',
                created_at      INTEGER NOT NULL,
                updated_at      INTEGER NOT NULL,
                UNIQUE(user_session_id, txid)
            )"""
        )
        # Indexes for fast queries
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_session_time "
            "ON transactions(user_session_id, timestamp DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_session_status "
            "ON transactions(user_session_id, status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_txid "
            "ON transactions(txid)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_account "
            "ON transactions(user_session_id, account_id)"
        )

        # Address book: labeled contacts per user session
        conn.execute(
            """CREATE TABLE IF NOT EXISTS address_book (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_session_id TEXT NOT NULL,
                label           TEXT NOT NULL,
                address         TEXT NOT NULL,
                category        TEXT NOT NULL DEFAULT 'general',
                notes           TEXT NOT NULL DEFAULT '',
                is_favorite     INTEGER NOT NULL DEFAULT 0,
                times_sent      INTEGER NOT NULL DEFAULT 0,
                last_sent       INTEGER,
                created_at      INTEGER NOT NULL,
                updated_at      INTEGER NOT NULL,
                UNIQUE(user_session_id, label)
            )"""
        )
        # Indexes for fast queries
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_address_book_session "
            "ON address_book(user_session_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_address_book_session_category "
            "ON address_book(user_session_id, category)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_address_book_address "
            "ON address_book(address)"
        )

        # Accounts table: multi-account support per user session
        conn.execute(
            """CREATE TABLE IF NOT EXISTS accounts (
                id                  TEXT PRIMARY KEY,
                user_session_id     TEXT NOT NULL,
                name                TEXT NOT NULL,
                display_order       INTEGER NOT NULL DEFAULT 0,
                color               TEXT,
                is_default          INTEGER NOT NULL DEFAULT 0,
                mnemonic_hash       TEXT,
                balance_cache       INTEGER DEFAULT 0,
                is_deleted          INTEGER NOT NULL DEFAULT 0,
                created_at          INTEGER NOT NULL,
                updated_at          INTEGER NOT NULL,
                UNIQUE(user_session_id, name)
            )"""
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_accounts_session "
            "ON accounts(user_session_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_accounts_session_default "
            "ON accounts(user_session_id, is_default)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_accounts_not_deleted "
            "ON accounts(user_session_id, is_deleted)"
        )

        # Account addresses table: addresses derived from account mnemonics
        conn.execute(
            """CREATE TABLE IF NOT EXISTS account_addresses (
                id              TEXT PRIMARY KEY,
                account_id      TEXT NOT NULL,
                address         TEXT NOT NULL UNIQUE,
                derivation_path TEXT,
                pubkey_hash     TEXT,
                is_active       INTEGER NOT NULL DEFAULT 1,
                created_at      INTEGER NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            )"""
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_account_addresses_account "
            "ON account_addresses(account_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_account_addresses_address "
            "ON account_addresses(address)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_account_addresses_active "
            "ON account_addresses(account_id, is_active)"
        )

        # Preferences table: user settings per session
        conn.execute(
            """CREATE TABLE IF NOT EXISTS preferences (
                user_session_id TEXT PRIMARY KEY,
                language TEXT DEFAULT 'en',
                currency TEXT DEFAULT 'USD',
                theme TEXT DEFAULT 'auto',
                time_format TEXT DEFAULT 'relative',
                amount_format TEXT DEFAULT 'full',
                notification_tx INTEGER DEFAULT 1,
                notification_price INTEGER DEFAULT 1,
                auto_lock_mins INTEGER DEFAULT 15,
                decimal_places INTEGER DEFAULT 8,
                hide_zero_balance INTEGER DEFAULT 0,
                sort_accounts TEXT DEFAULT 'created',
                biometric_enabled INTEGER DEFAULT 0,
                biometric_device_name TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_preferences_session "
            "ON preferences(user_session_id)"
        )

        # Authentication state: password hashes, biometric tokens, TOTP secrets
        conn.execute(
            """CREATE TABLE IF NOT EXISTS auth_state (
                user_session_id TEXT PRIMARY KEY,
                password_hash TEXT,
                biometric_enabled INTEGER NOT NULL DEFAULT 0,
                biometric_device_name TEXT,
                biometric_credential_id TEXT,
                biometric_public_key TEXT,
                totp_secret TEXT,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                last_failed_at INTEGER,
                last_login INTEGER,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_auth_state_session "
            "ON auth_state(user_session_id)"
        )

        # Biometric verification log for audit trail and rate limiting
        conn.execute(
            """CREATE TABLE IF NOT EXISTS biometric_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_session_id TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                credential_id TEXT,
                device_name TEXT,
                error_message TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (user_session_id) REFERENCES auth_state(user_session_id) ON DELETE CASCADE
            )"""
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_biometric_audit_session "
            "ON biometric_audit(user_session_id, created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_biometric_audit_action "
            "ON biometric_audit(user_session_id, action, created_at DESC)"
        )

        conn.commit()
        print(f"[wallet_history] Schema initialized in {_DB_PATH}")
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Transaction operations
# --------------------------------------------------------------------------- #

def add_transaction(
    session_id: str,
    txid: str,
    direction: str,
    amount_units: int,
    from_address: str,
    to_address: str,
    fee_units: int = 0,
    status: str = "pending",
    block_height: Optional[int] = None,
    confirmations: int = 0,
    memo: str = "",
    account_id: Optional[str] = None,
) -> dict:
    """Insert or update a transaction record. Returns the stored transaction dict.

    Args:
        session_id: User session identifier for isolation
        txid: Transaction hash (must be unique per session)
        direction: 'send' or 'receive'
        amount_units: Base units transferred
        from_address: Source address
        to_address: Destination address
        fee_units: Network fee in base units
        status: 'pending', 'confirmed', or 'failed'
        block_height: Height at which tx was confirmed (None if pending)
        confirmations: Current confirmation count
        memo: Optional user-supplied note
        account_id: Optional account ID for multi-account tracking

    Returns:
        dict with inserted transaction data
    """
    if direction not in ("send", "receive"):
        raise ValueError("direction must be 'send' or 'receive'")
    if status not in ("pending", "confirmed", "failed"):
        raise ValueError("status must be 'pending', 'confirmed', or 'failed'")

    now = int(time.time())
    confirmed_at = now if status == "confirmed" else None

    with get_connection() as conn:
        # Try to update if exists, else insert
        existing = conn.execute(
            "SELECT id FROM transactions WHERE user_session_id = ? AND txid = ?",
            (session_id, txid),
        ).fetchone()

        if existing:
            # Update existing record
            conn.execute(
                """UPDATE transactions
                   SET status = ?, block_height = ?, confirmations = ?,
                       confirmed_at = ?, updated_at = ?
                   WHERE user_session_id = ? AND txid = ?""",
                (status, block_height, confirmations, confirmed_at, now, session_id, txid),
            )
        else:
            # Insert new record
            conn.execute(
                """INSERT INTO transactions
                   (user_session_id, account_id, txid, direction, amount_units, fee_units,
                    from_address, to_address, status, block_height, confirmations,
                    memo, timestamp, confirmed_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    account_id,
                    txid,
                    direction,
                    amount_units,
                    fee_units,
                    from_address,
                    to_address,
                    status,
                    block_height,
                    confirmations,
                    memo,
                    now,
                    confirmed_at,
                    now,
                    now,
                ),
            )
        conn.commit()

        # Fetch and return the stored record
        row = conn.execute(
            "SELECT * FROM transactions WHERE user_session_id = ? AND txid = ?",
            (session_id, txid),
        ).fetchone()

    return dict(row) if row else {}


def get_transactions(
    session_id: str,
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    sort: str = "desc",
) -> dict:
    """Return a paginated list of transactions for a user session.

    Args:
        session_id: User session identifier
        limit: Max records per page (capped at 100)
        offset: Pagination offset
        status: Filter by status ('pending', 'confirmed', 'failed'), or None for all
        sort: 'asc' or 'desc' (default desc = newest first)

    Returns:
        dict with 'transactions', 'total', 'limit', 'offset'
    """
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    sort_dir = "ASC" if sort == "asc" else "DESC"

    with get_connection() as conn:
        where_clause = "user_session_id = ?"
        params = [session_id]

        if status:
            where_clause += " AND status = ?"
            params.append(status)

        # Total count
        total = conn.execute(
            f"SELECT COUNT(*) AS n FROM transactions WHERE {where_clause}",
            params,
        ).fetchone()["n"]

        # Paginated results
        rows = conn.execute(
            f"SELECT * FROM transactions WHERE {where_clause} "
            f"ORDER BY timestamp {sort_dir}, id {sort_dir} "
            f"LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    return {
        "transactions": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_transaction(session_id: str, txid: str) -> Optional[dict]:
    """Fetch a single transaction by txid.

    Args:
        session_id: User session identifier
        txid: Transaction hash

    Returns:
        Transaction dict, or None if not found
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM transactions WHERE user_session_id = ? AND txid = ?",
            (session_id, txid),
        ).fetchone()
    return dict(row) if row else None


def update_transaction_memo(session_id: str, txid: str, memo: str) -> Optional[dict]:
    """Update only the memo field of a transaction (immutable otherwise).

    Args:
        session_id: User session identifier
        txid: Transaction hash
        memo: New memo text (max 500 chars)

    Returns:
        Updated transaction dict, or None if not found
    """
    memo = str(memo or "").strip()[:500]
    now = int(time.time())

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM transactions WHERE user_session_id = ? AND txid = ?",
            (session_id, txid),
        ).fetchone()

        if not existing:
            return None

        conn.execute(
            "UPDATE transactions SET memo = ?, updated_at = ? WHERE user_session_id = ? AND txid = ?",
            (memo, now, session_id, txid),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM transactions WHERE user_session_id = ? AND txid = ?",
            (session_id, txid),
        ).fetchone()

    return dict(row) if row else None


def search_transactions(
    session_id: str,
    query: str = "",
    amount_min: Optional[int] = None,
    amount_max: Optional[int] = None,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    status: Optional[str] = None,
    direction: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Search transactions with full-text and filter options.

    Args:
        session_id: User session identifier
        query: Search query (matches txid, addresses, or memo)
        amount_min: Minimum amount in base units (optional)
        amount_max: Maximum amount in base units (optional)
        date_from: Start timestamp (optional)
        date_to: End timestamp (optional)
        status: Filter by status ('pending', 'confirmed', 'failed')
        direction: Filter by direction ('send', 'receive')
        limit: Max records per page (capped at 100)
        offset: Pagination offset

    Returns:
        dict with 'transactions', 'total', 'limit', 'offset'
    """
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))

    query = str(query or "").strip().lower()
    amount_min = int(amount_min) if amount_min is not None else None
    amount_max = int(amount_max) if amount_max is not None else None
    date_from = int(date_from) if date_from is not None else None
    date_to = int(date_to) if date_to is not None else None

    with get_connection() as conn:
        where_clause = "user_session_id = ?"
        params = [session_id]

        # Text search on txid, addresses, memo
        if query:
            where_clause += (
                " AND (LOWER(txid) LIKE ? OR LOWER(from_address) LIKE ? "
                "OR LOWER(to_address) LIKE ? OR LOWER(memo) LIKE ?)"
            )
            search_term = f"%{query}%"
            params.extend([search_term, search_term, search_term, search_term])

        # Amount range filter
        if amount_min is not None:
            where_clause += " AND amount_units >= ?"
            params.append(amount_min)
        if amount_max is not None:
            where_clause += " AND amount_units <= ?"
            params.append(amount_max)

        # Date range filter
        if date_from is not None:
            where_clause += " AND timestamp >= ?"
            params.append(date_from)
        if date_to is not None:
            where_clause += " AND timestamp <= ?"
            params.append(date_to)

        # Status filter
        if status:
            where_clause += " AND status = ?"
            params.append(status)

        # Direction filter
        if direction:
            where_clause += " AND direction = ?"
            params.append(direction)

        # Total count
        total = conn.execute(
            f"SELECT COUNT(*) AS n FROM transactions WHERE {where_clause}",
            params,
        ).fetchone()["n"]

        # Paginated results (newest first)
        rows = conn.execute(
            f"SELECT * FROM transactions WHERE {where_clause} "
            f"ORDER BY timestamp DESC, id DESC "
            f"LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    return {
        "transactions": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "query": query,
    }


def export_transactions_csv(
    session_id: str,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    include_fees: bool = True,
    include_memo: bool = True,
) -> str:
    """Export transactions as CSV.

    Args:
        session_id: User session identifier
        date_from: Start timestamp (optional)
        date_to: End timestamp (optional)
        include_fees: Include fee column
        include_memo: Include memo column

    Returns:
        CSV-formatted string with header row and summary
    """
    with get_connection() as conn:
        where_clause = "user_session_id = ?"
        params = [session_id]

        if date_from is not None:
            where_clause += " AND timestamp >= ?"
            params.append(date_from)
        if date_to is not None:
            where_clause += " AND timestamp <= ?"
            params.append(date_to)

        rows = conn.execute(
            f"SELECT * FROM transactions WHERE {where_clause} ORDER BY timestamp DESC",
            params,
        ).fetchall()

        # Calculate totals
        sent_total = 0
        received_total = 0
        fees_total = 0

        for row in rows:
            if row["direction"] == "send":
                sent_total += row["amount_units"]
                fees_total += row["fee_units"]
            else:
                received_total += row["amount_units"]

    # Build CSV header
    header_cols = ["Date", "Type", "Address", "Amount", "Status", "TXID"]
    if include_fees:
        header_cols.insert(4, "Fee")
    if include_memo:
        header_cols.append("Memo")

    lines = [",".join(header_cols)]

    # Add transaction rows
    for row in rows:
        r = dict(row)
        # Format timestamp as ISO 8601
        from datetime import datetime
        tx_date = datetime.utcfromtimestamp(r["timestamp"]).isoformat()

        tx_type = "Send" if r["direction"] == "send" else "Receive"
        address = r["to_address"] if r["direction"] == "send" else r["from_address"]
        amount = r["amount_units"] / 100  # Convert to display units (cents to MBITE)
        fee = r["fee_units"] / 100 if include_fees else None
        status = r["status"].capitalize()
        txid = r["txid"]
        memo = r["memo"] if include_memo else None

        row_data = [tx_date, tx_type, address, f"{amount:.8f}", status, txid]
        if include_fees:
            row_data.insert(4, f"{fee:.8f}" if fee else "0.00000000")
        if include_memo:
            # Escape quotes in memo
            escaped_memo = f'"{memo.replace(chr(34), chr(34) + chr(34))}"' if memo else '""'
            row_data.append(escaped_memo)

        lines.append(",".join(str(v) for v in row_data))

    # Add summary rows
    lines.append("")  # Blank line
    lines.append("Summary")
    lines.append(f"Total Sent,{sent_total / 100:.8f}")
    lines.append(f"Total Received,{received_total / 100:.8f}")
    if include_fees:
        lines.append(f"Total Fees,{fees_total / 100:.8f}")
    lines.append(f"Net,{(received_total - sent_total) / 100:.8f}")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Address book operations
# --------------------------------------------------------------------------- #

def add_contact(
    session_id: str,
    label: str,
    address: str,
    category: str = "general",
    notes: str = "",
) -> dict:
    """Add a labeled address to the user's address book.

    Args:
        session_id: User session identifier
        label: Display name (unique per session, max 100 chars)
        address: MoonBite address (max 120 chars)
        category: Category tag (max 50 chars)
        notes: Optional notes (max 500 chars)

    Returns:
        dict with inserted contact data

    Raises:
        ValueError: If label already exists for this session or validation fails
    """
    label = str(label or "").strip()[:100]
    if not label:
        raise ValueError("label is required")

    address = str(address or "").strip()
    if not address or len(address) > 120:
        raise ValueError("address is required and must be <= 120 chars")

    category = str(category or "general").strip()[:50]
    notes = str(notes or "").strip()[:500]

    now = int(time.time())

    with get_connection() as conn:
        # Check for duplicate label
        existing = conn.execute(
            "SELECT id FROM address_book WHERE user_session_id = ? AND label = ?",
            (session_id, label),
        ).fetchone()

        if existing:
            raise ValueError(f"contact with label '{label}' already exists")

        conn.execute(
            """INSERT INTO address_book
               (user_session_id, label, address, category, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, label, address, category, notes, now, now),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM address_book WHERE user_session_id = ? AND label = ?",
            (session_id, label),
        ).fetchone()

    return dict(row) if row else {}


def get_contacts(
    session_id: str,
    category: Optional[str] = None,
    sort: str = "created",
) -> list[dict]:
    """List all addresses in the user's address book.

    Args:
        session_id: User session identifier
        category: Filter by category, or None for all
        sort: 'created', 'updated', 'label', 'times_sent'

    Returns:
        list of contact dicts
    """
    valid_sorts = {
        "created": "created_at DESC",
        "updated": "updated_at DESC",
        "label": "label ASC",
        "times_sent": "times_sent DESC, created_at DESC",
    }
    order_by = valid_sorts.get(sort, "created_at DESC")

    with get_connection() as conn:
        if category:
            rows = conn.execute(
                f"SELECT * FROM address_book WHERE user_session_id = ? AND category = ? "
                f"ORDER BY {order_by}",
                (session_id, category),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT * FROM address_book WHERE user_session_id = ? "
                f"ORDER BY {order_by}",
                (session_id,),
            ).fetchall()

    return [dict(r) for r in rows]


def get_contact(session_id: str, contact_id: int) -> Optional[dict]:
    """Fetch a single contact by ID.

    Args:
        session_id: User session identifier
        contact_id: Contact database ID

    Returns:
        Contact dict, or None if not found
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM address_book WHERE user_session_id = ? AND id = ?",
            (session_id, contact_id),
        ).fetchone()
    return dict(row) if row else None


def update_contact(session_id: str, contact_id: int, updates: dict) -> Optional[dict]:
    """Update a contact's fields.

    Args:
        session_id: User session identifier
        contact_id: Contact database ID
        updates: dict with fields to update (label, address, category, notes, is_favorite)

    Returns:
        Updated contact dict, or None if not found

    Raises:
        ValueError: If label change conflicts with an existing label
    """
    with get_connection() as conn:
        # Verify contact exists and belongs to this session
        existing = conn.execute(
            "SELECT * FROM address_book WHERE user_session_id = ? AND id = ?",
            (session_id, contact_id),
        ).fetchone()

        if not existing:
            return None

        existing_dict = dict(existing)

        # Validate and build update
        now = int(time.time())
        update_fields = {}

        if "label" in updates:
            new_label = str(updates["label"]).strip()[:100]
            if new_label and new_label != existing_dict["label"]:
                # Check for duplicate
                conflict = conn.execute(
                    "SELECT id FROM address_book WHERE user_session_id = ? AND label = ? AND id != ?",
                    (session_id, new_label, contact_id),
                ).fetchone()
                if conflict:
                    raise ValueError(f"contact with label '{new_label}' already exists")
                update_fields["label"] = new_label

        if "address" in updates:
            addr = str(updates["address"]).strip()
            if addr and len(addr) <= 120:
                update_fields["address"] = addr

        if "category" in updates:
            cat = str(updates["category"]).strip()[:50]
            if cat:
                update_fields["category"] = cat

        if "notes" in updates:
            notes = str(updates["notes"]).strip()[:500]
            update_fields["notes"] = notes

        if "is_favorite" in updates:
            update_fields["is_favorite"] = 1 if updates["is_favorite"] else 0

        if update_fields:
            update_fields["updated_at"] = now
            cols = ", ".join(f"{k} = ?" for k in update_fields)
            vals = list(update_fields.values())
            conn.execute(
                f"UPDATE address_book SET {cols} WHERE user_session_id = ? AND id = ?",
                vals + [session_id, contact_id],
            )
            conn.commit()

        # Fetch updated record
        row = conn.execute(
            "SELECT * FROM address_book WHERE user_session_id = ? AND id = ?",
            (session_id, contact_id),
        ).fetchone()

    return dict(row) if row else None


def delete_contact(session_id: str, contact_id: int) -> bool:
    """Delete a contact from the address book.

    Args:
        session_id: User session identifier
        contact_id: Contact database ID

    Returns:
        True if deleted, False if not found
    """
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM address_book WHERE user_session_id = ? AND id = ?",
            (session_id, contact_id),
        ).fetchone()

        if not existing:
            return False

        conn.execute(
            "DELETE FROM address_book WHERE user_session_id = ? AND id = ?",
            (session_id, contact_id),
        )
        conn.commit()

    return True


def increment_send_count(session_id: str, contact_id: int) -> Optional[dict]:
    """Increment the times_sent counter when user sends to a contact.

    Args:
        session_id: User session identifier
        contact_id: Contact database ID

    Returns:
        Updated contact dict, or None if not found
    """
    now = int(time.time())
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM address_book WHERE user_session_id = ? AND id = ?",
            (session_id, contact_id),
        ).fetchone()

        if not existing:
            return None

        conn.execute(
            "UPDATE address_book SET times_sent = times_sent + 1, last_sent = ?, updated_at = ? "
            "WHERE user_session_id = ? AND id = ?",
            (now, now, session_id, contact_id),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM address_book WHERE user_session_id = ? AND id = ?",
            (session_id, contact_id),
        ).fetchone()

    return dict(row) if row else None


def export_address_book_csv(session_id: str) -> str:
    """Export address book as CSV (label, address, category, notes, times_sent, last_sent).

    Args:
        session_id: User session identifier

    Returns:
        CSV-formatted string
    """
    contacts = get_contacts(session_id)

    lines = [
        "label,address,category,notes,times_sent,last_sent",
    ]

    for c in contacts:
        # Escape quotes in fields
        label = f'"{c["label"].replace(chr(34), chr(34) + chr(34))}"'
        address = f'"{c["address"].replace(chr(34), chr(34) + chr(34))}"'
        category = f'"{c["category"].replace(chr(34), chr(34) + chr(34))}"'
        notes = f'"{c["notes"].replace(chr(34), chr(34) + chr(34))}"'
        times_sent = c.get("times_sent", 0)
        last_sent = c.get("last_sent", "")

        lines.append(f"{label},{address},{category},{notes},{times_sent},{last_sent}")

    return "\n".join(lines)


def import_address_book_csv(session_id: str, csv_data: str) -> dict:
    """Import addresses from CSV. Skips lines with parsing errors and duplicates.

    Args:
        session_id: User session identifier
        csv_data: CSV string with headers label,address,category,notes

    Returns:
        dict with 'imported', 'skipped', 'errors'
    """
    import csv
    import io

    imported, skipped, errors = 0, 0, []

    try:
        reader = csv.DictReader(io.StringIO(csv_data))
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
            try:
                label = row.get("label", "").strip()
                address = row.get("address", "").strip()
                category = row.get("category", "general").strip()
                notes = row.get("notes", "").strip()

                if not label or not address:
                    skipped += 1
                    continue

                # Try to add; skip if label already exists
                try:
                    add_contact(session_id, label, address, category, notes)
                    imported += 1
                except ValueError as e:
                    skipped += 1
                    errors.append(f"Row {row_num}: {str(e)}")

            except Exception as e:
                skipped += 1
                errors.append(f"Row {row_num}: {str(e)}")

    except Exception as e:
        return {
            "imported": 0,
            "skipped": 0,
            "errors": [f"CSV parse error: {str(e)}"],
        }

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
    }


# --------------------------------------------------------------------------- #
# Account management (multi-account support)
# --------------------------------------------------------------------------- #

def create_account(
    session_id: str,
    name: str,
    mnemonic: Optional[str] = None,
    color: Optional[str] = None,
    is_default: bool = False,
) -> dict:
    """Create a new account with optional mnemonic.

    Args:
        session_id: User session identifier
        name: Account display name (max 100 chars, unique per session)
        mnemonic: Optional BIP39 mnemonic seed (if None, caller must provide one)
        color: Optional color tag for UI (e.g., #FF5733, max 20 chars)
        is_default: Whether this is the default account

    Returns:
        dict with created account data

    Raises:
        ValueError: If name already exists or validation fails
    """
    name = str(name or "").strip()[:100]
    if not name:
        raise ValueError("name is required")

    color = str(color or "").strip()[:20] if color else None

    now = int(time.time())
    account_id = str(uuid.uuid4())

    # Hash the mnemonic if provided (don't store raw mnemonic in DB)
    mnemonic_hash = None
    if mnemonic:
        mnemonic_hash = hashlib.sha256(mnemonic.encode()).hexdigest()

    with get_connection() as conn:
        # Check for duplicate name in this session
        existing = conn.execute(
            "SELECT id FROM accounts WHERE user_session_id = ? AND name = ? AND is_deleted = 0",
            (session_id, name),
        ).fetchone()

        if existing:
            raise ValueError(f"account with name '{name}' already exists")

        # If this is the first account or explicitly default, set as default
        # and unset any other default accounts
        if is_default:
            conn.execute(
                "UPDATE accounts SET is_default = 0 WHERE user_session_id = ? AND is_default = 1",
                (session_id,),
            )

        # Get next display order
        display_order_result = conn.execute(
            "SELECT MAX(display_order) as max_order FROM accounts WHERE user_session_id = ? AND is_deleted = 0",
            (session_id,),
        ).fetchone()
        display_order = (display_order_result["max_order"] or 0) + 1

        conn.execute(
            """INSERT INTO accounts
               (id, user_session_id, name, display_order, color, is_default, mnemonic_hash, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (account_id, session_id, name, display_order, color, 1 if is_default else 0, mnemonic_hash, now, now),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()

    return dict(row) if row else {}


def list_accounts(session_id: str, include_deleted: bool = False) -> list[dict]:
    """Get all accounts for a user session.

    Args:
        session_id: User session identifier
        include_deleted: Whether to include soft-deleted accounts

    Returns:
        list of account dicts, ordered by display_order
    """
    with get_connection() as conn:
        if include_deleted:
            rows = conn.execute(
                "SELECT * FROM accounts WHERE user_session_id = ? ORDER BY display_order ASC",
                (session_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM accounts WHERE user_session_id = ? AND is_deleted = 0 ORDER BY display_order ASC",
                (session_id,),
            ).fetchall()

    return [dict(r) for r in rows]


def get_account(session_id: str, account_id: str) -> Optional[dict]:
    """Fetch a single account by ID.

    Args:
        session_id: User session identifier
        account_id: Account ID

    Returns:
        Account dict, or None if not found or deleted
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accounts WHERE id = ? AND user_session_id = ? AND is_deleted = 0",
            (account_id, session_id),
        ).fetchone()

    return dict(row) if row else None


def get_default_account(session_id: str) -> Optional[dict]:
    """Get the current default account for a user session.

    Args:
        session_id: User session identifier

    Returns:
        Default account dict, or None if no default set
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accounts WHERE user_session_id = ? AND is_default = 1 AND is_deleted = 0",
            (session_id,),
        ).fetchone()

    return dict(row) if row else None


def update_account(
    session_id: str,
    account_id: str,
    name: Optional[str] = None,
    color: Optional[str] = None,
) -> Optional[dict]:
    """Update account name and/or color.

    Args:
        session_id: User session identifier
        account_id: Account ID
        name: New account name (optional)
        color: New color tag (optional)

    Returns:
        Updated account dict, or None if not found

    Raises:
        ValueError: If new name conflicts with existing account
    """
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM accounts WHERE id = ? AND user_session_id = ? AND is_deleted = 0",
            (account_id, session_id),
        ).fetchone()

        if not existing:
            return None

        existing_dict = dict(existing)
        now = int(time.time())
        updates = {}

        if name is not None:
            new_name = str(name).strip()[:100]
            if new_name and new_name != existing_dict["name"]:
                # Check for duplicate
                conflict = conn.execute(
                    "SELECT id FROM accounts WHERE user_session_id = ? AND name = ? AND id != ? AND is_deleted = 0",
                    (session_id, new_name, account_id),
                ).fetchone()
                if conflict:
                    raise ValueError(f"account with name '{new_name}' already exists")
                updates["name"] = new_name

        if color is not None:
            color_val = str(color).strip()[:20] if color else None
            updates["color"] = color_val

        if updates:
            updates["updated_at"] = now
            cols = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values())
            conn.execute(
                f"UPDATE accounts SET {cols} WHERE id = ? AND user_session_id = ?",
                vals + [account_id, session_id],
            )
            conn.commit()

        row = conn.execute(
            "SELECT * FROM accounts WHERE id = ? AND user_session_id = ?",
            (account_id, session_id),
        ).fetchone()

    return dict(row) if row else None


def set_default_account(session_id: str, account_id: str) -> Optional[dict]:
    """Set an account as the default (unsets any previous default).

    Args:
        session_id: User session identifier
        account_id: Account ID to set as default

    Returns:
        Updated account dict, or None if not found

    Raises:
        ValueError: If account belongs to different session
    """
    with get_connection() as conn:
        # Verify account exists and belongs to this session
        existing = conn.execute(
            "SELECT * FROM accounts WHERE id = ? AND user_session_id = ? AND is_deleted = 0",
            (account_id, session_id),
        ).fetchone()

        if not existing:
            return None

        now = int(time.time())

        # Unset all other defaults
        conn.execute(
            "UPDATE accounts SET is_default = 0 WHERE user_session_id = ? AND is_default = 1",
            (session_id,),
        )

        # Set this as default
        conn.execute(
            "UPDATE accounts SET is_default = 1, updated_at = ? WHERE id = ?",
            (now, account_id),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()

    return dict(row) if row else None


def delete_account(session_id: str, account_id: str) -> bool:
    """Soft-delete an account (mark as deleted, don't remove data).

    Args:
        session_id: User session identifier
        account_id: Account ID

    Returns:
        True if deleted, False if not found or already deleted
    """
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM accounts WHERE id = ? AND user_session_id = ? AND is_deleted = 0",
            (account_id, session_id),
        ).fetchone()

        if not existing:
            return False

        now = int(time.time())

        # Soft delete
        conn.execute(
            "UPDATE accounts SET is_deleted = 1, updated_at = ? WHERE id = ?",
            (now, account_id),
        )

        # If this was the default, unset it
        conn.execute(
            "UPDATE accounts SET is_default = 0 WHERE id = ?",
            (account_id,),
        )

        conn.commit()

    return True


def add_account_address(
    account_id: str,
    address: str,
    derivation_path: Optional[str] = None,
    pubkey_hash: Optional[str] = None,
) -> dict:
    """Add an address to an account.

    Args:
        account_id: Account ID
        address: MoonBite address
        derivation_path: BIP32 derivation path (e.g., m/44'/0'/0'/0/0)
        pubkey_hash: Hex pubkey hash for balance tracking

    Returns:
        dict with created address data
    """
    now = int(time.time())
    addr_id = str(uuid.uuid4())

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO account_addresses
               (id, account_id, address, derivation_path, pubkey_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (addr_id, account_id, address, derivation_path, pubkey_hash, now),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM account_addresses WHERE id = ?",
            (addr_id,),
        ).fetchone()

    return dict(row) if row else {}


def get_account_addresses(account_id: str, active_only: bool = True) -> list[dict]:
    """Get all addresses for an account.

    Args:
        account_id: Account ID
        active_only: Only return active addresses

    Returns:
        list of address dicts
    """
    with get_connection() as conn:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM account_addresses WHERE account_id = ? AND is_active = 1 ORDER BY created_at ASC",
                (account_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM account_addresses WHERE account_id = ? ORDER BY created_at ASC",
                (account_id,),
            ).fetchall()

    return [dict(r) for r in rows]


def get_account_balance(session_id: str, account_id: str) -> int:
    """Get total balance for an account by summing its addresses' UTXOs.

    Args:
        session_id: User session identifier
        account_id: Account ID

    Returns:
        Total balance in base units (cents for MoonBite)
    """
    with get_connection() as conn:
        # Get all active addresses for this account
        addresses = conn.execute(
            "SELECT pubkey_hash FROM account_addresses WHERE account_id = ? AND is_active = 1",
            (account_id,),
        ).fetchall()

    # This will be filled by the caller with actual UTXO lookup
    # For now, return cached balance
    with get_connection() as conn:
        account = conn.execute(
            "SELECT balance_cache FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()

    return account["balance_cache"] if account else 0


def update_account_balance(session_id: str, account_id: str, balance: int) -> bool:
    """Update cached balance for an account.

    Args:
        session_id: User session identifier
        account_id: Account ID
        balance: New balance in base units

    Returns:
        True if updated, False if not found
    """
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM accounts WHERE id = ? AND user_session_id = ?",
            (account_id, session_id),
        ).fetchone()

        if not existing:
            return False

        now = int(time.time())
        conn.execute(
            "UPDATE accounts SET balance_cache = ?, updated_at = ? WHERE id = ?",
            (balance, now, account_id),
        )
        conn.commit()

    return True


# --------------------------------------------------------------------------- #
# Preferences and settings management
# --------------------------------------------------------------------------- #

def get_preference_defaults() -> dict:
    """Get default preferences for a new user."""
    return {
        "language": "en",
        "currency": "USD",
        "theme": "auto",
        "time_format": "relative",
        "amount_format": "full",
        "notification_tx": 1,
        "notification_price": 1,
        "auto_lock_mins": 15,
        "decimal_places": 8,
        "hide_zero_balance": 0,
        "sort_accounts": "created",
    }


def validate_preference_value(key: str, value: any) -> bool:
    """Validate a preference key-value pair before storing.

    Args:
        key: Preference key
        value: Value to validate

    Returns:
        True if valid, raises ValueError otherwise
    """
    valid_keys = {
        "language": {"type": str, "allowed": ["en", "es", "fr", "de", "ja", "zh"]},
        "currency": {"type": str, "allowed": ["USD", "EUR", "GBP", "JPY", "CNY", "BTC", "MBITE"]},
        "theme": {"type": str, "allowed": ["light", "dark", "auto"]},
        "time_format": {"type": str, "allowed": ["relative", "absolute", "unix"]},
        "amount_format": {"type": str, "allowed": ["full", "short", "scientific"]},
        "notification_tx": {"type": int, "allowed": [0, 1]},
        "notification_price": {"type": int, "allowed": [0, 1]},
        "auto_lock_mins": {"type": int, "min": 0, "max": 120},
        "decimal_places": {"type": int, "min": 2, "max": 8},
        "hide_zero_balance": {"type": int, "allowed": [0, 1]},
        "sort_accounts": {"type": str, "allowed": ["created", "updated", "name", "balance"]},
    }

    if key not in valid_keys:
        raise ValueError(f"unknown preference key: {key}")

    spec = valid_keys[key]
    expected_type = spec["type"]

    if not isinstance(value, expected_type):
        raise ValueError(f"{key} must be {expected_type.__name__}, got {type(value).__name__}")

    if "allowed" in spec and value not in spec["allowed"]:
        raise ValueError(f"{key}={value} not in allowed values: {spec['allowed']}")

    if "min" in spec and value < spec["min"]:
        raise ValueError(f"{key}={value} must be >= {spec['min']}")

    if "max" in spec and value > spec["max"]:
        raise ValueError(f"{key}={value} must be <= {spec['max']}")

    return True


def get_preferences(session_id: str) -> dict:
    """Get all user preferences with defaults filled in.

    Args:
        session_id: User session identifier

    Returns:
        dict with all preference keys (uses defaults for missing values)
    """
    defaults = get_preference_defaults()

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM preferences WHERE user_session_id = ?",
            (session_id,),
        ).fetchone()

    if row:
        prefs = dict(row)
        # Remove session_id and timestamps from returned dict
        prefs.pop("user_session_id", None)
        prefs.pop("created_at", None)
        prefs.pop("updated_at", None)
        # Merge with defaults (prefer stored values)
        result = {**defaults, **prefs}
    else:
        result = defaults

    return result


def update_preferences(session_id: str, updates: dict) -> dict:
    """Update user preferences. Creates row if doesn't exist.

    Args:
        session_id: User session identifier
        updates: dict with preference keys to update

    Returns:
        dict with all current preferences after update

    Raises:
        ValueError: If any preference value is invalid
    """
    # Validate all updates first
    for key, value in updates.items():
        validate_preference_value(key, value)

    now = int(time.time())

    with get_connection() as conn:
        # Check if preferences exist for this session
        existing = conn.execute(
            "SELECT user_session_id FROM preferences WHERE user_session_id = ?",
            (session_id,),
        ).fetchone()

        if existing:
            # Update existing preferences
            update_fields = {**updates, "updated_at": now}
            cols = ", ".join(f"{k} = ?" for k in update_fields)
            vals = list(update_fields.values())
            conn.execute(
                f"UPDATE preferences SET {cols} WHERE user_session_id = ?",
                vals + [session_id],
            )
        else:
            # Create new preferences with defaults + updates
            defaults = get_preference_defaults()
            all_prefs = {**defaults, **updates}
            all_prefs["user_session_id"] = session_id
            all_prefs["created_at"] = now
            all_prefs["updated_at"] = now

            cols = ", ".join(all_prefs.keys())
            placeholders = ", ".join("?" * len(all_prefs))
            conn.execute(
                f"INSERT INTO preferences ({cols}) VALUES ({placeholders})",
                list(all_prefs.values()),
            )

        conn.commit()

    # Return all preferences after update
    return get_preferences(session_id)


def reset_preferences(session_id: str) -> dict:
    """Reset user preferences to defaults.

    Args:
        session_id: User session identifier

    Returns:
        dict with reset preferences
    """
    defaults = get_preference_defaults()
    return update_preferences(session_id, defaults)


def delete_preferences(session_id: str) -> bool:
    """Delete all preferences for a user session.

    Args:
        session_id: User session identifier

    Returns:
        True if deleted, False if not found
    """
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT user_session_id FROM preferences WHERE user_session_id = ?",
            (session_id,),
        ).fetchone()

        if not existing:
            return False

        conn.execute(
            "DELETE FROM preferences WHERE user_session_id = ?",
            (session_id,),
        )
        conn.commit()

    return True


# --------------------------------------------------------------------------- #
# Biometric Authentication - WebAuthn/FIDO2
# --------------------------------------------------------------------------- #

def _hash_password(password: str) -> str:
    """Hash a password using Argon2id (if available, else SHA256 fallback).

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    try:
        from argon2 import PasswordHasher
        ph = PasswordHasher()
        return ph.hash(password)
    except ImportError:
        # Fallback to SHA256 if argon2-cffi not installed
        return hashlib.sha256(password.encode()).hexdigest()


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash.

    Args:
        password: Plain text password to verify
        password_hash: Hash to check against

    Returns:
        True if password matches, False otherwise
    """
    try:
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError, InvalidHash
        ph = PasswordHasher()
        try:
            ph.verify(password_hash, password)
            return True
        except (VerifyMismatchError, InvalidHash):
            return False
    except ImportError:
        # Fallback to SHA256 comparison
        return hashlib.sha256(password.encode()).hexdigest() == password_hash


def get_auth_state(session_id: str) -> Optional[dict]:
    """Get authentication state for a user session.

    Args:
        session_id: User session identifier

    Returns:
        Auth state dict, or None if not found
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM auth_state WHERE user_session_id = ?",
            (session_id,),
        ).fetchone()
    return dict(row) if row else None


def is_biometric_available(session_id: str) -> bool:
    """Check if biometric auth is enabled for a session.

    Args:
        session_id: User session identifier

    Returns:
        True if biometric is enabled and configured
    """
    auth_state = get_auth_state(session_id)
    if not auth_state:
        return False
    return auth_state.get("biometric_enabled", 0) == 1 and bool(auth_state.get("biometric_credential_id"))


def setup_biometric(
    session_id: str,
    credential_id: str,
    public_key: str,
    device_name: str = "Default Device",
) -> dict:
    """Register biometric credential for a user session.

    Args:
        session_id: User session identifier
        credential_id: WebAuthn credential ID (base64-encoded)
        public_key: COSE public key (base64-encoded)
        device_name: Human-readable device name

    Returns:
        Updated auth state dict
    """
    device_name = str(device_name or "").strip()[:100] or "Default Device"
    now = int(time.time())

    with get_connection() as conn:
        # Check if auth_state exists
        existing = conn.execute(
            "SELECT user_session_id FROM auth_state WHERE user_session_id = ?",
            (session_id,),
        ).fetchone()

        if existing:
            # Update existing
            conn.execute(
                """UPDATE auth_state
                   SET biometric_enabled = 1,
                       biometric_device_name = ?,
                       biometric_credential_id = ?,
                       biometric_public_key = ?,
                       updated_at = ?
                   WHERE user_session_id = ?""",
                (device_name, credential_id, public_key, now, session_id),
            )
        else:
            # Create new
            conn.execute(
                """INSERT INTO auth_state
                   (user_session_id, biometric_enabled, biometric_device_name,
                    biometric_credential_id, biometric_public_key, created_at, updated_at)
                   VALUES (?, 1, ?, ?, ?, ?, ?)""",
                (session_id, device_name, credential_id, public_key, now, now),
            )

        # Also update preferences for consistency
        conn.execute(
            """INSERT INTO preferences
               (user_session_id, biometric_enabled, biometric_device_name, created_at, updated_at)
               VALUES (?, 1, ?, ?, ?)
               ON CONFLICT(user_session_id) DO UPDATE SET
               biometric_enabled = 1,
               biometric_device_name = ?,
               updated_at = ?""",
            (session_id, device_name, now, now, device_name, now),
        )

        conn.commit()

        row = conn.execute(
            "SELECT * FROM auth_state WHERE user_session_id = ?",
            (session_id,),
        ).fetchone()

    return dict(row) if row else {}


def verify_biometric(session_id: str, assertion_id: str) -> bool:
    """Verify a biometric assertion (after WebAuthn validation on client).

    Args:
        session_id: User session identifier
        assertion_id: The credential ID from the assertion (for validation)

    Returns:
        True if biometric verification succeeds
    """
    auth_state = get_auth_state(session_id)
    if not auth_state or not auth_state.get("biometric_credential_id"):
        return False

    # The actual cryptographic verification of the assertion signature
    # happens on the client (browser WebAuthn API). This server-side
    # function assumes that verification has been done and just validates
    # that the credential ID matches.

    stored_credential_id = auth_state.get("biometric_credential_id")

    # Constant-time comparison to prevent timing attacks
    matches = hmac.compare_digest(
        stored_credential_id.encode() if isinstance(stored_credential_id, str) else stored_credential_id,
        assertion_id.encode() if isinstance(assertion_id, str) else assertion_id,
    )

    if matches:
        now = int(time.time())
        with get_connection() as conn:
            # Update last login timestamp
            conn.execute(
                "UPDATE auth_state SET last_login = ?, failed_attempts = 0 WHERE user_session_id = ?",
                (now, session_id),
            )
            # Log successful verification
            _log_biometric_event(conn, session_id, "verify", "success", assertion_id)
            conn.commit()

    return matches


def disable_biometric(session_id: str) -> bool:
    """Disable biometric authentication for a session.

    Args:
        session_id: User session identifier

    Returns:
        True if disabled, False if not found
    """
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT user_session_id FROM auth_state WHERE user_session_id = ?",
            (session_id,),
        ).fetchone()

        if not existing:
            return False

        now = int(time.time())

        # Disable biometric
        conn.execute(
            """UPDATE auth_state
               SET biometric_enabled = 0,
                   biometric_device_name = NULL,
                   biometric_credential_id = NULL,
                   biometric_public_key = NULL,
                   updated_at = ?
               WHERE user_session_id = ?""",
            (now, session_id),
        )

        # Update preferences
        conn.execute(
            """UPDATE preferences
               SET biometric_enabled = 0,
                   biometric_device_name = NULL,
                   updated_at = ?
               WHERE user_session_id = ?""",
            (now, session_id),
        )

        # Log the disable action
        _log_biometric_event(conn, session_id, "disable", "success")
        conn.commit()

    return True


def record_biometric_failure(session_id: str) -> int:
    """Record a failed biometric verification attempt and return attempt count.

    Args:
        session_id: User session identifier

    Returns:
        Number of failed attempts (for rate limiting check)
    """
    now = int(time.time())

    with get_connection() as conn:
        # Get current auth state
        auth_state = conn.execute(
            "SELECT failed_attempts FROM auth_state WHERE user_session_id = ?",
            (session_id,),
        ).fetchone()

        current_attempts = (auth_state["failed_attempts"] if auth_state else 0) + 1

        # Update failed attempts
        if auth_state:
            conn.execute(
                "UPDATE auth_state SET failed_attempts = ?, last_failed_at = ? WHERE user_session_id = ?",
                (current_attempts, now, session_id),
            )
        else:
            conn.execute(
                """INSERT INTO auth_state
                   (user_session_id, failed_attempts, last_failed_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, current_attempts, now, now, now),
            )

        # Log the failure
        _log_biometric_event(conn, session_id, "verify", "failed")
        conn.commit()

    return current_attempts


def check_biometric_rate_limit(session_id: str, max_attempts: int = 5, window_seconds: int = 60) -> tuple[bool, int]:
    """Check if user is rate-limited for biometric attempts.

    Args:
        session_id: User session identifier
        max_attempts: Max failed attempts in window
        window_seconds: Time window in seconds

    Returns:
        Tuple of (is_rate_limited, attempts_in_window)
    """
    now = int(time.time())
    cutoff = now - window_seconds

    with get_connection() as conn:
        # Count failed attempts in the window
        result = conn.execute(
            """SELECT COUNT(*) as count FROM biometric_audit
               WHERE user_session_id = ? AND action = 'verify' AND status = 'failed'
               AND created_at >= ?""",
            (session_id, cutoff),
        ).fetchone()

    attempts = result["count"] if result else 0
    is_limited = attempts >= max_attempts

    return (is_limited, attempts)


def _log_biometric_event(
    conn: sqlite3.Connection,
    session_id: str,
    action: str,
    status: str,
    credential_id: Optional[str] = None,
    error_message: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Internal helper to log biometric events (must be called within a transaction).

    Args:
        conn: Database connection
        session_id: User session identifier
        action: Event action (register, verify, disable)
        status: Event status (success, failed)
        credential_id: Optional credential ID
        error_message: Optional error details
        ip_address: Optional client IP
        user_agent: Optional user agent string
    """
    now = int(time.time())

    conn.execute(
        """INSERT INTO biometric_audit
           (user_session_id, action, status, credential_id, error_message, ip_address, user_agent, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, action, status, credential_id, error_message, ip_address, user_agent, now),
    )


def get_biometric_audit_log(
    session_id: str,
    action: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Get audit log for biometric events.

    Args:
        session_id: User session identifier
        action: Filter by action (register, verify, disable), or None for all
        limit: Max records per page
        offset: Pagination offset

    Returns:
        dict with 'events', 'total', 'limit', 'offset'
    """
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))

    with get_connection() as conn:
        where_clause = "user_session_id = ?"
        params = [session_id]

        if action:
            where_clause += " AND action = ?"
            params.append(action)

        # Total count
        total = conn.execute(
            f"SELECT COUNT(*) AS n FROM biometric_audit WHERE {where_clause}",
            params,
        ).fetchone()["n"]

        # Paginated results (newest first)
        rows = conn.execute(
            f"SELECT id, action, status, credential_id, error_message, created_at "
            f"FROM biometric_audit WHERE {where_clause} "
            f"ORDER BY created_at DESC "
            f"LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    return {
        "events": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
