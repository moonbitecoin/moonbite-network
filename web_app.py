"""MyCoin Web Dashboard — Flask application for blockchain visualization and interaction.

This module provides a RESTful API and web interface for MyCoin, allowing users to:
  - Generate new wallet addresses
  - Check wallet balances
  - View blockchain information
  - Mine blocks with configurable parameters
  - Monitor mining progress in real-time

Educational use only — never holds real funds.
"""

from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
from collections import defaultdict
from functools import wraps
from typing import Optional

from flask import Flask, jsonify, render_template, request, send_from_directory, session
from werkzeug.middleware.proxy_fix import ProxyFix

import exchange
import merchants
import swap_verifier
from node import Node
from store import BlockStore
from transaction import generate_keypair, pubkey_hash
from wallet import address_from_pubkey_hash, is_valid_address, pubkey_hash_from_address

# Pragmatic email validation for the listing-notify capture.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Optional durable block store. When MOONBITE_CHAIN_DB points at a path, the demo
# node persists every mined block and replays them on startup so the chain
# survives restarts (e.g. a droplet redeploy). Unset (the default, and in tests)
# keeps the node purely in-memory. Persistence never changes consensus: reload
# replays each block through full validation.
_CHAIN_DB = os.environ.get("MOONBITE_CHAIN_DB", "").strip() or None
_chain_store: Optional["BlockStore"] = None

app = Flask(__name__, template_folder="templates", static_folder="static")

# Signs the session cookie that scopes per-visitor wallet state. Set SECRET_KEY
# in production so sessions survive restarts; a random key is a safe default.
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# Trust exactly TRUSTED_PROXY_COUNT reverse-proxy hop(s) in front (nginx = 1).
# ProxyFix rewrites request.remote_addr to the client IP that our OWN proxy
# observed (the rightmost X-Forwarded-For hop it appended), so a client cannot
# forge its identity by sending extra XFF hops. Set to 0 if no proxy is present.
_TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "1"))
if _TRUSTED_PROXY_COUNT > 0:
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=_TRUSTED_PROXY_COUNT, x_proto=1, x_host=1
    )

# Hard cap on request body size. Flask/Werkzeug default to unlimited, so without
# this a single POST with a multi-hundred-MB body forces the worker to buffer +
# JSON-parse it — ~2.8x amplification measured, i.e. one 400 MB request spikes
# the process past 1 GB RAM and OOM-kills a small container. Every legitimate
# API body here (notify, orders, invoices, tx broadcast) is well under 256 KB,
# so Werkzeug rejects anything larger with 413 BEFORE reading the payload.
_MAX_CONTENT_LENGTH = int(os.environ.get("MOONBITE_MAX_BODY_BYTES", str(256 * 1024)))
app.config["MAX_CONTENT_LENGTH"] = _MAX_CONTENT_LENGTH

# Global state for mining operations
app.mining_state = {
    "is_mining": False,
    "blocks_to_mine": 0,
    "blocks_mined": 0,
    "current_block_height": 0,
    "mining_address": None,
    "mining_thread": None,
}

# Global node instance (initialized once per app instance)
app.node: Optional[Node] = None

# Per-visitor wallet addresses are stored in the signed session cookie (see
# /api/wallet/new), capped so the cookie cannot grow without bound.
_MAX_SESSION_ADDRESSES = 25

# Upper bound on blocks a single /api/mining/start request may enqueue. Without
# a cap, one request could ask for billions of blocks and tie up a worker's CPU
# indefinitely (a self-inflicted DoS). 100 is plenty for the demo reactor.
_MAX_MINE_BLOCKS = 100

# Lock for thread-safe mining operations
app.mining_lock = threading.Lock()

# --------------------------------------------------------------------------- #
# Lightweight in-process rate limiting (no external store, no third parties).
#
# A fixed-window counter per (client, endpoint) protects the write endpoints
# (wallet minting, mining, notify, order/merchant creation) from casual abuse.
# Trusted integrations can be issued an API key (MOONBITE_API_KEYS, comma-sep)
# and pass it as X-API-Key to bypass the limits. This is deliberately simple:
# it is anti-abuse for a single-node demo, not a distributed quota system.
# --------------------------------------------------------------------------- #
_API_KEYS = {
    k.strip() for k in os.environ.get("MOONBITE_API_KEYS", "").split(",") if k.strip()
}
# Off under pytest (many calls share one client IP) and whenever explicitly
# disabled; real deployments keep it on. A dedicated test flips it back on to
# assert the limiter actually fires.
_RATE_DISABLED = (
    os.environ.get("MOONBITE_DISABLE_RATELIMIT", "") == "1"
    or "PYTEST_CURRENT_TEST" in os.environ
    or "pytest" in sys.modules
)
_rl_lock = threading.Lock()
_rl_hits: "defaultdict[tuple, list]" = defaultdict(list)


def _client_id() -> str:
    """Caller identity for rate limiting. ProxyFix has already resolved
    request.remote_addr to the client IP our trusted proxy observed, so we do NOT
    parse X-Forwarded-For here — a client cannot spoof this by adding XFF hops."""
    return request.remote_addr or "unknown"


