#!/bin/bash
# MoonBite Difficulty Test - Start from Zero
# Starts node, enables mining, monitors retargets

cd "C:\Users\usman\Desktop\BigCoinBB"

echo "========================================================================"
echo "MOONBITE DIFFICULTY TEST: START FROM ZERO"
echo "========================================================================"
echo ""

# Kill any running instances
taskkill /F /IM python.exe 2>/dev/null || true
sleep 3

echo "[1] Starting blockchain node on port 5000..."
FLASK_DEBUG=0 PORT=5000 HOST=127.0.0.1 python web_app.py > blockchain.log 2>&1 &
NODE_PID=$!
echo "[OK] Node PID: $NODE_PID"

sleep 10

echo ""
echo "[2] Starting mining..."

# Start mining via API
python << 'PYMINING'
import requests
import time
import json

for i in range(5):
    try:
        # Get a new address
        addr_resp = requests.get("http://127.0.0.1:5000/api/wallet/new", timeout=5)
        addr_data = addr_resp.json()
        mining_addr = addr_data.get("address")

        if mining_addr:
            print(f"Mining address: {mining_addr[:50]}...")

            # Start mining
            mine_resp = requests.get(
                "http://127.0.0.1:5000/api/mining/start",
                params={"address": mining_addr},
                timeout=5
            )
            print(f"Mining started: {mine_resp.status_code}")

            # Check status
            time.sleep(2)
            info = requests.get("http://127.0.0.1:5000/api/blockchain/info", timeout=5).json()
            print(f"Height: {info.get('height', 0)} blocks")
            print(f"Difficulty: {info.get('difficulty_bits', 17)} bits")
            break
    except Exception as e:
        print(f"Attempt {i+1}: {e}")
        time.sleep(2)
PYMINING

echo ""
echo "[3] Running 30-minute monitor..."
echo ""

# Monitor for 30 minutes
python << 'PYMONITOR'
import requests
import time
import json
from datetime import datetime

BASE = "http://127.0.0.1:5000"
start = time.time()

print("=" * 70)
print("MOONBITE DIFFICULTY MONITOR - 30 MINUTE CHECKPOINT")
print("=" * 70)
print("")

last_height = 0
checkpoint_times = [5, 10, 15, 20, 25, 30]  # minutes
next_checkpoint = 0

while time.time() - start < 1800:  # 30 minutes
    try:
        info = requests.get(f"{BASE}/api/blockchain/info", timeout=5).json()
        height = info.get("height", 0)

        if height != last_height:
            elapsed = (time.time() - start) / 60
            print(f"[{elapsed:5.1f} min] Height: {height:5d} | Difficulty: {info.get('difficulty_bits', 17):2d} bits | MBITE: {info.get('total_money_coins', 0):8.1f}")
            last_height = height

        # Check for milestone
        if next_checkpoint < len(checkpoint_times):
            target_time = checkpoint_times[next_checkpoint] * 60
            if time.time() - start >= target_time and time.time() - start < target_time + 5:
                elapsed = (time.time() - start) / 60
                print(f"\n*** {int(checkpoint_times[next_checkpoint])} MINUTE CHECKPOINT ***")
                print(f"Height: {height} blocks")
                print(f"Difficulty: {info.get('difficulty_bits', 17)} bits")
                print(f"Mining rate: {height / elapsed:.1f} blocks/min (if at 1 block/sec)")
                print()
                next_checkpoint += 1

        time.sleep(1)

    except Exception as e:
        pass

print("")
print("=" * 70)
print("30 MINUTE MONITOR COMPLETE")
print("=" * 70)
print(f"Final Height: {last_height} blocks")
print(f"Expected at this rate to reach block 2016 in: {2016 / max(last_height/30, 0.1):.0f} minutes")
PYMONITOR

echo ""
echo "[OK] 30-minute checkpoint complete!"
echo ""
echo "Node is still mining in background (PID: $NODE_PID)"
echo "Full test continues for 3-4 hours total"
echo ""
echo "Check /usr/bin/bash: line 107: taskkill: command not found
blockchain.log for details"
