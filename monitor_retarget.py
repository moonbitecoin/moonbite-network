#!/usr/bin/env python3
"""
MoonBite Retarget Event Monitor
Continuously monitors blockchain and alerts when retarget happens
"""

import requests
import time
import sys
import io
from datetime import datetime

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_BASE = "https://moonbite.org"
RETARGET_INTERVAL = 2016
CHECK_INTERVAL = 5  # seconds between checks
BLOCKS_WARNING_THRESHOLD = 100  # alert when N blocks away from retarget

class RetargetMonitor:
    def __init__(self):
        self.last_height = 0
        self.last_difficulty = 0
        self.retarget_count = 0
        self.session_start = time.time()
        self.last_retarget_height = 0

    def fetch_info(self):
        """Fetch blockchain info from API"""
        try:
            response = requests.get(f"{API_BASE}/api/blockchain/info", timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"[!] API Error: {e}")
        return None

    def format_time(self, seconds):
        """Format seconds to readable time"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m {int(seconds%60)}s"
        else:
            hours = int(seconds/3600)
            minutes = int((seconds % 3600)/60)
            return f"{hours}h {minutes}m"

    def check_retarget(self, height, difficulty):
        """Check if retarget happened and return status"""
        blocks_into_epoch = height % RETARGET_INTERVAL
        blocks_to_retarget = RETARGET_INTERVAL - blocks_into_epoch
        current_epoch = height // RETARGET_INTERVAL

        return {
            'epoch': current_epoch,
            'blocks_in_epoch': blocks_into_epoch,
            'blocks_to_retarget': blocks_to_retarget,
            'progress': (blocks_into_epoch / RETARGET_INTERVAL) * 100,
        }

    def run(self):
        """Main monitoring loop"""
        print("=" * 80)
        print("MOONBITE RETARGET EVENT MONITOR")
        print("=" * 80)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Target retarget interval: {RETARGET_INTERVAL} blocks")
        print("=" * 80)
        print()

        previous_epoch = -1

        while True:
            try:
                info = self.fetch_info()
                if not info:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Connection failed, retrying...")
                    time.sleep(CHECK_INTERVAL)
                    continue

                height = info.get('height', 0)
                difficulty = info.get('difficulty', 0)
                bits = info.get('bits', 0)

                retarget_status = self.check_retarget(height, difficulty)
                current_epoch = retarget_status['epoch']
                blocks_in_epoch = retarget_status['blocks_in_epoch']
                blocks_to_retarget = retarget_status['blocks_to_retarget']
                progress = retarget_status['progress']

                # Check if we just passed a retarget
                if current_epoch > previous_epoch and blocks_in_epoch < 10:
                    # Retarget just happened!
                    difficulty_change = difficulty - self.last_difficulty
                    change_pct = (difficulty_change / self.last_difficulty * 100) if self.last_difficulty > 0 else 0

                    print()
                    print("!" * 80)
                    print("[RETARGET EVENT DETECTED]")
                    print("!" * 80)
                    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"Block Height: {height}")
                    print(f"Retarget Epoch: #{current_epoch}")
                    print(f"Previous Difficulty: {self.last_difficulty}")
                    print(f"New Difficulty: {difficulty}")
                    print(f"Change: {difficulty_change:+.0f} ({change_pct:+.2f}%)")
                    print(f"Difficulty Bits: {bits}")
                    print("!" * 80)
                    print()

                    previous_epoch = current_epoch
                    self.last_difficulty = difficulty

                # Status update every CHECK_INTERVAL seconds
                session_duration = time.time() - self.session_start
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Height: {height:>6} | "
                      f"Epoch {current_epoch}: {blocks_in_epoch:>4}/{RETARGET_INTERVAL} "
                      f"({progress:>5.1f}%) | "
                      f"{blocks_to_retarget:>4} blocks to retarget | "
                      f"Diff: {difficulty:>10.0f} | "
                      f"Uptime: {self.format_time(session_duration)}")

                # Alert when close to retarget
                if blocks_to_retarget <= BLOCKS_WARNING_THRESHOLD and blocks_to_retarget > 0:
                    if blocks_to_retarget % 50 == 0 or blocks_to_retarget <= 10:
                        print(f"    >>> {blocks_to_retarget} blocks away from retarget! <<<")

                self.last_height = height
                if self.last_difficulty == 0:
                    self.last_difficulty = difficulty

                time.sleep(CHECK_INTERVAL)

            except KeyboardInterrupt:
                print()
                print()
                print("=" * 80)
                print("MONITORING STOPPED")
                print("=" * 80)
                session_duration = time.time() - self.session_start
                print(f"Session duration: {self.format_time(session_duration)}")
                print(f"Final height: {self.last_height}")
                print(f"Retargets observed: {self.retarget_count}")
                print("=" * 80)
                sys.exit(0)
            except Exception as e:
                print(f"[ERROR] {e}")
                time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    monitor = RetargetMonitor()
    monitor.run()
