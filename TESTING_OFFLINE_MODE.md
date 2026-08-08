# Testing Offline Mode and Error Handling

## Setup

### Prerequisites
```bash
# Python 3.8+
python --version

# Start the MoonBite wallet server
python web_app.py

# Default runs on http://localhost:5000
```

### Browser Tools
- Chrome/Edge DevTools (F12)
- Network tab for throttling
- Console tab for logs
- Application tab for localStorage

## Testing Scenarios

### 1. Blockchain Status Monitoring

#### Test 1.1: Status Polling Every 30 Seconds
1. Open wallet: http://localhost:5000/wallet
2. Open DevTools → Network tab
3. Filter for `blockchain/status` requests
4. **Expected**: Request every ~30 seconds
5. **Response**: Full sync status with current_height, sync_percentage, etc.

**Verification:**
```javascript
// In DevTools Console
blockchainMonitor.getStatus()
// Should output:
// {
//   is_synced: true,
//   current_height: 12345,
//   sync_percentage: 100,
//   blockchain_healthy: true,
//   ...
// }
```

#### Test 1.2: Status Caching
1. Wallet open, blockchain synced (green indicator)
2. Open DevTools → Application → LocalStorage
3. Find key: `moonbite_blockchain_status`
4. **Expected**: Object with is_synced, current_height, cached_at timestamp

**Verification:**
```javascript
// In DevTools Console
const cached = JSON.parse(localStorage.getItem('moonbite_blockchain_status'));
console.log('Cached at:', new Date(cached.cached_at));
console.log('Synced:', cached.is_synced);
```

### 2. Connection Indicator States

#### Test 2.1: Green Indicator (Synced)
1. Wallet fully synced
2. Look at header indicator (right side)
3. **Expected**: Green dot with "Synced" text
4. Click indicator
5. **Expected**: Tooltip shows "Status: Synced", "Progress: 100%"

#### Test 2.2: Yellow Indicator (Syncing)
*Requires blockchain in partial sync state*
1. If blockchain is syncing: Yellow pulsing dot
2. Tooltip shows: "Status: Syncing...", partial progress %
3. **Expected**: Auto-updates every 30 seconds

#### Test 2.3: Red Indicator (Offline)
1. Simulate offline: DevTools → Network → Offline mode
2. Wait for BlockchainMonitor to detect (30s + API timeout)
3. **Expected**: Red pulsing dot with "Offline" text
4. Click for tooltip: "Status: Offline", "Progress: 0%"

### 3. Offline Warning Banner

#### Test 3.1: Banner Appears When Offline
1. Enable Offline mode (DevTools → Network → Offline)
2. Wait ~35 seconds for status check
3. **Expected**: Red banner appears below header
4. **Message**: "⚠️ Using cached data. Blockchain is offline or syncing."
5. Banner has close button (✕)

#### Test 3.2: Banner Disappears When Synced
1. Warning banner visible
2. Enable Network (DevTools → Network → Online)
3. Wait ~35 seconds for status check
4. **Expected**: Banner auto-disappears
5. Connection indicator turns green
6. "Cached" badges removed

#### Test 3.3: Banner Close Button
1. Warning visible
2. Click ✕ button on banner
3. **Expected**: Banner disappears (can reappear on next offline period)

### 4. Balance Caching

#### Test 4.1: Balance Loads on Success
1. Wallet synced, online
2. View dashboard screen
3. Balance displays normally
4. No "Cached" badge
5. Check localStorage:
   ```javascript
   JSON.parse(localStorage.getItem('moonbite_balance_cache'))
   // {balance_coins: 12.5, updated_at: 1691234567, is_stale: false}
   ```

#### Test 4.2: Balance Shows "Cached" Badge Offline
1. Balance loaded and cached (from Test 4.1)
2. Enable Offline mode
3. Go to different page, return to dashboard
4. Balance still displays
5. **Expected**: "Cached" badge appears next to amount
6. Badge is yellow/warning color

#### Test 4.3: Cache Updates on Reconnect
1. "Cached" badge visible
2. Enable network
3. Wait for balance refresh (~10 seconds)
4. **Expected**: "Cached" badge disappears
5. New balance displayed (if changed)

#### Test 4.4: Cache Survives Page Reload
1. Network offline
2. Balance cached with badge
3. Reload page (Ctrl+R)
4. **Expected**: Cached balance loads immediately
5. "Cached" badge shows
6. Balance persists

### 5. Send Button Disabling

#### Test 5.1: Send Button Disabled Offline
1. Dashboard screen open
2. Enable Offline mode
3. Wait for connection indicator to turn red
4. **Expected**: "Send" button is disabled (grayed out)
5. Try clicking: No action
6. Hover for tooltip: "Blockchain is offline or syncing"

