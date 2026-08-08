# Error Codes Quick Reference

## All Error Codes by Category

### Validation Errors (HTTP 400)

| Error Code | User Message | Use When |
|---|---|---|
| `VALIDATION_INVALID_ADDRESS` | Invalid address format | Address checksum fails or format wrong |
| `VALIDATION_INSUFFICIENT_BALANCE` | Insufficient balance for this transaction | UTXO sum < (amount + fee) |
| `VALIDATION_INVALID_AMOUNT` | Invalid or negative amount specified | Amount <= 0 or exceeds max |
| `VALIDATION_INVALID_MNEMONIC` | Invalid seed phrase (must be valid BIP39 mnemonic) | Mnemonic fails BIP39 validation |
| `VALIDATION_MISSING_FIELD` | Required field is missing from request | txid, address, or amount missing |

### Network/Sync Errors (HTTP 503)

| Error Code | User Message | Use When |
|---|---|---|
| `NETWORK_NOT_SYNCED` | Blockchain is still syncing, please wait | Block height < expected network height |
| `NETWORK_TX_REJECTED` | Transaction was rejected by the network | Mempool rejects tx (nonce, size, etc) |
| `NETWORK_OFFLINE` | Unable to reach the blockchain (offline mode) | Node connection lost |
| `NETWORK_CONNECTION_ERROR` | Connection error, retrying... | API timeout or connection refused |

### Security Errors

| Error Code | User Message | HTTP Status | Use When |
|---|---|---|---|
| `SECURITY_SESSION_EXPIRED` | Session has expired, please reload | 401 | Session cookie invalid/expired |
| `SECURITY_INVALID_PASSWORD` | Incorrect password | 401 | Password verification fails |
| `SECURITY_RATE_LIMITED` | Too many requests, please wait before trying again | 429 | Client exceeds rate limit |

### Storage Errors

| Error Code | User Message | HTTP Status | Use When |
|---|---|---|---|
| `STORAGE_QUOTA_EXCEEDED` | Local storage quota exceeded | 507 | localStorage.setItem() fails |
| `STORAGE_CORRUPTED` | Local data is corrupted, unable to proceed | 500 | Corrupted JSON in cache |

### General Errors

| Error Code | User Message | HTTP Status | Use When |
|---|---|---|---|
| `INTERNAL_ERROR` | An unexpected error occurred | 500 | Unhandled exception |

## Error Response Structure

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

## Quick Decision Tree

```
API Call Made
├─ Network/Connection fails?
│  └─ NETWORK_CONNECTION_ERROR
├─ Response JSON is valid?
│  ├─ No → Network/offline issue
│  │   └─ Check localStorage for cache
│  └─ Yes → Check status field
│     ├─ "error" → Check error_code
│     │  ├─ VALIDATION_* → User input error
│     │  ├─ NETWORK_* → Blockchain sync issue
│     │  ├─ SECURITY_* → Auth issue
│     │  ├─ STORAGE_* → Cache issue
│     │  └─ INTERNAL_ERROR → Server issue
│     └─ "success" → Process response data
```

## Frontend Error Handling Pattern

```javascript
try {
    const response = await fetch(`${API_BASE}/api/...`);
    const data = await response.json();

    if (data.status === 'error') {
        const { error_code, message, action } = data;

        // Handle by error_code
        switch (error_code) {
            case 'VALIDATION_INVALID_ADDRESS':
                // Highlight input field, show message
                break;
            case 'NETWORK_CONNECTION_ERROR':
                // Show retry button, cache fallback
                break;
            case 'SECURITY_SESSION_EXPIRED':
                // Clear session, redirect to login
                break;
            default:
                // Show generic error with message
        }

        // Show user message
        showAlert(`❌ ${message}`, 'danger');

        // Log action for user guidance
        if (action) console.log(`💡 ${action}`);

        return false;
    }

    // Process success response
    return data;
} catch (err) {
    // Network error (no response)
    showAlert(`❌ Network error: ${err.message}`, 'danger');
    return false;
}
```

## Blockchain Status Polling Pattern

