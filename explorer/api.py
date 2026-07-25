"""JSON API for the Big Coin mobile wallet.

These endpoints give a non-custodial wallet everything it needs to operate
against a real bigcoind without any address index:

    GET  /api/status                    chain tip + mempool + node info
    GET  /api/address/<addr>/utxos      spendable outputs for an address
    GET  /api/address/<addr>/balance    confirmed / unconfirmed / total
    GET  /api/fee                        suggested fee rate (BIG/kB)
    POST /api/tx/broadcast               relay a signed raw transaction
    GET  /api/tx/<txid>                   decoded transaction

UTXO lookup uses `scantxoutset`, so it works on a stock node (no -addrindex).
When the explorer is in DEMO_MODE there is no live UTXO set, so read endpoints
return empty/zero results with `"demo": true`, and broadcast returns 503.

The wallet builds and signs transactions ON DEVICE; the server only relays the
finished hex and reports chain state. No keys ever reach this server.
"""
import hmac
import threading
import time
from collections import defaultdict
from functools import wraps

from flask import Blueprint, jsonify, request

import config
import webhooks
from rpc import RpcClient, RPCConnectionError, RPCError

api = Blueprint("api", __name__, url_prefix="/api")


def _client():
    return RpcClient()


def _err(message, status):
    resp = jsonify({"error": message})
    resp.status_code = status
    return resp


# Minimal in-process anti-abuse limiter for the unauthenticated relay endpoints
# (single-node explorer). Keyed on remote_addr so it fails closed if a proxy
# hides the real client. Consensus validity is still enforced by the node.
_rl_lock = threading.Lock()
_rl_hits: "defaultdict[tuple, list]" = defaultdict(list)


def _rate_limit(max_calls, window_seconds=60):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # CORS preflight is not a real call — never throttle it, or a browser
            # miner's OPTIONS burst would spend the client's quota before it mines.
            if request.method == "OPTIONS":
                return fn(*args, **kwargs)
            key = (request.remote_addr or "unknown", fn.__name__)
            now = time.time()
            with _rl_lock:
                hits = _rl_hits[key]
                cutoff = now - window_seconds
                hits[:] = [t for t in hits if t > cutoff]
                if len(hits) >= max_calls:
                    retry = int(window_seconds - (now - hits[0])) + 1
                    resp = _err(f"rate limit exceeded ({max_calls}/{window_seconds}s)", 429)
                    resp.headers["Retry-After"] = str(retry)
                    return resp
                hits.append(now)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# MoonBite address prefixes per network. A wrong-network address is *well-formed*
# but belongs to another chain, so the node rejects it with an unhelpful "invalid
# address". We classify by prefix to explain the real problem to the miner.
_ADDR_NETWORKS = (
    # (network key, human label, bech32 HRPs, base58 leading chars)
    ("main", "mainnet", ("moon1", "moonmweb1"), ("M", "3")),
    ("test", "testnet", ("tmoon1", "tmoonmweb1"), ("m", "n", "2")),
    ("regtest", "regtest", ("rmoon1", "rmoonmweb1"), ()),
)

# What getblockchaininfo's "chain" value maps to as a human label.
_CHAIN_LABELS = {"main": "mainnet", "test": "testnet", "regtest": "regtest"}


def _classify_address_network(address):
    """Best-effort guess of which MoonBite network an address is for.

    Returns a network key ('main'|'test'|'regtest') or None if the prefix is
    unrecognized. Bech32 HRPs are unambiguous; base58 leading chars are a hint.
    """
    addr = address.strip()
    lower = addr.lower()
    for key, _label, hrps, _b58 in _ADDR_NETWORKS:
        if any(lower.startswith(h) for h in hrps):
            return key
    for key, _label, _hrps, b58 in _ADDR_NETWORKS:
        if b58 and addr[:1] in b58:
            return key
    return None


def _wrong_network_hint(address, node_chain):
    """If the address is for a different network than the node, explain it.

    Returns a targeted error string, or None if there is no clear mismatch (in
    which case the generic "invalid address" message stands).
    """
    guessed = _classify_address_network(address)
    if guessed is None or node_chain is None or guessed == node_chain:
        return None
    addr_label = _CHAIN_LABELS.get(guessed, guessed)
    node_label = _CHAIN_LABELS.get(node_chain, node_chain)
    want_prefix = {"main": "moon1…", "test": "tmoon1…", "regtest": "rmoon1…"}.get(
        node_chain, "the node's"
    )
    return (
        f"wrong network: that looks like a {addr_label} address, but this node "
        f"is {node_label}. Use a {node_label} address ({want_prefix})."
    )


