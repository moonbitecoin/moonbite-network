# Error Handling & Offline Mode Implementation Guide

## Overview

This document describes the comprehensive error handling and offline mode features implemented for the MoonBite wallet. These features improve user experience by providing clear error messages, detecting network issues, and enabling offline operation with cached data.

## 1. Error Standardization

### Error Response Format

All API errors now follow a standard format:

```json
{
  "status": "error",
  "error_code": "VALIDATION_INVALID_ADDRESS",
  "message": "Invalid address format",
  "action": "Please check the recipient address format",
  "timestamp": 1691234567.89,
  "debug": "Address validation failed: checksum mismatch"
}
```

**Response Fields:**
- `status`: Always "error" for error responses
- `error_code`: Machine-readable error identifier (e.g., VALIDATION_INVALID_ADDRESS)
- `message`: User-friendly error message suitable for display
- `action`: Suggested recovery action (optional)
- `timestamp`: Server-provided timestamp for logging/debugging
- `debug`: Developer information (only when debug=true or FLASK_DEBUG=1)

### Using json_error() Helper

In `web_app.py`, use the `json_error()` function to create standardized errors:

```python
from web_app import json_error

# Basic error
return json_error("VALIDATION_INVALID_AMOUNT")

# With custom message override
return json_error(
    "VALIDATION_INVALID_AMOUNT",
    user_message="Amount must be positive and less than your balance"
)

# With debug info (shown only when ?debug=true)
return json_error(
    "NETWORK_CONNECTION_ERROR",
    debug_message="Connection timeout after 30s",
    suggested_action="Please wait and try again"
)
```

### Error Code Categories

#### Validation Errors (400 - Bad Request)
- `VALIDATION_INVALID_ADDRESS` - Address format is invalid
- `VALIDATION_INSUFFICIENT_BALANCE` - Not enough funds
- `VALIDATION_INVALID_AMOUNT` - Amount is invalid or negative
- `VALIDATION_INVALID_MNEMONIC` - Seed phrase is not valid BIP39
- `VALIDATION_MISSING_FIELD` - Required field missing from request

#### Network/Sync Errors (503 - Service Unavailable)
- `NETWORK_NOT_SYNCED` - Blockchain still syncing
- `NETWORK_TX_REJECTED` - Transaction rejected by network
- `NETWORK_OFFLINE` - Unable to reach blockchain (offline)
- `NETWORK_CONNECTION_ERROR` - Connection/timeout error

#### Security Errors (401 - Unauthorized / 429 - Too Many Requests)
- `SECURITY_SESSION_EXPIRED` - Session ended, needs re-auth
- `SECURITY_INVALID_PASSWORD` - Wrong password
- `SECURITY_RATE_LIMITED` - Too many requests

#### Storage Errors (507 - Insufficient Storage)
- `STORAGE_QUOTA_EXCEEDED` - LocalStorage full
- `STORAGE_CORRUPTED` - Data corruption detected

#### Internal Error (500 - Server Error)
- `INTERNAL_ERROR` - Unexpected server error

## 2. Offline Mode Implementation

### BlockchainMonitor Class

The `BlockchainMonitor` class in `wallet-pwa.html` continuously monitors blockchain sync status:

```javascript
// Initialize (auto-starts polling)
blockchainMonitor = new BlockchainMonitor(30000); // Poll every 30 seconds
blockchainMonitor.start();

// Check if blockchain is healthy
if (blockchainMonitor.isHealthy()) {
    // Safe to send transactions
}

// Get current status
const status = blockchainMonitor.getStatus();
console.log(status.is_synced, status.current_height, status.sync_percentage);

// Stop monitoring
blockchainMonitor.stop();
```

### BlockchainStatus Response

The `/api/blockchain/status` endpoint returns:

```json
{
  "status": "success",
  "is_synced": true,
  "current_height": 12345,
  "peers_connected": 8,
  "blocks_behind": 0,
  "sync_percentage": 100.0,
  "last_block_time": 1691234500,
  "blockchain_healthy": true,
  "estimated_sync_seconds": 0,
  "timestamp": 1691234567.89
}
```

**Fields:**
- `is_synced`: True if fully synced to network
- `current_height`: Current block height
- `peers_connected`: Number of connected peers
- `blocks_behind`: How many blocks behind network
- `sync_percentage`: Sync progress (0-100)
- `last_block_time`: Unix timestamp of last block
- `blockchain_healthy`: True if sync is progressing normally
- `estimated_sync_seconds`: Seconds until synced (-1 if unknown)

### Connection Indicator (Header)

The wallet displays a connection status indicator in the header:

**States:**
- 🟢 **Green (Synced)**: Blockchain is fully synced and healthy
- 🟡 **Yellow (Syncing)**: Blockchain is syncing, progress visible in tooltip
- 🔴 **Red (Offline)**: Blockchain is offline or disconnected

