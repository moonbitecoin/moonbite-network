"""Explorer API backed by the production MoonBite Core node (JSON-RPC).

web_app.py's /api/explorer/* and /api/blockchain/info routes were written
against the in-process educational Python chain. When the operator points the
dashboard at a real node (BIGCOIN_RPC_URL / BIGCOIN_RPC_USER / _PASSWORD set,
DEMO_MODE not forced on) those routes delegate here, and the responses keep the
exact JSON shape the templates already consume so no page has to change.

Amounts are returned in the node's base unit (1 MBITE = 100_000_000 units) and
every payload carries ``units_per_coin`` so the front end can format them.
"""
from __future__ import annotations

import time

UNITS_PER_COIN = 100_000_000

# Emission schedule (ADR-010): 10 MBITE per block, halving every 1,650,000
# blocks. Computing issued supply from height is exact for coinbase subsidy
# and avoids a full UTXO-set scan (gettxoutsetinfo) on every page load.
SUBSIDY_UNITS = 10 * UNITS_PER_COIN
HALVING_INTERVAL = 1_650_000


def issued_supply_units(height: int) -> int:
    """Total coinbase subsidy issued for blocks 1..height (genesis is unspendable)."""
    total = 0
    remaining = height
    subsidy = SUBSIDY_UNITS
    while remaining > 0 and subsidy > 0:
        n = min(remaining, HALVING_INTERVAL)
        total += n * subsidy
        remaining -= n
        subsidy >>= 1
    return total


def _to_units(value) -> int:
    """Core returns amounts as decimal coins (float in JSON); convert exactly."""
    from decimal import Decimal

    return int((Decimal(str(value)) * UNITS_PER_COIN).to_integral_value())


def _block_summary(header: dict, tip_height: int) -> dict:
    """Summary from getblockheader only. It is served from the block index and
    never touches the block files: getblock and getblockstats both re-read the
    block and re-verify its RandomX proof of work, which costs seconds on a
    small seed box. Size is therefore only known on the block-detail route."""
    height = int(header["height"])
    return {
        "height": height,
        "hash": header["hash"],
        "confirmations": tip_height - height + 1,
        "timestamp": header["time"],
        "tx_count": int(header.get("nTx", 0) or 0),
        "size": None,
        "nonce": header.get("nonce", 0),
        "bits": header.get("bits"),
        "prev_hash": header.get("previousblockhash"),
        "merkle_root": header.get("merkleroot"),
        "difficulty": header.get("difficulty"),
        "subsidy": subsidy_units(height),
        "units_per_coin": UNITS_PER_COIN,
    }


def subsidy_units(height: int) -> int:
    return SUBSIDY_UNITS >> (height // HALVING_INTERVAL)


def _tx_summary(tx: dict) -> dict:
    """Shape matches web_app._tx_summary (Python chain) so explorer.html renders it."""
    outputs = []
    total_out = 0
    for out in tx.get("vout", []):
        units = _to_units(out.get("value", 0))
        total_out += units
        spk = out.get("scriptPubKey", {}) or {}
        address = spk.get("address")
        if not address:
            addrs = spk.get("addresses") or []
            address = addrs[0] if addrs else None
        outputs.append(
            {
                "amount": units,
                "pubkey_hash": spk.get("hex"),
                "address": address,
                "type": spk.get("type"),
            }
        )

    inputs = []
    is_coinbase = False
    for inp in tx.get("vin", []):
        if "coinbase" in inp:
            is_coinbase = True
            inputs.append({"prev_txid": None, "output_index": None, "coinbase": True})
        else:
            inputs.append(
                {"prev_txid": inp.get("txid"), "output_index": inp.get("vout")}
            )

    return {
        "txid": tx["txid"],
        "is_coinbase": is_coinbase,
        "input_count": len(inputs),
        "output_count": len(outputs),
        "total_out": total_out,
        "inputs": inputs,
        "outputs": outputs,
        "size": tx.get("size"),
        "units_per_coin": UNITS_PER_COIN,
    }


def _is_hash(s: str) -> bool:
    return len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s)


# --------------------------------------------------------------------------- #
# Route bodies. Each returns (payload_dict, http_status).
# --------------------------------------------------------------------------- #