def _allowed_origin(origin):
    """Return the value to echo in Access-Control-Allow-Origin, or None."""
    allow = [o.strip() for o in config.MINING_CORS_ORIGINS.split(",") if o.strip()]
    if "*" in allow:
        return "*"
    if origin and origin in allow:
        return origin
    return None


@api.after_request
def _cors(resp):
    """Permit the browser miner (served from the website origin) to call the
    JSON API cross-origin. Only origins in MINING_CORS_ORIGINS are echoed."""
    origin = request.headers.get("Origin")
    allowed = _allowed_origin(origin)
    if allowed:
        resp.headers["Access-Control-Allow-Origin"] = allowed
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@api.route("/status")
def status():
    client = _client()
    try:
        info = client.getblockchaininfo()
        mempool = client.getmempoolinfo()
        net = client.getnetworkinfo()
        height = client.getblockcount()
    except RPCConnectionError as exc:
        return _err(str(exc), 503)
    except RPCError as exc:
        return _err(str(exc), 502)

    return jsonify({
        "chain": info.get("chain", "?"),
        "blocks": info.get("blocks", height),
        "headers": info.get("headers", info.get("blocks", height)),
        "bestblockhash": info.get("bestblockhash", ""),
        "difficulty": info.get("difficulty", 0),
        "verificationprogress": info.get("verificationprogress", 1.0),
        "mempool_txs": mempool.get("size", 0),
        "mempool_bytes": mempool.get("bytes", 0),
        "connections": net.get("connections", 0),
        "subversion": net.get("subversion", ""),
        "demo": client.is_demo(),
    })


def _scan_utxos(client, address):
    """Returns (utxos, scan_height). Raises RPCError/RPCConnectionError.

    In demo mode there is no UTXO set, so returns ([], None)."""
    if client.is_demo():
        return [], None
    result = client.scantxoutset("start", [{"desc": f"addr({address})"}])
    if not result or not result.get("success", False):
        return [], result.get("height") if result else None
    scan_height = result.get("height")
    utxos = []
    for u in result.get("unspents", []):
        u_height = u.get("height")
        confirmations = 0
        if scan_height is not None and u_height is not None:
            confirmations = max(0, scan_height - u_height + 1)
        utxos.append({
            "txid": u.get("txid"),
            "vout": u.get("vout"),
            "amount": float(u.get("amount", 0)),
            "scriptPubKey": u.get("scriptPubKey"),
            "height": u_height,
            "confirmations": confirmations,
        })
    return utxos, scan_height


@api.route("/address/<address>/utxos")
def address_utxos(address):
    client = _client()
    address = address.strip()
    try:
        utxos, scan_height = _scan_utxos(client, address)
    except RPCConnectionError as exc:
        return _err(str(exc), 503)
    except RPCError as exc:
        return _err(str(exc), 502)

    return jsonify({
        "address": address,
        "utxos": utxos,
        "scan_height": scan_height,
        "demo": client.is_demo(),
    })


@api.route("/address/<address>/balance")
def address_balance(address):
    client = _client()
    address = address.strip()
    try:
        utxos, _ = _scan_utxos(client, address)
    except RPCConnectionError as exc:
        return _err(str(exc), 503)
    except RPCError as exc:
        return _err(str(exc), 502)

    confirmed = sum(u["amount"] for u in utxos if u["confirmations"] > 0)
    unconfirmed = sum(u["amount"] for u in utxos if u["confirmations"] == 0)
    return jsonify({
        "address": address,
        "confirmed": confirmed,
        "unconfirmed": unconfirmed,
        "total": confirmed + unconfirmed,
        "utxo_count": len(utxos),
        "demo": client.is_demo(),
    })


@api.route("/fee")
def fee():
    client = _client()
    # A conservative floor matching Core's default min relay fee (0.00001/kB).
    fallback = 0.00001
    if client.is_demo():
        return jsonify({"feerate": fallback, "blocks": None, "source": "default", "demo": True})
    try:
        est = client.estimatesmartfee(6)
        rate = est.get("feerate") if isinstance(est, dict) else None
        if rate and rate > 0:
            return jsonify({
                "feerate": float(rate), "blocks": est.get("blocks"),
                "source": "estimatesmartfee", "demo": False,
            })
    except (RPCError, RPCConnectionError):
        pass
    return jsonify({
        "feerate": fallback, "blocks": None,
        "source": "default", "demo": client.is_demo(),
    })


