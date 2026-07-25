"""Tests for the non-custodial merchant layer — payment observation.

Focus on the automation that lets a shop auto-reconcile: list_invoices and
poll_pending_invoices. A payment is a NEW inbound total over the baseline
snapshotted when the invoice was raised; the server only observes it. The chain
is a tiny in-memory ``received_lookup`` we can advance by hand.
"""

import importlib

import pytest

import merchants


@pytest.fixture()
def fresh_db(tmp_path):
    merchants._conn = None
    merchants._DB_PATH = tmp_path / "merchants.db"
    yield
    if merchants._conn is not None:
        merchants._conn.close()
    merchants._conn = None
    importlib.reload(merchants)


class FakeChain:
    """A mutable per-address running total of received base units."""

    def __init__(self):
        self._totals = {}

    def pay(self, address, coins):
        # coins -> base units (100 units == 1 coin, per merchants.UNITS_PER_COIN)
        self._totals[address] = self._totals.get(address, 0) + int(
            coins * merchants.UNITS_PER_COIN
        )

    def lookup(self, address):
        return self._totals.get(address, 0)


ADDR_A = "moon1cafe0000000000000000000000000000"
ADDR_B = "moon1shop0000000000000000000000000000"


def test_invoice_starts_pending_and_flips_paid_on_payment(fresh_db):
    chain = FakeChain()
    inv = merchants.create_invoice(ADDR_A, "2.5", chain.lookup, memo="latte")
    assert inv["status"] == "pending"
    assert inv["paid_units"] == 0

    chain.pay(ADDR_A, 3)  # overpay is fine (>= amount)
    updated = merchants.invoice_status(inv["id"], chain.lookup)
    assert updated["status"] == "paid"
    assert updated["paid_at"] is not None


def test_baseline_ignores_preexisting_funds(fresh_db):
    chain = FakeChain()
    chain.pay(ADDR_A, 100)  # merchant already had prior receipts
    inv = merchants.create_invoice(ADDR_A, "5", chain.lookup)
    # The pre-existing balance must NOT satisfy the new invoice.
    assert merchants.invoice_status(inv["id"], chain.lookup)["status"] == "pending"
    chain.pay(ADDR_A, 5)  # a genuinely new payment
    assert merchants.invoice_status(inv["id"], chain.lookup)["status"] == "paid"


def test_poll_pending_invoices_sweeps_and_marks_paid(fresh_db):
    chain = FakeChain()
    a = merchants.create_invoice(ADDR_A, "1", chain.lookup)
    b = merchants.create_invoice(ADDR_B, "2", chain.lookup)
    c = merchants.create_invoice(ADDR_A, "10", chain.lookup)  # stays unpaid

    chain.pay(ADDR_A, 1)   # satisfies a (amount 1) but not c (amount 10)
    chain.pay(ADDR_B, 2)   # satisfies b

    summary = merchants.poll_pending_invoices(chain.lookup)
    assert summary["checked"] == 3
    assert set(summary["paid"]) == {a["id"], b["id"]}
    assert summary["expired"] == []
    # Distinct addresses hit once each, not once per invoice.
    assert summary["addresses_scanned"] == 2

    assert merchants.invoice_status(c["id"], chain.lookup)["status"] == "pending"


def test_expiry_when_ttl_lapses(fresh_db):
    chain = FakeChain()
    # A lapsed TTL flips the invoice to 'expired' on the next observation. The
    # sweep observes every still-pending invoice, so it is one such trigger.
    inv = merchants.create_invoice(ADDR_A, "1", chain.lookup, ttl=-10)
    assert merchants.invoice_status(inv["id"], chain.lookup)["status"] == "expired"
    # And an unpaid invoice that lapses between sweeps is caught by the sweep.
    inv2 = merchants.create_invoice(ADDR_B, "1", chain.lookup, ttl=3600)
    with merchants._lock:
        merchants._connect().execute(
            "UPDATE invoices SET expires_at = ? WHERE id = ?",
            (0, inv2["id"]),
        )
        merchants._connect().commit()
    summary = merchants.poll_pending_invoices(chain.lookup)
    assert inv2["id"] in summary["expired"]


def test_poll_is_idempotent(fresh_db):
    chain = FakeChain()
    inv = merchants.create_invoice(ADDR_A, "1", chain.lookup)
    chain.pay(ADDR_A, 1)
    first = merchants.poll_pending_invoices(chain.lookup)
    assert inv["id"] in first["paid"]
    # Second sweep: nothing pending remains, so it neither re-pays nor errors.
    second = merchants.poll_pending_invoices(chain.lookup)
    assert second["checked"] == 0 and second["paid"] == []


def test_list_invoices_scopes_by_merchant_and_checks_chain(fresh_db):
    chain = FakeChain()
    m = merchants.add_merchant("Cafe", "food", ADDR_A, address_validator=None)
    inv = merchants.create_invoice(
        ADDR_A, "1", chain.lookup, merchant_id=m["id"]
    )
    merchants.create_invoice(ADDR_B, "1", chain.lookup)  # different, no merchant

    scoped = merchants.list_invoices(chain.lookup, merchant_id=m["id"])
    assert [r["id"] for r in scoped] == [inv["id"]]

    chain.pay(ADDR_A, 1)
    # Listing re-checks the chain, so the paid state shows up without a manual poll.
    scoped2 = merchants.list_invoices(chain.lookup, merchant_id=m["id"])
    assert scoped2[0]["status"] == "paid"
