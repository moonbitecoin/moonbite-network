#!/usr/bin/env python3
"""
EXTREME MINING - Maximum acceleration toward retarget
Uses 100 parallel workers requesting 50 blocks each
"""
import sys
import io
import requests
import concurrent.futures
import time
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_BASE = "https://moonbite.org"
MINING_ADDRESS = "M1CGk7jK5KqG2nQ9vK3pL2mR4nS5tU6vW7"

# Extreme parameters
NUM_PARALLEL_MINERS = 100  # Double the workers
BLOCKS_PER_REQUEST = 50    # 5x more blocks per request
TOTAL_TARGET = 2016

print("[*] EXTREME MINING INITIATED")
print(f"    Parallel workers: {NUM_PARALLEL_MINERS}")
print(f"    Blocks per request: {BLOCKS_PER_REQUEST}")
print(f"    Total requests capacity: {NUM_PARALLEL_MINERS * BLOCKS_PER_REQUEST} blocks per cycle")
print()

def mine_worker(worker_id, num_blocks):
    """Mine blocks"""
    try:
        r = requests.post(
            f"{API_BASE}/api/mining/start",
            json={"blocks": num_blocks, "address": MINING_ADDRESS},
            timeout=60
        )
        if r.status_code == 200:
            return (worker_id, r.json().get('blocks_mined', 0), None)
        else:
            return (worker_id, 0, f"HTTP {r.status_code}")
    except Exception as e:
        return (worker_id, 0, str(e))

def get_status():
    """Get blockchain status"""
    try:
        r = requests.get(f"{API_BASE}/api/blockchain/info", timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def main():
    start_time = time.time()
    info = get_status()
    if not info:
        print("[ERROR] Cannot connect to API")
        return

    start_height = info.get('height', 0)
    print(f"[*] Starting height: {start_height}")
    print()

    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_PARALLEL_MINERS) as executor:
        futures = []

        # Initial submission
        for i in range(NUM_PARALLEL_MINERS):
            f = executor.submit(mine_worker, i, BLOCKS_PER_REQUEST)
            futures.append(f)

        last_status = time.time()

        while True:
            info = get_status()
            if not info:
                time.sleep(1)
                continue

            height = info.get('height', 0)
            difficulty = info.get('difficulty', 0)
            coins = info.get('total_money_coins', 0)

            blocks_epoch = height % TOTAL_TARGET
            progress = (blocks_epoch / TOTAL_TARGET) * 100
            blocks_remain = TOTAL_TARGET - blocks_epoch

            # Status every 2 seconds
            now = time.time()
            if now - last_status >= 2:
                elapsed = int(now - start_time)
                rate = (height - start_height) / elapsed if elapsed > 0 else 0

                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"H:{height:>5} ({blocks_epoch:>4}/2016, {progress:>5.1f}%) | "
                      f"{blocks_remain:>4} rem | "
                      f"Rate: {rate:.1f} blk/s | "
                      f"Supply: {coins:>8,.0f}")

                if blocks_remain <= 200:
                    print(f"    [!!!] CRITICAL: {blocks_remain} blocks to retarget!")
                elif blocks_remain <= 500:
                    print(f"    [>>] {blocks_remain} blocks to retarget")

                last_status = now

            # Check retarget
            if blocks_epoch < 10 and blocks_epoch > 0:
                print()
                print("!" * 80)
                print("[RETARGET DETECTED]")
                print(f"Height: {height}")
                print(f"Difficulty: {difficulty}")
                print("!" * 80)
                executor.shutdown(wait=False)
                return

            # Check if target reached
            if height >= TOTAL_TARGET:
                print()
                print("!" * 80)
                print("[TARGET RETARGET REACHED]")
                print(f"Final Height: {height}")
                print(f"Final Difficulty: {difficulty}")
                elapsed = time.time() - start_time
                print(f"Time: {int(elapsed)} seconds | Rate: {(height-start_height)/elapsed:.1f} blk/s")
                print("!" * 80)
                executor.shutdown(wait=False)
                return

            # Resubmit completed futures
            done, pending = concurrent.futures.wait(
                futures, timeout=1, return_when=concurrent.futures.FIRST_COMPLETED
            )

            for f in done:
                try:
                    f.result()
                except:
                    pass
                # Resubmit
                new_f = executor.submit(mine_worker, 0, BLOCKS_PER_REQUEST)
                futures.append(new_f)

            futures = list(pending) + [new_f]

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] Mining stopped")