#### Test 5.2: Send Button Enabled Online
1. Offline with disabled Send button
2. Enable Network (DevTools → Online)
3. Wait for green indicator
4. **Expected**: "Send" button becomes enabled (normal color)
5. Can click and proceed

#### Test 5.3: Send Error Message Offline
1. If Send button somehow active while offline
2. Try to proceed with send
3. **Expected**: Error alert: "❌ Blockchain is offline or syncing. Please wait and try again."

### 6. Error Code Responses

#### Test 6.1: VALIDATION_INVALID_ADDRESS
```bash
curl -X POST http://localhost:5000/api/wallet/transaction/send \
  -H "Content-Type: application/json" \
  -d '{
    "txid": "abc123",
    "amount_units": 1000000,
    "from_address": "moonbc1invalid",
    "to_address": "moonbc2invalid"
  }'
```

**Expected Response:**
```json
{
  "status": "error",
  "error_code": "VALIDATION_INVALID_ADDRESS",
  "message": "Sender address is invalid",
  "action": "Please check the sender address",
  "timestamp": 1691234567.89
}
```

#### Test 6.2: VALIDATION_MISSING_FIELD
```bash
curl -X POST http://localhost:5000/api/wallet/hd/import \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response:**
```json
{
  "status": "error",
  "error_code": "VALIDATION_MISSING_FIELD",
  "message": "Seed phrase is required",
  "action": "Please enter your 12 or 24 word seed phrase",
  "timestamp": 1691234567.89
}
```

#### Test 6.3: VALIDATION_INVALID_MNEMONIC
```bash
curl -X POST http://localhost:5000/api/wallet/hd/import \
  -H "Content-Type: application/json" \
  -d '{"mnemonic": "one two three invalid"}'
```

**Expected Response:**
```json
{
  "status": "error",
  "error_code": "VALIDATION_INVALID_MNEMONIC",
  "message": "Invalid seed phrase (must be valid BIP39 mnemonic)",
  "action": "Please check that you entered the seed phrase correctly",
  "timestamp": 1691234567.89
}
```

#### Test 6.4: VALIDATION_INVALID_AMOUNT
```bash
curl -X POST http://localhost:5000/api/wallet/transaction/send \
  -H "Content-Type: application/json" \
  -d '{
    "txid": "abc123",
    "amount_units": -1000,
    "from_address": "moonbc1...",
    "to_address": "moonbc2..."
  }'
```

**Expected Response:**
```json
{
  "status": "error",
  "error_code": "VALIDATION_INVALID_AMOUNT",
  "message": "Amount must be greater than zero",
  "action": "Please check the amount and try again",
  "timestamp": 1691234567.89
}
```

#### Test 6.5: Debug Info (with ?debug=true)
```bash
curl 'http://localhost:5000/api/wallet/balance?debug=true'
```

If error occurs:
```json
{
  "status": "error",
  "error_code": "NETWORK_CONNECTION_ERROR",
  "message": "Connection error, retrying...",
  "debug": "Connection timeout after 30s",
  "timestamp": 1691234567.89
}
```

**Note**: Debug field only shows when:
- `debug=true` query parameter is set, OR
- `FLASK_DEBUG=1` environment variable is set

### 7. Blockchain Status Endpoint

#### Test 7.1: Full Sync Status
```bash
curl http://localhost:5000/api/blockchain/status
```

**Expected Response:**
```json
{
  "status": "success",
  "is_synced": true,
  "current_height": 12345,
  "peers_connected": 0,
  "blocks_behind": 0,
  "sync_percentage": 100.0,
  "last_block_time": 1691234500,
  "blockchain_healthy": true,
  "estimated_sync_seconds": 0,
  "timestamp": 1691234567.89
}
```

#### Test 7.2: Offline Status
1. Simulate offline (unplug network or DevTools Offline mode)
2. Call endpoint:
```bash
curl http://localhost:5000/api/blockchain/status
```

**Expected Response (HTTP 503):**
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

### 8. Frontend Error Display

#### Test 8.1: Error Alert Display
1. Trigger an error (e.g., invalid address on send)
2. **Expected**: Red error alert appears at top
3. **Format**: "❌ [user_message]"
4. **Duration**: 5 seconds (or dismissible)

#### Test 8.2: Suggested Action Display
1. Trigger error with action (e.g., import invalid mnemonic)
2. Open DevTools Console
3. **Expected**: Console message with suggested action
4. **Format**: "💡 [action_message]"

#### Test 8.3: Offline Warning Shows Action
1. Blockchain goes offline
2. Banner appears: "Using cached data. Blockchain is offline or syncing."
3. Try to send
4. **Expected**: Error message: "Blockchain is offline or syncing. Please wait and try again."

## Performance Testing

### Test 9.1: BlockchainMonitor Memory Usage
```javascript
// In DevTools Console
console.memory
// Before start
blockchainMonitor.start();
// After 10 polls (5 minutes)
console.memory
// Expected: <5MB increase
```

### Test 9.2: Status Polling Frequency
```javascript
// In DevTools Console → Network tab
// Filter: blockchain/status
// Count requests over 2 minutes
// Expected: ~4 requests (1 every 30s)
```

### Test 9.3: LocalStorage Size
```javascript
// In DevTools Console
function getStorageSize() {
  let size = 0;
  for (let key in localStorage) {
    size += localStorage[key].length + key.length;
  }
  return size + ' bytes';
}
getStorageSize()
// Expected: <10KB total
```

## Stress Testing

### Test 10.1: Rapid Online/Offline Toggles
1. DevTools Network → set throttling to "Offline"
2. Wait 10 seconds
3. Set to "Online"
4. Repeat 5 times rapidly
5. **Expected**: No crashes, status updates smoothly

### Test 10.2: Multiple Concurrent Requests
```javascript
// In DevTools Console
Promise.all([
  fetch('/api/wallet/balance'),
  fetch('/api/blockchain/status'),
  fetch('/api/blockchain/info')
]).then(r => Promise.all(r.map(x => x.json())))
  .then(console.log)
