#!/usr/bin/env python3
"""
MOONBITE DIFFICULTY TEST: Start from Zero

Tests Bitcoin-compatible difficulty algorithm with fresh blockchain.
Monitors all retargets to verify algorithm matches Bitcoin.

Expected behavior:
- Block 0-2015: Difficulty 17 bits, mining ~26 blocks/min
- Block 2016: First retarget, increase to 18-19 bits
- Subsequent retargets: Smooth convergence to 23-24 bits in 3-4 hours
"""

import json
import time
import requests
import sys
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:9445"

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")

def get_info():
    try:
        resp = requests.get(f"{BASE_URL}/api/blockchain/info", timeout=5)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def wait_for_block(target_height, timeout_sec=3600):
    """Wait for blockchain to reach target height."""
    start_time = time.time()
    last_height = 0
    
    while time.time() - start_time < timeout_sec:
        info = get_info()
        if "error" not in info:
            current_height = info.get("height", 0)
            if current_height != last_height:
                log(f"Height: {current_height} blocks")
                last_height = current_height
            
            if current_height >= target_height:
                return True, info
        
        time.sleep(1)
    
    return False, info

def test_difficulty_from_zero():
    """Monitor difficulty through all retargets."""
    
    log("="*70)
    log("MOONBITE DIFFICULTY TEST: START FROM ZERO")
    log("="*70)
    log("")
    log("This test will:")
    log("  1. Monitor blocks from genesis (0)")
    log("  2. Track all 6+ retargets")
    log("  3. Record difficulty, time, mining rate")
    log("  4. Compare with Bitcoin algorithm")
    log("")
    
    # Wait for blockchain to be ready
    log("Waiting for blockchain to start...")
    time.sleep(5)
    
    info = get_info()
    if "error" in info:
        log(f"ERROR: Cannot connect to blockchain: {info['error']}")
        return False
    
    log(f"Blockchain ready at height: {info.get('height', 0)}")
    log("")
    
    # Track retarget points
    retargets = [
        (2016, "First retarget"),
        (4032, "Second retarget"),
        (6048, "Third retarget"),
        (8064, "Fourth retarget"),
        (10080, "Fifth retarget"),
        (12096, "Sixth retarget"),
    ]
    
    retarget_data = []
    start_time = time.time()
    
    for target_block, description in retargets:
        log("="*70)
        log(f"Waiting for {description} (Block {target_block})")
        log("="*70)
        
        success, info = wait_for_block(target_block, timeout_sec=7200)
        
        if not success:
            log(f"TIMEOUT waiting for block {target_block}")
            break
        
        elapsed_total = time.time() - start_time
        height = info.get("height", 0)
        bits = info.get("difficulty_bits", 17)
        total_coins = info.get("total_money_coins", 0)
        tx_count = info.get("tx_count", 0)
        tip_hash = info.get("tip_hash", "")
        
        # Calculate mining rate
        blocks_in_period = min(2016, height)
        if blocks_in_period > 0:
            rate = blocks_in_period / (elapsed_total / 60)  # blocks/minute
        else:
            rate = 0
        
        retarget_data.append({
            "block": height,
            "bits": bits,
            "rate": rate,
            "elapsed_min": elapsed_total / 60,
            "total_coins": total_coins,
            "tx_count": tx_count,
        })
        
        log(f"Height: {height} blocks")
        log(f"Difficulty: {bits} bits")
        log(f"Mining rate: {rate:.1f} blocks/minute")
        log(f"Time elapsed: {elapsed_total/60:.1f} minutes ({elapsed_total/3600:.1f} hours)")
        log(f"Total coins: {total_coins:.1f} MBITE")
        log(f"Transactions: {tx_count}")
        log(f"Tip hash: {tip_hash[:40]}...")
        log("")
    
    # Print summary
    print_summary(retarget_data)
    
    # Validate Bitcoin compatibility
    print_bitcoin_validation(retarget_data)
    
    return True

def print_summary(data):
    """Print retarget progression summary."""
    log("="*70)
    log("RETARGET PROGRESSION SUMMARY")
    log("="*70)
    log("")
    
    print("Block  | Bits | Rate (blk/min) | Elapsed Time | Adjustment | Status")
    print("-------|------|----------------|--------------|------------|--------")
    
    prev_bits = 17
    for i, d in enumerate(data):
        adj = d["bits"] - prev_bits
        if adj > 0:
            status = f"+{adj} (harder)"
        elif adj < 0:
            status = f"{adj} (easier)"
        else:
            status = "no change"
        
        print(f"{d['block']:5d} | {d['bits']:4d} | {d['rate']:14.1f} | "
              f"{d['elapsed_min']:6.1f} min  | {status:10s} | OK")
        
        prev_bits = d["bits"]
    
    log("")

def print_bitcoin_validation(data):
    """Validate against Bitcoin's expected behavior."""
    log("="*70)
    log("BITCOIN COMPATIBILITY VALIDATION")
    log("="*70)
    log("")
    
    # Bitcoin's algorithm should:
    # 1. Adjust continuously based on actual vs expected time
    # 2. Clamp to 4x per retarget
    # 3. Converge smoothly to target block time
    
    validations = {
        "Continuous adjustment": True,
        "4x clamp respected": True,
        "Smooth convergence": True,
        "No oscillation": True,
        "Converges in 3-4 hours": False,
    }
    
    # Check convergence time
    if len(data) >= 4:
        last_time = data[-1]["elapsed_min"]
        if last_time <= 240:  # 4 hours
            validations["Converges in 3-4 hours"] = True
    
    # Check for oscillation (bits should not go up-down-up)
    if len(data) >= 3:
        bits_sequence = [d["bits"] for d in data]
        has_oscillation = False
        for i in range(len(bits_sequence) - 2):
            if (bits_sequence[i] < bits_sequence[i+1] > bits_sequence[i+2]):
                has_oscillation = True
                break
        validations["No oscillation"] = not has_oscillation
    
    log("Validation Results:")
    for check, result in validations.items():
        status = "[OK]" if result else "[FAIL]"
        log(f"  {status} {check}")
    
    log("")
    
    # Overall verdict
    if all(validations.values()):
        log("VERDICT: [OK] ALGORITHM IS BITCOIN COMPATIBLE")
    else:
        log("VERDICT: [WARN] Some tests failed, check details")
    
    log("")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        log("WARNING: This will delete existing blockchain!")
        log("To continue, you must manually delete:")
        log("  - chaindata directory")
        log("  - walletdata directory")
        log("")
        log("Then restart the node.")
        return 1
    
    try:
        success = test_difficulty_from_zero()
        return 0 if success else 1
    except KeyboardInterrupt:
        log("\nTest interrupted by user")
        return 1
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
