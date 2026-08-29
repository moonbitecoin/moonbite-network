"""MyCoin — Milestone 8: Wallet & Privacy (Bitcoin whitepaper section 10).

This module gives users a way to hold keys, derive human-shareable addresses,
check balances against a UTXO set, and build spendable transactions.

Privacy (whitepaper section 10): "a new key pair should be used for each
transaction to keep them from being linked to a common owner." `Wallet`
follows this: every send draws change to a freshly generated key, and callers
are encouraged to call `new_key()` per incoming payment.

Trade-offs vs. real Bitcoin (the "~10% difference"):
  * Addresses are MoonBite bech32 ("moon1…") over a *single* SHA-256 public-key
    hash. Real Bitcoin uses RIPEMD-160(SHA-256(pubkey)) (a 20-byte HASH160). We
    avoid RIPEMD-160 because it is missing from some OpenSSL 3 builds; the bech32
    envelope carries the "moon" HRP plus a checksum, the same idea as a Bitcoin
    native-segwit address. (Base58Check helpers are retained for internal use.)
  * Keys here are generated at random on each `new_key()` call and kept in
    memory. Real wallets use hierarchical-deterministic derivation (BIP32/39)
    so all keys stem from one recoverable seed. Here there is no seed and no
    persistence — losing the process loses the keys.
  * Coin selection is a simple greedy "largest/first-fit" scan, not the more
    sophisticated selection real wallets use to minimize fees and change.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Iterable

from transaction import (
    Transaction,
    TxInput,
    TxOutput,
    generate_keypair,
    pubkey_hash,
    sha256d,
)
from ecdsa import SigningKey, SECP256k1
from mnemonic import Mnemonic


# --------------------------------------------------------------------------- #
# Base58Check address encoding
# --------------------------------------------------------------------------- #
_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE = len(_ALPHABET)
_INDEX = {c: i for i, c in enumerate(_ALPHABET)}


def base58_encode(data: bytes) -> str:
    """Encode bytes to a Base58 string (Bitcoin alphabet).

    Leading zero bytes are preserved as leading '1' characters, matching
    Bitcoin's convention so that the version byte round-trips exactly.
    """
    # Count and strip leading zero bytes; they map to leading '1's.
    n_leading_zeros = 0
    for b in data:
        if b == 0:
            n_leading_zeros += 1
        else:
            break

    num = int.from_bytes(data, "big")
    chars: list[str] = []
    while num > 0:
        num, rem = divmod(num, _BASE)
        chars.append(_ALPHABET[rem])
    chars.append(_ALPHABET[0] * n_leading_zeros)
    return "".join(reversed(chars))


def base58_decode(s: str) -> bytes:
    """Decode a Base58 string back to bytes. Inverse of `base58_encode`."""
    # Leading '1's decode back to leading zero bytes.
    n_leading_ones = 0
    for c in s:
        if c == _ALPHABET[0]:
            n_leading_ones += 1
        else:
            break

    num = 0
    for c in s:
        if c not in _INDEX:
            raise ValueError(f"invalid base58 character: {c!r}")
        num = num * _BASE + _INDEX[c]

    # Convert the big integer back to bytes (minimal length), then re-prepend
    # the leading zero bytes that the '1' prefix represented.
    body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num > 0 else b""
    return b"\x00" * n_leading_ones + body


# --------------------------------------------------------------------------- #
# Bech32 address encoding (BIP173) — MoonBite "moon1…" addresses
#
# MoonBite's canonical human-readable address is bech32 with the "moon" HRP
# (mainnet). Because this educational chain hashes public keys with 32-byte
# SHA-256 rather than Bitcoin's 20-byte HASH160, a Base58Check version byte can
# only ever yield a leading *digit*; bech32 gives a clean, branded "moon1…"
# prefix instead, and round-trips the existing 32-byte hash with no consensus
# change. Base58 helpers above are retained for internal use and tests.
# --------------------------------------------------------------------------- #
_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_MOONBITE_HRP = "moon"


def _bech32_polymod(values: list[int]) -> int:
    generator = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= generator[i] if ((top >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _bech32_verify_checksum(hrp: str, data: list[int]) -> bool:
    return _bech32_polymod(_bech32_hrp_expand(hrp) + data) == 1


def _bech32_create_checksum(hrp: str, data: list[int]) -> list[int]:
    values = _bech32_hrp_expand(hrp) + data
    polymod = _bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def _bech32_encode(hrp: str, data: list[int]) -> str:
    combined = data + _bech32_create_checksum(hrp, data)
    return hrp + "1" + "".join(_BECH32_CHARSET[d] for d in combined)


def _bech32_decode(bech: str):
    if any(ord(x) < 33 or ord(x) > 126 for x in bech) or (
        bech.lower() != bech and bech.upper() != bech
    ):
        return (None, None)
    bech = bech.lower()
    pos = bech.rfind("1")
    if pos < 1 or pos + 7 > len(bech) or len(bech) > 90:
        return (None, None)
    if not all(x in _BECH32_CHARSET for x in bech[pos + 1:]):
        return (None, None)
    hrp = bech[:pos]
    data = [_BECH32_CHARSET.find(x) for x in bech[pos + 1:]]
    if not _bech32_verify_checksum(hrp, data):
        return (None, None)
    return (hrp, data[:-6])


def _convertbits(data, frombits: int, tobits: int, pad: bool = True):
    """Regroup a bit-stream between 8-bit bytes and 5-bit bech32 symbols."""
    acc = 0
    bits = 0
    ret: list[int] = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            return None
        acc = ((acc << frombits) | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return None
    return ret


def address_from_pubkey_hash(pkh_hex: str, hrp: str = _MOONBITE_HRP) -> str:
    """Build a MoonBite bech32 address ("moon1…") from a public-key hash (hex).

    The pubkey-hash bytes are regrouped from 8-bit to 5-bit symbols and encoded
    under the given human-readable prefix (default "moon" for mainnet) with a
    bech32 checksum.
    """
    data = _convertbits(bytes.fromhex(pkh_hex), 8, 5, True)
    if data is None:
        raise ValueError("cannot encode pubkey hash")
    return _bech32_encode(hrp, data)


def pubkey_hash_from_address(addr: str) -> str:
    """Decode a bech32 address back to its public-key hash (hex).

    Raises ValueError if the address is malformed or the bech32 checksum fails.
    """
    hrp, data = _bech32_decode(addr)
    if hrp is None or data is None:
        raise ValueError("invalid address")
    decoded = _convertbits(data, 5, 8, False)
    if decoded is None:
        raise ValueError("invalid address payload")
    return bytes(decoded).hex()


def is_valid_address(addr: str) -> bool:
    """True if `addr` is a well-formed Base58Check address with a valid checksum."""
    try:
        pubkey_hash_from_address(addr)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Wallet
# --------------------------------------------------------------------------- #
class Wallet:
    """An in-memory keychain implementing "a new key pair per transaction".

    Keys are indexed by their pubkey_hash so that, given a UTXO locked to a
    hash, the wallet can find the signing key that authorizes spending it.
    """

    def __init__(self) -> None:
        # pubkey_hash (hex) -> SigningKey
        self._keys: dict[str, SigningKey] = {}
        # pubkey_hash (hex) -> address (base58), preserving insertion order
        self._addresses: dict[str, str] = {}
        # Minimal record of sends this wallet created.
        self.history: list[dict] = []

    # ----- key management ------------------------------------------------- #
    def new_key(self) -> str:
        """Generate a fresh keypair, store it, and return its Base58 address."""
        sk, pubkey_hex = generate_keypair()
        pkh = pubkey_hash(pubkey_hex)
        addr = address_from_pubkey_hash(pkh)
        self._keys[pkh] = sk
        self._addresses[pkh] = addr
        return addr

    @property
    def addresses(self) -> list[str]:
        """All addresses this wallet owns, in the order they were created."""
        return list(self._addresses.values())

    def owns(self, pubkey_hash_hex: str) -> bool:
        """True if this wallet holds the signing key for `pubkey_hash_hex`."""
        return pubkey_hash_hex in self._keys

    # ----- persistence ---------------------------------------------------- #
    def export_privkeys(self) -> list[str]:
        """Serialize every signing key as hex, for saving to disk."""
        return [sk.to_string().hex() for sk in self._keys.values()]

    def load_privkey(self, privkey_hex: str) -> str:
        """Restore a signing key from hex, re-deriving its address (returned).

        The pubkey_hash and Base58 address are deterministic functions of the
        key, so a reloaded key reproduces exactly the same address it had
        before, letting a wallet recover ownership of its coins after a restart.
        """
        sk = SigningKey.from_string(bytes.fromhex(privkey_hex), curve=SECP256k1)
        pubkey_hex = sk.get_verifying_key().to_string().hex()
        pkh = pubkey_hash(pubkey_hex)
        addr = address_from_pubkey_hash(pkh)
        self._keys[pkh] = sk
        self._addresses[pkh] = addr
        return addr

    # ----- balance -------------------------------------------------------- #
    def balance(self, utxos: Iterable[tuple[str, int, TxOutput]]) -> int:
        """Sum the amounts of UTXOs locked to a pubkey_hash this wallet owns."""
        return sum(
            out.amount for _txid, _idx, out in utxos if self.owns(out.pubkey_hash)
        )

    # ----- spending ------------------------------------------------------- #
    def create_transaction(
        self,
        utxos: Iterable[tuple[str, int, TxOutput]],
        to_address: str,
        amount: int,
        fee: int = 0,
        change_address: str | None = None,
    ) -> Transaction:
        """Build and sign a transaction paying `amount` to `to_address`.

        Only owned UTXOs are considered. Owned UTXOs are greedily accumulated
        until they cover `amount + fee`; otherwise ValueError("insufficient
        funds") is raised. Output 0 pays the recipient; any surplus over
        `amount + fee` is returned as change to `change_address` (default: a
        freshly generated address, honoring the "new key per transaction"
        privacy guidance). A zero-value change output is never created.
        """
        if amount <= 0:
            raise ValueError("amount must be positive")
        if fee < 0:
            raise ValueError("fee must be non-negative")

        target = amount + fee

        # Greedily select owned UTXOs until we cover the target.
        selected: list[tuple[str, int, TxOutput]] = []
        total = 0
        for txid, index, out in utxos:
            if not self.owns(out.pubkey_hash):
                continue
            selected.append((txid, index, out))
            total += out.amount
            if total >= target:
                break

        if total < target:
            raise ValueError("insufficient funds")

        # Build outputs: recipient first, then change (if any).
        outputs = [TxOutput(amount, pubkey_hash_from_address(to_address))]
        change = total - target
        if change > 0:
            if change_address is None:
                change_address = self.new_key()  # new key per transaction
            outputs.append(
                TxOutput(change, pubkey_hash_from_address(change_address))
            )

        # Build inputs referencing each selected UTXO.
        inputs = [
            TxInput(prev_txid=txid, output_index=index)
            for txid, index, _out in selected
        ]
        tx = Transaction(inputs=inputs, outputs=outputs)

        # Sign each input with the key for the UTXO it spends.
        for i, (_txid, _index, out) in enumerate(selected):
            tx.sign_input(i, self._keys[out.pubkey_hash])

        self.history.append({"txid": tx.txid, "amount": amount, "to": to_address})
        return tx


# --------------------------------------------------------------------------- #
# HD Wallet (BIP32/39) — Hierarchical Deterministic key derivation
# --------------------------------------------------------------------------- #
class HDWallet(Wallet):
    """HD Wallet supporting BIP39 mnemonic seed phrases and BIP32 key derivation.

    Extends Wallet with:
    - BIP39 mnemonic seed phrase generation (12/24 words)
    - BIP32 hierarchical key derivation (m/44'/0'/0'/0/n path)
    - Seed persistence and recovery
    - Unlimited address generation from one seed
    """

    def __init__(self, mnemonic_phrase: str | None = None, passphrase: str = "") -> None:
        """Initialize HD wallet from mnemonic or generate new seed.

        Args:
            mnemonic_phrase: BIP39 mnemonic (12 or 24 words). If None, generates new.
            passphrase: Optional BIP39 passphrase for seed derivation.
        """
        super().__init__()
        self.mnemonic_obj = Mnemonic("english")

        if mnemonic_phrase is None:
            # Generate new 12-word mnemonic
            mnemonic_phrase = self.mnemonic_obj.generate(strength=128)

        # Validate mnemonic
        if not self.mnemonic_obj.check(mnemonic_phrase):
            raise ValueError("invalid BIP39 mnemonic phrase")

        self.mnemonic = mnemonic_phrase
        self.passphrase = passphrase

        # Derive BIP32 root from mnemonic
        seed = self.mnemonic_obj.to_seed(mnemonic_phrase, passphrase)
        self._root_key = self._derive_bip32_root(seed)

        # Track derivation path counter for new addresses
        self._derivation_index = 0

    @staticmethod
    def _derive_bip32_root(seed: bytes) -> dict:
        """Derive BIP32 root key from seed (Bitcoin standard).

        Returns dict with 'private_key' (bytes), 'chain_code' (bytes).
        """
        hmac_result = hmac.new(b"Bitcoin seed", seed, hashlib.sha512).digest()
        private_key = hmac_result[:32]
        chain_code = hmac_result[32:]
        return {"private_key": private_key, "chain_code": chain_code}

    @staticmethod
    def _ckd_priv(key_data: dict, index: int) -> dict:
        """Child Key Derivation (private) — BIP32 standard.

        Args:
            key_data: Parent key dict with 'private_key', 'chain_code'
            index: Child index (0-2^31-1 for normal, 2^31+ for hardened)

        Returns: Child key dict with same structure
        """
        if index >= 0x80000000:
            # Hardened derivation: use private key
            data = b"\x00" + key_data["private_key"] + index.to_bytes(4, "big")
        else:
            # Normal derivation: use public key (derived from private)
            from ecdsa.util import sigencode_string
            vk = SigningKey.from_string(
                key_data["private_key"], curve=SECP256k1
            ).get_verifying_key()
            data = vk.to_string() + index.to_bytes(4, "big")

        hmac_result = hmac.new(
            key_data["chain_code"], data, hashlib.sha512
        ).digest()
        child_key = (
            int.from_bytes(hmac_result[:32], "big")
            + int.from_bytes(key_data["private_key"], "big")
        ) % (SECP256k1.order or 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff)
        child_key_bytes = child_key.to_bytes(32, "big")
        child_chain_code = hmac_result[32:]

        return {"private_key": child_key_bytes, "chain_code": child_chain_code}

    def _derive_path(self, path: str = "m/44'/0'/0'/0/0") -> dict:
        """Derive key at BIP32 path (e.g., "m/44'/0'/0'/0/0" for first address).

        Standard MoonBite path: m/44'/0'/0'/0/n (account 0, change 0, index n)
        """
        key = self._root_key

        for component in path.split("/")[1:]:  # Skip 'm'
            if component == "":
                continue
            hardened = component.endswith("'")
            index = int(component.rstrip("'"))
            if hardened:
                index += 0x80000000
            key = self._ckd_priv(key, index)

        return key

    def new_key(self) -> str:
        """Generate next HD address using derivation path m/44'/0'/0'/0/n."""
        # Standard derivation: m/44'/0'/0'/0/n
        path = f"m/44'/0'/0'/0/{self._derivation_index}"
        self._derivation_index += 1

        key_data = self._derive_path(path)
        sk = SigningKey.from_string(key_data["private_key"], curve=SECP256k1)
        pubkey_hex = sk.get_verifying_key().to_string().hex()
        pkh = pubkey_hash(pubkey_hex)
        addr = address_from_pubkey_hash(pkh)

        self._keys[pkh] = sk
        self._addresses[pkh] = addr
        return addr

    def export_seed(self) -> str:
        """Export mnemonic seed phrase for recovery."""
        return self.mnemonic

    def derive_address(self, index: int) -> str:
        """Derive a specific address by index (m/44'/0'/0'/0/index).

        Useful for recovering specific addresses from seed without creating new ones.
        """
        path = f"m/44'/0'/0'/0/{index}"
        key_data = self._derive_path(path)
        sk = SigningKey.from_string(key_data["private_key"], curve=SECP256k1)
        pubkey_hex = sk.get_verifying_key().to_string().hex()
        pkh = pubkey_hash(pubkey_hex)
        addr = address_from_pubkey_hash(pkh)

        # Store the key if not already present
        if pkh not in self._keys:
            self._keys[pkh] = sk
            self._addresses[pkh] = addr

        return addr

    @classmethod
    def from_mnemonic(cls, mnemonic: str, passphrase: str = "") -> HDWallet:
        """Recover wallet from BIP39 mnemonic seed phrase."""
        return cls(mnemonic, passphrase)


# --------------------------------------------------------------------------- #
# Seed-phrase key derivation (shared with the browser wallet)
# --------------------------------------------------------------------------- #
# The wallet PWA derives its address in the browser so the user's seed phrase
# never crosses the network. That only works if both sides agree byte-for-byte,
# so this is the reference implementation and static/moonbite-address.js is a
# direct port of it. tests/test_address_derivation.py runs the JS under node
# and asserts the two produce identical addresses; change one and that test
# fails rather than silently splitting users' funds across two address spaces.
#
# The scheme is deliberately not BIP32/BIP39: the user's 9-word phrase is
# free-form (their own dice, their own generator), so there is no wordlist to
# index against and no checksum to validate.
SEED_DERIVATION_PREFIX = "moonbite-seed-v1:"


def normalize_seed_phrase(phrase: str) -> str:
    """Canonicalize a user-typed phrase so trivial typing differences agree.

    Case and runs of whitespace carry no meaning in a spoken/written phrase,
    and a user retyping their seed on a new device will not reproduce them
    exactly. Everything else is preserved verbatim — this normalizes
    formatting, not content.
    """
    return " ".join(phrase.strip().lower().split())


def privkey_from_seed_phrase(phrase: str) -> str:
    """Derive the private scalar (hex) from a seed phrase.

    The hash is reduced mod the curve order because a raw 256-bit digest can
    land outside [1, n-1], which is not a valid secp256k1 key.
    """
    normalized = normalize_seed_phrase(phrase)
    if not normalized:
        raise ValueError("seed phrase is empty")
    digest = hashlib.sha256((SEED_DERIVATION_PREFIX + normalized).encode("utf-8")).digest()
    scalar = int.from_bytes(digest, "big") % SECP256k1.order
    if scalar == 0:  # pragma: no cover — needs a preimage of the group order
        raise ValueError("degenerate key for this seed phrase")
    return format(scalar, "064x")


def derive_from_seed_phrase(phrase: str) -> dict:
    """Full derivation: seed phrase -> private key, public key, hash, address."""
    privkey_hex = privkey_from_seed_phrase(phrase)
    sk = SigningKey.from_string(bytes.fromhex(privkey_hex), curve=SECP256k1)
    # Raw X||Y, matching transaction.generate_keypair's vk.to_string().hex().
    pubkey_hex = sk.get_verifying_key().to_string().hex()
    pkh_hex = pubkey_hash(pubkey_hex)
    return {
        "private_key": privkey_hex,
        "public_key": pubkey_hex,
        "pubkey_hash": pkh_hex,
        "address": address_from_pubkey_hash(pkh_hex),
    }
