#!/usr/bin/env python3
"""
Massive Mining Load - Parallel stress test to accelerate block production
Targets retarget at block 2016
"""
import sys
import io
import requests
import concurrent.futures
import time
from datetime import datetime
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_BASE = "https://moonbite.org"
MINING_ADDRESS = "M1CGk7jK5KqG2nQ9vK3pL2mR4nS5tU6vW7"  # Example MoonBite address

# Mining parameters
NUM_PARALLEL_MINERS = 50  # Number of concurrent mining threads
BLOCKS_PER_REQUEST = 10   # Blocks to mine per request
TOTAL_TARGET_BLOCKS = 2016  # Target height

print("=" * 80)
print("MASSIVE MINING - ACCELERATED RETARGET TEST")
print("=" * 80)
print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Parallel miners: {NUM_PARALLEL_MINERS}")
print(f"Blocks per request: {BLOCKS_PER_REQUEST}")
print(f"Target: Retarget at block {TOTAL_TARGET_BLOCKS}")
print("=" * 80)
print()

stats = {
    'requests_sent': 0,
    'requests_success': 0,
    'requests_failed': 0,
    'total_blocks_requested': 0,
    'start_time': time.time(),
}

def mine_blocks(worker_id, num_blocks):
    """Submit a mining request for N blocks"""
    try:
        payload = {
            "blocks": num_blocks,
            "address": MINING_ADDRESS
        }

        response = requests.post(
            f"{API_BASE}/api/mining/start",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            blocks_mined = data.get('blocks_mined', 0)
            status = "SUCCESS"
            stats['requests_success'] += 1
            return (worker_id, status, blocks_mined, None)
        else:
            stats['requests_failed'] += 1
            return (worker_id, f"HTTP {response.status_code}", 0, response.text)
    except Exception as e:
        stats['requests_failed'] += 1
        return (worker_id, "ERROR", 0, str(e))
    finally:
        stats['requests_sent'] += 1

def get_blockchain_status():
    """Fetch current blockchain state"""
    try:
        response = requests.get(f"{API_BASE}/api/blockchain/info", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def main():
    # Get starting height
    start_info = get_blockchain_status()
    if not start_info:
        print("[ERROR] Could not connect to blockchain API")
        return

    start_height = start_info.get('height', 0)
    print(f"Starting height: {start_height} blocks")
    print()

    # Mining loop
    iteration = 0
    last_status_time = time.time()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_PARALLEL_MINERS) as executor:
            futures = []

            print(f"[*] Submitting mining requests...")
            print()

            # Submit initial batch
            for i in range(NUM_PARALLEL_MINERS):
                future = executor.submit(mine_blocks, i, BLOCKS_PER_REQUEST)
                futures.append(future)

            # Process results and resubmit
            while True:
                # Check blockchain status
                info = get_blockchain_status()
                if not info:
                    print("[!] Connection lost, retrying...")
                    time.sleep(5)
                    continue

                current_height = info.get('height', 0)
                current_difficulty = info.get('difficulty', 0)
                current_coins = info.get('total_money_coins', 0)

                blocks_in_epoch = current_height % 2016
                progress = (blocks_in_epoch / 2016) * 100
                blocks_remaining = 2016 - blocks_in_epoch

                # Status update every 5 seconds
                current_time = time.time()
                if current_time - last_status_time >= 5:
                    elapsed = int(current_time - stats['start_time'])
                    avg_block_rate = (current_height - start_height) / elapsed if elapsed > 0 else 0

                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"H:{current_height:>5} ({blocks_in_epoch:>4}/2016, {progress:>5.1f}%) | "
                          f"Supply: {current_coins:>8.0f} | "
                          f"Rate: {avg_block_rate:>4.2f} blk/s | "
                          f"Miners active: {NUM_PARALLEL_MINERS}")

                    last_status_time = current_time

                # Check if retarget happened
                if blocks_in_epoch < 50 and blocks_in_epoch > 0:
                    difficulty_change = current_difficulty - start_info.get('difficulty', 0)
                    if difficulty_change != 0:
                        print()
                        print("!" * 80)
                        print("[RETARGET EVENT DETECTED]")
                        print(f"Height: {current_height}")
                        print(f"Old Difficulty: {start_info.get('difficulty', 0)}")
                        print(f"New Difficulty: {current_difficulty}")
                        print(f"Change: {difficulty_change:+.0f}")
                        print("!" * 80)
                        print()

                # Check if we've reached target
                if current_height >= TOTAL_TARGET_BLOCKS:
                    print()
                    print("!" * 80)
                    print("[TARGET REACHED - RETARGET THRESHOLD]")
                    print(f"Final Height: {current_height}")
                    print(f"Final Difficulty: {current_difficulty}")
                    print(f"Final Supply: {current_coins:.0f} MBITE")
                    elapsed_time = time.time() - stats['start_time']
                    print(f"Time to retarget: {int(elapsed_time)} seconds")
                    print(f"Average block rate: {(current_height - start_height) / elapsed_time:.2f} blocks/sec")
                    print("!" * 80)

                    # Shutdown miners gracefully
                    executor.shutdown(wait=False)
                    return

                # Wait for any completed futures and resubmit
                done, pending = concurrent.futures.wait(
                    futures,
                    timeout=1,
                    return_when=concurrent.futures.FIRST_COMPLETED
                )

                for future in done:
                    try:
                        worker_id, status, blocks_mined, error = future.result()
                        if status == "SUCCESS":
                            stats['total_blocks_requested'] += blocks_mined
                    except:
                        pass

                    # Resubmit
                    future = executor.submit(mine_blocks, worker_id, BLOCKS_PER_REQUEST)
                    futures.append(future)

                futures = list(pending) + [future]

                iteration += 1

    except KeyboardInterrupt:
        print()
        print()
        print("=" * 80)
        print("MINING STOPPED BY USER")
        print("=" * 80)

        final_info = get_blockchain_status()
        if final_info:
            print(f"Final height: {final_info.get('height', 0)}")
            print(f"Final supply: {final_info.get('total_money_coins', 0):.0f} MBITE")
            elapsed = time.time() - stats['start_time']
            print(f"Mining duration: {int(elapsed)} seconds")
        print("=" * 80)

if __name__ == "__main__":
    main()
