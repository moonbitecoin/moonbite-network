# Error Handling & Offline Mode - Quick Start Guide

## TL;DR

Error handling and offline mode have been implemented. Everything works automatically with no configuration needed.

**Start the wallet:**
```bash
python web_app.py
```

**Open in browser:**
```
http://localhost:5000/wallet
```

## What You'll See

### Connection Indicator (Top Right)
- 🟢 **Green** = Blockchain synced, all good
- 🟡 **Yellow** = Blockchain syncing (pulsing)
- 🔴 **Red** = Offline or disconnected (pulsing)

**Click the indicator** for detailed sync info (tooltip).

### When Offline
1. Red warning banner appears: "⚠️ Using cached data..."
2. Balance shows "Cached" badge
3. Send button becomes disabled
4. Everything recovers automatically when connection restored

## Testing Offline Mode (60 seconds)

### Browser DevTools Method (Easiest)
1. Open wallet: http://localhost:5000/wallet
2. Press F12 (DevTools)
3. Go to **Network tab**
4. Find the dropdown menu at top (usually shows "No throttling")
5. Select **Offline**
6. Watch what happens:
   - Connection indicator turns RED
   - Warning banner appears
   - Balance shows "Cached" badge
   - Send button disables
7. Select **Online** again
   - Everything recovers automatically in ~30 seconds

### Without DevTools
```bash
# Unplug network cable or disable WiFi
# Wait 30 seconds for detection
# See connection indicator turn red
# Re-enable network to see recovery
```

## Quick API Tests

### Test Error: Invalid Address
```bash
curl -X POST http://localhost:5000/api/wallet/transaction/send \
  -H "Content-Type: application/json" \
  -d '{
    "txid": "test",
    "amount_units": 1000,
    "from_address": "bad",
    "to_address": "bad"
  }'
```

Expected response:
```json
{
  "status": "error",
  "error_code": "VALIDATION_INVALID_ADDRESS",
  "message": "Sender address is invalid",
  "action": "Please check the sender address"
}
```

### Test Error: Invalid Mnemonic
```bash
curl -X POST http://localhost:5000/api/wallet/hd/import \
  -H "Content-Type: application/json" \
  -d '{"mnemonic": "bad seed"}'
```

Expected response:
```json
{
  "status": "error",
  "error_code": "VALIDATION_INVALID_MNEMONIC",
  "message": "Invalid seed phrase (must be valid BIP39 mnemonic)",
  "action": "Please check that you entered the seed phrase correctly"
}
```

### Test Blockchain Status
```bash
curl http://localhost:5000/api/blockchain/status
```

Expected response:
```json
{
  "status": "success",
  "is_synced": true,
  "current_height": 12345,
  "sync_percentage": 100.0,
  "blockchain_healthy": true,
  "timestamp": 1691234567.89
}
```

## Error Codes at a Glance

| Code | HTTP | Meaning |
|------|------|---------|
| `VALIDATION_INVALID_ADDRESS` | 400 | Address format wrong |
| `VALIDATION_INVALID_AMOUNT` | 400 | Amount is invalid/negative |
| `VALIDATION_MISSING_FIELD` | 400 | Required field missing |
| `VALIDATION_INVALID_MNEMONIC` | 400 | Seed phrase not valid BIP39 |
| `NETWORK_OFFLINE` | 503 | No blockchain connection |
| `NETWORK_CONNECTION_ERROR` | 503 | Connection timeout/error |
| `SECURITY_SESSION_EXPIRED` | 401 | Session ended |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

**See ERROR_CODES_REFERENCE.md for complete list**

## Developer Quick Links

| Need | File |
|------|------|
| Understand error format | ERROR_HANDLING_GUIDE.md |
| List all error codes | ERROR_CODES_REFERENCE.md |
| Test everything | TESTING_OFFLINE_MODE.md |
| How to use json_error() | web_app.py (search: "def json_error") |
| How to check blockchain status | templates/wallet-pwa.html (search: "BlockchainMonitor") |

## Key Files Modified

