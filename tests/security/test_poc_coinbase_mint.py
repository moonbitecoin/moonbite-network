"""PoC regression for audit finding B1 — legacy-chain coinbase mint.

Root cause: validate_coinbase checked only sum(outputs) <= subsidy + fees, and
the coinbase never flows through Transaction.verify (which bounds each output to
0 < amount <= MAX_MONEY). So a coinbase with a huge positive output balanced by
a negative one summed to exactly the subsidy and passed — minting unbounded,
spendable value on the legacy Python chain.

These tests must FAIL against the pre-fix code and PASS after the per-output
bounds are added to validate_coinbase (utxo.py) and integer amounts are enforced
in TxOutput.from_dict (transaction.py).

Run:  python -m pytest tests/security/test_poc_coinbase_mint.py -v
"""

import pytest

import pow as powmod
from block import block_subsidy, build_block, create_coinbase
from node import INVALID, Node
from params import MAX_MONEY
from transaction import TxOutput
from utxo import validate_coinbase


def _malicious_coinbase(height, pkh, big=None):
    """A coinbase whose outputs SUM to exactly the subsidy (so the old sum-only
    check passes) but smuggle an out-of-range positive output balanced by a
    negative one."""
    big = MAX_MONEY if big is None else big
    cb = create_coinbase(height, pkh)
    subsidy = block_subsidy(height)
    cb.outputs = [
        TxOutput(big, pkh),                 # arbitrarily large — becomes spendable
        TxOutput(subsidy - big, pkh),       # negative, balances the sum
    ]
    assert sum(o.amount for o in cb.outputs) == subsidy  # defeats sum-only check
    return cb


def test_validate_coinbase_rejects_balanced_negative_output():
    cb = _malicious_coinbase(1, "aa" * 20)
    block = build_block(prev_hash="00" * 32, transactions=[cb], bits=0x1F00FFFF)
    # The sum check alone is satisfied; per-output bounds must reject it.
    assert validate_coinbase(block, height=1, expected_subsidy=block_subsidy(1),
                             fees=0) is False


def test_validate_coinbase_still_accepts_honest_coinbase():
    honest = create_coinbase(1, "bb" * 20)  # single output = subsidy
    block = build_block(prev_hash="00" * 32, transactions=[honest], bits=0x1F00FFFF)
    assert validate_coinbase(block, height=1, expected_subsidy=block_subsidy(1),
                             fees=0) is True


def test_mined_block_with_mint_coinbase_rejected_end_to_end():
    node = Node("solo")
    cb = _malicious_coinbase(1, "cc" * 20)
    block = build_block(prev_hash=node.chain.tip, transactions=[cb],
                        bits=node.chain.next_bits())
    powmod.mine(block)  # valid PoW — the only cost the attacker pays
    assert node.chain.add_block(block) == INVALID
    assert node.chain.height == 0  # nothing minted


def test_txoutput_from_dict_rejects_non_integer_amount():
    with pytest.raises(ValueError):
        TxOutput.from_dict({"amount": 1.5, "pubkey_hash": "dd" * 20})
    with pytest.raises(ValueError):
        TxOutput.from_dict({"amount": True, "pubkey_hash": "dd" * 20})
    # sanity: a normal integer output still round-trips
    assert TxOutput.from_dict({"amount": 5, "pubkey_hash": "dd" * 20}).amount == 5
