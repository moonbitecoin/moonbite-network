#!/usr/bin/env python3
"""
Start blockchain from zero and run difficulty test.
Uses web_app.py to start the node and test_difficulty_from_zero.py to monitor.
"""

import subprocess
import time
import sys
import os

def main():
    print("="*70)
    print("MOONBITE DIFFICULTY TEST: START FROM ZERO")
    print("="*70)
    print()

    # Change to correct directory
    os.chdir(r"C:\Users\usman\Desktop\BigCoinBB")

    # Start the web app (which runs the node)
    print("[1/2] Starting blockchain node via web_app.py...")
    print()

    # Start in background
    node_process = subprocess.Popen(
        [sys.executable, "web_app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    print(f"[OK] Node process started (PID: {node_process.pid})")
    print()

    # Wait for node to start
    print("Waiting 15 seconds for node to initialize...")
    time.sleep(15)

    print("[OK] Node should be ready")
    print()

    # Start the test
    print("[2/2] Starting difficulty monitor...")
    print()
    print("="*70)
    print()

    try:
        # Run test in foreground
        test_process = subprocess.Popen(
            [sys.executable, "test_difficulty_from_zero.py"],
            text=True
        )

        # Wait for test to complete
        test_process.wait()

        print()
        print("="*70)
        print("[OK] Test completed!")
        print("="*70)

    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Test stopped by user")
    finally:
        # Clean up
        print()
        print("Cleaning up...")
        try:
            node_process.terminate()
            node_process.wait(timeout=5)
            print("[OK] Node process stopped")
        except:
            node_process.kill()
            print("[OK] Node process killed")

if __name__ == "__main__":
    main()
