"""PoC/regression for audit finding: high-S ECDSA malleability (legacy chain).

(r, s) and (r, n - s) are both valid ECDSA signatures for the same message and
key. Because a tx's txid commits to its signatures, accepting high-S lets anyone
flip s and mutate the txid without the private key. Fix: the signer normalizes
to low-S and verify() rejects high-S.

Run: python -m pytest tests/security/test_poc_low_s_malleability.py -v
"""

from ecdsa import SECP256k1

from transaction import (
    Transaction, TxInput, TxOutput, canonical_low_s, generate_keypair,
    pubkey_hash,
)

N = SECP256k1.order


def _flip_s(sig_hex: str) -> str:
    """Return the malleated high/low-S counterpart: s -> n - s."""
    b = bytes.fromhex(sig_hex)
    r, s = b[:32], int.from_bytes(b[32:], "big")
    return (r + (N - s).to_bytes(32, "big")).hex()


def _signed_tx():
    sk, pubkey_hex = generate_keypair()
    pkh = pubkey_hash(pubkey_hex)
    prev = TxOutput(amount=1000, pubkey_hash=pkh)
    tx = Transaction([TxInput("aa" * 32, 0)], [TxOutput(900, "bb" * 20)])
    tx.sign_input(0, sk)
    resolver = lambda txid, i: prev if (txid, i) == ("aa" * 32, 0) else None
    return tx, resolver


def test_signer_always_emits_low_s():
    # RFC 6979 yields high-S ~half the time; the signer must canonicalize every
    # time, so many independent signings must all be low-S.
    for _ in range(40):
        tx, _ = _signed_tx()
        s = int.from_bytes(bytes.fromhex(tx.inputs[0].signature)[32:], "big")
        assert 0 < s <= N // 2


def test_honest_signed_tx_still_verifies():
    for _ in range(40):
        tx, resolver = _signed_tx()
        assert tx.verify(resolver) is True


def test_high_s_variant_is_rejected():
    tx, resolver = _signed_tx()
    assert tx.verify(resolver) is True                 # canonical form accepted
    tx.inputs[0].signature = _flip_s(tx.inputs[0].signature)  # malleate to high-S
    assert tx.verify(resolver) is False                # non-canonical rejected


def test_canonical_low_s_is_idempotent_and_correct():
    # A deliberately high-S signature is pulled down; an already-low one is kept.
    r = b"\x11" * 32
    high = r + (N - 5).to_bytes(32, "big")
    low = canonical_low_s(high)
    assert int.from_bytes(low[32:], "big") == 5
    assert canonical_low_s(low) == low
