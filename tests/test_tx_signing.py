"""Transactions signed in the browser must validate on the chain.

The wallet signs spends client-side, so the signing message is constructed
twice: by transaction.py and by static/moonbite-tx.js. The signature covers a
canonical JSON serialization, so a single differing byte — a space, a key
order, an integer printed differently — produces a signature the network
rejects and a user whose coins will not move.

These tests run the JavaScript under node and check both halves: that the
signing bytes are identical, and that Python's verifier actually accepts the
signatures the browser produced.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from transaction import Transaction, TxInput, TxOutput  # noqa: E402
from wallet import derive_from_seed_phrase  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

SEED = "device one alpha bravo charlie delta echo foxtrot golf"
RECIPIENT_PKH = "cc" * 32

node = shutil.which("node")
requires_node = pytest.mark.skipif(node is None, reason="node is not installed")


def _run_js(script: str):
    tmp = REPO / "_tx_signing_check.mjs"
    tmp.write_text(script, encoding="utf-8")
    try:
        proc = subprocess.run(
            [node, str(tmp)], cwd=REPO, capture_output=True, text=True, timeout=120
        )
        if proc.returncode != 0:
            raise AssertionError(f"node failed: {proc.stderr.strip()}")
        return json.loads(proc.stdout)
    finally:
        tmp.unlink(missing_ok=True)


def _build_in_js(utxos, amount_units, fee_units):
    script = f"""
    import {{ buildSignedTransaction, signingBytes }}
        from './static/moonbite-tx.js';
    const built = await buildSignedTransaction({{
        seedPhrase: {json.dumps(SEED)},
        toPubkeyHash: {json.dumps(RECIPIENT_PKH)},
        amountUnits: {amount_units},
        feeUnits: {fee_units},
        utxos: {json.dumps(utxos)}
    }});
    built.signingBytes =
        new TextDecoder().decode(signingBytes(built.transaction));
    console.log(JSON.stringify(built));
    """
    return _run_js(script)


def _python_signing_bytes(tx_dict) -> str:
    tx = Transaction(
        inputs=[TxInput(i["prev_txid"], i["output_index"]) for i in tx_dict["inputs"]],
        outputs=[TxOutput(o["amount"], o["pubkey_hash"]) for o in tx_dict["outputs"]],
    )
    return tx.signing_bytes().decode()


@requires_node
def test_signing_bytes_match_python_exactly():
    utxos = [{"txid": "aa" * 32, "vout": 0, "amount_units": 5_000_000_000}]
    built = _build_in_js(utxos, 1_000_000_000, 1000)
    assert built["signingBytes"] == _python_signing_bytes(built["transaction"])


@requires_node
def test_python_accepts_browser_signatures():
    """The real check: does the chain's verifier accept what the browser signed."""
    key = derive_from_seed_phrase(SEED)
    utxos = [
        {"txid": "aa" * 32, "vout": 0, "amount_units": 5_000_000_000},
        {"txid": "bb" * 32, "vout": 1, "amount_units": 2_000_000_000},
    ]
    built = _build_in_js(utxos, 6_000_000_000, 1000)
    tx = Transaction.from_dict(built["transaction"])

    # Stand in for the UTXO set: every input resolves to an output owned by
    # the seed's address, which is what the wallet would be spending.
    spendable = {
        (u["txid"], u["vout"]): TxOutput(u["amount_units"], key["pubkey_hash"])
        for u in utxos
    }

    assert tx.verify(lambda txid, idx: spendable.get((txid, idx))) is True


@requires_node
def test_change_returns_to_the_sender():
    key = derive_from_seed_phrase(SEED)
    utxos = [{"txid": "aa" * 32, "vout": 0, "amount_units": 5_000_000_000}]
    built = _build_in_js(utxos, 1_000_000_000, 1000)
    outputs = built["transaction"]["outputs"]

    assert len(outputs) == 2
    assert outputs[0]["pubkey_hash"] == RECIPIENT_PKH
    assert outputs[1]["pubkey_hash"] == key["pubkey_hash"], "change must come home"
    # Nothing may be conjured or quietly lost: in == out + fee.
    assert sum(o["amount"] for o in outputs) + 1000 == 5_000_000_000


@requires_node
def test_signature_does_not_transfer_to_another_transaction():
    """A signature must not survive being moved onto a different spend."""
    key = derive_from_seed_phrase(SEED)
    utxos = [{"txid": "aa" * 32, "vout": 0, "amount_units": 5_000_000_000}]
    built = _build_in_js(utxos, 1_000_000_000, 1000)

    tampered = json.loads(json.dumps(built["transaction"]))
    tampered["outputs"][0]["amount"] += 100_000_000  # pay the recipient more

    tx = Transaction.from_dict(tampered)
    spendable = {("aa" * 32, 0): TxOutput(5_000_000_000, key["pubkey_hash"])}
    assert tx.verify(lambda txid, idx: spendable.get((txid, idx))) is False


@requires_node
def test_cannot_spend_an_output_owned_by_someone_else():
    utxos = [{"txid": "aa" * 32, "vout": 0, "amount_units": 5_000_000_000}]
    built = _build_in_js(utxos, 1_000_000_000, 1000)
    tx = Transaction.from_dict(built["transaction"])

    # Same coin, but locked to a different owner's hash.
    stranger = {("aa" * 32, 0): TxOutput(5_000_000_000, "ee" * 32)}
    assert tx.verify(lambda txid, idx: stranger.get((txid, idx))) is False


@requires_node
def test_insufficient_funds_is_refused_before_signing():
    script = """
    import { buildSignedTransaction } from './static/moonbite-tx.js';
    let error = null;
    try {
        await buildSignedTransaction({
            seedPhrase: %s,
            toPubkeyHash: %s,
            amountUnits: 9999999999,
            feeUnits: 0,
            utxos: [{ txid: 'aa'.repeat(32), vout: 0, amount_units: 100 }]
        });
    } catch (e) { error = e.message; }
    console.log(JSON.stringify({ error }));
    """ % (json.dumps(SEED), json.dumps(RECIPIENT_PKH))
    assert _run_js(script)["error"] == "insufficient funds"
