"""The PIN must actually protect the stored seed phrase.

The scheme this replaces did not. It XORed the seed against simpleHash(pin), a
function that pads 56 leading zeros and carries its entropy in the last 8
characters, so for any seed shorter than that padding the keystream was the
literal character '0'. Every PIN decrypted correctly, and so did no PIN at all:
the stored blob was the seed XOR 0x30.

These tests run the browser implementation under node and check the properties
that were missing — that a wrong PIN fails, that two encryptions of the same
seed differ, and that tampering is detected — plus that wallets written by the
old scheme can still be read so they can be migrated.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SEED = "live test alpha bravo charlie delta echo foxtrot golf"

node = shutil.which("node")
requires_node = pytest.mark.skipif(node is None, reason="node is not installed")


def _run(body):
    script = f"""
    import {{ encryptSeed, decryptSeed, readSeed, isNewFormat, decryptLegacy }}
        from './static/moonbite-crypto.js';
    const SEED = {json.dumps(SEED)};
    {body}
    """
    tmp = REPO / "_crypto_check.mjs"
    tmp.write_text(script, encoding="utf-8")
    try:
        proc = subprocess.run(
            [node, str(tmp)], cwd=REPO, capture_output=True, text=True, timeout=300
        )
        if proc.returncode != 0:
            raise AssertionError(f"node failed: {proc.stderr.strip()[-1500:]}")
        return json.loads(proc.stdout)
    finally:
        tmp.unlink(missing_ok=True)


@requires_node
def test_round_trip_with_the_right_pin():
    out = _run("""
    const blob = await encryptSeed(SEED, '246810');
    console.log(JSON.stringify({ recovered: await decryptSeed(blob, '246810') }));
    """)
    assert out["recovered"] == SEED


@requires_node
def test_wrong_pin_returns_nothing():
    """The regression that mattered: every PIN used to work."""
    out = _run("""
    const blob = await encryptSeed(SEED, '246810');
    const wrong = ['000000', '111111', '999999', '246811', 'abcdef', ''];
    const results = {};
    for (const p of wrong) results[p] = await decryptSeed(blob, p);
    console.log(JSON.stringify({ results }));
    """)
    for pin, value in out["results"].items():
        assert value is None, f"PIN {pin!r} should not decrypt, got {value!r}"


@requires_node
def test_seed_is_not_recoverable_without_the_pin():
    # The old blob was the seed XOR 0x30; check that trick yields nothing now.
    # The comparison happens in node: XORing ciphertext yields arbitrary bytes,
    # and printing them back through stdout is not round-trip safe.
    out = _run("""
    const blob = await encryptSeed(SEED, '246810');
    const raw = Buffer.from(blob.split('.')[3], 'base64');
    let xored = '';
    for (const b of raw) xored += String.fromCharCode(b ^ 0x30);
    console.log(JSON.stringify({
        leaksWholeSeed: xored.includes(SEED),
        leaksAnyWord: SEED.split(' ').some(w => w.length > 3 && xored.includes(w)),
        ciphertextBytes: raw.length
    }));
    """)
    assert out["leaksWholeSeed"] is False
    assert out["leaksAnyWord"] is False
    assert out["ciphertextBytes"] > len(SEED)  # plaintext plus the GCM tag


@requires_node
def test_same_seed_and_pin_encrypt_differently():
    # A fresh salt and IV each time, so identical wallets are not linkable and
    # the ciphertext leaks nothing by repetition.
    out = _run("""
    const a = await encryptSeed(SEED, '246810');
    const b = await encryptSeed(SEED, '246810');
    console.log(JSON.stringify({
        differ: a !== b,
        saltsDiffer: a.split('.')[1] !== b.split('.')[1],
        ivsDiffer: a.split('.')[2] !== b.split('.')[2],
        bothDecrypt: (await decryptSeed(a, '246810')) === SEED
                  && (await decryptSeed(b, '246810')) === SEED
    }));
    """)
    assert out["differ"] and out["saltsDiffer"] and out["ivsDiffer"]
    assert out["bothDecrypt"]


@requires_node
def test_tampered_ciphertext_is_rejected():
    # GCM authenticates: a flipped byte must fail, not decrypt to garbage.
    out = _run("""
    const blob = await encryptSeed(SEED, '246810');
    const parts = blob.split('.');
    const raw = Buffer.from(parts[3], 'base64');
    raw[0] ^= 0xff;
    parts[3] = raw.toString('base64');
    console.log(JSON.stringify({ tampered: await decryptSeed(parts.join('.'), '246810') }));
    """)
    assert out["tampered"] is None


@requires_node
def test_legacy_blobs_are_readable_for_migration():
    out = _run("""
    // Reproduce exactly what the broken scheme wrote.
    let x = '';
    for (const ch of SEED) x += String.fromCharCode(ch.charCodeAt(0) ^ 0x30);
    const legacy = Buffer.from(x, 'binary').toString('base64');
    const viaReadSeed = await readSeed(legacy, 'any-pin');
    console.log(JSON.stringify({
        legacyRecovered: decryptLegacy(legacy),
        readSeedSeed: viaReadSeed.seed,
        flaggedForMigration: viaReadSeed.migrated,
        isNewFormat: isNewFormat(legacy)
    }));
    """)
    assert out["legacyRecovered"] == SEED
    assert out["readSeedSeed"] == SEED
    assert out["flaggedForMigration"] is True
    assert out["isNewFormat"] is False


@requires_node
def test_new_blobs_are_not_treated_as_legacy():
    out = _run("""
    const blob = await encryptSeed(SEED, '246810');
    const r = await readSeed(blob, '246810');
    console.log(JSON.stringify({
        isNewFormat: isNewFormat(blob),
        migrated: r.migrated,
        seed: r.seed
    }));
    """)
    assert out["isNewFormat"] is True
    assert out["migrated"] is False
    assert out["seed"] == SEED
