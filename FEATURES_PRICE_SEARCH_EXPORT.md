# MoonBite Wallet: Price Ticker, Transaction Search & CSV Export

## Overview

This implementation adds three major features to the MoonBite wallet PWA:

1. **Price Ticker** - Real-time MBITE price display with 24h history
2. **Transaction Search** - Full-text and advanced filtering for transaction history
3. **CSV Export** - Export transaction history in CSV or JSON format

---

## 1. Price Ticker

### Backend: `price_feed.py`

#### Functions

**`get_price() -> dict`**
- Fetches current MBITE price with caching (15-minute TTL)
- Falls back to demo price if exchange fetch fails
- Returns: `{price_usd, change_24h, high_24h, low_24h, market_cap, volume_24h, timestamp}`

**`get_price_history(hours=24) -> dict`**
- Returns price history for specified hours (1-720 supported)
- Generates synthetic data based on current price
- Returns: `{prices: [{timestamp, price_usd}, ...], count, start_timestamp, end_timestamp}`

**`clear_cache()`**
- Manually clears the price cache (for testing)

#### Demo Implementation

Currently uses hardcoded demo prices:
- MBITE: $45.67
- 24h Change: +2.5%
- High: $48.32, Low: $43.21
- Market Cap: $9.1B, Volume: $45.6M

**To integrate real exchange data**, modify `_fetch_from_exchange()`:

```python
# Example: CoinGecko API integration
import requests
def _fetch_from_exchange():
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "moonbite",
                "vs_currencies": "usd",
                "include_market_cap": "true",
                "include_24h_vol": "true",
                "include_24h_change": "true"
            },
            timeout=5
        )
        data = resp.json().get("moonbite", {})
        return {
            "price_usd": data.get("usd", 0),
            "change_24h": data.get("usd_24h_change", 0),
            "market_cap": data.get("usd_market_cap", 0),
            "volume_24h": data.get("usd_24h_vol", 0),
            "timestamp": int(time.time()),
        }
    except Exception as e:
        return None
```

### API Endpoints

**`GET /api/price/mbite`**
```json
{
  "status": "success",
  "data": {
    "price_usd": 45.67,
    "change_24h": 2.5,
    "high_24h": 48.32,
    "low_24h": 43.21,
    "market_cap": 9134000000,
    "volume_24h": 45600000,
    "timestamp": 1705332600
  }
}
```

**`GET /api/price/mbite/history?hours=24`**
```json
{
  "status": "success",
  "data": {
    "prices": [
      {"timestamp": 1705249200, "price_usd": 43.21},
      {"timestamp": 1705252800, "price_usd": 43.45},
      ...
    ],
    "count": 24,
    "start_timestamp": 1705249200,
    "end_timestamp": 1705332600
  }
}
```

### Frontend: `wallet-pwa.html`

**PriceTickerManager Class**
- Manages price fetching and caching with localStorage
- 5-minute client-side cache TTL
- Draws simple line chart for 24h price history
- Updates display with trend indicators (📈/📉)

**UI Components**
- Price ticker in dashboard (💰 Price button)
- Modal showing detailed price information
- 24h price chart canvas
- Color-coded change indicator (green for +, red for -)

**Usage**
```javascript
// Fetch and display price details
await priceTickerManager.showDetails();

// Manual price fetch
const price = await priceTickerManager.fetchPrice();
```

---

## 2. Transaction Search

### Backend: `wallet_history.py`

**`search_transactions(session_id, query, filters...) -> dict`**

Supports comprehensive search and filtering:

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Text search (txid, addresses, memo) |
| `amount_min` | int | Minimum amount in base units |
| `amount_max` | int | Maximum amount in base units |
| `date_from` | int | Start timestamp (unix) |
| `date_to` | int | End timestamp (unix) |
| `status` | str | 'pending', 'confirmed', or 'failed' |
| `direction` | str | 'send' or 'receive' |
| `limit` | int | Records per page (1-100, default 20) |
| `offset` | int | Pagination offset (default 0) |

Returns:
```python
{
    "transactions": [...],  # Matching transaction records
    "total": 42,           # Total matching count
    "limit": 20,
    "offset": 0,
    "query": "search_text"
}
```

### API Endpoint

