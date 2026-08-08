# MoonBite Wallet History API Documentation

## Overview

The Wallet History backend provides transaction tracking and address book management for the MoonBite wallet. Each user session maintains isolated transaction history and contact lists via SQLite with WAL mode for concurrent access.

## Database Schema

### Transactions Table
```sql
transactions (
    id                  INTEGER PRIMARY KEY
    user_session_id     TEXT NOT NULL       -- Session isolation
    txid                TEXT NOT NULL       -- Transaction hash
    direction           TEXT NOT NULL       -- 'send' or 'receive'
    amount_units        INTEGER NOT NULL    -- Base units transferred
    fee_units           INTEGER NOT NULL    -- Network fee
    from_address        TEXT NOT NULL       -- Source address
    to_address          TEXT NOT NULL       -- Destination address
    status              TEXT NOT NULL       -- 'pending', 'confirmed', 'failed'
    block_height        INTEGER             -- Height of confirmation
    confirmations       INTEGER NOT NULL    -- Confirmation count
    timestamp           INTEGER NOT NULL    -- Creation timestamp
    confirmed_at        INTEGER             -- Confirmation timestamp
    memo                TEXT NOT NULL       -- User-editable note
    created_at          INTEGER NOT NULL    -- Record creation time
    updated_at          INTEGER NOT NULL    -- Last update time

    UNIQUE(user_session_id, txid)
)

INDEXES:
    idx_transactions_session_time    (user_session_id, timestamp DESC)
    idx_transactions_session_status  (user_session_id, status)
    idx_transactions_txid            (txid)
```

### Address Book Table
```sql
address_book (
    id              INTEGER PRIMARY KEY
    user_session_id TEXT NOT NULL       -- Session isolation
    label           TEXT NOT NULL       -- Display name (max 100 chars)
    address         TEXT NOT NULL       -- MoonBite address (max 120 chars)
    category        TEXT NOT NULL       -- Category tag (max 50 chars)
    notes           TEXT NOT NULL       -- Optional notes (max 500 chars)
    is_favorite     INTEGER NOT NULL    -- Favorite flag (0/1)
    times_sent      INTEGER NOT NULL    -- Send count
    last_sent       INTEGER             -- Last send timestamp
    created_at      INTEGER NOT NULL    -- Record creation time
    updated_at      INTEGER NOT NULL    -- Last update time

    UNIQUE(user_session_id, label)
)

INDEXES:
    idx_address_book_session             (user_session_id)
    idx_address_book_session_category    (user_session_id, category)
    idx_address_book_address             (address)
```

## REST API Endpoints

### Transaction History

#### Create Transaction: POST /api/wallet/transaction/send
Create a new transaction record after sending coins on-chain.

**Request:**
```json
{
    "txid": "abc123...",
    "amount_units": 50000,
    "from_address": "moon1xxxxx",
    "to_address": "moon2yyyyy",
    "fee_units": 100,
    "status": "pending",
    "memo": "Payment description"
}
```

**Response (201 Created):**
```json
{
    "status": "success",
    "transaction": {
        "id": 1,
        "user_session_id": "...",
        "txid": "abc123...",
        "direction": "send",
        "amount_units": 50000,
        "fee_units": 100,
        "from_address": "moon1xxxxx",
        "to_address": "moon2yyyyy",
        "status": "pending",
        "block_height": null,
        "confirmations": 0,
        "timestamp": 1691234567,
        "confirmed_at": null,
        "memo": "Payment description",
        "created_at": 1691234567,
        "updated_at": 1691234567
    }
}
```

**Error (400 Bad Request):**
```json
{
    "status": "error",
    "message": "txid is required"
}
```

---

#### List Transactions: GET /api/wallet/transactions
Retrieve paginated transaction list with optional filtering.

**Query Parameters:**
- `limit` (int, 1-100, default 20): Max records per page
- `offset` (int, default 0): Pagination offset
- `status` (string, optional): Filter by 'pending', 'confirmed', or 'failed'
- `sort` (string, 'asc' or 'desc', default 'desc'): Sort order (newest first)

**Request:**
```
GET /api/wallet/transactions?limit=20&offset=0&status=confirmed&sort=desc
```