**Interactions:**
- Click indicator to see detailed tooltip
- Tooltip shows: status, height, progress %, time since last block
- Automatically updates every 30 seconds

### Offline Warning Banner

When blockchain is offline or syncing:
- Red warning banner appears below header
- Message: "Using cached data. Blockchain is offline or syncing."
- Dismissible with close button (⊗)
- Auto-recovers when connection restored

### Balance Caching

When blockchain is offline, the wallet:

1. **Loads from Cache**
   ```javascript
   localStorage.getItem('moonbite_balance_cache')
   // Returns: {balance_coins: 12.5, updated_at: 1691234567, is_stale: false}
   ```

2. **Shows "Cached" Badge**
   - Appears next to balance amount
   - Indicates data is not fresh
   - Yellow warning color

3. **Auto-Updates on Recovery**
   - When connection restored, fetches fresh balance
   - Removes "Cached" badge
   - Updates localStorage

### Disabling Send When Offline

The Send button is automatically disabled when:
- Blockchain is not synced
- Connection is lost
- Trying to send shows error: "Blockchain is offline or syncing. Please wait and try again."

## 3. Updated Endpoints

### Wallet Endpoints

#### POST /api/wallet/new
**Success (200):**
```json
{
  "status": "success",
  "address": "moonbc1...",
  "pubkey_hash": "abc123...",
  "pubkey": "def456..."
}
```

**Error (500):**
```json
{
  "status": "error",
  "error_code": "INTERNAL_ERROR",
  "message": "An unexpected error occurred",
  "action": "Please try again or reload the page",
  "debug": "KeyError: 'params'"
}
```

#### GET /api/wallet/balance
**Success (200):**
```json
{
  "status": "success",
  "balance_coins": 12.5,
  "balance_units": 1250000000,
  "balance_display": "12.5",
  "utxo_count": 3
}
```

**Error (503):**
```json
{
  "status": "error",
  "error_code": "NETWORK_CONNECTION_ERROR",
  "message": "Connection error, retrying...",
  "action": "Please wait and try again"
}
```

#### POST /api/wallet/hd/import
**Success (200):**
```json
{
  "status": "success",
  "message": "Wallet recovered from mnemonic. Use /api/wallet/hd/address to generate addresses."
}
```

**Error - Missing Field (400):**
```json
{
  "status": "error",
  "error_code": "VALIDATION_MISSING_FIELD",
  "message": "Seed phrase is required",
  "action": "Please enter your 12 or 24 word seed phrase"
}
```

**Error - Invalid Mnemonic (400):**
```json
{
  "status": "error",
  "error_code": "VALIDATION_INVALID_MNEMONIC",
  "message": "Invalid seed phrase (must be valid BIP39 mnemonic)",
  "action": "Please check that you entered the seed phrase correctly",
  "debug": "ValueError: Invalid mnemonic checksum"
}
```

#### POST /api/wallet/transaction/send
**Validation Errors (400):**

Missing txid:
```json
{
  "status": "error",
  "error_code": "VALIDATION_MISSING_FIELD",
  "message": "Transaction ID is required"
}
```

Invalid amount:
```json
{
  "status": "error",
  "error_code": "VALIDATION_INVALID_AMOUNT",
  "message": "Amount must be greater than zero",
  "action": "Please check the amount and try again"
}
```

Invalid address:
```json
{
  "status": "error",
  "error_code": "VALIDATION_INVALID_ADDRESS",
  "message": "Recipient address is invalid",
  "action": "Please check the recipient address format"
}
```

**Success (201):**
```json
{
  "status": "success",
  "transaction": {
    "id": 123,
    "txid": "abc123...",
    "direction": "send",
    "amount_units": 1000000,
    "from_address": "moon1...",
    "to_address": "moon2...",
    "fee_units": 1000,
    "status": "pending",
    "timestamp": "2024-08-08T10:30:00Z"
  }
}
```

### Blockchain Endpoints

#### GET /api/blockchain/info
**Success (200):**
```json
{
  "status": "success",
  "height": 12345,
  "tip_hash": "abc123...",
  "total_money_satoshis": 1250000000,
  "total_money_coins": 12.5,
  "tx_count": 456,
  "mempool_size": 10,
  "bits": 524288,
  "difficulty": 281474976710656
}
```

**Error (503):**
```json
{
  "status": "error",
  "error_code": "NETWORK_CONNECTION_ERROR",
  "message": "Connection error, retrying...",
  "action": "Please try again"
}
```

#### GET /api/blockchain/status
**Success (200):**
```json
{
  "status": "success",
  "is_synced": true,
  "current_height": 12345,
  "peers_connected": 8,
  "blocks_behind": 0,
  "sync_percentage": 100.0,
  "last_block_time": 1691234500,
  "blockchain_healthy": true,
  "estimated_sync_seconds": 0,
  "timestamp": 1691234567.89
}
```

