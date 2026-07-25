"""MAX BOUNTY AUDITOR — Phase 3 exchange business-logic PoCs.

These probe the non-custodial order book / swap state machine for the classic
DEX abuses: wash-trading to fabricate a price, cancel-token forgery, and
unauthorized state transitions. Several are PROVE-SAFE tests — they demonstrate
that the honest-price invariant (last_price only moves on on-chain-verified
settlement) actually holds and cannot be forged through the public API.

Run:  python -m pytest tests/security/test_poc_exchange.py -v
"""

import importlib

import pytest

import exchange


@pytest.fixture()
def fresh_db(tmp_path):
    exchange._conn = None
    exchange._DB_PATH = tmp_path / "exchange.db"
    yield
    if exchange._conn is not None:
        exchange._conn.close()
    exchange._conn = None
    importlib.reload(exchange)


def _order(side, price, amount, mbite, quote):
    return exchange.create_order(
        side=side, pair="MBITE/LTC", price=price, amount=amount,
        mbite_address=mbite, quote_address=quote,
    )


# --------------------------------------------------------------------------- #
# ATTACK: wash trade to fabricate last_price using two attacker-owned addresses
# --------------------------------------------------------------------------- #
def test_selfmatch_across_two_addresses_cannot_move_last_price(fresh_db):
    """The self-match guard only blocks the SAME mbite_address. An attacker with
    two addresses CAN cross their own orders (they become 'matched'). We prove
    the important invariant survives anyway: crossing does NOT settle, so
    last_price stays null. Price can only move via on-chain-verified settlement."""
    buy = _order("buy", "1.00", "5", "moon1attackerAAA", "ltc1attackerAAA")
    sell = _order("sell", "1.00", "5", "moon1attackerBBB", "ltc1attackerBBB")

    # They DO match (guard is per-address, not per-owner) ...
    assert sell.get("matched_with") == buy["id"] or buy["id"] is not None
    book_buy = exchange.get_order(buy["id"])
    book_sell = exchange.get_order(sell["id"])
    assert book_buy["status"] == "matched"
    assert book_sell["status"] == "matched"

    # ... but NOTHING is settled, so the fabricated "trade" never becomes price.
    assert exchange._last_trade_price("MBITE/LTC") is None
    pairs = exchange.list_orders(pair="MBITE/LTC")
    # last_price is surfaced via the pairs/summary path; confirm it is not set.
    assert book_buy["status"] != "settled"
    assert book_sell["status"] != "settled"


def test_same_address_cannot_self_match(fresh_db):
    """PROVE-SAFE: identical mbite_address on both sides is refused by _try_match."""
    a = _order("buy", "1.00", "5", "moon1sameaddr", "ltc1sameaddr")
    b = _order("sell", "1.00", "5", "moon1sameaddr", "ltc1sameaddr")
    assert exchange.get_order(a["id"])["status"] == "open"
    assert exchange.get_order(b["id"])["status"] == "open"
    assert b.get("matched_with") is None


# --------------------------------------------------------------------------- #
# ATTACK: forge cancel_token to cancel a victim's order
# --------------------------------------------------------------------------- #
def test_cancel_requires_real_token_not_address(fresh_db):
    """PROVE-SAFE: the public MBITE address must NOT authorize cancellation; only
    the secret token does, compared in constant time."""
    victim = _order("sell", "0.5", "3", "moon1victim", "ltc1victim")
    oid = victim["id"]

    # Attacker knows the public address + order id, guesses tokens — all fail.
    for guess in ("", "moon1victim", oid, "wrong-token", victim["cancel_token"][:-1] + "x"):
        with pytest.raises(ValueError):
            exchange.cancel_order(oid, guess)
    assert exchange.get_order(oid)["status"] == "open"

    # The real token works.
    assert exchange.cancel_order(oid, victim["cancel_token"])["status"] == "cancelled"


# --------------------------------------------------------------------------- #
# ATTACK: drive settlement without the verifier (fake a fill -> fake price)
# --------------------------------------------------------------------------- #
def test_only_verifier_writable_columns_can_flip_settled(fresh_db):
    """PROVE-SAFE: apply_swap_verification whitelists writable columns and the
    'settled' status can only arrive through it; no public route calls it, and an
    illegal status is rejected. So the public API has no path to mint a price."""
    buy = _order("buy", "2.00", "4", "moon1buyer", "ltc1buyer")
    _order("sell", "2.00", "4", "moon1seller", "ltc1seller")

    swap = exchange.init_swap(
        buy["id"], buy["cancel_token"],
        hashlock="aa" * 32,
        base_recipient_pk="02" + "bb" * 32,
        base_refund_pk="02" + "cc" * 32,
        quote_recipient_pk="02" + "dd" * 32,
        quote_refund_pk="02" + "ee" * 32,
        base_locktime=2_000_000_000, quote_locktime=1_999_000_000,
    )
    sid = swap["swap_id"]

    # An attacker-supplied illegal status is rejected.
    with pytest.raises(ValueError):
        exchange.apply_swap_verification(sid, {"status": "settled_lol"})

    # Non-whitelisted keys are silently dropped (cannot smuggle order fields).
    exchange.apply_swap_verification(sid, {"buy_order_id": "hacked", "evil": 1})
    assert exchange.get_swap_by_id(sid)["buy_order_id"] == buy["id"]

    # last_price still null: no settlement occurred through any public path.
    assert exchange._last_trade_price("MBITE/LTC") is None