```
**Expected**: All requests complete successfully

### Test 10.3: Network Timeout Handling
1. DevTools Network → throttle to "GPRS" (very slow)
2. Perform API call
3. Wait for timeout (>30s)
4. **Expected**: NETWORK_CONNECTION_ERROR, not crash

## Checklist for Full Testing

- [ ] BlockchainMonitor polls every 30 seconds
- [ ] Connection indicator shows green when synced
- [ ] Connection indicator shows yellow when syncing
- [ ] Connection indicator shows red when offline
- [ ] Tooltip shows detailed status on click
- [ ] Offline warning banner appears when offline
- [ ] Banner close button works
- [ ] Banner auto-dismisses on reconnect
- [ ] Balance caches to localStorage
- [ ] "Cached" badge shows when offline
- [ ] "Cached" badge removed when online
- [ ] Cache persists across page reload
- [ ] Send button disabled when offline
- [ ] Send button enabled when online
- [ ] All error codes return correct format
- [ ] Error messages are user-friendly
- [ ] Actions/suggestions are helpful
- [ ] Debug info only shows when enabled
- [ ] No memory leaks on long-running monitor
- [ ] No console errors or warnings
- [ ] Mobile responsive (on actual device or emulation)

## Troubleshooting

### BlockchainMonitor Not Detecting Offline
1. Check DevTools Network tab for `blockchain/status` requests
2. Verify no cached responses (disable cache in DevTools)
3. Check browser console for errors
4. Confirm `blockchainMonitor` object exists:
   ```javascript
   console.log(blockchainMonitor)
   ```

### "Cached" Badge Not Appearing
1. Verify balance is cached:
   ```javascript
   localStorage.getItem('moonbite_balance_cache')
   ```
2. Check if API call failed (Network tab)
3. Verify error handling in updateBalance()

### Connection Indicator Not Updating
1. Check if BlockchainMonitor started:
   ```javascript
   blockchainMonitor.pollTimer // should be set
   ```
2. Verify polling interval:
   ```javascript
   blockchainMonitor.pollIntervalMs // should be 30000
   ```
3. Check browser console for errors

### Offline Banner Not Showing
1. Verify blockchain status is offline:
   ```javascript
   blockchainMonitor.getStatus().blockchain_healthy // should be false
   ```
2. Check if banner element exists:
   ```javascript
   document.getElementById('offlineWarning')
   ```
3. Verify CSS classes applied

## Success Criteria

### Minimal Viable Implementation
- [ ] Error standardization working
- [ ] BlockchainMonitor polling
- [ ] Connection indicator updates
- [ ] Balance caching
- [ ] Send button disabled offline

### Complete Implementation
- [ ] All error codes returned correctly
- [ ] Offline warning banner with close
- [ ] Status tooltip with details
- [ ] "Cached" badges on offline data
- [ ] Error messages show actions
- [ ] Debug info available
- [ ] No performance issues
- [ ] Mobile responsive

### Production Ready
- [ ] All above plus:
- [ ] Comprehensive error logging
- [ ] Analytics on error rates
- [ ] Graceful degradation
- [ ] Localization support
- [ ] Accessibility compliance
- [ ] Security review passed