@api.route("/tx/broadcast", methods=["POST"])
@_rate_limit(20, 60)
def broadcast():
    client = _client()
    if client.is_demo():
        return _err("no live node available (explorer is in demo mode)", 503)

    data = request.get_json(silent=True) or {}
    rawtx = (data.get("rawtx") or data.get("hex") or "").strip()
    if not rawtx:
        return _err("missing 'rawtx' hex in request body", 400)

    try:
        txid = client.sendrawtransaction(rawtx)
    except RPCConnectionError as exc:
        return _err(str(exc), 503)
    except RPCError as exc:
        return _err(str(exc), 400)

    return jsonify({"txid": txid})


@api.route("/mine", methods=["POST", "OPTIONS"])
@_rate_limit(10, 60)
def mine():
    """Trigger real mining of one block to `address`. The NODE performs the
    proof-of-work (generatetoaddress); this endpoint just relays the request so
    a browser/phone can mine the live chain. Disabled unless MINING_ENABLED."""
    if request.method == "OPTIONS":
        return ("", 204)

    if not config.MINING_ENABLED:
        return _err("mining endpoint is disabled (set MINING_ENABLED=1 on the explorer)", 403)

    client = _client()
    if client.is_demo():
        return _err("no live node available (explorer is in demo mode)", 503)

    data = request.get_json(silent=True) or {}
    address = (data.get("address") or "").strip()
    if not address:
        return _err("missing 'address' in request body", 400)

    # Validate the address on the node before mining to it.
    try:
        info = client.validateaddress(address)
        if not info.get("isvalid"):
            # A well-formed address for the wrong network is the common footgun
            # (e.g. a tmoon1… testnet address sent to a mainnet node). Detect it
            # and say so, instead of the bare "invalid address".
            node_chain = None
            try:
                node_chain = (client.getblockchaininfo() or {}).get("chain")
            except (RPCConnectionError, RPCError):
                pass
            hint = _wrong_network_hint(address, node_chain)
            return _err(hint or "invalid MoonBite address", 400)
    except RPCConnectionError as exc:
        return _err(str(exc), 503)
    except RPCError as exc:
        return _err(str(exc), 502)

    try:
        before = client.getblockcount()
        hashes = client.generatetoaddress(1, address, config.MINING_MAXTRIES)
    except RPCConnectionError as exc:
        return _err(str(exc), 503)
    except RPCError as exc:
        return _err(str(exc), 502)

    hashes = hashes or []
    return jsonify({
        "mined": len(hashes),
        "hashes": hashes,
        "height": before + len(hashes),
        "address": address,
        # False when the PoW budget was exhausted this call without a block --
        # the client should simply call again.
        "found": bool(hashes),
    })


@api.route("/tx/<txid>")
def tx_json(txid):
    client = _client()
    txid = txid.strip()
    try:
        transaction = client.getrawtransaction(txid, True)
    except RPCConnectionError as exc:
        return _err(str(exc), 503)
    except RPCError as exc:
        return _err(str(exc), 404)
    return jsonify(transaction)


# ------------------------------------------------------------------------- #
# Block explorer JSON (browse blocks / fetch a block / resolve a search).
# Read-only and demo-safe: every RPC used here is backed by demo_data, so
# these keep working on the public instance even when the node is down.
# ------------------------------------------------------------------------- #


def _block_summary(block: dict) -> dict:
    """Compact, stable summary of a getblock (verbosity>=1) result."""
    txids = block.get("tx") or []
    # verbosity 2 returns tx objects; normalise to a count either way.
    tx_count = block.get("nTx")
    if tx_count is None:
        tx_count = len(txids)
    return {
        "height": block.get("height"),
        "hash": block.get("hash"),
        "time": block.get("time"),
        "tx_count": tx_count,
        "size": block.get("size"),
        "difficulty": block.get("difficulty"),
        "nonce": block.get("nonce"),
        "bits": block.get("bits"),
        "merkleroot": block.get("merkleroot"),
        "previousblockhash": block.get("previousblockhash"),
        "nextblockhash": block.get("nextblockhash"),
    }