**Response (200 OK):**
```json
{
    "status": "success",
    "data": {
        "transactions": [
            {
                "id": 2,
                "user_session_id": "...",
                "txid": "def456...",
                "direction": "receive",
                "amount_units": 100000,
                "fee_units": 0,
                "from_address": "moon3zzzzz",
                "to_address": "moon1xxxxx",
                "status": "confirmed",
                "block_height": 150,
                "confirmations": 10,
                "timestamp": 1691234600,
                "confirmed_at": 1691234620,
                "memo": "",
                "created_at": 1691234600,
                "updated_at": 1691234620
            }
        ],
        "total": 1,
        "limit": 20,
        "offset": 0
    }
}
```

---

#### Get Transaction Detail: GET /api/wallet/transactions/:txid
Fetch a single transaction by hash.

**Request:**
```
GET /api/wallet/transactions/abc123...
```

**Response (200 OK):**
```json
{
    "status": "success",
    "data": {
        "id": 1,
        "user_session_id": "...",
        "txid": "abc123...",
        "direction": "send",
        "amount_units": 50000,
        "fee_units": 100,
        "from_address": "moon1xxxxx",
        "to_address": "moon2yyyyy",
        "status": "pending",
        "block_height": null,
        "confirmations": 0,
        "timestamp": 1691234567,
        "confirmed_at": null,
        "memo": "Payment description",
        "created_at": 1691234567,
        "updated_at": 1691234567
    }
}
```

**Error (404 Not Found):**
```json
{
    "status": "error",
    "message": "transaction not found"
}
```

---

#### Update Transaction Memo: PATCH /api/wallet/transactions/:txid
Edit the memo/note of a transaction (immutable otherwise).

**Request:**
```json
{
    "memo": "Updated note about this transaction"
}
```

**Response (200 OK):**
```json
{
    "status": "success",
    "data": {
        "id": 1,
        "user_session_id": "...",
        "txid": "abc123...",
        "memo": "Updated note about this transaction",
        ...
    }
}
```

---

### Address Book

#### Add Contact: POST /api/address-book/add
Add a labeled address to the contact list.

**Request:**
```json
{
    "label": "Alice",
    "address": "moon1alice",
    "category": "friends",
    "notes": "College friend"
}
```

**Response (201 Created):**
```json
{
    "status": "success",
    "data": {
        "id": 1,
        "user_session_id": "...",
        "label": "Alice",
        "address": "moon1alice",
        "category": "friends",
        "notes": "College friend",
        "is_favorite": 0,
        "times_sent": 0,
        "last_sent": null,
        "created_at": 1691234567,
        "updated_at": 1691234567
    }
}
```

**Error (400 Bad Request):**
```json
{
    "status": "error",
    "message": "contact with label 'Alice' already exists"
}
```

---

#### List Contacts: GET /api/address-book
Retrieve all contacts with optional filtering and sorting.

**Query Parameters:**
- `category` (string, optional): Filter by category (e.g., 'friends', 'work')
- `sort` (string, default 'created'): Sort by 'created', 'updated', 'label', or 'times_sent'

**Request:**
```
GET /api/address-book?category=friends&sort=times_sent
```

**Response (200 OK):**
```json
{
    "status": "success",
    "data": [
        {
            "id": 1,
            "user_session_id": "...",
            "label": "Alice",
            "address": "moon1alice",
            "category": "friends",
            "notes": "College friend",
            "is_favorite": 0,
            "times_sent": 3,
            "last_sent": 1691234567,
            "created_at": 1691234500,
            "updated_at": 1691234567
        }
    ]
}
```

---

#### Get Contact Detail: GET /api/address-book/:id
Fetch a single contact by ID.

**Request:**
```
GET /api/address-book/1
```

**Response (200 OK):**
```json
{
    "status": "success",
    "data": {
        "id": 1,
        "user_session_id": "...",
        "label": "Alice",
        "address": "moon1alice",
        "category": "friends",
        "notes": "College friend",
        "is_favorite": 0,
        "times_sent": 3,
        "last_sent": 1691234567,
        "created_at": 1691234500,
        "updated_at": 1691234567
    }
}
```

---

#### Update Contact: PATCH /api/address-book/:id
Update one or more contact fields.

**Request:**
```json
{
    "label": "Alice Smith",
    "category": "work",
    "is_favorite": 1
}
```

**Response (200 OK):**
```json
{
    "status": "success",
    "data": {
        "id": 1,
        "user_session_id": "...",
        "label": "Alice Smith",
        "address": "moon1alice",
        "category": "work",
        "notes": "College friend",
        "is_favorite": 1,
        "times_sent": 3,
        "last_sent": 1691234567,
        "created_at": 1691234500,
        "updated_at": 1691234600
    }
}
```

