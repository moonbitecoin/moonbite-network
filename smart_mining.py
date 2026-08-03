#!/usr/bin/env python3
"""
SMART MINING - Rate-limit aware acceleration
Respects 20 req/60s limit while maximizing blocks per request
"""
import sys
import io
import requests
import time
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_BASE = "https://moonbite.org"
RATE_LIMIT = 20  # requests per 60 seconds
RATE_WINDOW = 60  # seconds
BLOCKS_PER_REQUEST = 100  # Request max blocks per call

print("=" * 80)
print("SMART MINING - RATE-LIMIT AWARE")
print("=" * 80)
print(f"Rate limit: {RATE_LIMIT} requests per {RATE_WINDOW} seconds")
print(f"Blocks per request: {BLOCKS_PER_REQUEST}")
print(f"Max throughput: {RATE_LIMIT * BLOCKS_PER_REQUEST} blocks per 60s")
print("=" * 80)
print()

def get_status():
    """Get blockchain status"""
    try:
        r = requests.get(f"{API_BASE}/api/blockchain/info", timeout=5)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def get_valid_address():
    """Get a valid mining address"""
    try:
        r = requests.get(f"{API_BASE}/api/blockchain/info", timeout=5)
        if r.status_code == 200:
            data = r.json()
            # Try to get from explorer or use default
            return "MoonBiteMiner"  # Default coinbase recipient
    except:
        pass
    return "MoonBiteMiner"

def mine_blocks(num_blocks, address):
    """Request mining"""
    try:
        r = requests.post(
            f"{API_BASE}/api/mining/start",
            json={"blocks": num_blocks, "address": address},
            timeout=60
        )
        if r.status_code == 200:
            return r.json().get('blocks_mined', 0)
        else:
            return 0
    except:
        return 0

def main():
    info = get_status()
    if not info:
        print("[ERROR] Cannot connect")
        return

    start_height = info.get('height', 0)
    start_time = time.time()
    address = get_valid_address()

    print(f"[*] Starting height: {start_height}")
    print(f"[*] Mining address: {address}")
    print()

    request_count = 0
    last_request_time = time.time()

    while True:
        info = get_status()
        if not info:
            time.sleep(1)
            continue

        height = info.get('height', 0)
        difficulty = info.get('difficulty', 0)
        coins = info.get('total_money_coins', 0)

        blocks_epoch = height % 2016
        progress = (blocks_epoch / 2016) * 100
        blocks_remain = 2016 - blocks_epoch

        # Display status
        elapsed = time.time() - start_time
        rate = (height - start_height) / elapsed if elapsed > 0 else 0

        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
              f"H:{height:>5} ({blocks_epoch:>4}/2016, {progress:>5.1f}%) | "
              f"Remain: {blocks_remain:>4} | "
              f"Rate: {rate:.2f} blk/s | "
              f"Reqs: {request_count}/20")

        if blocks_remain <= 100:
            print(f"    [!!!] {blocks_remain} blocks to retarget!")

        # Check retarget
        if blocks_epoch < 10 and blocks_epoch > 0:
            print()
            print("!" * 80)
            print("[RETARGET DETECTED]")
            print(f"Height: {height} | Difficulty: {difficulty}")
            print("!" * 80)
            return

        # Rate limit check: Allow 20 requests per 60 seconds
        current_time = time.time()
        time_since_last = current_time - last_request_time

        if request_count < RATE_LIMIT:
            # Can make another request within the window
            if time_since_last >= (RATE_WINDOW / RATE_LIMIT):
                # Space requests evenly
                print(f"  -> Submitting mining request for {BLOCKS_PER_REQUEST} blocks...")
                blocks_mined = mine_blocks(BLOCKS_PER_REQUEST, address)
                if blocks_mined > 0:
                    print(f"     [OK] {blocks_mined} blocks requested")
                request_count += 1
                last_request_time = current_time
            else:
                time.sleep(0.5)
        else:
            # Rate limit window is full, wait for reset
            wait_time = RATE_WINDOW - (current_time - (last_request_time - (RATE_WINDOW - time_since_last)))
            if wait_time > 0:
                print(f"  -> Rate limit reached, waiting {int(wait_time)}s for reset...")
                time.sleep(min(wait_time, 2))
            else:
                request_count = 0
                last_request_time = current_time

        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] Mining stopped")