**Offline Error (503):**
```json
{
  "status": "error",
  "is_synced": false,
  "current_height": 0,
  "peers_connected": 0,
  "blocks_behind": -1,
  "sync_percentage": 0,
  "last_block_time": 0,
  "blockchain_healthy": false,
  "estimated_sync_seconds": -1,
  "timestamp": 1691234567.89
}
```

## 4. Frontend Implementation Details

### Error Handling in Fetch Calls

```javascript
try {
    const response = await fetch(`${API_BASE}/api/wallet/balance`);
    const data = await response.json();

    if (data.status === 'error') {
        // Handle standard error response
        showAlert(`❌ ${data.message}`, 'danger');
        if (data.action) {
            console.log(`Suggested action: ${data.action}`);
        }
        return;
    }

    // Process success response
    updateUI(data);
} catch (err) {
    // Network/fetch error (not JSON error)
    showAlert(`❌ Network error: ${err.message}`, 'danger');
}
```

### Checking Blockchain Status Before Operations

```javascript
// Before sending a transaction
if (!blockchainMonitor.isHealthy()) {
    showAlert('❌ Blockchain is offline or syncing. Please wait and try again.', 'danger');
    return;
}

// Get detailed status for UI
const status = blockchainMonitor.getStatus();
if (status.sync_percentage < 100) {
    showAlert(`⏳ Syncing: ${status.sync_percentage}%`, 'warning');
    return;
}
```

### Accessing Debug Information

To view debug information in API responses, append `?debug=true`:

```javascript
// Enable debug mode
const response = await fetch(`${API_BASE}/api/wallet/balance?debug=true`);
const data = await response.json();
console.log('Debug info:', data.debug);
```

Or set environment variable:
```bash
export FLASK_DEBUG=1
python web_app.py
```

## 5. Local Storage Schema

### blockchain_status
```json
{
  "is_synced": true,
  "current_height": 12345,
  "sync_percentage": 100.0,
  "last_block_time": 1691234500,
  "blockchain_healthy": true,
  "cached_at": 1691234567890
}
```

### balance_cache
```json
{
  "balance_coins": 12.5,
  "updated_at": 1691234567,
  "is_stale": false
}
```

## 6. Testing Error Handling

### Test Invalid Address

```bash
curl -X POST http://localhost:5000/api/wallet/transaction/send \
  -H "Content-Type: application/json" \
  -d '{
    "txid": "abc123",
    "amount_units": 1000000,
    "from_address": "invalid",
    "to_address": "also_invalid"
  }'
```

Expected error:
```json
{
  "status": "error",
  "error_code": "VALIDATION_INVALID_ADDRESS",
  "message": "Sender address is invalid",
  "action": "Please check the sender address"
}
```

### Test Invalid Mnemonic

```bash
curl -X POST http://localhost:5000/api/wallet/hd/import \
  -H "Content-Type: application/json" \
  -d '{"mnemonic": "invalid seed phrase"}'
```

Expected error:
```json
{
  "status": "error",
  "error_code": "VALIDATION_INVALID_MNEMONIC",
  "message": "Invalid seed phrase (must be valid BIP39 mnemonic)",
  "action": "Please check that you entered the seed phrase correctly"
}
```

### Test Offline Mode

1. Open wallet in browser
2. Go to DevTools Network tab
3. Set throttling to "Offline"
4. Try to perform operations
5. See offline warning banner
6. Observe Send button disabled
7. Notice balance shows "Cached"
8. Restore connection to see recovery

## 7. Deployment Considerations

### Environment Variables

```bash
# Enable debug mode (shows debug field in errors)
export FLASK_DEBUG=1

# Set max request body size
export MOONBITE_MAX_BODY_BYTES=262144

# Enable specific API keys
export MOONBITE_API_KEYS="key1,key2,key3"
```

### Production Best Practices

1. **Never enable debug mode in production** - exposes internal details
2. **Use error_code for frontend handling** - don't parse message text
3. **Log error_code and timestamp** - helps with debugging
4. **Implement retry logic** - for NETWORK_* errors
5. **Cache responses** - use localStorage for availability
6. **Monitor error rates** - track spike in NETWORK_CONNECTION_ERROR

## 8. Future Enhancements

- [ ] Add exponential backoff for retry logic
- [ ] Implement transaction queue for offline mode
- [ ] Add push notifications for sync completion
- [ ] Create error analytics dashboard
- [ ] Add multilingual error messages
- [ ] Implement auto-recovery patterns
- [ ] Add network latency indicators
- [ ] Create error rate monitoring

## Summary

This implementation provides:
- **Consistent error format** across all endpoints
- **User-friendly messages** that suggest actions
- **Debug information** for developers when needed
- **Offline detection** with visual indicators
- **Balance caching** for offline access
- **Operation restrictions** when offline
- **Auto-recovery** when connection restored

All features work together to create a resilient, user-friendly wallet experience that gracefully handles network issues and provides clear guidance to users.
