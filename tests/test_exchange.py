"""Tests for the non-custodial order book — focus on cancel-token authorization.

The cancel path must NOT trust the MBITE address (it is public in the order
book); only the secret cancel_token minted at creation may cancel an order.
"""

import importlib

import pytest

import exchange


@pytest.fixture()
def fresh_db(tmp_path):
    """Point the exchange module at an isolated, empty SQLite file per test."""
    exchange._conn = None
    exchange._DB_PATH = tmp_path / "exchange.db"
    yield
    if exchange._conn is not None:
        exchange._conn.close()
    exchange._conn = None
    importlib.reload(exchange)  # restore the module's real DB path for other tests


def _make_order():
    return exchange.create_order(
        side="sell",
        pair="MBITE/LTC",
        price="0.001",
        amount="10",
        mbite_address="moon1makeraddress",
        quote_address="ltc1quoteaddress",
    )


def test_create_returns_cancel_token(fresh_db):
    order = _make_order()
    assert order["cancel_token"]
    assert len(order["cancel_token"]) >= 20


def test_public_reads_never_leak_token(fresh_db):
    order = _make_order()
    oid = order["id"]

    # get_order (public GET path)
    assert "cancel_token" not in exchange.get_order(oid)
    # order book listing
    book = exchange.list_orders(pair="MBITE/LTC")
    assert all("cancel_token" not in row for row in book["asks"])
    # settle hint
    assert "cancel_token" not in exchange.settle_hint(oid)["order"]


def test_cancel_with_correct_token_succeeds(fresh_db):
    order = _make_order()
    result = exchange.cancel_order(order["id"], order["cancel_token"])
    assert result["status"] == "cancelled"


def test_cancel_with_public_address_is_rejected(fresh_db):
    """The old, broken auth: the public MBITE address must NOT cancel an order."""
    order = _make_order()
    with pytest.raises(ValueError, match="cancel token"):
        exchange.cancel_order(order["id"], "moon1makeraddress")
    assert exchange.get_order(order["id"])["status"] == "open"


@pytest.mark.parametrize("bad", ["NaN", "nan", "Infinity", "-Infinity", "inf", "1e400"])
def test_create_rejects_non_finite_or_huge_amounts(fresh_db, bad):
    """Non-finite / absurd Decimals must raise ValueError, not crash with
    decimal.InvalidOperation (which surfaced as an HTTP 500 in production)."""
    with pytest.raises(ValueError):
        exchange.create_order(
            side="buy", pair="MBITE/LTC", price=bad, amount="1",
            mbite_address="moon1x", quote_address="ltc1x",
        )
    with pytest.raises(ValueError):
        exchange.create_order(
            side="buy", pair="MBITE/LTC", price="0.001", amount=bad,
            mbite_address="moon1x", quote_address="ltc1x",
        )


def test_cancel_with_wrong_or_empty_token_is_rejected(fresh_db):
    order = _make_order()
    with pytest.raises(ValueError, match="cancel token"):
        exchange.cancel_order(order["id"], "not-the-token")
    with pytest.raises(ValueError, match="cancel token"):
        exchange.cancel_order(order["id"], "")
    assert exchange.get_order(order["id"])["status"] == "open"


# --------------------------------------------------------------------------- #
# Phase 2a: atomic-swap settlement coordination (plumbing only, no on-chain
# verification). A swap may progress no further than 'both_locked' and NO trade
# is ever marked settled here, so last_price must stay null.
# --------------------------------------------------------------------------- #

_H = "a" * 64  # a fake 32-byte SHA256 hashlock (64 hex chars)
_PK = "02" + "b" * 64  # a fake 33-byte compressed pubkey (66 hex chars)


def _matched_pair():
    """Create a crossing sell + buy from different addresses; both go 'matched'."""
    sell = exchange.create_order(
        side="sell", pair="MBITE/LTC", price="0.0005", amount="100",
        mbite_address="moon1seller0001", quote_address="ltc1seller0001",
    )
    buy = exchange.create_order(
        side="buy", pair="MBITE/LTC", price="0.0006", amount="100",
        mbite_address="moon1buyer0001", quote_address="ltc1buyer0001",
    )
    assert buy["status"] == "matched"
    return sell, buy


