#!/usr/bin/env python3
"""
Live MoonBite Blockchain Monitor
Real-time monitoring of chain state, difficulty, mining activity, and network stats
"""

import requests
import time
from datetime import datetime, timedelta
from collections import deque
import os
import sys
import io

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_BASE = "https://moonbite.org"
REFRESH_INTERVAL = 2  # seconds
HISTORY_SIZE = 60  # keep 60 data points for graph

class BlockchainMonitor:
    def __init__(self):
        self.height_history = deque(maxlen=HISTORY_SIZE)
        self.difficulty_history = deque(maxlen=HISTORY_SIZE)
        self.coins_history = deque(maxlen=HISTORY_SIZE)
        self.block_time_history = deque(maxlen=HISTORY_SIZE)
        self.last_height = 0
        self.last_timestamp = time.time()
        self.start_time = time.time()
        self.blocks_mined_this_session = 0

    def clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def fetch_blockchain_info(self):
        """Fetch current blockchain state"""
        try:
            response = requests.get(f"{API_BASE}/api/blockchain/info", timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            pass
        return None

    def format_time_ago(self, seconds):
        """Format time difference in human-readable format"""
        if seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            return f"{int(seconds/60)}m ago"
        else:
            return f"{int(seconds/3600)}h ago"

    def draw_bar(self, value, max_value, width=40):
        """Draw a simple text-based bar graph"""
        if max_value == 0:
            return "█" * width
        filled = int((value / max_value) * width)
        return "█" * filled + "░" * (width - filled)

    def draw_sparkline(self, data):
        """Draw a sparkline graph from data points"""
        if not data or len(data) < 2:
            return ""

        sparklines = "▁▂▃▄▅▆▇█"
        min_val = min(data)
        max_val = max(data)

        if min_val == max_val:
            return "".join([sparklines[-1] for _ in data])

        result = ""
        for val in data:
            index = int((val - min_val) / (max_val - min_val) * (len(sparklines) - 1))
            result += sparklines[index]

        return result

    def update(self):
        """Fetch and update blockchain data"""
        info = self.fetch_blockchain_info()
        if not info:
            return False

        current_height = info.get('height', 0)
        current_time = time.time()

        # Track new blocks
        if current_height > self.last_height:
            self.blocks_mined_this_session += (current_height - self.last_height)
            block_time = current_time - self.last_timestamp
            self.block_time_history.append(block_time)

        self.height_history.append(current_height)
        self.difficulty_history.append(info.get('bits', 0))
        self.coins_history.append(info.get('total_money_coins', 0))

        self.last_height = current_height
        self.last_timestamp = current_time

        return info

    def render(self, info):
        """Render the monitoring dashboard"""
        self.clear_screen()

        current_time = datetime.now().strftime("%H:%M:%S")
        session_duration = time.time() - self.start_time

        # Header
        print("╔════════════════════════════════════════════════════════════════════════════╗")
        print("║                     * MOONBITE BLOCKCHAIN LIVE MONITOR *                   ║")
        print("╚════════════════════════════════════════════════════════════════════════════╝")
        print()

        # Real-time Stats
        print("[*] BLOCKCHAIN STATE")
        print("─" * 80)

        height = info.get('height', 0)
        bits = info.get('bits', 0)
        coins = info.get('total_money_coins', 0)
        tx_count = info.get('tx_count', 0)
        mempool = info.get('mempool_size', 0)
        tip_hash = info.get('tip_hash', '?')

        print(f"  Block Height:        {height:>10}  ", end="")

        # Visual bar for blocks
        blocks_to_retarget = 2016
        progress = min(height % blocks_to_retarget / blocks_to_retarget * 100, 100)
        if height < blocks_to_retarget:
            remaining = blocks_to_retarget - height
            print(f"[{self.draw_bar(height, blocks_to_retarget, 20)}] {progress:.1f}% to retarget")
            print(f"                       Blocks to retarget: {remaining}")
        else:
            retarget_num = (height // blocks_to_retarget)
            print(f"Retarget #{retarget_num} complete")

        print(f"  Difficulty:          {bits:>10} bits    ", end="")
        if len(self.difficulty_history) > 1:
            diff_change = self.difficulty_history[-1] - self.difficulty_history[-2]
            direction = "↑" if diff_change > 0 else ("↓" if diff_change < 0 else "→")
            print(f"{direction}")
        else:
            print()

        print(f"  Total MBITE:         {coins:>10.1f}    Circulating supply")
        print(f"  Transactions:        {tx_count:>10}    Total on chain")
        print(f"  Mempool:             {mempool:>10}    Pending transactions")
        print()

        # Hash
        print(f"  Tip Hash:            {tip_hash[:32]}...")
        print()

        # Mining Activity
        print("[+] MINING ACTIVITY")
        print("─" * 80)

        if len(self.block_time_history) > 0:
            avg_block_time = sum(self.block_time_history) / len(self.block_time_history)
            min_block_time = min(self.block_time_history)
            max_block_time = max(self.block_time_history)

            print(f"  Blocks this session: {self.blocks_mined_this_session:>10}")
            print(f"  Avg block time:      {avg_block_time:>10.1f}s")
            print(f"  Min block time:      {min_block_time:>10.1f}s")
            print(f"  Max block time:      {max_block_time:>10.1f}s")

            # Sparkline of block times
            sparkline = self.draw_sparkline(list(self.block_time_history))
            print(f"  Block time trend:    {sparkline}")
        else:
            print(f"  Waiting for blocks...")

        print()

        # Price & Supply
        print("[#] ECONOMICS")
        print("─" * 80)

        subsidy_per_block = 50
        blocks_mined = height
        from params import MAX_SUPPLY, CENTS_PER_COIN
    total_supply_cap = MAX_SUPPLY / CENTS_PER_COIN  # derived, never hardcoded

        print(f"  Block subsidy:       {subsidy_per_block:>10.1f} MBITE per block")
        print(f"  Mined supply:        {coins:>10.1f} / {total_supply_cap:.1f} ({100*coins/total_supply_cap:.2f}%)")
        print(f"  Remaining:           {total_supply_cap - coins:>10.1f} MBITE")

        # Halving calculation
        halving_interval = 210_000
        next_halving = ((height // halving_interval) + 1) * halving_interval
        blocks_to_halving = next_halving - height

        print(f"  Next halving:        Block {next_halving} ({blocks_to_halving} blocks away)")
        print()

        # Network Performance
        print("[>] NETWORK PERFORMANCE")
        print("─" * 80)

        if session_duration > 0:
            blocks_per_hour = self.blocks_mined_this_session / (session_duration / 3600)
            print(f"  Mining rate:         {blocks_per_hour:>10.2f} blocks/hour")

        print(f"  Session uptime:      {int(session_duration):>10}s ({int(session_duration/60)}m {int(session_duration%60)}s)")
        print(f"  Last update:         {current_time}")
        print()

        # Charts
        print("[^] TRENDS (last 60 updates)")
        print("─" * 80)

        if self.height_history:
            print(f"  Height trend:   {self.draw_sparkline(list(self.height_history))}")
        if self.difficulty_history:
            print(f"  Difficulty:     {self.draw_sparkline(list(self.difficulty_history))}")
        if self.coins_history:
            print(f"  Supply growth:  {self.draw_sparkline(list(self.coins_history))}")

        print()

        # Footer
        print("╔════════════════════════════════════════════════════════════════════════════╗")
        print("║ Updating every 2 seconds... Press Ctrl+C to stop monitoring               ║")
        print("╚════════════════════════════════════════════════════════════════════════════╝")

def main():
    """Main monitoring loop"""
    monitor = BlockchainMonitor()

    print("*** Starting MoonBite Blockchain Monitor...")
    print(f"==> Connecting to {API_BASE}")
    time.sleep(2)

    try:
        while True:
            info = monitor.update()
            if info:
                monitor.render(info)
            else:
                print("[X] Failed to connect to blockchain API")
                print(f"   Retrying in {REFRESH_INTERVAL} seconds...")

            time.sleep(REFRESH_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n")
        print("╔════════════════════════════════════════════════════════════════════════════╗")
        print("║                    [OK] MONITORING STOPPED                                  ║")
        print("╚════════════════════════════════════════════════════════════════════════════╝")
        print()

        # Final summary
        session_duration = time.time() - monitor.start_time
        print("[*] SESSION SUMMARY:")
        print(f"   Duration:     {int(session_duration/60)}m {int(session_duration%60)}s")
        print(f"   Blocks mined: {monitor.blocks_mined_this_session}")
        print(f"   Final height: {monitor.last_height}")
        if monitor.blocks_mined_this_session > 0:
            print(f"   Avg block time: {session_duration/monitor.blocks_mined_this_session:.1f}s")
        print()
        return 0

if __name__ == "__main__":
    sys.exit(main())
