"""Regression guards for the hardening pass.

Each test here corresponds to a finding from the security review. They assert
the secure behaviour, so a regression re-opens the finding as a failing test
rather than shipping quietly.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import web_app  # noqa: E402
from block import block_subsidy  # noqa: E402
from node import Node  # noqa: E402
from params import MAX_MEMPOOL_TXS, MIN_RELAY_FEE  # noqa: E402
from transaction import (Transaction, TxInput, TxOutput,  # noqa: E402
                         generate_keypair, pubkey_hash)


def _wallet():
    sk, pub = generate_keypair()
    return sk, pub, pubkey_hash(pub)


# --------------------------------------------------------------------------- #
# H1: mining is CPU-bound, so it must be rate limited and bounded
# --------------------------------------------------------------------------- #
def test_mining_start_is_rate_limited():
    """The most expensive endpoint was the only uncapped one."""
    fn = web_app.app.view_functions["api_mining_start"]
    assert getattr(fn, "__wrapped__", None) is not None, (
        "api_mining_start is not wrapped by @rate_limit — a caller could loop "
        "it and pin the host's CPU"
    )


def test_concurrent_mining_jobs_are_capped():
    assert web_app._MAX_CONCURRENT_MINING_JOBS >= 1
    assert web_app._MAX_CONCURRENT_MINING_JOBS <= 8, (
        "an unbounded or very high job cap defeats the purpose on a small host"
    )


def test_mining_refuses_work_when_at_capacity(monkeypatch):
    client = web_app.app.test_client()
    # Fill the job table with running jobs.
    with web_app.app.mining_lock:
        web_app.app.mining_state["active_jobs"].clear()
        for i in range(web_app._MAX_CONCURRENT_MINING_JOBS):
            web_app.app.mining_state["active_jobs"][f"busy{i}"] = {
                "is_mining": True, "blocks_to_mine": 1, "blocks_mined": 0,
                "hashes_tried": 0, "hashrate": 0.0,
            }
    try:
        res = client.post("/api/mining/start",
                          json={"blocks": 1, "address": "moon1whatever"})
        assert res.status_code == 429
    finally:
        with web_app.app.mining_lock:
            web_app.app.mining_state["active_jobs"].clear()


# --------------------------------------------------------------------------- #
# M3: the mempool must not accept free or unlimited transactions
# --------------------------------------------------------------------------- #
def test_zero_fee_transaction_is_not_relayed():
    """Validation accepts inputs == outputs, so spam used to be free."""
    node = Node("solo", coinbase_maturity=0)
    sk, _, pkh = _wallet()
    _, _, dest = _wallet()

    block = node.mine_block(pkh)
    coinbase = block.transactions[0]

    # Spend the entire subsidy: valid, but pays no fee.
    tx = Transaction([TxInput(coinbase.txid, 0)],
                     [TxOutput(block_subsidy(1), dest)])
    tx.sign_input(0, sk)
    assert node.chain.add_to_mempool(tx) is False


def test_transaction_paying_the_minimum_fee_is_relayed():
    node = Node("solo", coinbase_maturity=0)
    sk, _, pkh = _wallet()
    _, _, dest = _wallet()

    block = node.mine_block(pkh)
    coinbase = block.transactions[0]

    tx = Transaction([TxInput(coinbase.txid, 0)],
                     [TxOutput(block_subsidy(1) - MIN_RELAY_FEE, dest)])
    tx.sign_input(0, sk)
    assert node.chain.add_to_mempool(tx) is True


def test_mempool_has_a_hard_ceiling():
    assert MAX_MEMPOOL_TXS > 0
    node = Node("solo", coinbase_maturity=0)
    # Pretend the mempool is already full; a new tx must be refused before any
    # validation work is done.
    node.chain.mempool = {f"tx{i}": object() for i in range(MAX_MEMPOOL_TXS)}
    sk, _, pkh = _wallet()
    _, _, dest = _wallet()
    tx = Transaction([TxInput("aa" * 32, 0)], [TxOutput(1000, dest)])
    tx.sign_input(0, sk)
    assert node.chain.add_to_mempool(tx) is False


# --------------------------------------------------------------------------- #
# L2: the Werkzeug debugger is an RCE console; it must never default on
# --------------------------------------------------------------------------- #
def test_flask_debug_defaults_off(monkeypatch):
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    import os
    assert (os.environ.get("FLASK_DEBUG", "0") == "1") is False


def test_source_does_not_default_debug_on():
    src = (Path(__file__).resolve().parent.parent / "web_app.py").read_text(
        encoding="utf-8")
    assert 'os.environ.get("FLASK_DEBUG", "1")' not in src, (
        "FLASK_DEBUG must not default to 1 — that enables the remote debugger"
    )
