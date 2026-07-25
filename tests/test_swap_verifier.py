"""Tests for the Phase 2b on-chain HTLC verifier (swap_verifier.py).

Two layers:
  * pure script/preimage primitives (deterministic, no chain);
  * the verify_swap state machine, driven by an in-memory FakeChain that mimics
    a moonbited node's decoded-tx view, plus a full DB-integration pass showing
    a settled swap finally moving last_price.

No real node is spun up here; the FakeChain replays the exact JSON shapes the
verifier reads. Regtest end-to-end against the real binary is a separate gate.
"""

import hashlib
import importlib

import pytest

import exchange
import swap_verifier as sv

# A real preimage and its hashlock — the verifier only ever trusts the preimage
# it can re-hash to this value.
PREIMAGE = ("11" * 32)
HASHLOCK = hashlib.sha256(bytes.fromhex(PREIMAGE)).hexdigest()
PK_RECIP = "02" + "aa" * 32   # 33-byte compressed pubkeys (66 hex)
PK_REFUND = "02" + "bb" * 32
PK_QRECIP = "02" + "cc" * 32
PK_QREFUND = "02" + "dd" * 32


# --------------------------------------------------------------------------- #
# Pure primitives
# --------------------------------------------------------------------------- #

def test_redeemscript_has_expected_opcode_frame():
    script = sv.htlc_redeemscript(HASHLOCK, PK_RECIP, PK_REFUND, 172800).hex()
    # OP_IF OP_SHA256 push32 ...
    assert script.startswith("63a820")
    assert script.startswith("63a820" + HASHLOCK)
    # ... OP_CHECKLOCKTIMEVERIFY (b1) appears in the refund branch ...
    assert "b1" in script
    # ... and the whole thing ends OP_CHECKSIG OP_ENDIF.
    assert script.endswith("ac68")


def test_p2wsh_script_pubkey_is_sha256_witness_program():
    script = sv.htlc_redeemscript(HASHLOCK, PK_RECIP, PK_REFUND, 172800)
    spk = sv.p2wsh_script_pubkey(script).hex()
    assert spk == "0020" + hashlib.sha256(script).hexdigest()


def test_scriptnum_encoding_is_minimal_little_endian():
    assert sv._encode_scriptnum(0) == b""
    assert sv._encode_scriptnum(1) == b"\x01"
    assert sv._encode_scriptnum(255) == b"\xff\x00"   # high bit set -> pad
    assert sv._encode_scriptnum(256) == b"\x00\x01"


def test_find_preimage_locates_by_hash_only():
    items = ["3045deadbeef", "01", PREIMAGE, "abcd"]
    assert sv.find_preimage(items, HASHLOCK) == PREIMAGE
    assert sv.find_preimage(["3045", "abcd"], HASHLOCK) is None


def test_spend_input_items_merges_witness_and_scriptsig():
    # witness path
    vin_w = {"txinwitness": ["3045aa", PREIMAGE, "01", "deadbeef"]}
    assert PREIMAGE in sv.spend_input_items(vin_w)
    # legacy scriptSig path: push 0x02 bytes then push the 32-byte preimage
    script_sig = "02" + "3045" + "20" + PREIMAGE
    vin_l = {"scriptSig": {"hex": script_sig}}
    assert PREIMAGE in sv.spend_input_items(vin_l)


# --------------------------------------------------------------------------- #
# FakeChain adapter — an in-memory stand-in for a node's read surface.
# --------------------------------------------------------------------------- #

class FakeChain:
    def __init__(self):
        self._outputs = {}   # txid -> list[{"n","value","spk"}]
        self._confs = {}     # txid -> int
        self._spends = {}    # (txid, vout) -> {"txid","items","confirmations"}

    def add_funding(self, txid, vout, value, spk_hex, confs):
        self._outputs.setdefault(txid, []).append(
            {"n": vout, "value": value, "spk": spk_hex}
        )
        self._confs[txid] = confs

    def add_spend(self, funding_txid, vout, spend_txid, items, confs):
        self._spends[(funding_txid, vout)] = {
            "txid": spend_txid, "items": list(items), "confirmations": confs,
        }

    # --- adapter interface -------------------------------------------------- #
    def confirmations(self, txid):
        return self._confs.get(txid, 0)

    def find_output(self, txid, spk_hexset):
        from decimal import Decimal
        for o in self._outputs.get(txid, []):
            if o["spk"] in spk_hexset:
                return {
                    "vout": o["n"],
                    "value": Decimal(str(o["value"])),
                    "confirmations": self._confs.get(txid, 0),
                }
        return None

    def find_spend(self, txid, vout):
        return self._spends.get((txid, vout))


