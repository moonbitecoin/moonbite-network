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


def test_cancel_with_wrong_or_empty_token_is_rejected(fresh_db):
    order = _make_order()
    with pytest.raises(ValueError, match="cancel token"):
        exchange.cancel_order(order["id"], "not-the-token")
    with pytest.raises(ValueError, match="cancel token"):
        exchange.cancel_order(order["id"], "")
    assert exchange.get_order(order["id"])["status"] == "open"