```javascript
// Start monitoring
blockchainMonitor = new BlockchainMonitor(30000); // Poll every 30s
blockchainMonitor.start();

// Before risky operations
if (!blockchainMonitor.isHealthy()) {
    showAlert('❌ Blockchain offline or syncing', 'danger');
    return;
}

// Check sync progress
const status = blockchainMonitor.getStatus();
if (status.sync_percentage < 100) {
    console.log(`Syncing: ${status.sync_percentage}%`);
}

// Stop when done
blockchainMonitor.stop();
```

## Common Error Scenarios

### Scenario: User enters invalid address
1. Frontend validates format (basic check)
2. API validates checksum → `VALIDATION_INVALID_ADDRESS`
3. Show: "Invalid address format"
4. Suggest: "Please check the recipient address format"

### Scenario: Network goes offline
1. BlockchainMonitor detects no response → `NETWORK_CONNECTION_ERROR`
2. Status changes to offline (red indicator)
3. Balance loads from cache (shows "Cached" badge)
4. Send button disabled with tooltip
5. On reconnect: auto-updates, removes badge

### Scenario: Session expires
1. User left wallet open > session timeout
2. Next API call → `SECURITY_SESSION_EXPIRED`
3. Clear walletPassword, show unlock screen
4. User re-enters password to unlock

### Scenario: Invalid seed phrase import
1. User enters random words
2. API validates BIP39 → `VALIDATION_INVALID_MNEMONIC`
3. Show: "Invalid seed phrase (must be valid BIP39 mnemonic)"
4. Suggest: "Please check that you entered the seed phrase correctly"
5. User can try again

### Scenario: Insufficient balance
1. User tries to send more than they have
2. API calculates UTXO sum < amount + fee → `VALIDATION_INSUFFICIENT_BALANCE`
3. Show: "Insufficient balance for this transaction"
4. Display: current balance vs requested amount

## Testing Error Codes

### Generate VALIDATION_INVALID_ADDRESS
```bash
curl -X POST http://localhost:5000/api/wallet/transaction/send \
  -H "Content-Type: application/json" \
  -d '{"txid":"x","amount_units":1000000,"from_address":"bad","to_address":"bad"}'
```

### Generate VALIDATION_MISSING_FIELD
```bash
curl -X POST http://localhost:5000/api/wallet/hd/import \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Generate VALIDATION_INVALID_MNEMONIC
```bash
curl -X POST http://localhost:5000/api/wallet/hd/import \
  -H "Content-Type: application/json" \
  -d '{"mnemonic":"one two three four five"}'
```

### Generate NETWORK_CONNECTION_ERROR
```bash
# Throttle network in DevTools or:
timeout 1 curl http://localhost:5000/api/wallet/balance
```

### Generate SECURITY_SESSION_EXPIRED
```javascript
// Clear session cookie and try API call
document.cookie = 'session=; expires=Thu, 01 Jan 1970 00:00:00 UTC;';
await fetch(`${API_BASE}/api/wallet/hd/address`);
```

### View debug info
```bash
curl 'http://localhost:5000/api/wallet/balance?debug=true'
```

## Integration Checklist

- [ ] All endpoints use json_error() for exceptions
- [ ] error_code used for frontend logic (not message)
- [ ] User messages are displayed to users
- [ ] Actions/suggestions shown when relevant
- [ ] Debug info logged in development
- [ ] BlockchainMonitor started on page load
- [ ] Balance cached to localStorage
- [ ] Send button disabled when offline
- [ ] Offline warning banner implemented
- [ ] Status tooltip shows detailed info
- [ ] Connection indicator updates every 30s
- [ ] Cache recovers on reconnection

## Performance Notes

- **Error Response Time**: < 1ms (deterministic)
- **BlockchainMonitor Poll**: 30s interval (configurable)
- **localStorage Size**: ~500 bytes per cache entry
- **No memory leaks**: All intervals cleared on stop()

## Security Notes

- Debug info only shown when debug=true or FLASK_DEBUG=1
- Never expose internal stack traces to users
- error_codes are static (no dynamic content)
- Messages can be localized without code changes
- Rate limiting still enforced on SECURITY_RATE_LIMITED errors