def _swap(**overrides):
    """A both_locked swap row as list_swaps_for_verification would return it."""
    row = {
        "swap_id": "s1", "buy_order_id": "b1", "sell_order_id": "a1",
        "pair": "MBITE/LTC", "price": "0.0005", "amount": "100",
        "hashlock": HASHLOCK,
        "base_recipient_pk": PK_RECIP, "base_refund_pk": PK_REFUND,
        "quote_recipient_pk": PK_QRECIP, "quote_refund_pk": PK_QREFUND,
        "base_locktime": 172800, "quote_locktime": 86400,
        "base_htlc_txid": "b" * 64, "quote_htlc_txid": "q" * 64,
        "base_redeem_txid": None, "quote_redeem_txid": None, "preimage": None,
        "base_confs": 0, "quote_confs": 0, "status": "both_locked",
    }
    row.update(overrides)
    return row


def _fund(swap, base, quote, *, base_val="100", quote_val="0.05",
          base_confs=6, quote_confs=6):
    """Seed both chains with correctly-addressed, confirmed funding outputs."""
    base_spk = sv.p2wsh_script_pubkey(
        sv.htlc_redeemscript(swap["hashlock"], swap["base_recipient_pk"],
                             swap["base_refund_pk"], swap["base_locktime"])
    ).hex()
    quote_spk = sv.p2wsh_script_pubkey(
        sv.htlc_redeemscript(swap["hashlock"], swap["quote_recipient_pk"],
                             swap["quote_refund_pk"], swap["quote_locktime"])
    ).hex()
    base.add_funding(swap["base_htlc_txid"], 0, base_val, base_spk, base_confs)
    quote.add_funding(swap["quote_htlc_txid"], 0, quote_val, quote_spk, quote_confs)
    return base_spk, quote_spk


# --------------------------------------------------------------------------- #
# verify_swap state machine
# --------------------------------------------------------------------------- #

def test_happy_path_settles_when_both_legs_redeem():
    swap = _swap()
    base, quote = FakeChain(), FakeChain()
    _fund(swap, base, quote)
    # Buyer redeems the quote HTLC, revealing the preimage on-chain.
    quote.add_spend(swap["quote_htlc_txid"], 0, "qr" * 32, ["3045", PREIMAGE], 6)
    # Seller sweeps the MBITE HTLC with that same preimage.
    base.add_spend(swap["base_htlc_txid"], 0, "br" * 32, ["3045", PREIMAGE], 6)

    updates = sv.verify_swap(swap, base, quote, now=0)
    assert updates["status"] == "settled"
    assert updates["preimage"] == PREIMAGE
    assert updates["quote_redeem_txid"] == "qr" * 32
    assert updates["base_redeem_txid"] == "br" * 32
    assert updates["settled_at"] == 0


def test_quote_redeemed_but_base_pending_stops_at_quote_redeemed():
    swap = _swap()
    base, quote = FakeChain(), FakeChain()
    _fund(swap, base, quote)
    quote.add_spend(swap["quote_htlc_txid"], 0, "qr" * 32, ["3045", PREIMAGE], 6)
    # base HTLC not yet swept

    updates = sv.verify_swap(swap, base, quote, now=0)
    assert updates["status"] == "quote_redeemed"
    assert updates["preimage"] == PREIMAGE
    assert "base_redeem_txid" not in updates


def test_refund_branch_expires_swap():
    swap = _swap()
    base, quote = FakeChain(), FakeChain()
    _fund(swap, base, quote)
    # quote output spent WITHOUT revealing a preimage => refund branch.
    quote.add_spend(swap["quote_htlc_txid"], 0, "rf" * 32, ["3045", PK_QREFUND], 6)

    updates = sv.verify_swap(swap, base, quote, now=0)
    assert updates["status"] == "expired"


def test_unredeemed_past_quote_locktime_expires():
    swap = _swap()
    base, quote = FakeChain(), FakeChain()
    _fund(swap, base, quote)
    # no spends; clock is past the quote timelock
    updates = sv.verify_swap(swap, base, quote, now=swap["quote_locktime"] + 1)
    assert updates["status"] == "expired"


def test_unredeemed_before_locktime_is_a_noop():
    swap = _swap()
    base, quote = FakeChain(), FakeChain()
    _fund(swap, base, quote)
    assert sv.verify_swap(swap, base, quote, now=1) == {}


