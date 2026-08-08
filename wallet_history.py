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

import os
import sqlite3
import time
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
    """Initialize transaction and address book tables if they don't exist."""
    conn = get_connection()
    try:
        # Transaction table: tracks all send/receive activity
        conn.execute(
            """CREATE TABLE IF NOT EXISTS transactions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_session_id TEXT NOT NULL,
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
                   (user_session_id, txid, direction, amount_units, fee_units,
                    from_address, to_address, status, block_height, confirmations,
                    memo, timestamp, confirmed_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
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