---

#### Delete Contact: DELETE /api/address-book/:id
Remove a contact from the address book.

**Request:**
```
DELETE /api/address-book/1
```

**Response (200 OK):**
```json
{
    "status": "success",
    "message": "contact deleted"
}
```

**Error (404 Not Found):**
```json
{
    "status": "error",
    "message": "contact not found"
}
```

---

#### Export Address Book: GET /api/address-book/export
Export all contacts as CSV file (attachment).

**Request:**
```
GET /api/address-book/export
```

**Response (200 OK):**
```
Content-Type: text/csv
Content-Disposition: attachment;filename=address-book.csv

label,address,category,notes,times_sent,last_sent
Alice,moon1alice,friends,College friend,3,1691234567
Bob,moon1bob,work,Colleague,1,1691234500
```

---

#### Import Address Book: POST /api/address-book/import
Bulk import contacts from CSV.

**Request (multipart form):**
```
POST /api/address-book/import
Content-Type: multipart/form-data

file: address-book.csv (CSV with headers: label,address,category,notes)
```

**Request (raw body):**
```
POST /api/address-book/import
Content-Type: text/plain

label,address,category,notes
Charlie,moon1charlie,friends,New friend
David,moon1david,work,Manager
```

**Response (200 OK):**
```json
{
    "status": "success",
    "data": {
        "imported": 2,
        "skipped": 0,
        "errors": []
    }
}
```

**Partial Success (200 OK with errors):**
```json
{
    "status": "success",
    "data": {
        "imported": 1,
        "skipped": 1,
        "errors": [
            "Row 2: contact with label 'Alice' already exists"
        ]
    }
}
```

---

## Session Isolation

All endpoints use a per-visitor `user_session_id` to ensure transaction history and contacts are isolated. The session ID is derived from the Flask session cookie:

```python
session_id = session.get("session_id") or secrets.token_hex(16)
```

This means:
- Each unique visitor has their own transaction history and address book
- Data cannot leak between sessions
- Clearing a session cookie provides privacy

---

## Error Responses

All error responses follow this format:

```json
{
    "status": "error",
    "message": "Human-readable error description"
}
```

Common HTTP status codes:
- **200 OK**: Successful GET
- **201 Created**: Successful POST (resource created)
- **400 Bad Request**: Invalid input or validation failed
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Unexpected server error

---

## Rate Limiting

The following endpoints have rate limits per client IP:

- `POST /api/wallet/transaction/send`: 30 requests per 60 seconds
- `PATCH /api/wallet/transactions/:txid`: 60 requests per 60 seconds
- `POST /api/address-book/add`: 30 requests per 60 seconds
- `PATCH /api/address-book/:id`: 60 requests per 60 seconds
- `DELETE /api/address-book/:id`: 30 requests per 60 seconds
- `GET /api/address-book/export`: 10 requests per 60 seconds
- `POST /api/address-book/import`: 10 requests per 60 seconds

Rate limit can be bypassed by providing an `X-API-Key` header matching a key in `MOONBITE_API_KEYS`.

---

## Module API (Python)

### wallet_history.get_connection() → sqlite3.Connection
Open a database connection with WAL mode and FK constraints enabled.

### wallet_history.create_schema()
Initialize transaction and address book tables if they don't exist.

### wallet_history.add_transaction(...) → dict
Insert or update a transaction record.

```python
tx = wallet_history.add_transaction(
    session_id="user_session_123",
    txid="abc123...",
    direction="send",  # or "receive"
    amount_units=50000,
    from_address="moon1xxxxx",
    to_address="moon2yyyyy",
    fee_units=100,
    status="pending",  # or "confirmed", "failed"
    block_height=None,
    confirmations=0,
    memo="Optional note",
)
```

### wallet_history.get_transactions(...) → dict
Retrieve paginated transaction list.

```python
result = wallet_history.get_transactions(
    session_id="user_session_123",
    limit=20,
    offset=0,
    status="confirmed",  # optional filter
    sort="desc",
)
# Returns: {"transactions": [...], "total": N, "limit": 20, "offset": 0}
```

### wallet_history.get_transaction(session_id, txid) → dict | None
Fetch a single transaction by hash.

### wallet_history.update_transaction_memo(session_id, txid, memo) → dict | None
Update only the memo field of a transaction.

### wallet_history.add_contact(...) → dict
Add a labeled address to the contact list.

