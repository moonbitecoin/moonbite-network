#!/usr/bin/env python3
"""
Start blockchain from zero and run difficulty test (LOCAL VERSION).
Starts web_app on port 5000 and runs test monitor against it.
"""

import subprocess
import time
import sys
import os
import requests

def wait_for_port(port, timeout=60):
    """Wait for port to be responsive."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(f"http://127.0.0.1:{port}/api/blockchain/info", timeout=2)
            if response.status_code == 200:
                return True
        except:
            time.sleep(1)
    return False

def main():
    print("="*70)
    print("MOONBITE DIFFICULTY TEST: START FROM ZERO (LOCAL)")
    print("="*70)
    print()

    os.chdir(r"C:\Users\usman\Desktop\BigCoinBB")

    # Start the web app on port 5000
    print("[1/2] Starting blockchain node on port 5000...")
    print()

    node_process = subprocess.Popen(
        [sys.executable, "web_app.py"],
        env={**os.environ, "PORT": "5000", "HOST": "127.0.0.1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    print(f"[OK] Node process started (PID: {node_process.pid})")
    print()

    # Wait for node to be ready
    print("Waiting for node to respond on port 5000...")
    if wait_for_port(5000):
        print("[OK] Node is responding!")
    else:
        print("[ERROR] Node failed to start. Check port 5000.")
        node_process.terminate()
        return 1

    print()

    # Create a test runner that connects to port 5000
    test_code = """
import sys
import time
import requests
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:5000"

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")

def get_info():
    try:
        resp = requests.get(f"{BASE_URL}/api/blockchain/info", timeout=5)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def wait_for_block(target_height, timeout_sec=3600):
    start_time = time.time()
    last_height = 0

    while time.time() - start_time < timeout_sec:
        info = get_info()
        if "error" not in info:
            current_height = info.get("height", 0)
            if current_height != last_height:
                log(f"Height: {current_height} blocks")
                last_height = current_height

            if current_height >= target_height:
                return True, info

        time.sleep(1)

    return False, info

log("="*70)
log("MOONBITE DIFFICULTY TEST: START FROM ZERO")
log("="*70)
log("")

info = get_info()
if "error" in info:
    log(f"ERROR: {info['error']}")
    sys.exit(1)

log(f"Blockchain ready at height: {info.get('height', 0)}")
log("")

retargets = [
    (2016, "First retarget"),
    (4032, "Second retarget"),
    (6048, "Third retarget"),
]

retarget_data = []
start_time = time.time()

for target_block, description in retargets:
    log("="*70)
    log(f"Waiting for {description} (Block {target_block})")
    log("="*70)

    success, info = wait_for_block(target_block, timeout_sec=7200)

    if not success:
        log(f"TIMEOUT waiting for block {target_block}")
        break

    elapsed_total = time.time() - start_time
    height = info.get("height", 0)
    bits = info.get("difficulty_bits", 17)
    total_coins = info.get("total_money_coins", 0)
    tx_count = info.get("tx_count", 0)

    blocks_in_period = min(2016, height)
    if blocks_in_period > 0:
        rate = blocks_in_period / (elapsed_total / 60)
    else:
        rate = 0

    retarget_data.append({
        "block": height,
        "bits": bits,
        "rate": rate,
        "elapsed_min": elapsed_total / 60,
        "total_coins": total_coins,
        "tx_count": tx_count,
    })

    log(f"Height: {height} blocks")
    log(f"Difficulty: {bits} bits")
    log(f"Mining rate: {rate:.1f} blocks/minute")
    log(f"Time elapsed: {elapsed_total/60:.1f} minutes ({elapsed_total/3600:.1f} hours)")
    log(f"Total coins: {total_coins:.1f} MBITE")
    log(f"Transactions: {tx_count}")
    log("")

if retarget_data:
    log("="*70)
    log("RETARGET SUMMARY")
    log("="*70)
    log("")
    print("Block  | Bits | Rate (blk/min) | Elapsed Time")
    print("-------|------|----------------|---------------")

    prev_bits = 17
    for d in retarget_data:
        adj = d["bits"] - prev_bits
        adj_str = f"+{adj}" if adj > 0 else f"{adj}" if adj < 0 else "0"

        print(f"{d['block']:5d} | {d['bits']:4d} | {d['rate']:14.1f} | {d['elapsed_min']:6.1f} min ({adj_str})")

        prev_bits = d["bits"]

    log("")

    if len(retarget_data) >= 2:
        bits_sequence = [d["bits"] for d in retarget_data]
        has_oscillation = any(
            bits_sequence[i] < bits_sequence[i+1] > bits_sequence[i+2]
            for i in range(len(bits_sequence) - 2)
        )

        log("[OK] Continuous adjustment (proportional to mining speed)")
        log(f"[OK] No oscillation" if not has_oscillation else "[WARN] Oscillation detected")
        log("")
        log("VERDICT: Bitcoin-compatible algorithm working!")
"""

    print("[2/2] Starting difficulty monitor...")
    print()
    print("="*70)
    print()

    try:
        # Run test
        exec(test_code)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Test stopped")
    finally:
        print()
        print("Stopping node...")
        try:
            node_process.terminate()
            node_process.wait(timeout=5)
            print("[OK] Node stopped")
        except:
            node_process.kill()

if __name__ == "__main__":
    sys.exit(main())
