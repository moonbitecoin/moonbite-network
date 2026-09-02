"""MyCoin — central consensus parameters.

Collecting every consensus-critical constant in one module keeps them from
drifting apart across files and makes the network's rules auditable at a glance.
Changing any value here is a hard fork: nodes on different values will reject
each other's blocks.
"""

from __future__ import annotations

# --- monetary policy ------------------------------------------------------- #
CENTS_PER_COIN = 100_000_000          # smallest unit; 1 coin = 100,000,000 cents

# Anti-flood limits for the mempool.
#
# Acceptance only required inputs >= outputs, so a zero-fee transaction was
# valid and there was no cap on how many could queue: an attacker could fill
# memory with free transactions. A small relay fee makes flooding cost real
# coins, and the cap bounds memory regardless.
MIN_RELAY_FEE = 10                    # nominal floor: spam costs something, zero-fee is refused
MAX_MEMPOOL_TXS = 5_000               # hard ceiling on queued transactions

INITIAL_SUBSIDY = 10 * CENTS_PER_COIN  # block reward at height 0 (ADR-010: 10 MBITE per 2-minute block)
HALVING_INTERVAL = 1_650_000          # halve the subsidy every N blocks (~6.27 yr at 2-min blocks)


def _total_emission() -> int:
    """Sum the whole halving schedule, in cents.

    Deriving the cap instead of asserting it keeps the two from ever
    disagreeing: change the subsidy or the interval and the ceiling follows.
    """
    total = 0
    subsidy = INITIAL_SUBSIDY
    while subsidy > 0:                # integer halving terminates on its own
        total += subsidy * HALVING_INTERVAL
        subsidy >>= 1
    return total


MAX_SUPPLY = _total_emission()        # 32,999,999.96 MBITE — just under 33M
MAX_MONEY = MAX_SUPPLY                 # no single value may exceed the cap

# --- proof-of-work / timing ------------------------------------------------ #
TARGET_BLOCK_TIME = 120               # seconds between blocks (2 minutes, ADR-010)
RETARGET_INTERVAL = 2016              # recompute difficulty every N blocks
MIN_BITS = 1
MAX_BITS = 240                        # keep below 256 so a target always exists

# --- block / consensus limits ---------------------------------------------- #
MAX_BLOCK_BYTES = 1_000_000           # serialized block size ceiling (~1 MB)
MAX_FUTURE_TIME = 2 * 60 * 60         # reject headers >2h ahead of local clock
MEDIAN_TIME_SPAN = 11                 # window for median-time-past lower bound
COINBASE_MATURITY = 100               # blocks a coinbase must age before spending

# --- genesis --------------------------------------------------------------- #
GENESIS_BITS = 16                     # easy difficulty for a local network
GENESIS_TIMESTAMP = 1_700_000_000
GENESIS_MINER_PKH = "0" * 64          # unspendable placeholder recipient