def _init(order, cancel_token, **overrides):
    params = dict(
        hashlock=_H,
        base_recipient_pk=_PK, base_refund_pk=_PK,
        quote_recipient_pk=_PK, quote_refund_pk=_PK,
        base_locktime=48 * 3600, quote_locktime=24 * 3600,
    )
    params.update(overrides)
    return exchange.init_swap(order["id"], cancel_token, **params)


def test_init_swap_creates_swap_in_init_state(fresh_db):
    sell, buy = _matched_pair()
    swap = _init(buy, buy["cancel_token"])
    assert swap["status"] == "swap_init"
    assert swap["buy_order_id"] == buy["id"]
    assert swap["sell_order_id"] == sell["id"]
    assert swap["hashlock"] == _H
    assert swap["price"] == "0.0005"  # maker (resting sell) price
    assert swap["base_htlc_txid"] is None and swap["quote_htlc_txid"] is None
    assert swap["settled_at"] is None  # nothing settles in 2a


def test_init_swap_requires_matched_order(fresh_db):
    order = _make_order()  # open, not matched
    with pytest.raises(ValueError, match="not matched"):
        _init(order, order["cancel_token"])


def test_init_swap_rejects_bad_cancel_token(fresh_db):
    _sell, buy = _matched_pair()
    with pytest.raises(ValueError, match="cancel token"):
        _init(buy, "wrong-token")


def test_init_swap_enforces_timelock_ordering(fresh_db):
    _sell, buy = _matched_pair()
    with pytest.raises(ValueError, match="quote_locktime must be earlier"):
        _init(buy, buy["cancel_token"], base_locktime=1000, quote_locktime=2000)


def test_init_swap_enforces_timelock_gap(fresh_db):
    _sell, buy = _matched_pair()
    # quote < base but gap under MIN_TIMELOCK_GAP_SECONDS
    with pytest.raises(ValueError, match="timelock gap too small"):
        _init(buy, buy["cancel_token"], base_locktime=1000, quote_locktime=999)


def test_init_swap_rejects_duplicate(fresh_db):
    sell, buy = _matched_pair()
    _init(buy, buy["cancel_token"])
    # Second init on either side of the same pair is refused.
    with pytest.raises(ValueError, match="already exists"):
        _init(sell, sell["cancel_token"], hashlock="c" * 64)


def test_report_funding_advances_state_machine(fresh_db):
    _sell, buy = _matched_pair()
    _init(buy, buy["cancel_token"])
    after_base = exchange.report_funding(
        buy["id"], buy["cancel_token"], "base", "d" * 64
    )
    assert after_base["status"] == "base_funded"
    after_quote = exchange.report_funding(
        buy["id"], buy["cancel_token"], "quote", "e" * 64
    )
    assert after_quote["status"] == "both_locked"
    assert after_quote["base_htlc_txid"] == "d" * 64
    assert after_quote["quote_htlc_txid"] == "e" * 64


def test_report_funding_requires_existing_swap(fresh_db):
    _sell, buy = _matched_pair()
    with pytest.raises(ValueError, match="no swap"):
        exchange.report_funding(buy["id"], buy["cancel_token"], "base", "d" * 64)


def test_swap_never_settles_so_last_price_stays_null(fresh_db):
    _sell, buy = _matched_pair()
    _init(buy, buy["cancel_token"])
    exchange.report_funding(buy["id"], buy["cancel_token"], "base", "d" * 64)
    exchange.report_funding(buy["id"], buy["cancel_token"], "quote", "e" * 64)
    # Even fully "locked", no settlement occurs in Phase 2a: price stays null.
    assert exchange.list_orders(pair="MBITE/LTC")["last_price"] is None
    assert exchange.get_swap(buy["id"])["status"] == "both_locked"
