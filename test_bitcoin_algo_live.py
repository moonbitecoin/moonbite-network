#!/usr/bin/env python3
"""
Test Bitcoin difficulty algorithm with live Flask API.
Run this while web_app.py is running on localhost:5000
"""

import requests
import time
from datetime import datetime

BASE = "http://localhost:5000"

def get_blockchain_info():
    """Fetch current blockchain state."""
    try:
        resp = requests.get(f"{BASE}/api/blockchain/info", timeout=5)
        return resp.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    print("=" * 70)
    print("BITCOIN DIFFICULTY ALGORITHM - LIVE TEST")
    print("=" * 70)
    print()

    # Check if Flask is responding
    info = get_blockchain_info()
    if not info:
        print("ERROR: Flask not responding on http://localhost:5000")
        print("Make sure to run: python web_app.py")
        return

    print("✅ Connected to Flask API")
    print()

    # Show initial state
    print("INITIAL STATE:")
    print(f"  Height: {info['height']} blocks")
    print(f"  Difficulty: {info['bits']} bits")
    print(f"  Total coins: {info['total_money_coins']} MBITE")
    print()

    # Explain Bitcoin algorithm
    print("=" * 70)
    print("BITCOIN DIFFICULTY ALGORITHM (implemented in pow.py)")
    print("=" * 70)
    print()
    print("How it works:")
    print("  1. Every 2016 blocks = 1 retarget period")
    print("  2. Compare actual time vs expected time (14 days)")
    print("  3. Adjust difficulty proportionally")
    print("  4. Clamp to 4x per retarget (safety)")
    print()
    print("Expected timeline:")
    print("  - Blocks 0-2015:   Difficulty = 16 bits (initial)")
    print("  - Block 2016:      RETARGET #1 (difficulty changes)")
    print("  - Block 4032:      RETARGET #2")
    print("  - Block 6048:      RETARGET #3")
    print()
    print("Test this by:")
    print("  1. Start mining via API: POST /api/mining/start")
    print("  2. Watch height increase")
    print("  3. At block 2016, difficulty should adjust")
    print()
    print("Example mining command:")
    print("  curl -X POST http://localhost:5000/api/mining/start \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{\"blocks\": 2100, \"miner_address\": \"moon1...\"}'")
    print()
    print("=" * 70)
    print()

    # Monitor loop
    print("LIVE MONITORING (press Ctrl+C to stop):")
    print()

    last_height = 0
    last_bits = info['bits']
    start_time = time.time()

    try:
        while True:
            info = get_blockchain_info()
            if not info:
                time.sleep(2)
                continue

            height = info.get('height', 0)
            bits = info.get('bits', 16)

            if height != last_height:
                elapsed = (time.time() - start_time) / 60
                ts = datetime.now().strftime('%H:%M:%S')

                if bits != last_bits:
                    change = bits - last_bits
                    direction = "↑ HARDER" if change > 0 else "↓ EASIER"
                    print(f"[{ts}] 🎯 RETARGET! Height: {height:5d} | Difficulty: {bits:2d} bits {direction} ({change:+d}) | Rate: {height/elapsed:.1f} blk/min")
                    last_bits = bits
                elif height % 100 == 0:
                    print(f"[{ts}] Height: {height:5d} | Difficulty: {bits:2d} bits | Rate: {height/elapsed:.1f} blk/min")

                last_height = height

            time.sleep(1)

    except KeyboardInterrupt:
        print()
        print()
        print("=" * 70)
        print("TEST STOPPED")
        print("=" * 70)
        final_info = get_blockchain_info()
        if final_info:
            print(f"Final Height: {final_info['height']} blocks")
            print(f"Final Difficulty: {final_info['bits']} bits")
            print(f"Total Time: {(time.time() - start_time)/60:.1f} minutes")

if __name__ == "__main__":
    main()
