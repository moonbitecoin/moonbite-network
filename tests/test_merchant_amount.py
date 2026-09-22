"""Merchant invoice amount validation (audit money finding).

_amount_units used to round an amount finer than one base unit down to 0, so an
invoice for 0.001 MBITE (base = 0.01 at UNITS_PER_COIN=100) was created for ZERO
units — payable by paying nothing. _pos_amount also accepted non-finite Decimals.
These tests pin the fixes. Basis is the default UNITS_PER_COIN=100.
"""

from decimal import Decimal

import pytest

import merchants


def test_whole_and_multi_unit_amounts_convert():
    assert merchants._amount_units(Decimal("0.01")) == 1     # exactly one base unit
    assert merchants._amount_units(Decimal("1.5")) == 150
    assert merchants._amount_units(Decimal("2")) == 200


def test_sub_base_unit_amount_is_rejected_not_zeroed():
    # 0.001 * 100 = 0.1 base units -> used to floor to 0 (free goods).
    with pytest.raises(ValueError):
        merchants._amount_units(Decimal("0.001"))


def test_non_finite_amounts_rejected():
    for bad in ("inf", "-inf", "nan"):
        with pytest.raises(ValueError):
            merchants._pos_amount(bad)


def test_zero_negative_and_oversized_rejected():
    for bad in ("0", "-1", "100000001"):   # last exceeds _MAX_INVOICE_COINS
        with pytest.raises(ValueError):
            merchants._pos_amount(bad)


def test_normal_amount_accepted():
    assert merchants._pos_amount("50") == Decimal("50")
