#!/usr/bin/env python3
"""
Persistent Retarget Watcher - Alerts on retarget event
Runs indefinitely, logs to file, prints alerts to console
"""
import sys
import io
import requests
import time
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_BASE = "https://moonbite.org"
RETARGET_INTERVAL = 2016
LOG_FILE = "retarget_watcher.log"

def log_msg(msg):
    """Log message to both file and console"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {msg}"
    print(log_line)
    with open(LOG_FILE, 'a') as f:
        f.write(log_line + "\n")

def main():
    log_msg("=" * 80)
    log_msg("RETARGET WATCHER STARTED")
    log_msg("=" * 80)
    log_msg(f"Target: Retarget at block {RETARGET_INTERVAL}")
    log_msg(f"Log file: {LOG_FILE}")
    log_msg("=" * 80)

    previous_epoch = -1
    last_difficulty = 0
    check_count = 0

    while True:
        try:
            response = requests.get(f"{API_BASE}/api/blockchain/info", timeout=5)
            if response.status_code == 200:
                data = response.json()
                height = data.get('height', 0)
                difficulty = data.get('difficulty', 0)
                bits = data.get('bits', 0)
                coins = data.get('total_money_coins', 0)

                epoch = height // RETARGET_INTERVAL
                blocks_in_epoch = height % RETARGET_INTERVAL
                blocks_to_retarget = RETARGET_INTERVAL - blocks_in_epoch
                progress = (blocks_in_epoch / RETARGET_INTERVAL) * 100

                # RETARGET EVENT DETECTION
                if epoch > previous_epoch and blocks_in_epoch < 10:
                    difficulty_change = difficulty - last_difficulty
                    change_pct = (difficulty_change / last_difficulty * 100) if last_difficulty > 0 else 0

                    alert = "\n" + ("!" * 80)
                    alert += "\n*** RETARGET EVENT DETECTED ***\n"
                    alert += f"Height: {height} | Epoch: #{epoch}\n"
                    alert += f"Previous Difficulty: {last_difficulty}\n"
                    alert += f"New Difficulty: {difficulty} (bits: {bits})\n"
                    alert += f"Change: {difficulty_change:+.0f} ({change_pct:+.2f}%)\n"
                    alert += ("!" * 80)

                    log_msg(alert)

                    previous_epoch = epoch
                    last_difficulty = difficulty

                # Periodic status update (every 10 checks = ~50 seconds)
                check_count += 1
                if check_count % 10 == 0:
                    log_msg(f"H:{height:>5} | {blocks_in_epoch:>4}/{RETARGET_INTERVAL} ({progress:>5.1f}%) | "
                           f"{blocks_to_retarget:>4} blocks to retarget | Supply: {coins:>8.0f}")

                if last_difficulty == 0:
                    last_difficulty = difficulty

                time.sleep(5)
            else:
                log_msg(f"API error: HTTP {response.status_code}")
                time.sleep(5)

        except KeyboardInterrupt:
            log_msg("=" * 80)
            log_msg("WATCHER STOPPED BY USER")
            log_msg("=" * 80)
            sys.exit(0)
        except Exception as e:
            log_msg(f"ERROR: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