def rate_limit(max_calls: int, window_seconds: int = 60):
    """Cap a route at `max_calls` per rolling `window_seconds` per client.

    A valid X-API-Key (configured via MOONBITE_API_KEYS) bypasses the cap.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            has_valid_key = bool(_API_KEYS) and request.headers.get("X-API-Key", "") in _API_KEYS
            if _RATE_DISABLED or has_valid_key:
                return fn(*args, **kwargs)
            key = (_client_id(), fn.__name__)
            now = time.time()
            with _rl_lock:
                hits = _rl_hits[key]
                cutoff = now - window_seconds
                hits[:] = [t for t in hits if t > cutoff]
                if len(hits) >= max_calls:
                    retry = int(window_seconds - (now - hits[0])) + 1
                    resp = jsonify({
                        "status": "error",
                        "message": f"rate limit exceeded ({max_calls}/{window_seconds}s)",
                        "retry_after": retry,
                    })
                    resp.headers["Retry-After"] = str(retry)
                    return resp, 429
                hits.append(now)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_node() -> Node:
    """Get or create the global node instance.

    When a durable store is configured (MOONBITE_CHAIN_DB), stored blocks are
    replayed into the fresh node on first creation so the chain persists across
    restarts. Each block is re-validated by `add_block`, so a tampered store is
    rejected rather than trusted.
    """
    global _chain_store
    if app.node is None:
        app.node = Node("web-app", coinbase_maturity=0)
        if _CHAIN_DB is not None:
            _chain_store = BlockStore(_CHAIN_DB)
            genesis_hash = app.node.chain.tip
            replayed = 0
            for block in _chain_store.load_blocks_in_height_order():
                if block.hash == genesis_hash:
                    continue
                try:
                    if app.node.chain.add_block(block):
                        replayed += 1
                except Exception as e:  # noqa: BLE001 — skip any invalid stored block
                    print(f"Skipping unloadable block {block.hash[:12]}: {e}")
            if replayed:
                print(f"Replayed {replayed} persisted block(s); height={app.node.chain.height}")
    return app.node


def _persist_block(block) -> None:
    """Save a freshly mined block to the durable store, if one is configured."""
    if _chain_store is not None and block is not None:
        try:
            _chain_store.save_block(block, get_node().chain.heights[block.hash])
        except Exception as e:  # noqa: BLE001 — persistence must never break mining
            print(f"Persist error for block {block.hash[:12]}: {e}")


def received_at_address(address: str) -> int:
    """Total base units ever paid to `address` across the active chain.

    Watch-only style, monotonic (never drops when the merchant later spends), so
    it is a stable baseline for detecting a specific inbound invoice payment.
    Non-custodial: we only *observe* the chain; we never move or hold funds.
    """
    try:
        pkh = pubkey_hash_from_address(address)
    except Exception:
        return 0
    node = get_node()
    chain = node.chain
    total = 0
    for block_hash in chain.active_chain():
        block = chain.blocks[block_hash]
        for tx in block.transactions:
            for out in tx.outputs:
                if out.pubkey_hash == pkh:
                    total += out.amount
    return total


# --------------------------------------------------------------------------- #
# Merchant payment observation — production node (JSON-RPC) backend
#
# The merchant layer needs a received_lookup(address) -> base units. In the demo
# it reads the in-process educational chain (received_at_address above). Against
# the real moonbited node we ask it directly. A stock node has no address index,
# so we use `scantxoutset`, which reports the address's *current unspent* balance.
# That is enough to detect a fresh invoice payment (a new inbound total over the
# baseline snapshotted when the invoice was raised), provided the merchant does
# not spend from the receive address mid-invoice — so give each invoice/merchant
# a dedicated receive address.
# --------------------------------------------------------------------------- #
_merchant_rpc_client = None
_merchant_rpc_lock = threading.Lock()
_merchant_recv_cache: dict = {}
# scantxoutset walks the whole UTXO set (seconds, single-scan-at-a-time), so a
# short cache keeps rapid invoice-status polls from hammering the node.
_MERCHANT_RECV_TTL = float(os.environ.get("MOONBITE_MERCHANT_SCAN_TTL", "5"))


def _merchant_use_rpc() -> bool:
    """True when the operator has pointed us at a real node (RPC creds/URL set)
    and has not forced demo mode. Unset in dev/tests -> stay on the demo chain.

    NOTE: production should also set DEMO_MODE=0 so the RPC client keeps retrying
    the node on a transient outage instead of latching into demo sample data.
    """
    if os.environ.get("DEMO_MODE", "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    return bool(
        os.environ.get("BIGCOIN_RPC_URL")
        or os.environ.get("BIGCOIN_RPC_USER")
        or os.environ.get("BIGCOIN_RPC_PASSWORD")
    )


def _get_merchant_rpc():
    """Lazily build the explorer RPC client. explorer/rpc.py uses a bare
    ``import config``, so the explorer dir must be on sys.path (mirrors the
    settlement-verifier route)."""
    global _merchant_rpc_client
    if _merchant_rpc_client is None:
        _exp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "explorer")
        if _exp_dir not in sys.path:
            sys.path.insert(0, _exp_dir)
        from explorer.rpc import RpcClient

        _merchant_rpc_client = RpcClient()
    return _merchant_rpc_client


def received_at_address_rpc(address: str) -> int:
    """Current unspent balance at `address` from the production node, in base
    units (merchants.UNITS_PER_COIN). Fail-safe: ANY error returns 0 so an
    invoice is never falsely marked paid — it just stays pending and is retried
    on the next poll."""
    from decimal import Decimal

    now = time.time()
    with _merchant_rpc_lock:
        hit = _merchant_recv_cache.get(address)
        if hit is not None and now - hit[0] < _MERCHANT_RECV_TTL:
            return hit[1]
        try:
            client = _get_merchant_rpc()
            result = client.scantxoutset("start", [{"desc": f"addr({address})"}])
        except Exception:  # noqa: BLE001 — node down/auth/demo => observe nothing
            return 0
        if not isinstance(result, dict) or not result.get("success", True):
            return 0
        try:
            units = int(
                (Decimal(str(result.get("total_amount", 0))) * merchants.UNITS_PER_COIN)
                .to_integral_value()
            )
        except Exception:  # noqa: BLE001 — malformed amount
            return 0
        _merchant_recv_cache[address] = (time.time(), units)
        return units


def merchant_received_lookup(address: str) -> int:
    """The received_lookup handed to the merchant layer: production node when
    configured, else the in-process educational chain."""
    if _merchant_use_rpc():
        return received_at_address_rpc(address)
    return received_at_address(address)


def mining_worker(blocks_to_mine: int, miner_address: str) -> None:
    """Background worker thread for mining blocks."""
    node = get_node()
    # Bind the state dict once: this run should consistently update its own dict
    # even if app.mining_state is later reassigned (e.g. by a test fixture reset).
    state = app.mining_state
    state["blocks_mined"] = 0
    state["current_block_height"] = node.chain.height
    state["hashes_tried"] = 0
    state["hashrate"] = 0.0
    state["started_at"] = time.time()

    for i in range(blocks_to_mine):
        if not state["is_mining"]:
            break

        try:
            block = node.mine_block(miner_address)
            if block is not None:
                _persist_block(block)
                # `mine()` starts at nonce 0 and increments until a hash meets
                # target, so nonce+1 is the real number of hashes tried for this
                # block. Summing them over elapsed time is an honest hashrate.
                state["hashes_tried"] += block.header.nonce + 1
                elapsed = max(1e-6, time.time() - state["started_at"])
                state["hashrate"] = state["hashes_tried"] / elapsed
                state["blocks_mined"] = i + 1
                state["current_block_height"] = node.chain.height
            else:
                break
        except Exception as e:
            print(f"Mining error: {e}")
            break

    state["is_mining"] = False


# ============================================================================= #
# Routes
# ============================================================================= #


@app.route("/")
def home_page():
    """Render the marketing homepage (editorial/terminal home-v2 design)."""
    return render_template("home_v2.html")


@app.route("/home-classic")
def home_classic_page():
    """Render the previous cinematic film-scroll homepage (kept for reference)."""
    return render_template("home.html")


@app.route("/take-a-bite")
def take_a_bite_page():
    """Render the "You can't buy MoonBite" cinematic mining-demo landing page."""
    return render_template("take_a_bite.html")


@app.route("/logo-sting")
def logo_sting_page():
    """Render the MoonBite logo animation (Boot -> Bite -> Lockup sting)."""
    return render_template("logo_sting.html")


@app.route("/home-v2")
def home_v2_page():
    """Preview the new editorial/terminal MoonBite home design."""
    return render_template("home_v2.html")


@app.route("/dashboard")
def dashboard_page():
    """Render the live network dashboard."""
    return render_template("index.html")


# --- bitcoin.org-style information architecture (marketing pages) ------------ #
# Introduction
@app.route("/individuals")
def individuals_page():
    """MoonBite for individuals."""
    return render_template("individuals.html")


@app.route("/businesses")
def businesses_page():
    """MoonBite for businesses."""
    return render_template("businesses.html")


@app.route("/getting-started")
def getting_started_page():
    """Step-by-step getting-started walkthrough."""
    return render_template("getting_started.html")


@app.route("/how-it-works")
def how_it_works_page():
    """Plain-language explanation of how MoonBite works."""
    return render_template("how_it_works.html")


@app.route("/you-need-to-know")
def you_need_to_know_page():
    """Honest caveats before using MoonBite."""
    return render_template("you_need_to_know.html")


@app.route("/whitepaper")
def whitepaper_page():
    """Protocol & design overview."""
    return render_template("whitepaper.html")


# Resources
@app.route("/resources")
def resources_page():
    """Directory of MoonBite tools and docs."""
    return render_template("resources.html")


@app.route("/exchanges")
def exchanges_page():
    """Where to get MBITE (listings coming soon)."""
    return render_template("exchanges.html")


@app.route("/community")
def community_page():
    """Ways to participate in the MoonBite community."""
    return render_template("community.html")


@app.route("/vocabulary")
def vocabulary_page():
    """Glossary of MoonBite / crypto terms."""
    return render_template("vocabulary.html")


@app.route("/events")
def events_page():
    """MoonBite events and milestones."""
    return render_template("events.html")


@app.route("/moonbite-core")
def moonbite_core_page():
    """The MoonBite Core reference node software."""
    return render_template("moonbite_core.html")


# Participate
@app.route("/support")
def support_page():
    """Support the MoonBite network."""
    return render_template("support.html")


@app.route("/buy")
def buy_page():
    """Getting MBITE (buying — coming soon)."""
    return render_template("buy.html")


@app.route("/sell")
def sell_page():
    """Selling MBITE (coming soon)."""
    return render_template("sell.html")


@app.route("/full-node")
def full_node_page():
    """Running a full node."""
    return render_template("full_node.html")


@app.route("/development")
def development_page():
    """Building on and contributing to MoonBite."""
    return render_template("development.html")


# Other
@app.route("/scams")
def scams_page():
    """How to avoid MoonBite-related scams."""
    return render_template("scams.html")


@app.route("/legal")
def legal_page():
    """Plain-language legal disclaimer."""
    return render_template("legal.html")


@app.route("/privacy")
def privacy_page():
    """Plain-language privacy policy."""
    return render_template("privacy.html")


@app.route("/press")
def press_page():
    """Press and brand information."""
    return render_template("press.html")


@app.route("/blog")
def blog_page():
    """MoonBite build log."""
    return render_template("blog.html")


@app.route("/get-wallet")
def get_wallet_page():
    """Render the wallet landing page."""
    return render_template("get_wallet.html")


@app.route("/mine")
def mine_page():
    """Render the mining landing page."""
    return render_template("mine.html")


@app.route("/markets")
def markets_page():
    """Render the markets / listings landing page."""
    return render_template("markets.html")


@app.route("/merchants")
def merchants_page():
    """Render the merchant directory + accept-MBITE pay-flow page."""
    return render_template("merchants.html")


@app.route("/developers")
def developers_page():
    """Render the developers landing page."""
    return render_template("developers.html")


@app.route("/learn")
def learn_page():
    """Render the learn / FAQ landing page."""
    return render_template("learn.html")


@app.route("/about")
def about_page():
    """Render the about landing page."""
    return render_template("about.html")


@app.route("/why")
def why_page():
    """Render the 'why MoonBite' page."""
    return render_template("why.html")


@app.route("/wallet")
def wallet_page():
    """Render the wallet page."""
    return render_template("wallet.html")


@app.route("/mining")
def mining_page():
    """Render the mining page."""
    return render_template("mining.html")


@app.route("/explorer")
def explorer_page():
    """Render the block explorer page."""
    return render_template("explorer.html")


@app.route("/downloads/<path:filename>")
def downloads(filename: str):
    """Serve real release artifacts from website/downloads."""
    return send_from_directory("website/downloads", filename)


@app.route("/api/notify", methods=["POST"])
@rate_limit(10, 60)
def api_notify():
    """Capture an email for the exchange-listing announcement."""
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip()
    source = str(data.get("source", "unknown")).strip()[:64]

    # Basic server-side email validation (no third parties, no SMTP)
    if not EMAIL_RE.match(email) or len(email) > 254:
        return jsonify({"status": "error", "message": "Invalid email address"}), 400

    record = {"email": email, "source": source, "ts": int(time.time())}
    try:
        with open("notify_signups.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        # Ephemeral FS (e.g. Railway) — client keeps a localStorage fallback.
        pass

    return jsonify({"status": "success", "message": "You're on the list"})


# ============================================================================= #
# API Routes — Internal Exchange (non-custodial order book)
#
# The server matchmakes order *intents* only. It never holds coins, keys, or
# balances; settlement is a wallet-to-wallet atomic swap off this server.
# ============================================================================= #


@app.route("/api/exchange/pairs", methods=["GET"])
def api_exchange_pairs():
    """List the trading pairs the order book supports."""
    return jsonify({"status": "success", "pairs": exchange.SUPPORTED_PAIRS}), 200


@app.route("/api/exchange/orders", methods=["GET"])
def api_exchange_orders():
    """Return the order book (bids/asks) for a pair, or all open orders."""
    pair = request.args.get("pair")
    status = request.args.get("status", "open")
    try:
        book = exchange.list_orders(pair=pair, status=status)
        return jsonify({"status": "success", **book}), 200
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/exchange/order", methods=["POST"])
@rate_limit(30, 60)
def api_exchange_create_order():
    """Post a new public order intent to the book."""
    data = request.get_json(silent=True) or {}
    try:
        order = exchange.create_order(
            side=str(data.get("side", "")).strip(),
            pair=str(data.get("pair", "")).strip(),
            price=data.get("price"),
            amount=data.get("amount"),
            mbite_address=data.get("mbite_address", ""),
            quote_address=data.get("quote_address", ""),
        )
        return jsonify({"status": "success", "order": order}), 201
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/exchange/order/<order_id>", methods=["GET"])
def api_exchange_get_order(order_id: str):
    """Fetch a single order by id."""
    order = exchange.get_order(order_id)
    if order is None:
        return jsonify({"status": "error", "message": "order not found"}), 404
    return jsonify({"status": "success", "order": order}), 200


@app.route("/api/exchange/order/<order_id>/cancel", methods=["POST"])
def api_exchange_cancel_order(order_id: str):
    """Cancel an open order — requires the secret cancel_token from creation."""
    data = request.get_json(silent=True) or {}
    try:
        order = exchange.cancel_order(order_id, str(data.get("cancel_token", "")))
        return jsonify({"status": "success", "order": order}), 200
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/exchange/order/<order_id>/settle", methods=["GET"])
def api_exchange_settle_hint(order_id: str):
    """Return the atomic-swap hand-off instructions for a matched order."""
    try:
        return jsonify({"status": "success", **exchange.settle_hint(order_id)}), 200
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 404


# --- Phase 2a: atomic-swap settlement coordination (non-custodial) ---------- #
# Records the HTLC hand-off and self-reported funding for a matched pair. The
# server verifies nothing on-chain yet (Phase 2b) and moves no funds; a swap
# progresses no further than 'both_locked' and no trade is marked settled here.


@app.route("/api/exchange/order/<order_id>/swap", methods=["GET"])
def api_exchange_get_swap(order_id: str):
    """Return the settlement-coordination swap for a matched order, if any."""
    swap = exchange.get_swap(order_id)
    if swap is None:
        return jsonify({"status": "error", "message": "no swap for this order"}), 404
    return jsonify({"status": "success", "swap": swap}), 200


@app.route("/api/exchange/order/<order_id>/swap/init", methods=["POST"])
@rate_limit(30, 60)
def api_exchange_swap_init(order_id: str):
    """Register the HTLC hand-off for a matched order pair. Auth: cancel_token."""
    data = request.get_json(silent=True) or {}
    try:
        swap = exchange.init_swap(
            order_id=order_id,
            cancel_token=str(data.get("cancel_token", "")),
            hashlock=data.get("hashlock", ""),
            base_recipient_pk=data.get("base_recipient_pubkey", ""),
            base_refund_pk=data.get("base_refund_pubkey", ""),
            quote_recipient_pk=data.get("quote_recipient_pubkey", ""),
            quote_refund_pk=data.get("quote_refund_pubkey", ""),
            base_locktime=data.get("base_locktime"),
            quote_locktime=data.get("quote_locktime"),
        )
        return jsonify({"status": "success", "swap": swap}), 201
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/exchange/order/<order_id>/swap/funded", methods=["POST"])
@rate_limit(30, 60)
def api_exchange_swap_funded(order_id: str):
    """Report an HTLC funding txid for one leg (base|quote). Auth: cancel_token.

    Phase 2a records the report and advances the state machine; it does NOT
    verify the tx on-chain (Phase 2b) and never treats it as settlement.
    """
    data = request.get_json(silent=True) or {}
    try:
        swap = exchange.report_funding(
            order_id=order_id,
            cancel_token=str(data.get("cancel_token", "")),
            leg=str(data.get("leg", "")).strip(),
            txid=data.get("txid", ""),
        )
        return jsonify({"status": "success", "swap": swap}), 200
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/exchange/verify", methods=["POST"])
def api_exchange_verify():
    """Run one Phase 2b on-chain verification pass over pending swaps.

    Read-only against the operator's node: confirms HTLC fundings/redemptions and
    advances genuinely-settled trades (the only path that moves last_price). This
    is an OPERATOR trigger, not a public endpoint — intended to be called on a
    timer (cron/systemd). It is:
      * disabled unless VERIFIER_ENABLED is set (a swap never settles otherwise);
      * gated by a shared secret VERIFIER_TRIGGER_TOKEN (X-Verifier-Token header)
        so the public cannot make the box hammer the node;
      * safe when a chain is unreachable/unconfigured — it simply settles nothing
        (the quote leg uses a NullAdapter until the Phase 2c quote adapter lands).
    """
    from explorer import config as ex_config

    if not ex_config.VERIFIER_ENABLED:
        return jsonify({"status": "error", "message": "verifier disabled"}), 403

    expected = os.environ.get("VERIFIER_TRIGGER_TOKEN", "")
    provided = request.headers.get("X-Verifier-Token", "")
    if not expected or not hmac.compare_digest(expected, provided):
        return jsonify({"status": "error", "message": "unauthorized"}), 403

    # Only now touch the RPC client. explorer/rpc.py uses a bare ``import config``
    # (it is designed to run with explorer/ on the path), so make that resolve.
    _exp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "explorer")
    if _exp_dir not in sys.path:
        sys.path.insert(0, _exp_dir)
    from explorer.rpc import RpcClient

    base_adapter = swap_verifier.MoonNodeAdapter(RpcClient())
    quote_adapter = swap_verifier.NullAdapter()  # Phase 2c wires a real quote leg
    try:
        applied = swap_verifier.run_verification_pass(
            exchange, base_adapter, quote_adapter,
            min_confs_base=ex_config.VERIFIER_MIN_CONFS_BASE,
            min_confs_quote=ex_config.VERIFIER_MIN_CONFS_QUOTE,
        )
    except Exception as e:  # noqa: BLE001 - node unreachable etc. => 503, never 500
        return jsonify({"status": "error", "message": f"node unavailable: {e}"}), 503

    return jsonify({
        "status": "success",
        "verified": len(applied),
        "results": [{"swap_id": sid, "status": u.get("status")} for sid, u in applied],
    }), 200


# ============================================================================= #
# API Routes — Merchant adoption (non-custodial "Accept MBITE")
#
# A directory of businesses that voluntarily accept MBITE, plus invoices they
# raise. The server never holds funds — a payment is *observed* on-chain at the
# merchant's own address; settlement is wallet-to-wallet.
# ============================================================================= #


@app.route("/api/merchants", methods=["GET"])
def api_merchants_list():
    """List merchants in the directory, optionally filtered by category."""
    category = request.args.get("category")
    try:
        rows = merchants.list_merchants(category=category)
        return jsonify(
            {"status": "success", "merchants": rows, "categories": list(merchants.CATEGORIES)}
        ), 200
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/merchants", methods=["POST"])
@rate_limit(10, 60)
def api_merchants_add():
    """Register a merchant that accepts MBITE (opt-in)."""
    data = request.get_json(silent=True) or {}
    try:
        row = merchants.add_merchant(
            name=data.get("name"),
            category=str(data.get("category", "")).strip(),
            mbite_address=data.get("mbite_address", ""),
            url=data.get("url", ""),
            blurb=data.get("blurb", ""),
            address_validator=is_valid_address,
        )
        return jsonify({"status": "success", "merchant": row}), 201
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/merchant/invoice", methods=["POST"])
@rate_limit(30, 60)
def api_merchant_invoice_create():
    """Raise a non-custodial payment request against a merchant address."""
    data = request.get_json(silent=True) or {}
    try:
        inv = merchants.create_invoice(
            address=data.get("address", ""),
            amount=data.get("amount"),
            received_lookup=merchant_received_lookup,
            merchant_id=data.get("merchant_id"),
            memo=data.get("memo", ""),
            address_validator=is_valid_address,
        )
        return jsonify({"status": "success", "invoice": inv}), 201
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/merchant/invoice/<invoice_id>", methods=["GET"])
def api_merchant_invoice_status(invoice_id: str):
    """Poll an invoice — re-checks the chain for payment each call."""
    try:
        inv = merchants.invoice_status(invoice_id, merchant_received_lookup)
        return jsonify({"status": "success", "invoice": inv}), 200
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 404


def _qr_svg(payload: str) -> Optional[str]:
    """Render `payload` as an SVG QR code, or None if the encoder is unavailable.

    Pure-Python (qrcode's SVG factory needs no Pillow). Kept optional so the app
    still runs — the customer can always copy the payment URI — if the dependency
    is not installed.
    """
    try:
        import qrcode
        import qrcode.image.svg as svg
    except Exception:  # noqa: BLE001 — optional dependency
        return None
    import io
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(image_factory=svg.SvgPathImage).save(buf)
    return buf.getvalue().decode("utf-8")


@app.route("/api/merchant/invoices", methods=["GET"])
def api_merchant_invoices_list():
    """List invoices (optionally for one merchant), each freshly checked on-chain.

    A shop dashboard read: pass ?merchant_id=… to scope to one seller. Listing
    also advances any invoice that has been paid or expired since last seen.
    """
    merchant_id = request.args.get("merchant_id")
    try:
        rows = merchants.list_invoices(merchant_received_lookup, merchant_id=merchant_id)
        return jsonify({"status": "success", "invoices": rows}), 200
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/merchant/invoices/poll", methods=["POST"])
@rate_limit(10, 60)
def api_merchant_invoices_poll():
    """Sweep all pending invoices once, auto-marking paid/expired ones.

    The automation a shop (or a timer) uses so it need not poll each invoice by
    hand. Non-custodial: only observes the chain and records the result.
    """
    try:
        summary = merchants.poll_pending_invoices(merchant_received_lookup)
        return jsonify({"status": "success", **summary}), 200
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/merchant/invoice/<invoice_id>/qr.svg", methods=["GET"])
def api_merchant_invoice_qr(invoice_id: str):
    """Serve a scannable QR of the invoice's BIP21-style payment URI.

    Non-custodial: the QR just encodes moonbite:<address>?amount=… so the payer's
    own wallet prefills the send. The server never touches funds.
    """
    try:
        inv = merchants.invoice_status(invoice_id, merchant_received_lookup)
    except ValueError:
        return jsonify({"status": "error", "message": "invoice not found"}), 404
    svg_doc = _qr_svg(inv["pay_uri"])
    if svg_doc is None:
        return jsonify({"status": "error", "message": "QR encoder unavailable"}), 501
    return app.response_class(svg_doc, mimetype="image/svg+xml")


# ============================================================================= #
# API Routes — Wallet
# ============================================================================= #


@app.route("/api/wallet/new", methods=["GET"])
@rate_limit(30, 60)
def api_wallet_new():
    """Generate a new keypair and return address + pubkey_hash."""
    try:
        sk, pubkey_hex = generate_keypair()
        pkh = pubkey_hash(pubkey_hex)
        address = address_from_pubkey_hash(pkh)

        # Scope generated addresses to THIS visitor's signed session cookie — not
        # a process-global dict — so one user's /balance never aggregates another
        # user's addresses, and the server holds no unbounded in-memory state.
        # Persist only the pubkey_hash (all /balance needs); keep it well under
        # the ~4KB cookie limit and bounded so it cannot grow without limit.
        pkhs = [h for h in session.get("wallet_pkhs", []) if h != pkh]
        pkhs.append(pkh)
        session["wallet_pkhs"] = pkhs[-_MAX_SESSION_ADDRESSES:]

        return jsonify(
            {
                "status": "success",
                "address": address,
                "pubkey_hash": pkh,
                "pubkey": pubkey_hex,
            }
        ), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/wallet/balance", methods=["GET"])
def api_wallet_balance():
    """Get balance for all generated addresses in this session."""
    try:
        node = get_node()
        total_balance = 0
        utxo_count = 0

        # Only this visitor's own session-scoped addresses (see /api/wallet/new).
        for pkh in session.get("wallet_pkhs", []):
            # Iterate through all UTXOs and find those matching this pubkey_hash
            for _txid, _idx, out in node.chain.utxo.items():
                if out.pubkey_hash == pkh:
                    total_balance += out.amount
                    utxo_count += 1

        # MoonBite's smallest unit is a "cent": 1 MBITE = 100,000,000 cents
        # (same 8-decimal precision as Bitcoin). Report the real coin value.
        from params import CENTS_PER_COIN
        balance_coins = total_balance / CENTS_PER_COIN

        return jsonify(
            {
                "status": "success",
                "balance_coins": balance_coins,
                "balance_units": total_balance,
                "balance_display": f"{balance_coins:.8f}".rstrip("0").rstrip(".") or "0",
                "utxo_count": utxo_count,
            }
        ), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================= #
# API Routes — Blockchain Info
# ============================================================================= #


@app.route("/api/blockchain/info", methods=["GET"])
def api_blockchain_info():
    """Get blockchain state: height, tip hash, total money, tx count."""
    try:
        node = get_node()
        chain = node.chain

        # Count total transactions in the active chain
        tx_count = sum(
            len(block.transactions)
            for block_hash in chain.active_chain()
            for block in [chain.blocks[block_hash]]
        )

        # Calculate total money (sum of coinbase outputs)
        # In a real system, this would be tracked more efficiently
        total_money_satoshis = sum(
            output.amount
            for block_hash in chain.active_chain()
            for block in [chain.blocks[block_hash]]
            for tx in block.transactions
            for output in tx.outputs
        )
        total_money_coins = total_money_satoshis / 100_000_000

        tip_bits = chain.blocks[chain.tip].header.bits if chain.tip else 0

        return jsonify(
            {
                "status": "success",
                "height": chain.height,
                "tip_hash": chain.tip,
                "total_money_satoshis": total_money_satoshis,
                "total_money_coins": total_money_coins,
                "tx_count": tx_count,
                "mempool_size": len(chain.mempool),
                "bits": tip_bits,
                "difficulty": (1 << tip_bits) if tip_bits else 0,
            }
        ), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================= #
# API Routes — Mining
# ============================================================================= #


@app.route("/api/mining/start", methods=["POST"])
@rate_limit(20, 60)
def api_mining_start():
    """Start mining blocks. Expects JSON: {"blocks": N, "address": "..."}"""
    with app.mining_lock:
        if app.mining_state["is_mining"]:
            return jsonify(
                {
                    "status": "error",
                    "message": "Mining already in progress",
                }
            ), 400

        try:
            data = request.get_json()
            blocks_to_mine = data.get("blocks", 1)
            miner_address = data.get("address")

            # Reject a non-integer or out-of-range block count (bool is an int
            # subclass, so exclude it explicitly). Capping at _MAX_MINE_BLOCKS
            # stops a single request from pinning a worker on unbounded PoW.
            if isinstance(blocks_to_mine, bool) or not isinstance(blocks_to_mine, int):
                return jsonify(
                    {
                        "status": "error",
                        "message": "'blocks' must be an integer",
                    }
                ), 400

            if not miner_address or blocks_to_mine <= 0 or blocks_to_mine > _MAX_MINE_BLOCKS:
                return jsonify(
                    {
                        "status": "error",
                        "message": f"Invalid blocks (1-{_MAX_MINE_BLOCKS}) or address",
                    }
                ), 400

            # Validate and convert address to pubkey_hash
            try:
                from wallet import pubkey_hash_from_address
                miner_pubkey_hash = pubkey_hash_from_address(miner_address)
            except Exception as e:
                return jsonify(
                    {
                        "status": "error",
                        "message": f"Invalid address format: {str(e)}",
                    }
                ), 400

            app.mining_state["is_mining"] = True
            app.mining_state["blocks_to_mine"] = blocks_to_mine
            app.mining_state["blocks_mined"] = 0
            app.mining_state["mining_address"] = miner_address

            # Start mining in a background thread (pass pubkey_hash, not address)
            thread = threading.Thread(
                target=mining_worker, args=(blocks_to_mine, miner_pubkey_hash), daemon=True
            )
            app.mining_state["mining_thread"] = thread
            thread.start()

            return jsonify(
                {
                    "status": "mining",
                    "blocks_to_mine": blocks_to_mine,
                }
            ), 200

        except Exception as e:
            app.mining_state["is_mining"] = False
            return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/mining/status", methods=["GET"])
def api_mining_status():
    """Get current mining status."""
    try:
        from block import block_subsidy

        node = get_node()
        chain = node.chain
        next_bits = chain.next_bits()
        # Difficulty = expected hashes to find a block = 2**bits (target is
        # 2**(256-bits), so P(meet)=2**-bits). Report it two ways.
        difficulty = 1 << next_bits
        hashrate = float(app.mining_state.get("hashrate", 0.0))
        # Estimated seconds to the next block at the measured hashrate.
        eta_seconds = (difficulty / hashrate) if hashrate > 0 else None
        next_height = chain.height + 1
        block_reward = block_subsidy(next_height)
        return jsonify(
            {
                "status": "mining" if app.mining_state["is_mining"] else "idle",
                "blocks_mined": app.mining_state["blocks_mined"],
                "total_blocks": app.mining_state["blocks_to_mine"],
                "current_height": chain.height,
                "tip_hash": chain.tip,
                "bits": next_bits,
                "difficulty": difficulty,
                "hashes_tried": app.mining_state.get("hashes_tried", 0),
                "hashrate": round(hashrate, 2),
                "eta_next_block_seconds": (round(eta_seconds, 2)
                                           if eta_seconds is not None else None),
                "next_block_reward_coins": block_reward / 100_000_000,
            }
        ), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/mining/stop", methods=["GET"])
def api_mining_stop():
    """Stop the current mining operation."""
    try:
        app.mining_state["is_mining"] = False
        return jsonify({"status": "stopped"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================= #
# API Routes — Transactions
# ============================================================================= #


@app.route("/api/transactions", methods=["GET"])
def api_transactions():
    """Get recent transactions from mempool and recent blocks."""
    try:
        node = get_node()
        transactions = []

        # Get mempool transactions (pending)
        for txid, tx in list(node.chain.mempool.items())[:10]:
            transactions.append(
                {
                    "txid": txid,
                    "status": "pending",
                    "inputs": len(tx.inputs),
                    "outputs": len(tx.outputs),
                }
            )

        # Get transactions from the last 5 blocks
        chain = node.chain
        for block_hash in chain.active_chain()[-5:]:
            block = chain.blocks[block_hash]
            for tx in block.transactions:
                transactions.append(
                    {
                        "txid": tx.txid,
                        "status": "confirmed",
                        "inputs": len(tx.inputs),
                        "outputs": len(tx.outputs),
                    }
                )

        return jsonify(
            {
                "status": "success",
                "transactions": transactions[:20],  # Limit to 20 most recent
            }
        ), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/mempool", methods=["GET"])
def api_mempool():
    """Return only the pending (unconfirmed) transactions in the mempool.

    Shape matches the wallet page's mempool panel: each entry carries the txid,
    input/output counts, and the total output value in cents.
    """
    try:
        node = get_node()
        transactions = []
        for txid, tx in node.chain.mempool.items():
            total_out_cents = sum(out.amount for out in tx.outputs)
            transactions.append(
                {
                    "txid": txid,
                    "inputs": len(tx.inputs),
                    "outputs": len(tx.outputs),
                    "total_out_cents": total_out_cents,
                }
            )
        return jsonify({"status": "success", "transactions": transactions}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================= #
# API Routes — Block Explorer
# ============================================================================= #


def _block_summary(chain, block_hash: str) -> dict:
    """Build a compact summary dict for a block."""
    block = chain.blocks[block_hash]
    header = block.header
    height = chain.heights[block_hash]
    confirmations = chain.height - height + 1
    return {
        "height": height,
        "hash": block_hash,
        "confirmations": confirmations,
        "timestamp": header.timestamp,
        "tx_count": len(block.transactions),
        "size": block.serialized_size(),
        "nonce": header.nonce,
        "bits": header.bits,
        "prev_hash": header.prev_hash,
        "merkle_root": header.merkle_root,
    }


def _tx_summary(tx) -> dict:
    """Build a detailed summary dict for a transaction."""
    outputs = []
    total_out = 0
    for out in tx.outputs:
        total_out += out.amount
        try:
            address = address_from_pubkey_hash(out.pubkey_hash)
        except Exception:
            address = None
        outputs.append(
            {
                "amount": out.amount,
                "pubkey_hash": out.pubkey_hash,
                "address": address,
            }
        )

    inputs = []
    for inp in tx.inputs:
        inputs.append(
            {
                "prev_txid": inp.prev_txid,
                "output_index": inp.output_index,
            }
        )

    return {
        "txid": tx.txid,
        "is_coinbase": tx.is_coinbase(),
        "input_count": len(tx.inputs),
        "output_count": len(tx.outputs),
        "total_out": total_out,
        "inputs": inputs,
        "outputs": outputs,
    }


@app.route("/api/explorer/blocks", methods=["GET"])
def api_explorer_blocks():
    """Return a paginated list of blocks, newest first."""
    try:
        node = get_node()
        chain = node.chain

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

        active = chain.active_chain()  # genesis -> tip
        newest_first = list(reversed(active))
        page = newest_first[offset : offset + limit]

        blocks = [_block_summary(chain, h) for h in page]

        return jsonify(
            {
                "status": "success",
                "blocks": blocks,
                "total": len(active),
                "offset": offset,
                "limit": limit,
            }
        ), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/explorer/block/<identifier>", methods=["GET"])
def api_explorer_block(identifier: str):
    """Return a block by height or hash, including its transactions."""
    try:
        node = get_node()
        chain = node.chain

        block_hash = None
        # Numeric identifier -> treat as height
        if identifier.isdigit():
            target_height = int(identifier)
            for h in chain.active_chain():
                if chain.heights[h] == target_height:
                    block_hash = h
                    break
        elif identifier in chain.blocks:
            block_hash = identifier

        if block_hash is None:
            return jsonify(
                {"status": "error", "message": "Block not found"}
            ), 404

        summary = _block_summary(chain, block_hash)
        block = chain.blocks[block_hash]
        summary["transactions"] = [_tx_summary(tx) for tx in block.transactions]

        return jsonify({"status": "success", "block": summary}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/explorer/tx/<txid>", methods=["GET"])
def api_explorer_tx(txid: str):
    """Return a transaction by txid from the active chain or mempool."""
    try:
        node = get_node()
        chain = node.chain

        # Search the active chain (newest first)
        for block_hash in reversed(chain.active_chain()):
            block = chain.blocks[block_hash]
            for tx in block.transactions:
                if tx.txid == txid:
                    summary = _tx_summary(tx)
                    summary["status"] = "confirmed"
                    summary["block_hash"] = block_hash
                    summary["block_height"] = chain.heights[block_hash]
                    summary["confirmations"] = (
                        chain.height - chain.heights[block_hash] + 1
                    )
                    return jsonify({"status": "success", "transaction": summary}), 200

        # Search the mempool
        if txid in chain.mempool:
            summary = _tx_summary(chain.mempool[txid])
            summary["status"] = "pending"
            summary["confirmations"] = 0
            return jsonify({"status": "success", "transaction": summary}), 200

        return jsonify({"status": "error", "message": "Transaction not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/explorer/search", methods=["GET"])
def api_explorer_search():
    """Resolve a query to a block (by height/hash) or a transaction (by txid)."""
    try:
        node = get_node()
        chain = node.chain
        query = (request.args.get("q") or "").strip()

        if not query:
            return jsonify(
                {"status": "error", "message": "Empty search query"}
            ), 400

        # Height
        if query.isdigit():
            target_height = int(query)
            for h in chain.active_chain():
                if chain.heights[h] == target_height:
                    return jsonify(
                        {"status": "success", "kind": "block", "id": str(target_height)}
                    ), 200

        # Block hash
        if query in chain.blocks:
            return jsonify({"status": "success", "kind": "block", "id": query}), 200

        # Transaction (chain or mempool)
        for block_hash in reversed(chain.active_chain()):
            for tx in chain.blocks[block_hash].transactions:
                if tx.txid == query:
                    return jsonify(
                        {"status": "success", "kind": "tx", "id": query}
                    ), 200
        if query in chain.mempool:
            return jsonify({"status": "success", "kind": "tx", "id": query}), 200

        return jsonify(
            {"status": "error", "message": "No block or transaction matches that query"}
        ), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================= #
# Error Handlers
# ============================================================================= #


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"status": "error", "message": "Not found"}), 404


@app.errorhandler(413)
def payload_too_large(error):
    """Reject over-sized request bodies (see MAX_CONTENT_LENGTH) with clean JSON
    instead of buffering the payload."""
    return jsonify({"status": "error", "message": "Request body too large"}), 413


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors."""
    return jsonify({"status": "error", "message": "Internal server error"}), 500


# ============================================================================= #
# CORS Headers — allow-listed origins only (no wildcard)
#
# Same-origin requests (the dashboard calling its own API) never need these
# headers. This only scopes *cross-origin* access. Because the write APIs
# consume application/json, browsers send a CORS preflight; refusing unknown
# origins here blocks cross-site reads and cross-origin forged writes.
# ============================================================================= #

_DEFAULT_ALLOWED_ORIGINS = {
    "https://moonbite.org",
    "https://www.moonbite.org",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
}
# Override/extend via ALLOWED_ORIGINS="https://a.example,https://b.example".
ALLOWED_ORIGINS = {
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
} or _DEFAULT_ALLOWED_ORIGINS


@app.after_request
def add_cors_headers(response):
    """Reflect CORS headers only for allow-listed origins — never a wildcard."""
    origin = request.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# CSP is intentionally conservative: the site serves all scripts/styles from its
# own origin but uses a few inline <script>/<style> blocks (theme + reveal), so
# script/style allow 'unsafe-inline'. Everything else is locked to 'self', no
# framing, no plugins. Tightening to nonces is future work (see AUDIT_REPORT.md).
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


@app.after_request
def add_security_headers(response):
    """Baseline hardening headers on every response (see AUDIT_REPORT.md #4).

    HSTS defends against SSL-strip downgrade; nosniff blocks MIME confusion;
    frame-ancestors/X-Frame-Options stop clickjacking; Referrer-Policy limits
    leakage. Safe to also set at the nginx edge — duplicates are harmless."""
    response.headers.setdefault(
        "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Content-Security-Policy", _CSP)
    return response


# ============================================================================= #
# App Initialization
# ============================================================================= #


if __name__ == "__main__":
    # Initialize the node on startup
    get_node()
    # Production deploys run this under gunicorn (web_app:app) and never reach
    # this block. When launched directly, honor the environment so the same
    # file works locally (defaults) and on a server/PaaS (PORT/HOST/FLASK_DEBUG).
    host = os.environ.get("HOST", "localhost")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print(f"MoonBite Dashboard starting on http://{host}:{port}")
    app.run(debug=debug, host=host, port=port)
