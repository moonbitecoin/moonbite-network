# MoonBite Live Deployment - Bitcoin Algorithm Update

**Target**: DigitalOcean droplet (moonbite.org)
**Goal**: Deploy new Bitcoin-compatible pow.py and monitor retargets
**Time**: ~10 min deployment + 2-3 hours monitoring

---

## Prerequisites

You need:
- SSH access to your DigitalOcean droplet
- Droplet IP address and SSH key
- Access to local pow.py (C:\Users\usman\Desktop\BigCoinBB\pow.py)

---

## Step 1: Connect to Droplet

```bash
# Get your droplet IP from DigitalOcean dashboard
# Then connect via SSH (adjust IP and key path):

ssh root@<YOUR_DROPLET_IP> -i /path/to/ssh/key
# Or if password auth:
ssh root@<YOUR_DROPLET_IP>
```

Replace `<YOUR_DROPLET_IP>` with your actual droplet IP.

---

## Step 2: Locate Node Directory

```bash
# Find where moonbite-node is running
cd /root/moonbite-node
ls -la

# You should see:
# - pow.py (old version - will be replaced)
# - node.py
# - web_app.py
# - blockchain data files
```

---

## Step 3: Backup Old pow.py

```bash
# IMPORTANT: Back up the current version first
cp pow.py pow.py.backup.2026-07-31

echo "[OK] Backup created: pow.py.backup.2026-07-31"
```

---

## Step 4: Transfer New pow.py

**FROM YOUR LOCAL MACHINE** (Windows terminal):

```bash
# In Command Prompt/PowerShell:
cd C:\Users\usman\Desktop\BigCoinBB

# Copy the new pow.py to the droplet:
scp -i "path\to\ssh\key" pow.py root@<YOUR_DROPLET_IP>:/root/moonbite-node/

# Or using password:
# scp pow.py root@<YOUR_DROPLET_IP>:/root/moonbite-node/
```

**Example** (with SSH key):
```bash
scp -i C:\Users\usman\.ssh\id_rsa pow.py root@165.232.XXX.XXX:/root/moonbite-node/
```

If successful, you'll see:
```
pow.py                                    100% [██████████] (size)
```

---

## Step 5: Verify Upload

**On the droplet** (via SSH):

```bash
# Check file size matches
ls -lh pow.py pow.py.backup*

# Should show similar sizes - verify checksum:
md5sum pow.py
md5sum pow.py.backup.2026-07-31
```

If different, the file uploaded correctly.

---

## Step 6: Restart the Node

**On the droplet**:

```bash
# Find and kill the old node process
ps aux | grep python | grep web_app

# Kill it (replace XXXX with actual PID):
kill -9 XXXX

# Or kill all Python processes running node:
killall python

# Wait 3 seconds
sleep 3

# Restart the node
python web_app.py > node.log 2>&1 &

echo "Node starting..."
sleep 5

# Verify it's running:
curl http://127.0.0.1:5000/api/blockchain/info | python -m json.tool | head -10
```

You should see:
```json
{
    "height": 2046,
    "difficulty_bits": 19,
    ...
    "status": "success"
}
```

---

## Step 7: Enable Mining (if not already running)

**On the droplet**:

```bash
# Get a new mining address
curl -s http://127.0.0.1:5000/api/wallet/new | python -c "import sys, json; print(json.load(sys.stdin)['address'])"

# Start mining (replace with actual address):
curl -X POST http://127.0.0.1:5000/api/mining/start \
  -H "Content-Type: application/json" \
  -d '{"blocks": 100, "miner_address": "moon1..."}'
```

---

## Step 8: Monitor Retargets

**From your local machine**, create a monitoring script:

```bash
# Create monitor script
cat > monitor_retargets.py << 'EOF'
import requests
import time
from datetime import datetime

BASE = "https://moonbite.org"  # or http://<IP>:5000 if not proxied
start = time.time()

print("="*70)
print("MOONBITE LIVE RETARGET MONITORING")
print("="*70)
print("")

last_height = 0
last_bits = 17

while True:
    try:
        resp = requests.get(f"{BASE}/api/blockchain/info", timeout=5)
        info = resp.json()

        height = info.get("height", 0)
        bits = info.get("difficulty_bits", 17)
        coins = info.get("total_money_coins", 50)

        if height != last_height:
            elapsed = (time.time() - start) / 60
            rate = height / elapsed if elapsed > 0 else 0

            ts = datetime.now().strftime('%H:%M:%S')

            if bits != last_bits:
                print(f"[{ts}] *** RETARGET *** Height: {height} | Difficulty: {bits} bits (was {last_bits}) | Rate: {rate:.1f} blk/min")
                last_bits = bits
            elif height % 100 == 0:
                print(f"[{ts}] Height: {height} | Difficulty: {bits} | Rate: {rate:.1f} blk/min")

            last_height = height

        if height >= 4032:  # Retarget #2
            print(f"\n*** RETARGET #2 (Block 4032) REACHED ***")
            print(f"Height: {height}")
            print(f"Difficulty: {bits} bits")
            print(f"Time elapsed: {(time.time() - start)/60:.1f} minutes")
            break

        time.sleep(2)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)

print("\nMonitoring complete!")
EOF

python monitor_retargets.py
```

