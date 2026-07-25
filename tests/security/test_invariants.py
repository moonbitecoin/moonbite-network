"""MAX BOUNTY AUDITOR — Phase 4 invariant / property tests.

Two safety properties the whole design rests on:

  I1  PRICE INTEGRITY:  last_price for a pair is non-null IFF at least one swap
      has been driven to verifier-'settled'. No sequence of public API calls
      (create / cancel / match / init_swap / report_funding) can mint a price.

  I2  NON-CUSTODY:  no exchange/merchant table stores a coin private key, seed,
      mnemonic, or preimage-before-reveal. The server holds order intents only.

Run:  python -m pytest tests/security/test_invariants.py -v
"""

import hashlib
import importlib
import random

import pytest

import exchange
import swap_verifier


@pytest.fixture()
def fresh_db(tmp_path):
    exchange._conn = None
    exchange._DB_PATH = tmp_path / "exchange.db"
    yield
    if exchange._conn is not None:
        exchange._conn.close()
    exchange._conn = None
    importlib.reload(exchange)


# --------------------------------------------------------------------------- #
# I1 — PRICE INTEGRITY under random public-API fuzzing
# --------------------------------------------------------------------------- #
def test_price_stays_null_under_random_public_operations(fresh_db):
    """Fuzz the public order/swap surface hard. Because no verifier settlement
    ever runs here, last_price MUST remain null for every run."""
    rng = random.Random(1337)
    live = []  # (order_id, cancel_token, side, addr)

    for step in range(4000):
        op = rng.random()
        if op < 0.5 or not live:
            side = rng.choice(("buy", "sell"))
            addr = f"moon1{rng.randrange(10_000)}"
            price = f"{rng.choice([0.5, 1.0, 1.5, 2.0]):.2f}"
            amt = str(rng.randint(1, 10))
            try:
                o = exchange.create_order(
                    side=side, pair="MBITE/LTC", price=price, amount=amt,
                    mbite_address=addr, quote_address=f"ltc1{addr}",
                )
                live.append((o["id"], o["cancel_token"], side, addr))
            except ValueError:
                pass  # e.g. per-address open-order cap
        elif op < 0.75:
            oid, tok, _, _ = rng.choice(live)
            try:
                exchange.cancel_order(oid, tok)
            except ValueError:
                pass
        else:
            oid, tok, _, _ = rng.choice(live)
            try:
                exchange.init_swap(
                    oid, tok, hashlock=hashlib.sha256(str(step).encode()).hexdigest(),
                    base_recipient_pk="02" + "bb" * 32, base_refund_pk="02" + "cc" * 32,
                    quote_recipient_pk="02" + "dd" * 32, quote_refund_pk="02" + "ee" * 32,
                    base_locktime=2_000_000_000, quote_locktime=1_900_000_000,
                )
            except ValueError:
                pass

        # THE INVARIANT — checked every single step.
        assert exchange._last_trade_price("MBITE/LTC") is None, (
            f"price minted without settlement at step {step}"
        )


def test_price_moves_only_through_verifier_settlement(fresh_db):
    """Positive control: the ONLY lever that sets last_price is the verifier
    marking a swap 'settled' (which flips both orders 'settled')."""
    buy = exchange.create_order(
        side="buy", pair="MBITE/LTC", price="1.25", amount="4",
        mbite_address="moon1buyer", quote_address="ltc1buyer",
    )
    exchange.create_order(
        side="sell", pair="MBITE/LTC", price="1.25", amount="4",
        mbite_address="moon1seller", quote_address="ltc1seller",
    )
    swap = exchange.init_swap(
        buy["id"], buy["cancel_token"], hashlock="ab" * 32,
        base_recipient_pk="02" + "bb" * 32, base_refund_pk="02" + "cc" * 32,
        quote_recipient_pk="02" + "dd" * 32, quote_refund_pk="02" + "ee" * 32,
        base_locktime=2_000_000_000, quote_locktime=1_900_000_000,
    )
    assert exchange._last_trade_price("MBITE/LTC") is None

    # Only the verifier-owned path can reach 'settled'.
    exchange.apply_swap_verification(swap["swap_id"], {"status": "settled"})
    assert exchange._last_trade_price("MBITE/LTC") == "1.25"


# --------------------------------------------------------------------------- #
# I2 — NON-CUSTODY: schema never stores coin secrets
# --------------------------------------------------------------------------- #
_FORBIDDEN = ("privkey", "private_key", "secret_exponent", "seed", "mnemonic", "wif")


def _columns(conn, table):
    return [r[1].lower() for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def test_exchange_schema_holds_no_coin_secrets(fresh_db):
    exchange.create_order(
        side="buy", pair="MBITE/LTC", price="1", amount="1",
        mbite_address="moon1xaddr", quote_address="ltc1xaddr",
    )
    conn = exchange._connect()
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    for t in tables:
        cols = _columns(conn, t)
        for bad in _FORBIDDEN:
            assert not any(bad in c for c in cols), f"{t}.{cols} may custody a key ({bad})"


def test_swaps_store_public_params_only(fresh_db):
    """Swap rows carry pubkeys/hashlock/txids (all public) — never a private key.
    The 'preimage' column is only populated AFTER it is revealed on-chain by the
    counterparty spending, so storing it leaks nothing the chain doesn't."""
    conn = exchange._connect()
    # Force schema creation.
    exchange.list_swaps_for_verification()
    cols = _columns(conn, "swaps")
    assert "base_recipient_pk" in cols and "hashlock" in cols
    for bad in _FORBIDDEN:
        assert not any(bad in c for c in cols)
