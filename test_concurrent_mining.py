#!/usr/bin/env python3
"""
Test concurrent mining from multiple clients
Verifies that multiple mining requests can run in parallel
"""
import sys
import io
import requests
import threading
import time
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_BASE = "http://localhost:5000"
MINING_ADDRESS = "moon1xkxpy5aa5wgkues3kstlwxakfazydy88wrd3rh67gg8rsrgqt7yq7u03r9"

print("=" * 80)
print("CONCURRENT MINING TEST - Multiple Clients Simultaneously")
print("=" * 80)
print()

def test_client(client_id: int, num_blocks: int):
    """Simulate a mining client making requests"""
    print(f"[Client {client_id}] Starting mining for {num_blocks} blocks...")
    try:
        # Submit mining request
        r = requests.post(
            f"{API_BASE}/api/mining/start",
            json={"blocks": num_blocks, "address": MINING_ADDRESS},
            timeout=10
        )

        if r.status_code == 200:
            data = r.json()
            job_id = data.get('job_id', 'unknown')
            print(f"[Client {client_id}] SUCCESS: Mining job {job_id} started")
            return job_id
        else:
            print(f"[Client {client_id}] ERROR: HTTP {r.status_code}")
            print(f"  Response: {r.text}")
            return None
    except Exception as e:
        print(f"[Client {client_id}] ERROR: {e}")
        return None

def check_status():
    """Check mining status"""
    try:
        r = requests.get(f"{API_BASE}/api/mining/status", timeout=5)
        if r.status_code == 200:
            data = r.json()
            print()
            print("-" * 80)
            print("MINING STATUS")
            print("-" * 80)
            print(f"Status: {data.get('status')}")
            print(f"Active jobs: {data.get('active_jobs')}")
            print(f"Total blocks mined: {data.get('blocks_mined')}")
            print(f"Current height: {data.get('current_height')}")
            print(f"Combined hashrate: {data.get('combined_hashrate')} h/s")
            print("-" * 80)
            print()
            return data
    except Exception as e:
        print(f"[!] Status check failed: {e}")
    return None

def main():
    # Test 1: Sequential submissions (should now all succeed)
    print("[*] Submitting 3 concurrent mining requests...")
    print()

    threads = []
    job_ids = []

    for i in range(3):
        t = threading.Thread(target=lambda cid=i: job_ids.append(test_client(cid, 5)))
        threads.append(t)
        t.start()
        time.sleep(0.5)  # Small delay between requests

    # Wait for all submissions
    for t in threads:
        t.join()

    print()
    print("[*] All requests submitted. Waiting for mining to progress...")
    print()

    # Monitor for 15 seconds
    for i in range(15):
        time.sleep(1)
        status = check_status()

        if status and status.get('status') == 'idle':
            print("[*] Mining completed!")
            break

        if i % 3 == 2:  # Print every 3 seconds
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring... ({i+1}/15)")

    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    final_status = check_status()
    if final_status:
        print(f"Final blockchain height: {final_status.get('current_height')}")
        print(f"Total blocks produced: {final_status.get('blocks_mined')}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] Test interrupted")