```
web_app.py                  - Error handling + blockchain status endpoint
templates/wallet-pwa.html   - Offline mode UI + BlockchainMonitor class
```

## Features at a Glance

✅ All API errors standardized with `error_code` field
✅ User-friendly error messages with suggested actions
✅ Blockchain sync monitoring (polls every 30 seconds)
✅ Visual connection indicator (green/yellow/red)
✅ Balance caching for offline access
✅ Automatic send button disabling when offline
✅ Warning banner when using cached data
✅ Auto-recovery when connection restored
✅ No configuration needed - works out of the box

## Common Questions

### Q: Why is the Send button disabled?
**A:** Blockchain is offline or syncing. Wait for green indicator and try again.

### Q: Why does my balance show "Cached"?
**A:** Network is offline. The balance was loaded from your device storage. It will update automatically when connection restored.

### Q: Can I send transactions offline?
**A:** No, transactions require blockchain connection. The Send button is disabled to prevent confusion. When online, the button will be enabled.

### Q: How often does it check blockchain status?
**A:** Every 30 seconds. You can change this in `wallet-pwa.html` (line: `new BlockchainMonitor(30000)`)

### Q: Will cached data be lost?
**A:** No. Cache stays in browser localStorage until cleared. It persists across page reloads.

### Q: Can I see debug information?
**A:** Yes! Add `?debug=true` to API call URLs:
```bash
curl 'http://localhost:5000/api/wallet/balance?debug=true'
```

Or set environment variable:
```bash
export FLASK_DEBUG=1
python web_app.py
```

### Q: What if I find a bug?
**A:** Check TESTING_OFFLINE_MODE.md for troubleshooting steps. The most common issues:
- BlockchainMonitor not detecting offline: Check DevTools Network tab for `blockchain/status` requests
- "Cached" badge not showing: Verify balance is cached: `localStorage.getItem('moonbite_balance_cache')`
- Connection indicator not updating: Check if monitor started: `blockchainMonitor.pollTimer`

## 5-Minute Setup

1. **Start server:**
   ```bash
   python web_app.py
   ```

2. **Open wallet:**
   ```
   http://localhost:5000/wallet
   ```

3. **Test offline mode:**
   - Open DevTools (F12)
   - Network tab → Offline mode
   - Watch indicator turn red
   - See warning banner and cached balance
   - Switch back to Online
   - See recovery in ~30 seconds

4. **Test error handling:**
   ```bash
   curl -X POST http://localhost:5000/api/wallet/transaction/send \
     -H "Content-Type: application/json" \
     -d '{"txid":"x","amount_units":1000,"from_address":"bad","to_address":"bad"}'
   ```

   See standardized error response with `error_code` field

5. **View blockchain status:**
   ```bash
   curl http://localhost:5000/api/blockchain/status
   ```

   See sync info including `is_synced`, `current_height`, `sync_percentage`

## What's Automatic

These features require **zero configuration**:

- ✅ Error standardization on all endpoints
- ✅ Blockchain status monitoring (30s polls)
- ✅ Connection indicator updates
- ✅ Offline warning banner
- ✅ Balance caching
- ✅ Send button disabling
- ✅ Auto-recovery on reconnect

Just start the app and it works!

## Next Steps

1. **For users**: Test offline mode, try sending transactions
2. **For developers**: Review ERROR_HANDLING_GUIDE.md for integration patterns
3. **For QA**: Use TESTING_OFFLINE_MODE.md for comprehensive testing
4. **For DevOps**: Set FLASK_DEBUG=1 if you need debug info in errors

## Need Help?

- **Error codes**: ERROR_CODES_REFERENCE.md
- **How to integrate**: ERROR_HANDLING_GUIDE.md
- **Testing procedures**: TESTING_OFFLINE_MODE.md
- **Implementation details**: IMPLEMENTATION_SUMMARY.md
- **Full implementation**: This file, web_app.py, wallet-pwa.html

---

**Status**: ✅ Ready to use
**Test Time**: 5 minutes
**Configuration Required**: None
**Breaking Changes**: None (backward compatible)
