"""MoonBite — Proof-of-Work with Bitcoin-compatible difficulty adjustment.

Mining searches for a header nonce whose double-SHA-256 hash is below a target.
This implements Bitcoin's actual retargeting algorithm (Bitcoin Core):

1. Every 2016 blocks, recalculate the target based on actual vs. expected time
2. New target = old target × (actual_timespan / expected_timespan)
3. Clamp to prevent wild swings: new_target in [old/4, old×4]
4. Ensure minimum target >= MINIMUM_TARGET

Design: `bits` encodes the target as a compact representation (similar to Bitcoin).
For simplicity, we store the target as a full 256-bit integer and convert to/from
bits when needed for the chain (for compatibility with block headers).

This is **identical to Bitcoin's algorithm** and produces the same difficulty
adjustments over 2-week (2016-block) cycles.
"""

from __future__ import annotations
import math
from block import Block

# Consensus timing comes from params.py — the single source of truth.
from params import TARGET_BLOCK_TIME
from params import RETARGET_INTERVAL  # single source of truth
EXPECTED_TIMESPAN = TARGET_BLOCK_TIME * RETARGET_INTERVAL  # 20,160 minutes = 1,209,600 seconds

# Difficulty bounds
MIN_BITS = 1
MAX_BITS = 240  # keep well under 256 so a target always exists

# Minimum target (Bitcoin's limit, corresponds to bits=0x1d00ffff)
# This is roughly 2^224, but we use a simpler bound: allow down to 1 bit difficulty
MINIMUM_TARGET = 1 << (256 - MAX_BITS)  # = 2^(256-240) = 2^16
MAXIMUM_TARGET = 1 << (256 - MIN_BITS)  # = 2^(256-1) = nearly all hashes valid


def bits_to_target(bits: int) -> int:
    """Convert difficulty bits to full 256-bit target.

    bits is the count of required leading zero bits.
    target = 2^(256 - bits)
    """
    if bits < MIN_BITS or bits > MAX_BITS:
        raise ValueError(f"bits {bits} outside range [{MIN_BITS}, {MAX_BITS}]")
    return 1 << (256 - bits)


def target_to_bits(target: int) -> int:
    """Convert 256-bit target back to difficulty bits.

    bits = 256 - log2(target), rounded appropriately.
    Ensures target is within valid range.
    """
    if target < MINIMUM_TARGET:
        return MAX_BITS
    if target >= MAXIMUM_TARGET:
        return MIN_BITS

    # Find the highest bit position in target
    # bit_length() gives position of highest bit + 1
    # For target = 2^n, we need bits = 256 - n
    # So bits = 256 - (bit_length() - 1) = 257 - bit_length()
    bit_length = target.bit_length()
    if bit_length > 256:
        return MIN_BITS

    bits = 257 - bit_length
    return max(MIN_BITS, min(MAX_BITS, bits))


def hash_meets_target(hash_hex: str, bits: int) -> bool:
    """True if hash is below the target (hash < 2^(256-bits))."""
    target = bits_to_target(bits)
    return int(hash_hex, 16) < target


def block_meets_target(block: Block) -> bool:
    return hash_meets_target(block.hash, block.header.bits)


def mine(block: Block, max_nonce: int = 1 << 32) -> bool:
    """Increment the block's nonce until its hash meets the target.

    Returns True and leaves the winning nonce in the header on success; returns
    False if the nonce space is exhausted (caller should change something, e.g.
    the coinbase extra-nonce or timestamp, and retry).
    """
    for nonce in range(max_nonce):
        block.header.nonce = nonce
        if hash_meets_target(block.hash, block.header.bits):
            return True
    return False


def calculate_next_bits(
    current_bits: int, actual_timespan: int, expected_timespan: int | None = None
) -> int:
    """Bitcoin-compatible difficulty retarget.

    Called every RETARGET_INTERVAL (2016) blocks. Adjusts the target based on
    how long the last interval actually took vs. expected time.

    Algorithm (identical to Bitcoin Core):
    1. new_target = old_target * (actual_timespan / expected_timespan)
    2. Clamp to [old_target/4, old_target*4] to prevent wild swings
    3. Ensure within [MINIMUM_TARGET, MAXIMUM_TARGET]

    Args:
        current_bits: Current difficulty (leading zero bits)
        actual_timespan: How long the last 2016 blocks actually took (seconds)
        expected_timespan: Expected time for 2016 blocks (defaults to 1,209,600 sec)

    Returns:
        New difficulty in bits, clamped to valid range.
    """
    if expected_timespan is None:
        expected_timespan = EXPECTED_TIMESPAN

    # Convert current bits to target
    old_target = bits_to_target(current_bits)

    # Bitcoin's algorithm: adjust target by timespan ratio, with clamp
    # new_target = old_target * (actual_timespan / expected_timespan)

    # Clamp actual_timespan to prevent extreme adjustments
    # Bitcoin clamps to [timespan/4, timespan*4]
    min_timespan = expected_timespan // 4
    max_timespan = expected_timespan * 4
    clamped_timespan = max(min_timespan, min(max_timespan, actual_timespan))

    # Calculate new target (using integer arithmetic to avoid float errors)
    # new_target = old_target * clamped_timespan / expected_timespan
    new_target = (old_target * clamped_timespan) // expected_timespan

    # Ensure target stays within valid bounds
    new_target = max(MINIMUM_TARGET, min(MAXIMUM_TARGET, new_target))

    # Convert back to bits
    new_bits = target_to_bits(new_target)

    return new_bits
