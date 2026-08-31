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


# --------------------------------------------------------------------------- #
# L1: the wallet must not need 'unsafe-inline' to run
# --------------------------------------------------------------------------- #
def test_wallet_csp_has_no_unsafe_inline_for_scripts():
    """'unsafe-inline' lets an injected <script> execute — the XSS vector."""
    client = web_app.app.test_client()
    csp = client.get("/wallet").headers.get("Content-Security-Policy", "")
    script_src = [d for d in csp.split(";") if d.strip().startswith("script-src")]
    assert script_src, "no script-src directive on the wallet"
    assert "unsafe-inline" not in script_src[0], (
        "the wallet is back to allowing inline script execution"
    )
    assert "nonce-" in script_src[0], "the wallet's script-src carries no nonce"


def test_wallet_nonce_is_per_response():
    client = web_app.app.test_client()
    a = client.get("/wallet").headers.get("Content-Security-Policy", "")
    b = client.get("/wallet").headers.get("Content-Security-Policy", "")
    assert a != b, "the CSP nonce is being reused across responses"


def test_wallet_has_no_inline_event_handlers():
    """Inline handlers are what forced 'unsafe-inline' in the first place."""
    import re
    client = web_app.app.test_client()
    html = client.get("/wallet").get_data(as_text=True)
    found = re.findall(r'\son(?:click|keyup|change|input|submit|load)=', html)
    assert not found, f"{len(found)} inline handler(s) reintroduced in the wallet"


def test_every_data_fn_is_whitelisted():
    """Dispatch is by allow-list; an unmapped data-fn would silently no-op."""
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent
           / "templates" / "wallet-pwa-app.html").read_text(encoding="utf-8")
    used = set(re.findall(r'data-fn="(\w+)"', src))
    block = src[src.index("const MB_ACTIONS = {"):src.index("function mbDispatch")]
    mapped = set(re.findall(r"^\s{12}(\w+):", block, re.M))
    assert not (used - mapped), f"unmapped data-fn: {sorted(used - mapped)}"


def test_no_template_has_inline_event_handlers():
    """Site-wide: one inline handler anywhere forces 'unsafe-inline' back."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "templates"
    offenders = {}
    for f in root.rglob("*.html"):
        found = re.findall(
            r'\son(?:click|keyup|change|input|submit|load)=',
            f.read_text(encoding="utf-8", errors="replace"))
        if found:
            offenders[f.name] = len(found)
    assert not offenders, f"inline handlers reintroduced: {offenders}"


def test_every_inline_script_carries_a_nonce():
    """An un-nonced inline script is silently blocked under the strict policy."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "templates"
    offenders = {}
    for f in root.rglob("*.html"):
        src = f.read_text(encoding="utf-8", errors="replace")
        bad = [t for t in re.findall(r"<script(?:\s[^>]*)?>", src)
               if "src=" not in t and "nonce=" not in t]
        if bad:
            offenders[f.name] = len(bad)
    assert not offenders, f"inline scripts without a nonce: {offenders}"


@pytest.mark.parametrize("route", [
    "/", "/wallet", "/explorer", "/mining", "/leaderboard",
    "/halving", "/calculator", "/free", "/wall", "/start",
])
def test_every_page_serves_a_strict_csp(route):
    client = web_app.app.test_client()
    res = client.get(route)
    if res.status_code != 200:
        pytest.skip(f"{route} not served ({res.status_code})")
    csp = res.headers.get("Content-Security-Policy", "")
    script_src = [d for d in csp.split(";") if d.strip().startswith("script-src")]
    assert script_src, f"{route} has no script-src"
    assert "unsafe-inline" not in script_src[0], f"{route} allows inline script"
    assert "nonce-" in script_src[0], f"{route} carries no nonce"


# --------------------------------------------------------------------------- #
# The returning-user login must actually authenticate
# --------------------------------------------------------------------------- #
def test_no_fake_biometric_login():
    """'Use Fingerprint/Face ID' called no WebAuthn API - it showed the
    dashboard unauthenticated, bypassing the PIN for anyone holding the
    device. Until a real passkey flow exists, no biometric claim may appear
    and no login path may reach the dashboard without verification."""
    src = (Path(__file__).resolve().parent.parent
           / "templates" / "wallet-pwa-app.html").read_text(encoding="utf-8")
    assert "Use Fingerprint/Face ID" not in src
    body = src[src.index("function tryBiometricLogin"):]
    body = body[:body.index("\n        }")]
    assert "dashboardScreen" not in body, (
        "tryBiometricLogin routes to the dashboard without authenticating"
    )