def blockchain_info(rpc) -> tuple[dict, int]:
    info = rpc.getblockchaininfo()
    height = int(info["blocks"])
    mempool = rpc.getmempoolinfo()
    try:
        stats = rpc.call("getchaintxstats")
        tx_count = int(stats.get("txcount", 0))
    except Exception:  # noqa: BLE001 — stats are decorative
        tx_count = 0
    issued = issued_supply_units(height)
    tip = rpc.call("getblockheader", info["bestblockhash"])
    return (
        {
            "status": "success",
            "height": height,
            "tip_hash": info["bestblockhash"],
            "total_money_satoshis": issued,
            "total_money_coins": issued / UNITS_PER_COIN,
            "tx_count": tx_count,
            "mempool_size": int(mempool.get("size", 0)),
            "bits": tip.get("bits"),
            "difficulty": info.get("difficulty"),
            "chain": info.get("chain"),
            "headers": info.get("headers"),
            "median_time": info.get("mediantime"),
            "units_per_coin": UNITS_PER_COIN,
            "source": "moonbite-core",
            "timestamp": time.time(),
        },
        200,
    )


def blocks(rpc, limit: int, offset: int) -> tuple[dict, int]:
    tip = int(rpc.getblockcount())
    total = tip + 1
    start = tip - offset
    out = []
    h = start
    while h >= 0 and len(out) < limit:
        out.append(_block_summary(rpc.call("getblockheader", rpc.getblockhash(h)), tip))
        h -= 1
    return (
        {"status": "success", "blocks": out, "total": total, "offset": offset, "limit": limit},
        200,
    )


def block(rpc, identifier: str) -> tuple[dict, int]:
    from explorer.rpc import RPCError

    try:
        if identifier.isdigit():
            block_hash = rpc.getblockhash(int(identifier))
        elif _is_hash(identifier):
            block_hash = identifier.lower()
        else:
            return {"status": "error", "message": "Block not found"}, 404
        header = rpc.call("getblockheader", block_hash)
    except RPCError:
        return {"status": "error", "message": "Block not found"}, 404
    tip = int(rpc.getblockcount())
    summary = _block_summary(header, tip)
    # The one place a full block read is unavoidable: the transaction list.
    try:
        raw = rpc.getblock(block_hash, 2)
        summary["transactions"] = [_tx_summary(t) for t in raw.get("tx", [])]
        summary["size"] = raw.get("size", summary["size"])
    except Exception as exc:  # noqa: BLE001 — slow/loaded node: still show the header
        summary["transactions"] = []
        summary["transactions_error"] = str(exc)
    return {"status": "success", "block": summary}, 200


def tx(rpc, txid: str) -> tuple[dict, int]:
    from explorer.rpc import RPCError

    if not _is_hash(txid):
        return {"status": "error", "message": "Transaction not found"}, 404
    try:
        raw = rpc.getrawtransaction(txid.lower(), True)
    except RPCError:
        return {"status": "error", "message": "Transaction not found"}, 404
    summary = _tx_summary(raw)
    confs = int(raw.get("confirmations", 0) or 0)
    if raw.get("blockhash") and confs > 0:
        summary["status"] = "confirmed"
        summary["block_hash"] = raw["blockhash"]
        summary["confirmations"] = confs
        tip = int(rpc.getblockcount())
        summary["block_height"] = tip - confs + 1
        summary["timestamp"] = raw.get("blocktime")
    else:
        summary["status"] = "pending"
        summary["confirmations"] = 0
    return {"status": "success", "transaction": summary}, 200


def search(rpc, query: str) -> tuple[dict, int]:
    from explorer.rpc import RPCError

    q = query.strip()
    if not q:
        return {"status": "error", "message": "Empty search query"}, 400
    if q.isdigit():
        try:
            rpc.getblockhash(int(q))
            return {"status": "success", "kind": "block", "id": q}, 200
        except RPCError:
            pass
    if _is_hash(q):
        q = q.lower()
        try:
            rpc.getblock(q, 1)
            return {"status": "success", "kind": "block", "id": q}, 200
        except RPCError:
            pass
        try:
            rpc.getrawtransaction(q, True)
            return {"status": "success", "kind": "tx", "id": q}, 200
        except RPCError:
            pass
    return {"status": "error", "message": "Not found"}, 404


def mempool(rpc) -> tuple[dict, int]:
    raw = rpc.getrawmempool(True) or {}
    txs = []
    for txid, entry in raw.items():
        try:
            full = rpc.getrawtransaction(txid, True)
            total_out = sum(_to_units(o.get("value", 0)) for o in full.get("vout", []))
            n_in, n_out = len(full.get("vin", [])), len(full.get("vout", []))
        except Exception:  # noqa: BLE001 — tx may have just left the pool
            total_out, n_in, n_out = 0, 0, 0
        txs.append(
            {
                "txid": txid,
                "inputs": n_in,
                "outputs": n_out,
                "total_out_cents": total_out,
                "total_out": total_out,
                "size": entry.get("vsize", entry.get("size")),
                "units_per_coin": UNITS_PER_COIN,
            }
        )
    return {"status": "success", "transactions": txs}, 200