---

## Step 9: Validation Checklist

After deployment, verify:

- ✅ pow.py uploaded successfully
- ✅ Node restarted and responding
- ✅ Mining is running
- ✅ Blocks are being mined (height increasing)
- ✅ Retarget #2 reaches block 4032
- ✅ Difficulty increases appropriately
- ✅ Mining rate smoothly converges

---

## Expected Results

### Timeline to Retarget #2 (Block 4032)

From current state (block ~2046):

```
Now:            Block 2046
+1.3 hours:     Block 4032 (RETARGET #2)
                Difficulty: 19 bits (increases from current)
+3-4 hours:     Block 6048 (RETARGET #3)
                Difficulty: 20-22 bits
                CONVERGING TO TARGET
```

### Bitcoin Compatibility Indicators

After retarget #2, you should see:
- ✅ Difficulty increased (not decreased or same)
- ✅ Mining rate decreased (slowing down to target)
- ✅ No sudden jumps (smooth adjustment)
- ✅ No oscillation (difficulty goes up, then stabilizes)

---

## Troubleshooting

### Problem: "Connection refused" after restart

```bash
# Node might still be starting. Wait 10 seconds and try again:
sleep 10
curl http://127.0.0.1:5000/api/blockchain/info
```

### Problem: Mining not starting

```bash
# Check if mining API is responsive:
curl -X POST http://127.0.0.1:5000/api/mining/start \
  -H "Content-Type: application/json" \
  -d '{"blocks": 10, "miner_address": "moon1..."}'

# Should return 200 OK with mining started message
```

### Problem: Difficulty doesn't change

This means retarget hasn't happened yet. Check:
1. Is height increasing? (blocks being mined)
2. Are we past block 4032? (second retarget point)
3. Is the node running the new pow.py?

Verify:
```bash
# Check which pow.py is loaded
grep -n "new_target = " /root/moonbite-node/pow.py
# Should show new Bitcoin algorithm, not old discrete logic
```

### Problem: Need to rollback

```bash
# Restore old version:
cp pow.py.backup.2026-07-31 pow.py

# Restart node:
killall python
sleep 3
python web_app.py > node.log 2>&1 &
```

---

## Verification Commands

Quick checks to confirm deployment:

```bash
# Check pow.py is loaded (on droplet):
python -c "from pow import calculate_next_bits; print('Bitcoin algorithm loaded')"

# Test algorithm:
python << 'EOF'
from pow import calculate_next_bits, EXPECTED_TIMESPAN

# Test: Mining 2x too fast should increase difficulty
current = 17
actual_time = EXPECTED_TIMESPAN // 2  # 2x faster
next_bits = calculate_next_bits(current, actual_time)
print(f"Mining 2x fast: 17 -> {next_bits} bits")
assert next_bits > 17, "Difficulty should increase"
print("✓ Algorithm working correctly")
EOF
```

---

## Success Criteria

Deployment is successful when:

1. ✅ `curl https://moonbite.org/api/blockchain/info` returns 200 OK
2. ✅ Height is increasing (blocks being mined)
3. ✅ Next retarget (block 4032) shows difficulty change
4. ✅ Mining rate shows smooth convergence
5. ✅ No errors in node.log

---

## Next Steps

After deployment:

1. **Monitor for ~2 hours** until retarget #2 (block 4032)
2. **Record the results**:
   - Difficulty before: 19 bits
   - Difficulty after: 20-21 bits (should increase)
   - Mining rate change

3. **Create a report** comparing with Bitcoin predictions

4. **Announce to users** if all tests pass

---

## Quick Deploy Script

To simplify, here's a one-command deployment (run from droplet):

```bash
#!/bin/bash
# On droplet:

cd /root/moonbite-node
cp pow.py pow.py.backup.$(date +%Y-%m-%d)

# Download new version from your source
# (You would paste the new pow.py here or upload it)

# Restart
killall python || true
sleep 3
python web_app.py > node.log 2>&1 &

echo "[OK] Deployment complete!"
```

---

## Support

If you hit issues:
1. Check node.log for errors: `tail -50 /root/moonbite-node/node.log`
2. Verify pow.py syntax: `python -m py_compile pow.py`
3. Test manually: See "Verification Commands" above
4. Rollback if needed: Use `.backup` file

---

**Ready to deploy? Follow the steps above!**

Status: **DEPLOYMENT GUIDE READY**