def test_liar_funding_txid_parks_the_swap():
    swap = _swap()
    base, quote = FakeChain(), FakeChain()
    # Fund the QUOTE leg correctly but point the BASE funding at an output that
    # pays some unrelated scriptPubKey (a lie).
    _, _ = _fund(swap, base, quote)
    base._outputs[swap["base_htlc_txid"]] = [
        {"n": 0, "value": "100", "spk": "0014" + "ee" * 20}
    ]
    quote.add_spend(swap["quote_htlc_txid"], 0, "qr" * 32, ["3045", PREIMAGE], 6)
    assert sv.verify_swap(swap, base, quote, now=0) == {}


def test_underfunded_htlc_parks_the_swap():
    swap = _swap()
    base, quote = FakeChain(), FakeChain()
    _fund(swap, base, quote, base_val="1")  # base pays 1 MBITE, needs 100
    quote.add_spend(swap["quote_htlc_txid"], 0, "qr" * 32, ["3045", PREIMAGE], 6)
    assert sv.verify_swap(swap, base, quote, now=0) == {}


def test_shallow_confirmations_park_the_swap():
    swap = _swap()
    base, quote = FakeChain(), FakeChain()
    _fund(swap, base, quote, base_confs=2)  # below default min_confs of 6
    quote.add_spend(swap["quote_htlc_txid"], 0, "qr" * 32, ["3045", PREIMAGE], 6)
    assert sv.verify_swap(swap, base, quote, now=0) == {}


def test_terminal_swap_is_never_reprocessed():
    for terminal in ("settled", "expired"):
        swap = _swap(status=terminal)
        assert sv.verify_swap(swap, FakeChain(), FakeChain(), now=0) == {}


# --------------------------------------------------------------------------- #
# DB integration: a settled swap moves last_price; nothing else does.
# --------------------------------------------------------------------------- #

@pytest.fixture()
def fresh_db(tmp_path):
    exchange._conn = None
    exchange._DB_PATH = tmp_path / "exchange.db"
    yield
    if exchange._conn is not None:
        exchange._conn.close()
    exchange._conn = None
    importlib.reload(exchange)


def _matched_and_locked(fresh_db):
    """Create a crossing pair, init the swap, and report both fundings."""
    sell = exchange.create_order(
        side="sell", pair="MBITE/LTC", price="0.0005", amount="100",
        mbite_address="moon1seller", quote_address="ltc1seller",
    )
    buy = exchange.create_order(
        side="buy", pair="MBITE/LTC", price="0.0006", amount="100",
        mbite_address="moon1buyer", quote_address="ltc1buyer",
    )
    assert buy["status"] == "matched"
    exchange.init_swap(
        buy["id"], buy["cancel_token"], hashlock=HASHLOCK,
        base_recipient_pk=PK_RECIP, base_refund_pk=PK_REFUND,
        quote_recipient_pk=PK_QRECIP, quote_refund_pk=PK_QREFUND,
        base_locktime=172800, quote_locktime=86400,
    )
    exchange.report_funding(buy["id"], buy["cancel_token"], "base", "b" * 64)
    exchange.report_funding(buy["id"], buy["cancel_token"], "quote", "c" * 64)
    swap = exchange.get_swap(buy["id"])
    assert swap["status"] == "both_locked"
    return buy, swap


def test_pass_settles_and_moves_last_price(fresh_db):
    buy, swap = _matched_and_locked(fresh_db)
    assert exchange.list_orders(pair="MBITE/LTC")["last_price"] is None

    base, quote = FakeChain(), FakeChain()
    _fund(swap, base, quote)
    quote.add_spend("c" * 64, 0, "d1" * 32, ["3045", PREIMAGE], 6)
    base.add_spend("b" * 64, 0, "br" * 32, ["3045", PREIMAGE], 6)

    applied = sv.run_verification_pass(exchange, base, quote, now=0)
    assert len(applied) == 1

    assert exchange.get_swap(buy["id"])["status"] == "settled"
    # last_price finally reflects the maker (resting sell) price, on-chain-proven.
    assert exchange.list_orders(pair="MBITE/LTC")["last_price"] == "0.0005"


def test_pass_with_refund_marks_expired_and_leaves_price_null(fresh_db):
    buy, swap = _matched_and_locked(fresh_db)
    base, quote = FakeChain(), FakeChain()
    _fund(swap, base, quote)
    quote.add_spend("c" * 64, 0, "d2" * 32, ["3045", PK_QREFUND], 6)

    sv.run_verification_pass(exchange, base, quote, now=0)
    assert exchange.get_swap(buy["id"])["status"] == "expired"
    assert exchange.list_orders(pair="MBITE/LTC")["last_price"] is None