```python
contact = wallet_history.add_contact(
    session_id="user_session_123",
    label="Alice",
    address="moon1alice",
    category="friends",  # optional
    notes="College friend",  # optional
)
```

### wallet_history.get_contacts(...) → list[dict]
Retrieve all contacts with optional filtering and sorting.

```python
contacts = wallet_history.get_contacts(
    session_id="user_session_123",
    category="friends",  # optional filter
    sort="created",  # or "updated", "label", "times_sent"
)
```

### wallet_history.get_contact(session_id, contact_id) → dict | None
Fetch a single contact by ID.

### wallet_history.update_contact(session_id, contact_id, updates) → dict | None
Update one or more contact fields.

```python
updated = wallet_history.update_contact(
    session_id="user_session_123",
    contact_id=1,
    updates={
        "label": "Alice Smith",
        "category": "work",
        "is_favorite": 1,
    }
)
```

### wallet_history.delete_contact(session_id, contact_id) → bool
Delete a contact. Returns True if deleted, False if not found.

### wallet_history.increment_send_count(session_id, contact_id) → dict | None
Increment the times_sent counter (called when user sends to a contact).

### wallet_history.export_address_book_csv(session_id) → str
Export address book as CSV-formatted string.

### wallet_history.import_address_book_csv(session_id, csv_data) → dict
Import contacts from CSV. Returns {"imported": N, "skipped": M, "errors": [...]}.

---

## Usage Examples

### JavaScript/Fetch

**Add a transaction:**
```javascript
const response = await fetch('/api/wallet/transaction/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        txid: 'abc123...',
        amount_units: 50000,
        from_address: 'moon1xxxxx',
        to_address: 'moon2yyyyy',
        fee_units: 100,
        memo: 'Payment for lunch',
    })
});
const data = await response.json();
console.log(data);
```

**List transactions:**
```javascript
const response = await fetch('/api/wallet/transactions?limit=20&status=confirmed');
const data = await response.json();
console.log(data.data.transactions);
```

**Add a contact:**
```javascript
const response = await fetch('/api/address-book/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        label: 'Alice',
        address: 'moon1alice',
        category: 'friends',
        notes: 'College friend',
    })
});
const data = await response.json();
console.log(data.data);
```

### Python

**Add a transaction:**
```python
import wallet_history

tx = wallet_history.add_transaction(
    session_id=session_id,
    txid='abc123...',
    direction='send',
    amount_units=50000,
    from_address='moon1xxxxx',
    to_address='moon2yyyyy',
    fee_units=100,
    memo='Payment for lunch',
)
print(tx)
```

**List transactions:**
```python
result = wallet_history.get_transactions(
    session_id=session_id,
    limit=20,
    status='confirmed',
)
for tx in result['transactions']:
    print(tx['txid'], tx['amount_units'])
```

**Add a contact:**
```python
contact = wallet_history.add_contact(
    session_id=session_id,
    label='Alice',
    address='moon1alice',
    category='friends',
    notes='College friend',
)
print(contact)
```

---

## Configuration

Set these environment variables to customize behavior:

- `MOONBITE_WALLET_HISTORY_DB` (default: `wallet_history.db`): Path to SQLite database file
- `TRUSTED_PROXY_COUNT` (default: `1`): Number of reverse-proxy hops to trust for client IP
- `MOONBITE_API_KEYS`: Comma-separated API keys to bypass rate limiting

---

## Implementation Details

### Concurrency & Performance

- **SQLite WAL mode**: Multiple readers can work concurrently without blocking
- **Per-request connections**: Each HTTP request opens and closes its own DB connection
- **Indexes**: Query performance optimized for common filters (session + timestamp, session + status)
- **Unique constraints**: Prevent duplicate transactions and contact labels per session

### Security

- **Session isolation**: All queries filter by user_session_id for multi-user safety
- **Input validation**: All text fields validated for length and content
- **No SQL injection**: Uses parameterized queries throughout
- **Immutable transactions**: Only memo can be edited after creation
- **Rate limiting**: Protects write endpoints from abuse

### Data Retention

- Transaction history and address book persist for the lifetime of the database file
- On ephemeral filesystems (e.g., Railway), data resets on redeploy
- On persistent filesystems (e.g., VPS), data survives restarts

---

## Testing

Run the test suite to verify all functionality:

```bash
python test_wallet_history.py
```

All 19 tests should pass:
- Transaction creation, retrieval, listing, filtering, updating
- Address book CRUD operations
- Category filtering and sorting
- CSV import/export
- Session isolation for both tables