**`GET /api/wallet/transactions/search`**

Query parameters:
```
q=moon1abc          # Text search
amount_min=1000     # Min amount (base units, 1 MBITE = 100 units)
amount_max=50000    # Max amount
date_from=1705249200
date_to=1705332600
status=confirmed    # 'pending', 'confirmed', 'failed'
direction=send      # 'send' or 'receive'
limit=20
offset=0
```

Example:
```bash
curl "http://localhost:5000/api/wallet/transactions/search?q=moon1&status=confirmed&amount_min=1000&amount_max=100000"
```

Response:
```json
{
  "status": "success",
  "data": {
    "transactions": [
      {
        "id": 1,
        "txid": "abc123...",
        "direction": "send",
        "amount_units": 250000,
        "status": "confirmed",
        "from_address": "moon1sender",
        "to_address": "moon1recipient",
        "memo": "Payment",
        "timestamp": 1705330000
      }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0,
    "query": "moon1"
  }
}
```

### Frontend: `wallet-pwa.html`

**TransactionSearchManager Class**
- Builds parameterized search queries
- Displays results with formatting
- Supports filter persistence

**UI Components**
- Search modal with advanced filters
- Status, type, amount, and date range filters
- Real-time result display with count
- Result previews showing txid, direction, and status

**Usage**
```javascript
// Open search modal
document.getElementById('transactionSearchModal').classList.add('active');

// Execute search
await transactionSearchManager.search();

// Clear filters
transactionSearchManager.clearFilters();
```

---

## 3. CSV & JSON Export

### Backend: `wallet_history.py`

**`export_transactions_csv(session_id, date_from, date_to, include_fees, include_memo) -> str`**

Exports transactions with:
- ISO 8601 timestamps
- Transaction type (Send/Receive)
- Relevant address (to for sends, from for receives)
- Amount in MBITE (base units / 100)
- Optional fee column
- Optional memo column
- Summary rows with totals and net

Example CSV output:
```csv
Date,Type,Address,Amount,Fee,Status,TXID,Memo
2026-08-08T12:34:56,Send,moon1recipient,2.50000000,0.00050000,Confirmed,abc123...,"Payment"
2026-08-08T12:45:00,Receive,moon1sender,1.00000000,0.00000000,Confirmed,def456...,""

Summary
Total Sent,2.50000000
Total Received,1.00000000
Total Fees,0.00050000
Net,-1.50000000
```

### API Endpoints

**`GET /api/wallet/transactions/export`**

Query parameters:
```
format=csv           # 'csv' or 'json' (default 'csv')
date_from=1705249200 # Optional
date_to=1705332600   # Optional
include_fees=true    # Include fee column (default true)
include_memo=true    # Include memo column (default true)
```

Returns:
- **CSV**: Direct file download with `Content-Disposition: attachment`
- **JSON**: Paginated transaction list as JSON file

Example:
```bash
curl "http://localhost:5000/api/wallet/transactions/export?format=csv&include_fees=true" > transactions.csv
```

### Frontend: `wallet-pwa.html`

**ExportModal**
- Format selector (CSV/JSON)
- Date range picker (optional, all if not specified)
- Checkboxes to include/exclude fees and memo
- Automatic file download with timestamped filename

**Usage**
```javascript
// Open export modal
document.getElementById('exportModal').classList.add('active');

// Triggered by "Export" button
// Downloads: transactions_YYYY-MM-DD.csv
```

---

## localStorage Caching

### Price Cache
- Key: `moonbite_price_cache`
- TTL: 5 minutes
- Stores: `{data: {...}, timestamp}`

### Search Results
- Cached automatically by browser HTTP caching
- Consider implementing per-session cache for frequently used filters

---

## Data Flow

### Price Display
```
Dashboard Load
    ↓
priceTickerManager.fetchPrice()
    ↓
Check localStorage cache (5min TTL)
    ↓
[Cache Hit] → Return cached price
[Cache Miss] → GET /api/price/mbite
    ↓
[Success] → Cache result, update UI
[Fail] → Fall back to cached, show demo price
    ↓
Update header with "💰 Price" button
```

