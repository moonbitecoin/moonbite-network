"""Phase 2b — on-chain HTLC atomic-swap verifier (trustless observer).

The exchange server COORDINATES a cross-chain HTLC swap (see exchange.py) but
never custodies coins or keys. This module is the read-only verifier that turns
a self-reported ``both_locked`` swap into a genuinely on-chain-verified
``settled`` trade — the single gate that lets last_price move.

It does exactly one thing: READ two chains (via a small adapter interface) and
decide, from what is actually confirmed on-chain, how far a swap has progressed:

    both_locked ── quote redeemed (preimage now public) ──▶ quote_redeemed
                ── base redeemed with that same preimage  ──▶ base_redeemed
                ── both redemptions confirmed to depth    ──▶ settled
                ── a refund branch confirmed / timed out   ──▶ expired

Invariants this file upholds:
  * The server never learns the preimage before it is PUBLIC on-chain. We only
    ever read it out of a confirmed spend of the quote HTLC.
  * Nothing is taken on the caller's word: funding/redeem txids are only HINTS
    telling the verifier where to look; every fact is re-derived from chain data
    (script match, amount, confirmations, SHA256(preimage) == hashlock).
  * No transaction is ever built, signed, or broadcast here. Read-only.

The pure script helpers (redeemscript assembly, scriptPubKey derivation,
preimage extraction) are deterministic and unit-tested without a node. The node
path (MoonNodeAdapter) wraps explorer.rpc.RpcClient and is exercised end-to-end
on regtest with the real moonbited binary.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Iterable, Optional

# States added by Phase 2b, beyond exchange.SWAP_STATES (2a). Kept here so the
# verifier owns the on-chain half of the machine; exchange.py imports these.
VERIFIER_STATES = (
    "quote_redeemed",  # quote HTLC spent via hashlock branch; preimage is public
    "base_redeemed",   # base (MBITE) HTLC spent with that same preimage
    "settled",         # both redemptions confirmed to depth; feeds last_price
    "expired",         # a refund branch confirmed / timelock elapsed — never settles
)

# Confirmation depth required before a fact is trusted (reorg safety). The quote
# chain (BTC especially) is slower/heavier, so it can be tuned independently.
DEFAULT_MIN_CONFS_BASE = 6
DEFAULT_MIN_CONFS_QUOTE = 6

# --------------------------------------------------------------------------- #
# Bitcoin Script primitives — just enough to SERIALIZE an HTLC redeemscript and
# derive its funding scriptPubKey(s). No interpreter, no signing. MoonBite is a
# Litecoin fork, so this is standard Bitcoin Script.
# --------------------------------------------------------------------------- #

OP_0 = 0x00
OP_IF = 0x63
OP_ELSE = 0x67
OP_ENDIF = 0x68
OP_DROP = 0x75
OP_EQUAL = 0x87
OP_EQUALVERIFY = 0x88
OP_SHA256 = 0xA8
OP_HASH160 = 0xA9
OP_CHECKSIG = 0xAC
OP_CHECKLOCKTIMEVERIFY = 0xB1


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _has_ripemd160() -> bool:
    try:
        hashlib.new("ripemd160")
        return True
    except (ValueError, TypeError):
        return False


def hash160(data: bytes) -> bytes:
    """RIPEMD160(SHA256(x)). Only needed for legacy P2SH funding addresses."""
    return hashlib.new("ripemd160", hashlib.sha256(data).digest()).digest()


def _pushdata(data: bytes) -> bytes:
    """Minimal script push of ``data``. HTLC pushes are all < 76 bytes."""
    n = len(data)
    if n < 0x4C:
        return bytes([n]) + data
    if n <= 0xFF:
        return bytes([0x4C, n]) + data
    raise ValueError("push too large for an HTLC redeemscript")


def _encode_scriptnum(n: int) -> bytes:
    """CScriptNum minimal little-endian encoding (used for the CLTV locktime)."""
    if n == 0:
        return b""
    negative = n < 0
    abs_n = -n if negative else n
    out = bytearray()
    while abs_n:
        out.append(abs_n & 0xFF)
        abs_n >>= 8
    if out[-1] & 0x80:
        out.append(0x80 if negative else 0x00)
    elif negative:
        out[-1] |= 0x80
    return bytes(out)


def htlc_redeemscript(
    hashlock_hex: str,
    recipient_pk_hex: str,
    refund_pk_hex: str,
    locktime: int,
) -> bytes:
    """Assemble the canonical hash-timelock redeemscript for one swap leg.

        OP_IF
            OP_SHA256 <hashlock> OP_EQUALVERIFY <recipient_pk> OP_CHECKSIG
        OP_ELSE
            <locktime> OP_CHECKLOCKTIMEVERIFY OP_DROP <refund_pk> OP_CHECKSIG
        OP_ENDIF

    The recipient claims by revealing the preimage (top branch); after the
    timelock the funder refunds themselves (bottom branch).
    """
    h = bytes.fromhex(hashlock_hex)
    recip = bytes.fromhex(recipient_pk_hex)
    refund = bytes.fromhex(refund_pk_hex)
    if len(h) != 32:
        raise ValueError("hashlock must be 32 bytes")
    return b"".join(
        [
            bytes([OP_IF, OP_SHA256]),
            _pushdata(h),
            bytes([OP_EQUALVERIFY]),
            _pushdata(recip),
            bytes([OP_CHECKSIG, OP_ELSE]),
            _pushdata(_encode_scriptnum(int(locktime))),
            bytes([OP_CHECKLOCKTIMEVERIFY, OP_DROP]),
            _pushdata(refund),
            bytes([OP_CHECKSIG, OP_ENDIF]),
        ]
    )


def p2wsh_script_pubkey(redeemscript: bytes) -> bytes:
    """Native SegWit v0 witness program: OP_0 <sha256(redeemscript)>."""
    return bytes([OP_0, 0x20]) + sha256(redeemscript)


def p2sh_script_pubkey(redeemscript: bytes) -> bytes:
    """Legacy P2SH: OP_HASH160 <hash160(redeemscript)> OP_EQUAL."""
    return bytes([OP_HASH160, 0x14]) + hash160(redeemscript) + bytes([OP_EQUAL])


def funding_script_pubkeys(redeemscript: bytes) -> set:
    """Every scriptPubKey hex an HTLC of this redeemscript could be funded to.

    MoonBite is bech32-native so P2WSH is the expected form; we also accept
    wrapped P2SH when the platform's RIPEMD160 is available.
    """
    spks = {p2wsh_script_pubkey(redeemscript).hex()}
    if _has_ripemd160():
        spks.add(p2sh_script_pubkey(redeemscript).hex())
    return spks


def find_preimage(items_hex: Iterable[str], hashlock_hex: str) -> Optional[str]:
    """Return the witness/scriptSig item whose SHA256 equals the hashlock.

    Position-independent: a redemption pushes the preimage somewhere in its
    input; we identify it purely by SHA256(item) == hashlock, so we cannot be
    fooled by argument ordering across wallet implementations.
    """
    target = hashlock_hex.lower()
    for item in items_hex:
        if not item:
            continue
        try:
            raw = bytes.fromhex(item)
        except ValueError:
            continue
        if sha256(raw).hex() == target:
            return item.lower()
    return None


def _parse_scriptsig_pushes(script_sig_hex: str) -> list:
    """Extract pushed data items (hex) from a legacy scriptSig hex string."""
    try:
        blob = bytes.fromhex(script_sig_hex)
    except ValueError:
        return []
    items, i, n = [], 0, len(blob)
    while i < n:
        op = blob[i]
        i += 1
        if op < 0x4C:
            size = op
        elif op == 0x4C and i < n:
            size = blob[i]
            i += 1
        elif op == 0x4D and i + 1 < n:
            size = blob[i] | (blob[i + 1] << 8)
            i += 2
        else:
            break  # non-push opcode; HTLC spends only push before the redeemscript
        items.append(blob[i : i + size].hex())
        i += size
    return items


def spend_input_items(vin: dict) -> list:
    """Normalize a decoded spend input into a flat list of pushed data (hex).

    Handles both SegWit (``txinwitness``) and legacy (``scriptSig.hex``) so the
    preimage can be located regardless of the funding address type.
    """
    items = list(vin.get("txinwitness") or [])
    script_sig = vin.get("scriptSig") or {}
    if script_sig.get("hex"):
        items.extend(_parse_scriptsig_pushes(script_sig["hex"]))
    return items


# --------------------------------------------------------------------------- #
# Chain adapter interface (duck-typed). A verifier is driven by two of these —
# one per leg. Real implementation: MoonNodeAdapter (RPC). Test implementation:
# a fake in tests. Every method is READ-ONLY.
#
#   confirmations(txid)            -> int   (0 if unknown/unconfirmed)
#   find_output(txid, spk_hexset)  -> {"vout":int,"value":Decimal,"confirmations":int} | None
#   find_spend(txid, vout)         -> {"txid":str,"items":[hex,...],"confirmations":int} | None
# --------------------------------------------------------------------------- #


class NullAdapter:
    """A leg whose chain the operator has not wired up yet.

    Returns "nothing confirmed" for every query, so a swap depending on this leg
    can never advance — the honest default. Used for the quote (LTC/BTC) leg
    until a quote-chain node or explorer-agreement adapter exists (Phase 2c):
    the verifier still runs, verifies what it can, and simply never settles a
    trade whose settlement it cannot independently prove.
    """

    def confirmations(self, txid):
        return 0

    def find_output(self, txid, spk_hexset):
        return None

    def find_spend(self, txid, vout):
        return None


class MoonNodeAdapter:
    """Read-only chain adapter backed by a moonbited/bigcoind JSON-RPC node.

    Fully trustless for the MBITE leg (queries the operator's own node). Can
    also serve a quote leg when the operator runs an LTC/BTC node. Discovering
    the spender of a specific output needs either txindex or a bounded block
    scan; we use a scan from the funding height forward (2c will index this).
    """

    def __init__(self, client, scan_window: int = 400):
        self._client = client
        self._scan_window = scan_window

    def _get_tx(self, txid: str) -> Optional[dict]:
        try:
            return self._client.getrawtransaction(txid, True)
        except Exception:  # noqa: BLE001 - unknown tx / node hiccup => treat as absent
            return None

    def confirmations(self, txid: str) -> int:
        tx = self._get_tx(txid)
        return int(tx.get("confirmations", 0)) if tx else 0

    def find_output(self, txid: str, spk_hexset: set) -> Optional[dict]:
        tx = self._get_tx(txid)
        if not tx:
            return None
        confs = int(tx.get("confirmations", 0))
        for vout in tx.get("vout", []):
            spk = (vout.get("scriptPubKey") or {}).get("hex")
            if spk and spk in spk_hexset:
                return {
                    "vout": int(vout["n"]),
                    "value": Decimal(str(vout["value"])),
                    "confirmations": confs,
                }
        return None

    def _tx_height(self, txid: str) -> Optional[int]:
        tx = self._get_tx(txid)
        if not tx or "blockhash" not in tx:
            return None
        try:
            return int(self._client.getblock(tx["blockhash"], 1)["height"])
        except Exception:  # noqa: BLE001
            return None

    def find_spend(self, txid: str, vout: int) -> Optional[dict]:
        """Locate the tx that spends output (txid, vout), if any is confirmed.

        Bounded forward scan from the funding block; adequate for regtest and
        low volume. Phase 2c replaces this with a spent-output index.
        """
        start = self._tx_height(txid)
        if start is None:
            return None
        try:
            tip = int(self._client.getblockcount())
        except Exception:  # noqa: BLE001
            return None
        end = min(tip, start + self._scan_window)
        for height in range(start, end + 1):
            try:
                block = self._client.getblock(self._client.getblockhash(height), 2)
            except Exception:  # noqa: BLE001
                continue
            for tx in block.get("tx", []):
                for vin in tx.get("vin", []):
                    if vin.get("txid") == txid and int(vin.get("vout", -1)) == vout:
                        return {
                            "txid": tx["txid"],
                            "items": spend_input_items(vin),
                            "confirmations": tip - height + 1,
                        }
        return None


# --------------------------------------------------------------------------- #
# The verifier: a pure function of (swap row, two adapters) -> state updates.
# Idempotent and poll-safe. It advances a swap as far as the confirmed on-chain
# evidence allows, and never further.
# --------------------------------------------------------------------------- #

_ACTIONABLE = {"both_locked", "quote_redeemed", "base_redeemed"}


def _expected_amounts(swap: dict) -> tuple:
    """(base MBITE amount, quote amount) that each HTLC must be funded with."""
    amount = Decimal(str(swap["amount"]))
    price = Decimal(str(swap["price"]))
    return amount, amount * price


def verify_swap(
    swap: dict,
    base_adapter,
    quote_adapter,
    *,
    min_confs_base: int = DEFAULT_MIN_CONFS_BASE,
    min_confs_quote: int = DEFAULT_MIN_CONFS_QUOTE,
    now: Optional[int] = None,
) -> dict:
    """Inspect the chains and return the swap's updated fields.

    Returns a dict of columns to persist (possibly empty if nothing confirmed
    changed). Callers apply it via exchange.apply_swap_verification. The returned
    ``status`` is always a legal forward transition or unchanged — never a
    regression, so a reorg that removes evidence simply yields no update until
    depth is re-reached (2c adds active rollback).
    """
    import time as _time

    if swap.get("status") not in _ACTIONABLE:
        return {}
    now = int(_time.time()) if now is None else int(now)
    updates: dict = {}

    base_amount, quote_amount = _expected_amounts(swap)

    base_redeem = htlc_redeemscript(
        swap["hashlock"], swap["base_recipient_pk"], swap["base_refund_pk"],
        swap["base_locktime"],
    )
    quote_redeem = htlc_redeemscript(
        swap["hashlock"], swap["quote_recipient_pk"], swap["quote_refund_pk"],
        swap["quote_locktime"],
    )
    base_spks = funding_script_pubkeys(base_redeem)
    quote_spks = funding_script_pubkeys(quote_redeem)

    # 1) Both fundings must be real: pay the derived HTLC address, for at least
    #    the agreed amount, confirmed to depth. A liar's txid fails this and the
    #    swap simply parks — it never advances on an unverifiable claim.
    base_fund = base_adapter.find_output(swap.get("base_htlc_txid") or "", base_spks)
    quote_fund = quote_adapter.find_output(swap.get("quote_htlc_txid") or "", quote_spks)
    if not base_fund or not quote_fund:
        return {}
    if base_fund["value"] < base_amount or quote_fund["value"] < quote_amount:
        return {}  # underfunded HTLC — cannot back the trade; park.
    if (
        base_fund["confirmations"] < min_confs_base
        or quote_fund["confirmations"] < min_confs_quote
    ):
        return {}  # funding not yet buried deep enough to trust.

    # 2) Quote-leg redemption reveals the preimage publicly. Read it out; do not
    #    accept it from anyone. A refund-branch spend => the swap expired.
    preimage = swap.get("preimage")
    quote_redeem_txid = swap.get("quote_redeem_txid")
    if not preimage:
        spend = quote_adapter.find_spend(swap["quote_htlc_txid"], quote_fund["vout"])
        if spend:
            found = find_preimage(spend["items"], swap["hashlock"])
            if found is None:
                # Output was spent, but not via the hashlock branch => refund.
                updates["status"] = "expired"
                return updates
            if spend["confirmations"] >= min_confs_quote:
                preimage = found
                quote_redeem_txid = spend["txid"]
                updates.update(
                    preimage=preimage,
                    quote_redeem_txid=quote_redeem_txid,
                    quote_confs=spend["confirmations"],
                    status="quote_redeemed",
                )
        else:
            # Not redeemed yet; expire only once the quote timelock has elapsed.
            if now >= int(swap["quote_locktime"]):
                updates["status"] = "expired"
            return updates

    if not preimage:  # revealed but not yet buried to depth
        return updates

    # 3) Base-leg redemption must use that SAME preimage. Confirm it and settle.
    base_redeem_txid = swap.get("base_redeem_txid")
    if not base_redeem_txid:
        spend = base_adapter.find_spend(swap["base_htlc_txid"], base_fund["vout"])
        if not spend:
            return updates  # counterparty hasn't swept the MBITE leg yet.
        if find_preimage(spend["items"], swap["hashlock"]) != preimage:
            # Spent by the refund branch (or a different preimage — impossible
            # given the hashlock, so this is a refund) => expired.
            updates["status"] = "expired"
            return updates
        if spend["confirmations"] < min_confs_base:
            return updates
        base_redeem_txid = spend["txid"]
        updates.update(
            base_redeem_txid=base_redeem_txid,
            base_confs=spend["confirmations"],
            status="base_redeemed",
        )

    # 4) Both legs redeemed and confirmed to depth => the trade truly settled.
    updates["status"] = "settled"
    updates["settled_at"] = now
    return updates


def run_verification_pass(
    exchange,
    base_adapter,
    quote_adapter,
    *,
    min_confs_base: int = DEFAULT_MIN_CONFS_BASE,
    min_confs_quote: int = DEFAULT_MIN_CONFS_QUOTE,
    now: Optional[int] = None,
) -> list:
    """Verify every watchable swap once and persist any confirmed progress.

    Poll-driven and idempotent: safe to call on a timer. Returns the list of
    (swap_id, updates) actually applied, so a scheduler can log progress. The
    ``exchange`` module is injected to keep this file free of DB/import cycles.
    """
    applied = []
    for swap in exchange.list_swaps_for_verification():
        updates = verify_swap(
            swap, base_adapter, quote_adapter,
            min_confs_base=min_confs_base, min_confs_quote=min_confs_quote, now=now,
        )
        if updates:
            exchange.apply_swap_verification(swap["swap_id"], updates)
            applied.append((swap["swap_id"], updates))
    return applied
