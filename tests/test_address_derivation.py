"""The browser and the chain must derive the same address from a seed phrase.

The wallet PWA derives its address client-side so the user's seed never
crosses the network, which means the derivation exists twice: once in
wallet.py and once in static/moonbite-address.js. If those two ever disagree,
a user's coins land at an address their other device cannot see and the wallet
silently reports a zero balance on real funds.

These tests run the JavaScript under node and compare it against the Python
reference for a spread of phrases, so a change to either side fails here
instead of in someone's wallet.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wallet import (derive_from_seed_phrase, is_valid_address,  # noqa: E402
                    normalize_seed_phrase)

REPO = Path(__file__).resolve().parent.parent

# Ordinary phrases, plus the formatting variants a user actually produces when
# retyping a seed on a second device.
PHRASES = [
    "mineral swift option stale harbor cinder volt marrow flint",
    "alpha bravo charlie delta echo foxtrot golf hotel india",
    "  MINERAL   Swift Option Stale Harbor Cinder Volt Marrow Flint  ",
    "zebra zebra zebra zebra zebra zebra zebra zebra zebra",
    "one",
    "trailing space at the end ",
    "TABS\tAND\nNEWLINES between words",
]

node = shutil.which("node")
requires_node = pytest.mark.skipif(node is None, reason="node is not installed")


def _derive_in_js(phrases: list[str]) -> list[dict]:
    """Run the browser derivation under node and return its results."""
    script = f"""
    import {{ deriveFromSeedPhrase }} from './static/moonbite-address.js';
    const phrases = {json.dumps(phrases)};
    const out = [];
    for (const p of phrases) out.push(await deriveFromSeedPhrase(p));
    console.log(JSON.stringify(out));
    """
    # .mjs so node treats the bare file as an ES module without a package.json.
    tmp = REPO / "_derivation_check.mjs"
    tmp.write_text(script, encoding="utf-8")
    try:
        proc = subprocess.run(
            [node, str(tmp)],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            raise AssertionError(f"node failed: {proc.stderr.strip()}")
        return json.loads(proc.stdout)
    finally:
        tmp.unlink(missing_ok=True)


@requires_node
def test_js_and_python_agree_on_every_field():
    js_results = _derive_in_js(PHRASES)
    assert len(js_results) == len(PHRASES)

    for phrase, js in zip(PHRASES, js_results):
        py = derive_from_seed_phrase(phrase)
        for field in ("private_key", "public_key", "pubkey_hash", "address"):
            assert js[field] == py[field], (
                f"{field} differs for {phrase!r}:\n"
                f"  js={js[field]}\n  py={py[field]}"
            )


@requires_node
def test_js_addresses_are_valid_on_chain():
    for js in _derive_in_js(PHRASES):
        assert is_valid_address(js["address"])


def test_addresses_are_unique_per_phrase():
    # The bug this replaced handed every user the same address, so assert
    # distinctness explicitly rather than trusting the hash.
    distinct = {
        derive_from_seed_phrase(p)["address"]
        for p in PHRASES
        if normalize_seed_phrase(p) != normalize_seed_phrase(PHRASES[0])
    }
    assert len(distinct) == len(
        {normalize_seed_phrase(p) for p in PHRASES if normalize_seed_phrase(p) != normalize_seed_phrase(PHRASES[0])}
    )


def test_normalization_is_stable_across_retyping():
    base = derive_from_seed_phrase(PHRASES[0])["address"]
    for variant in (
        PHRASES[0].upper(),
        f"   {PHRASES[0]}   ",
        PHRASES[0].replace(" ", "  "),
        PHRASES[0].replace(" ", "\t"),
    ):
        assert derive_from_seed_phrase(variant)["address"] == base


def test_empty_phrase_is_rejected():
    for empty in ("", "   ", "\t\n"):
        with pytest.raises(ValueError):
            derive_from_seed_phrase(empty)


def test_single_word_change_changes_the_address():
    a = derive_from_seed_phrase(PHRASES[0])["address"]
    b = derive_from_seed_phrase(PHRASES[0].replace("flint", "flame"))["address"]
    assert a != b
