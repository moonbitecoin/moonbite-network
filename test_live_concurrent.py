#!/usr/bin/env python3
"""Test concurrent mining on live moonbite.org"""
import sys, io, requests, threading, time
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_BASE = "https://moonbite.org"
MINING_ADDRESS = "moon1xkxpy5aa5wgkues3kstlwxakfazydy88wrd3rh67gg8rsrgqt7yq7u03r9"

print("=" * 80)
print("LIVE CONCURRENT MINING TEST - moonbite.org")
print("=" * 80)
print()

job_ids = []

def submit_mining_job(client_id, blocks):
    try:
        r = requests.post(
            f"{API_BASE}/api/mining/start",
            json={"blocks": blocks, "address": MINING_ADDRESS},
            timeout=10,
            verify=False  # Self-signed cert
        )
        if r.status_code == 200:
            data = r.json()
            job_id = data.get('job_id')
            job_ids.append(job_id)
            print(f"[Client {client_id}] SUCCESS: Mining job {job_id[:12]}... started")
            return True
        else:
            print(f"[Client {client_id}] ERROR: HTTP {r.status_code}")
            if "mining" in r.text.lower() and "progress" in r.text.lower():
                print("  -> PROBLEM: Still blocking concurrent mining!")
            return False
    except Exception as e:
        print(f"[Client {client_id}] ERROR: {e}")
        return False

# Test: Submit 3 mining jobs simultaneously
print("[*] Submitting 3 concurrent mining jobs to live server...\n")

threads = []
for i in range(3):
    t = threading.Thread(target=submit_mining_job, args=(i, 10))
    threads.append(t)
    t.start()
    time.sleep(0.2)

for t in threads:
    t.join()

print()
if len(job_ids) == 3:
    print("[OK] SUCCESS: All 3 mining jobs accepted concurrently!")
    print(f"     Job IDs: {[jid[:8] for jid in job_ids]}")
    print()

    # Check status
    time.sleep(2)
    try:
        r = requests.get(f"{API_BASE}/api/mining/status", timeout=5, verify=False)
        if r.status_code == 200:
            data = r.json()
            print(f"[*] Mining Status:")
            print(f"    Active jobs: {data.get('active_jobs')}")
            print(f"    Current height: {data.get('current_height')}")
            print(f"    Combined hashrate: {data.get('combined_hashrate')} h/s")
    except Exception as e:
        print(f"[!] Status check failed: {e}")
else:
    print("[FAIL] Only {} jobs accepted (expected 3)".format(len(job_ids)))

print()
print("=" * 80)