@api.route("/blocks")
def blocks():
    """Paginated list of block summaries, newest first.

    Query params: limit (1..50, default 15), offset (>=0, default 0)."""
    client = _client()
    try:
        limit = int(request.args.get("limit", 15))
    except (TypeError, ValueError):
        limit = 15
    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0
    limit = max(1, min(limit, 50))
    offset = max(0, offset)

    try:
        tip = client.getblockcount()
        top = tip - offset
        summaries = []
        for h in range(top, max(-1, top - limit), -1):
            block_hash = client.getblockhash(h)
            block = client.getblock(block_hash, 1)
            summaries.append(_block_summary(block))
    except RPCConnectionError as exc:
        return _err(str(exc), 503)
    except RPCError as exc:
        return _err(str(exc), 502)

    return jsonify({
        "blocks": summaries,
        "tip": tip,
        "total": tip + 1,
        "offset": offset,
        "limit": limit,
        "demo": client.is_demo(),
    })


@api.route("/block/<identifier>")
def block_json(identifier):
    """A single block (by height or hash) including its txids."""
    client = _client()
    key = identifier.strip()
    try:
        block_hash = client.getblockhash(int(key)) if key.isdigit() else key
        block = client.getblock(block_hash, 1)
    except RPCConnectionError as exc:
        return _err(str(exc), 503)
    except RPCError:
        return _err("block not found", 404)

    summary = _block_summary(block)
    summary["tx"] = block.get("tx") or []
    summary["confirmations"] = block.get("confirmations")
    summary["demo"] = client.is_demo()
    return jsonify(summary)


@api.route("/search")
def search_json():
    """Resolve a query to a block or transaction. Returns {kind, id}."""
    client = _client()
    q = (request.args.get("q") or "").strip()
    if not q:
        return _err("empty search query", 400)

    # Integer -> block height.
    if q.isdigit():
        try:
            client.getblockhash(int(q))
            return jsonify({"kind": "block", "id": q, "demo": client.is_demo()})
        except (RPCError, RPCConnectionError):
            return _err("no block at that height", 404)

    # 64-char hex -> tx first, then block.
    if len(q) == 64 and all(c in "0123456789abcdefABCDEF" for c in q):
        ql = q.lower()
        try:
            client.getrawtransaction(ql, True)
            return jsonify({"kind": "tx", "id": ql, "demo": client.is_demo()})
        except (RPCError, RPCConnectionError):
            pass
        try:
            client.getblock(ql, 1)
            return jsonify({"kind": "block", "id": ql, "demo": client.is_demo()})
        except (RPCError, RPCConnectionError):
            pass

    return _err("no block or transaction matches that query", 404)


# ------------------------------------------------------------------------- #
# Webhooks. Registration is gated behind an API key so a public explorer is
# never turned into an open relay. Deletion requires the per-hook secret.
# ------------------------------------------------------------------------- #


def _require_api_key():
    """Return an error response if the request lacks a valid API key, else None."""
    if not config.WEBHOOKS_ENABLED:
        return _err("webhooks are disabled", 503)
    if not config.WEBHOOK_API_KEY:
        return _err("webhook registration is not configured", 503)
    provided = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(provided, config.WEBHOOK_API_KEY):
        return _err("missing or invalid API key", 401)
    return None


@api.route("/webhooks", methods=["POST"])
def webhooks_register():
    denied = _require_api_key()
    if denied is not None:
        return denied
    data = request.get_json(silent=True) or {}
    try:
        created = webhooks.register(
            url=data.get("url"),
            event=data.get("event"),
            address=data.get("address"),
        )
    except webhooks.WebhookError as exc:
        return _err(exc.message, exc.status)
    return jsonify(created), 201


@api.route("/webhooks/<hook_id>", methods=["GET"])
def webhooks_get(hook_id):
    hook = webhooks.get(hook_id.strip())
    if hook is None:
        return _err("webhook not found", 404)
    return jsonify(hook)


@api.route("/webhooks/<hook_id>", methods=["DELETE"])
def webhooks_delete(hook_id):
    # The secret authorises deletion; accept it via header or JSON body.
    secret = request.headers.get("X-Webhook-Secret", "")
    if not secret:
        data = request.get_json(silent=True) or {}
        secret = data.get("secret", "")
    try:
        ok = webhooks.delete(hook_id.strip(), secret)
    except webhooks.WebhookError as exc:
        return _err(exc.message, exc.status)
    if not ok:
        return _err("webhook not found", 404)
    return jsonify({"deleted": hook_id})