### Transaction Search
```
User clicks "🔍 Search" button
    ↓
Open transactionSearchModal
    ↓
User sets filters & clicks "Search"
    ↓
transactionSearchManager.search()
    ↓
Build query params → GET /api/wallet/transactions/search
    ↓
Server queries SQLite with WHERE clauses
    ↓
Return results with pagination
    ↓
Display in modal with formatting
```

### CSV Export
```
User clicks "📥 Export" button
    ↓
Open exportModal
    ↓
User selects format, date range, options
    ↓
Click "Export"
    ↓
GET /api/wallet/transactions/export?...
    ↓
Server builds CSV/JSON
    ↓
Download file: transactions_YYYY-MM-DD.{csv,json}
```

---

## Database Indices

The following indices support efficient search:

```sql
idx_transactions_session_time      -- (user_session_id, timestamp DESC)
idx_transactions_session_status    -- (user_session_id, status)
idx_transactions_txid              -- (txid)
idx_transactions_account           -- (user_session_id, account_id)
```

Full-text search on `(txid, from_address, to_address, memo)` uses LIKE queries.
For large datasets (10k+ transactions), consider adding FTS (Full-Text Search).

---

## Performance Considerations

1. **Price Updates**: 5-minute client cache + 15-minute server cache
   - Minimizes API calls
   - Stale data acceptable for price ticker

2. **Search Queries**: Limited to 100 results per page
   - Server-side pagination prevents large result sets
   - Date range filters reduce query scope

3. **CSV Export**: Loads all matching transactions into memory
   - OK for < 100k transactions
   - Consider streaming for larger exports

---

## Error Handling

### Price Fetch Failures
- Falls back to cached price
- Shows demo price if cache empty
- No user-facing error (graceful degradation)

### Search Errors
- Returns `{"status": "error", "message": "..."}` with 400/500 status
- Frontend displays user-friendly error message
- Search results cleared on error

### Export Errors
- Returns error JSON with description
- User sees modal error message
- No file downloaded on failure

---

## Testing

Run the test suites:

```bash
# Test price feed
python test_price_feed.py

# Test search and export
python test_transaction_features.py
```

Both test suites verify:
- ✅ Caching mechanisms
- ✅ Search filters individually and combined
- ✅ CSV format and structure
- ✅ Date range filtering
- ✅ Summary calculations

---

## Future Enhancements

1. **Real Exchange Integration**
   - CoinGecko API integration
   - Kraken/Binance WebSocket for live updates
   - Historical price archive (>24h)

2. **Advanced Search**
   - Full-text search with ranking
   - Saved filter presets
   - Search history/autocomplete

3. **Export Formats**
   - Excel (.xlsx) with formatting
   - QIF for accounting software
   - PDF reports with charts

4. **Analytics**
   - Portfolio performance charts
   - Tax report generation
   - Transaction categorization

5. **Mobile Optimization**
   - Swipe to access price/search/export
   - Floating price ticker widget
   - Bottom sheet modals for export

---

## API Summary Table

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/price/mbite` | GET | Current price |
| `/api/price/mbite/history` | GET | 24h price history |
| `/api/wallet/transactions/search` | GET | Search with filters |
| `/api/wallet/transactions/export` | GET | Export CSV/JSON |

All endpoints require session cookie (auto-managed by wallet).
All responses use consistent JSON format: `{status, data/message}`.

---

## Integration Checklist

- [x] price_feed.py module created
- [x] wallet_history.py extended with search & export
- [x] Flask API routes added to web_app.py
- [x] HTML modals added to wallet-pwa.html
- [x] JavaScript managers implemented
- [x] UI buttons added to dashboard
- [x] localStorage caching implemented
- [x] Tests created and passing
- [ ] Exchange API key configured (if using real prices)
- [ ] Production deployment

---

## File Changes Summary

### New Files
- `/price_feed.py` - Price fetching and caching logic
- `/test_price_feed.py` - Price feed tests
- `/test_transaction_features.py` - Search and export tests

### Modified Files
- `/web_app.py` - Added price and transaction export endpoints
- `/wallet_history.py` - Added search_transactions() and export_transactions_csv()
- `/templates/wallet-pwa.html` - Added 3 new modals and JavaScript managers

### No Breaking Changes
- All existing APIs preserved
- Backward compatible with current wallet state
- New features are opt-in (buttons in UI)

