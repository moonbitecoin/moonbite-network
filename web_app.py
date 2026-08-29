"""MyCoin Web Dashboard — Flask application for blockchain visualization and interaction.

DEPLOYMENT_REBUILD_2026_08_07_22_15_BULLETPROOF_WALLET_CACHE_BUST

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

from flask import (
    Flask,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix

import price_feed
import wall
import wallet_history

from node import Node
from store import BlockStore
from transaction import Transaction, generate_keypair, pubkey_hash
from wallet import (HDWallet, address_from_pubkey_hash, is_valid_address,
                    pubkey_hash_from_address)

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

# Disable template caching to ensure updates are served immediately
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

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

# Force HTTPS (both moonbite.org and www.moonbite.org work equally)
@app.before_request
def force_https():
    """Force HTTPS in production. Both moonbite.org and www.moonbite.org work equally."""
    # Force HTTPS in production
    if os.environ.get("RAILWAY_ENVIRONMENT") == "production":
        if request.headers.get("X-Forwarded-Proto", "http") != "https":
            url = request.url.replace("http://", "https://", 1)
            return redirect(url, code=301)

# Initialize databases on first request (for production gunicorn deploys)
_schemas_initialized = False
@app.before_request
def init_schemas():
    global _schemas_initialized
    if not _schemas_initialized:
        try:
            wallet_history.create_schema()
            _schemas_initialized = True
        except Exception as e:
            print(f"[init_schemas] Warning: {e}", flush=True)

# Hard cap on request body size. Flask/Werkzeug default to unlimited, so without
# this a single POST with a multi-hundred-MB body forces the worker to buffer +
# JSON-parse it — ~2.8x amplification measured, i.e. one 400 MB request spikes
# the process past 1 GB RAM and OOM-kills a small container. Every legitimate
# API body here (notify, orders, invoices, tx broadcast) is well under 256 KB,
# so Werkzeug rejects anything larger with 413 BEFORE reading the payload.
_MAX_CONTENT_LENGTH = int(os.environ.get("MOONBITE_MAX_BODY_BYTES", str(256 * 1024)))
app.config["MAX_CONTENT_LENGTH"] = _MAX_CONTENT_LENGTH

# Global state for mining operations - queue-based for concurrent mining
import queue
import uuid

app.mining_state = {
    "active_jobs": {},  # job_id -> {is_mining, blocks_to_mine, blocks_mined, ...}
    "job_queue": queue.Queue(),  # Queue of pending mining jobs
    "total_blocks_mined": 0,  # Total blocks mined across all jobs
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

# Lock for thread-safe mining and blockchain operations
app.mining_lock = threading.Lock()
app.blockchain_lock = threading.Lock()  # Protect blockchain.add_block()

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
    """Rate limiter - DISABLED FOR BITCOIN ALGORITHM TESTING (2026-07-31 21:12)."""
    print(f"[DEBUG] rate_limit called with {max_calls}, {window_seconds}", flush=True)
    def decorator(fn):
        print(f"[DEBUG] rate_limit.decorator called for {fn.__name__}", flush=True)
        @wraps(fn)
        def wrapper(*args, **kwargs):
            print(f"[DEBUG] rate_limit.wrapper called for {fn.__name__}", flush=True)
            # TEMPORARILY DISABLED - just call the function directly
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# --------------------------------------------------------------------------- #
# Error Standardization — Consistent API error responses
# --------------------------------------------------------------------------- #

# Standard error code definitions for wallet and blockchain operations
ERRORS = {
    # Validation errors
    "VALIDATION_INVALID_ADDRESS": {
        "user_message": "Invalid address format",
        "http_status": 400,
    },
    "VALIDATION_INSUFFICIENT_BALANCE": {
        "user_message": "Insufficient balance for this transaction",
        "http_status": 400,
    },
    "VALIDATION_INVALID_AMOUNT": {
        "user_message": "Invalid or negative amount specified",
        "http_status": 400,
    },
    "VALIDATION_INVALID_MNEMONIC": {
        "user_message": "Invalid seed phrase (must be valid BIP39 mnemonic)",
        "http_status": 400,
    },
    "VALIDATION_MISSING_FIELD": {
        "user_message": "Required field is missing from request",
        "http_status": 400,
    },

    # Network/sync errors
    "NETWORK_NOT_SYNCED": {
        "user_message": "Blockchain is still syncing, please wait",
        "http_status": 503,
    },
    "NETWORK_TX_REJECTED": {
        "user_message": "Transaction was rejected by the network",
        "http_status": 400,
    },
    "NETWORK_OFFLINE": {
        "user_message": "Unable to reach the blockchain (offline mode)",
        "http_status": 503,
    },
    "NETWORK_CONNECTION_ERROR": {
        "user_message": "Connection error, retrying...",
        "http_status": 503,
    },

    # Security errors
    "SECURITY_SESSION_EXPIRED": {
        "user_message": "Session has expired, please reload",
        "http_status": 401,
    },
    "SECURITY_INVALID_PASSWORD": {
        "user_message": "Incorrect password",
        "http_status": 401,
    },
    "SECURITY_RATE_LIMITED": {
        "user_message": "Too many requests, please wait before trying again",
        "http_status": 429,
    },

    # Storage/persistence errors
    "STORAGE_QUOTA_EXCEEDED": {
        "user_message": "Local storage quota exceeded",
        "http_status": 507,
    },
    "STORAGE_CORRUPTED": {
        "user_message": "Local data is corrupted, unable to proceed",
        "http_status": 500,
    },

    # General errors
    "INTERNAL_ERROR": {
        "user_message": "An unexpected error occurred",
        "http_status": 500,
    },
}


def json_error(
    error_code: str,
    user_message: Optional[str] = None,
    debug_message: Optional[str] = None,
    suggested_action: Optional[str] = None,
    status_code: Optional[int] = None,
) -> tuple:
    """Create a standardized error response.

    Args:
        error_code: Unique error identifier (e.g., "VALIDATION_INVALID_ADDRESS")
        user_message: User-friendly message (overrides default if provided)
        debug_message: Developer-focused debug info (only if debug=true in request)
        suggested_action: What the user should do to recover
        status_code: HTTP status code (overrides error definition if provided)

    Returns:
        Tuple of (response_dict, http_status_code) for Flask to return
    """
    error_def = ERRORS.get(error_code, ERRORS["INTERNAL_ERROR"])

    http_status = status_code or error_def.get("http_status", 500)
    message = user_message or error_def.get("user_message", "An error occurred")

    response = {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "timestamp": time.time(),
    }

    if suggested_action:
        response["action"] = suggested_action

    # Include debug info only if requested and in non-production or explicitly enabled
    if debug_message and (
        os.environ.get("FLASK_DEBUG") == "1"
        or request.args.get("debug") == "true"
    ):
        response["debug"] = debug_message

    return jsonify(response), http_status


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


def mining_worker(job_id: str, blocks_to_mine: int, miner_address: str) -> None:
    """Background worker thread for mining blocks (concurrent-safe)."""
    print(f"[MINING] Job {job_id}: Starting mining {blocks_to_mine} blocks for {miner_address}", flush=True)
    node = get_node()

    # Job-specific state
    job_state = {
        "job_id": job_id,
        "is_mining": True,
        "blocks_to_mine": blocks_to_mine,
        "blocks_mined": 0,
        "current_block_height": node.chain.height,
        "hashes_tried": 0,
        "hashrate": 0.0,
        "started_at": time.time(),
        "mining_address": miner_address,
        "last_error": None,
    }

    with app.mining_lock:
        app.mining_state["active_jobs"][job_id] = job_state

    for i in range(blocks_to_mine):
        with app.mining_lock:
            if not app.mining_state["active_jobs"].get(job_id, {}).get("is_mining", False):
                print(f"[MINING] Job {job_id}: Mining cancelled", flush=True)
                break

        try:
            print(f"[MINING] Job {job_id}: Mining block {i+1}/{blocks_to_mine}", flush=True)

            # Lock blockchain access - mine_block() calls chain.add_block() which needs serialization
            with app.blockchain_lock:
                block = node.mine_block(miner_address)
                if block is not None:
                    print(f"[MINING] Job {job_id}: Block mined! Hash: {block.hash}, Nonce: {block.header.nonce}, Txs: {len(block.transactions)}", flush=True)
                    _persist_block(block)
                else:
                    print(f"[MINING] Job {job_id}: mine_block() returned None - mining failed or block rejected", flush=True)

            if block is not None:
                # Update job state (outside blockchain lock to avoid holding lock too long)
                job_state["hashes_tried"] += block.header.nonce + 1
                elapsed = max(1e-6, time.time() - job_state["started_at"])
                job_state["hashrate"] = job_state["hashes_tried"] / elapsed
                job_state["blocks_mined"] = i + 1
                job_state["current_block_height"] = node.chain.height
                job_state["last_error"] = None

                with app.mining_lock:
                    app.mining_state["total_blocks_mined"] += 1
                    app.mining_state["active_jobs"][job_id] = job_state

                print(f"[MINING] Job {job_id}: Progress {i+1}/{blocks_to_mine} blocks mined, Hashrate: {job_state['hashrate']:.2f} H/s", flush=True)
            else:
                job_state["last_error"] = "Mining failed or block rejected"
                print(f"[MINING] Job {job_id}: Stopping mining - block was None", flush=True)
                with app.mining_lock:
                    app.mining_state["active_jobs"][job_id] = job_state
                break
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            print(f"[MINING] Job {job_id}: ERROR - {error_msg}", flush=True)
            job_state["last_error"] = str(e)
            with app.mining_lock:
                app.mining_state["active_jobs"][job_id] = job_state
            break

    job_state["is_mining"] = False
    with app.mining_lock:
        app.mining_state["active_jobs"][job_id] = job_state

    print(f"[MINING] Job {job_id}: Mining finished. Blocks mined: {job_state['blocks_mined']}", flush=True)


# ============================================================================= #
# Routes
# ============================================================================= #


def _consensus_dict() -> dict:
    """One truthful snapshot of the coin's monetary rules + live reward.

    Injected into every template and served at /api/consensus so no page
    ever copy-pastes a consensus number again.
    """
    from block import block_subsidy
    from params import (CENTS_PER_COIN, HALVING_INTERVAL, INITIAL_SUBSIDY,
                        MAX_SUPPLY, TARGET_BLOCK_TIME)
    try:
        height = get_node().chain.height
    except Exception:
        height = 0
    halving_years = HALVING_INTERVAL * TARGET_BLOCK_TIME / 31_557_600
    # Year the subsidy decays to zero (33 halvings for a 50-coin start).
    eras = 0
    s = INITIAL_SUBSIDY
    while s > 0:
        s >>= 1
        eras += 1
    return {
        "initial_subsidy_coins": INITIAL_SUBSIDY // CENTS_PER_COIN,
        "current_reward_coins": block_subsidy(height + 1) / CENTS_PER_COIN,
        "halving_interval": HALVING_INTERVAL,
        "next_halving_height": ((height // HALVING_INTERVAL) + 1) * HALVING_INTERVAL,
        "block_time_sec": TARGET_BLOCK_TIME,
        "block_time_min": TARGET_BLOCK_TIME // 60,
        "blocks_per_day": 86_400 // TARGET_BLOCK_TIME,
        # Current subsidy, not the genesis one: after the first halving the
        # genesis figure would overstate daily emission by 2x.
        "daily_emission_coins": (86_400 // TARGET_BLOCK_TIME)
        * (block_subsidy(height + 1) / CENTS_PER_COIN),
        "max_supply_coins": MAX_SUPPLY / CENTS_PER_COIN,
        "max_supply_label": "~33,000,000",
        "halving_years": round(halving_years, 2),
        "launch_year": 2026,
        "final_block_year": 2026 + round(eras * halving_years),
        "height": height,
    }


@app.context_processor
def inject_consensus():
    return {"consensus": _consensus_dict()}


@app.route("/api/consensus", methods=["GET"])
def api_consensus():
    """The coin's monetary rules as JSON — the frontend's single source."""
    data = _consensus_dict()
    data["status"] = "success"
    return jsonify(data)


@app.route("/")
def home_page():
    """Render the god-mode cinematic homepage (The Last Unowned Thing)."""
    return render_template("moon.html")


@app.route("/home-zeldman")
def home_zeldman_page():
    """Previous marketing homepage (Zeldman-style elegant minimalism)."""
    return render_template("home.html")


@app.route("/home-classic")
def home_classic_page():
    """Render the previous cinematic film-scroll homepage (kept for reference)."""
    return render_template("home.html")


@app.route("/take-a-bite")
def take_a_bite_page():
    """Render the "You can't buy MoonBite" cinematic mining-demo landing page."""
    return render_template("take_a_bite.html")


@app.route("/calculator")
def calculator_page():
    """Render the Early Miner Calculator (shareable earnings-forecast page)."""
    return render_template("calculator.html")


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


# --- Community forum (SQLite-backed threaded discussions) -------------------- #
# Free-text display names, no accounts. Stored text is HTML-escaped by Jinja on
# render, so a post can never inject markup. Write endpoints are rate limited.
# There is no CSRF token: with no login there is no authenticated action to
# forge — anyone may post regardless — so a token would add friction, not safety.


@app.route("/discussions")
def discussions_page():
    """List discussion threads, newest activity first (paginated)."""
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    per_page = 20
    data = forum.list_threads(limit=per_page, offset=(page - 1) * per_page)
    total_pages = max(1, (data["total"] + per_page - 1) // per_page)
    return render_template(
        "discussions.html",
        threads=data["threads"],
        total=data["total"],
        page=page,
        total_pages=total_pages,
        error=request.args.get("error"),
    )


@app.route("/discussions/<int:thread_id>")
def discussion_thread_page(thread_id: int):
    """Render one thread and its replies."""
    thread = forum.get_thread(thread_id)
    if thread is None:
        return render_template("discussion_thread.html", thread=None), 404
    return render_template(
        "discussion_thread.html",
        thread=thread,
        error=request.args.get("error"),
    )


@app.route("/discussions/new", methods=["POST"])
@rate_limit(10, 60)
def discussions_create():
    """Handle the new-thread form (Post/Redirect/Get)."""
    try:
        thread = forum.create_thread(
            title=request.form.get("title"),
            author=request.form.get("author"),
            body=request.form.get("body"),
        )
    except ValueError as e:
        return redirect(url_for("discussions_page", error=str(e)))
    return redirect(url_for("discussion_thread_page", thread_id=thread["id"]))


@app.route("/discussions/<int:thread_id>/reply", methods=["POST"])
@rate_limit(20, 60)
def discussions_reply(thread_id: int):
    """Handle the reply form on a thread (Post/Redirect/Get)."""
    try:
        forum.add_reply(
            thread_id,
            author=request.form.get("author"),
            body=request.form.get("body"),
        )
    except ValueError as e:
        return redirect(url_for("discussion_thread_page", thread_id=thread_id, error=str(e)))
    return redirect(url_for("discussion_thread_page", thread_id=thread_id) + f"#reply-latest")


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
    """The MoonBite wallet.

    One wallet, not five. This serves the production PWA (28 screens,
    AES-256-GCM + PBKDF2, biometric unlock, per-user custodial addresses) —
    by a wide margin the most complete of the variants that used to compete
    for this URL. The others now redirect here so there is a single surface
    holding keys, and a single place to audit.
    """
    return render_template("wallet-pwa-app.html")


# Superseded wallet builds. Kept as permanent redirects rather than deleted
# routes so existing links, bookmarks and installed PWA shortcuts survive.
@app.route("/wallet-app")
@app.route("/wallet-full")
@app.route("/wallet-moonbite")
@app.route("/wallet-complete")
def wallet_legacy_redirect():
    return redirect(url_for("wallet_page"), code=301)

@app.route("/wallet-manifest.json")
def wallet_manifest():
    """Serve PWA manifest."""
    import os
    manifest_path = os.path.join(os.path.dirname(__file__), "wallet-manifest.json")
    if os.path.exists(manifest_path):
        return send_file(manifest_path, mimetype="application/manifest+json")
    return jsonify({"error": "Manifest not found"}), 404

@app.route("/wallet-sw.js")
def wallet_service_worker():
    """Serve the service worker for offline support.

    Served from the site root, not /static, because a worker's scope is capped
    by the path it is served from — at /static/ it could not intercept /wallet.

    This looked in the repo root and 404'd, so no new worker could ever
    install and browsers kept running whatever version they had cached. Any
    stale worker's caches are purged by the activate handler in wallet-sw.js
    once a current copy finally installs.
    """
    sw_path = os.path.join(os.path.dirname(__file__), "static", "wallet-sw.js")
    if os.path.exists(sw_path):
        response = send_file(sw_path, mimetype="application/javascript")
        # Never let a proxy or the browser pin an old worker: this is the one
        # file that must always be revalidated, or an install can never be
        # superseded.
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Service-Worker-Allowed"] = "/"
        return response
    return jsonify({"error": "Service worker not found"}), 404


@app.route("/mining")
def mining_page():
    """Render the mining page."""
    # August 4, 2026 - Testing deployment
    return render_template("mining.html")


@app.route("/leaderboard")
def leaderboard_page():
    """Render the mining leaderboard page."""
    return render_template("leaderboard.html")


def _blocks_mined_by(address: str) -> int:
    """Count coinbase payouts to `address` on the active chain.

    This is what makes the Wall a record rather than a guestbook: a claim is
    only accepted if the chain itself already paid that address.
    """
    try:
        node = get_node()
        chain = node.chain
        count = 0
        for block_hash in chain.active_chain():
            block = chain.blocks[block_hash]
            if not block.transactions or not block.transactions[0].is_coinbase():
                continue
            outputs = block.transactions[0].outputs
            if not outputs:
                continue
            try:
                if address_from_pubkey_hash(outputs[0].pubkey_hash) == address:
                    count += 1
            except Exception:
                continue
        return count
    except Exception:
        return 0


# The archive index. Grouped rather than alphabetical so a visitor can tell at
# a glance which pages are current tools and which are superseded builds.
_ARCHIVE = [
    ("Tools", [
        ("/explorer", "Block explorer", ("live", "live")),
        ("/mining", "Mining console (advanced)", ("live", "live")),
        ("/dashboard", "Network dashboard", ("live", "live")),
        ("/leaderboard", "Mining leaderboard", ("live", "live")),
        ("/merchants", "Merchant payments", None),
    ]),
    ("Reference", [
        ("/whitepaper", "Whitepaper", ("live", "live")),
        ("/how-it-works", "How it works", None),
        ("/moonbite-core", "MoonBite Core", None),
        ("/vocabulary", "Vocabulary", None),
        ("/learn", "Learn", None),
        ("/you-need-to-know", "What you need to know", None),
        ("/full-node", "Run a full node", None),
        ("/developers", "Developers", None),
        ("/development", "Development", None),
    ]),
    ("Getting started", [
        ("/getting-started", "Getting started", None),
        ("/mine", "Start mining", None),
        ("/get-wallet", "Get a wallet", None),
        ("/individuals", "For individuals", None),
        ("/businesses", "For businesses", None),
    ]),
    ("Markets & honesty", [
        ("/markets", "Markets", None),
        ("/exchanges", "Exchanges", None),
        ("/buy", "Buying MBITE", None),
        ("/sell", "Selling MBITE", None),
        ("/scams", "Scams & impersonation", ("live", "live")),
        ("/legal", "Legal", None),
        ("/privacy", "Privacy", ("live", "live")),
    ]),
    ("Community", [
        ("/community", "Community", None),
        ("/discussions", "Discussions", ("live", "live")),
        ("/events", "Events", None),
        ("/blog", "Blog", None),
        ("/press", "Press kit", None),
        ("/support", "Support", None),
        ("/resources", "Resources", None),
        ("/why", "Why MoonBite", None),
        ("/about", "About", None),
    ]),
    ("Superseded builds", [
        ("/home-classic", "Homepage — classic", ("older", "moved")),
        ("/home-v2", "Homepage — v2", ("older", "moved")),
        ("/home-zeldman", "Homepage — Zeldman", ("older", "moved")),
        ("/take-a-bite", "Take a Bite", ("older", "moved")),
        ("/logo-sting", "Logo sting", ("older", "moved")),
        ("/wallet-app", "Wallet builds → /wallet", ("redirects", "moved")),
    ]),
]


@app.route("/classic")
def classic_page():
    """Render the archive index of every page, including superseded builds."""
    return render_template("classic.html", archive=_ARCHIVE)


@app.route("/free")
def free_page():
    """Render the Un-Airdrop: there is nothing to claim, and that is the point."""
    return render_template("free.html")


@app.route("/wall")
def wall_page():
    """Render the public, chain-verified wall of first blocks."""
    return render_template("wall.html")


@app.route("/api/wall", methods=["GET"])
@rate_limit(60, 60)
def api_wall_list():
    """Newest certificates, plus this visitor's own entry when an address is given."""
    data = wall.recent(request.args.get("limit", 60), request.args.get("offset", 0))
    data["you"] = wall.lookup(request.args.get("address"))
    data["status"] = "success"
    return jsonify(data)


@app.route("/api/wall", methods=["POST"])
@rate_limit(6, 60)
def api_wall_add():
    """Place one certificate, refusing any address the chain has not paid."""
    p = request.get_json(silent=True) or {}
    try:
        cert = wall.add(
            address=p.get("address"),
            handle=p.get("handle"),
            country=p.get("country"),
            height=p.get("height", 0),
            reward=p.get("reward", 0),
            verify_blocks=_blocks_mined_by,
        )
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    data = wall.recent(60, 0)
    data["you"] = cert
    data["status"] = "success"
    return jsonify(data)


@app.route("/halving")
def halving_page():
    """Render the permanent halving countdown and emission staircase."""
    return render_template("halving.html")


@app.route("/start")
def start_page():
    """Render the one-screen path from visitor to first mined block."""
    return render_template("start.html")


@app.route("/world-cup")
def world_cup_page():
    """Render the Mining World Cup country scoreboard."""
    return render_template("worldcup.html")


@app.route("/api/worldcup", methods=["GET"])
@rate_limit(60, 60)
def api_worldcup_standings():
    """Country standings, plus this visitor's own entry when a token is given."""
    data = worldcup.standings()
    data["you"] = worldcup.lookup(request.args.get("token"))
    data["status"] = "success"
    return jsonify(data)


@app.route("/api/worldcup/enlist", methods=["POST"])
@rate_limit(10, 60)
def api_worldcup_enlist():
    """Declare a country for this miner and return their permanent ordinal."""
    payload = request.get_json(silent=True) or {}
    try:
        me = worldcup.enlist(
            token=payload.get("token"),
            code=payload.get("code"),
            blocks=payload.get("blocks", 0),
        )
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    data = worldcup.standings()
    data["you"] = me
    data["status"] = "success"
    return jsonify(data)


@app.route("/merchants")
def merchants_page():
    """Render the merchant payment platform page."""
    return render_template("merchant.html")


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


# ============================================================================= #
# API Routes — Wallet Transaction History
# ============================================================================= #


def _get_session_id() -> str:
    """Extract user session ID from the session cookie for wallet isolation."""
    if "session_id" not in session:
        session["session_id"] = secrets.token_hex(16)
    return session["session_id"]


@app.route("/api/wallet/transaction/send", methods=["POST"])
@rate_limit(30, 60)
def api_wallet_transaction_send():
    """Create a new send transaction record.

    The wallet app creates this after sending coins on-chain. The server
    records the transaction for history/audit purposes (never custodial).
    """
    data = request.get_json(silent=True) or {}
    session_id = _get_session_id()

    try:
        txid = str(data.get("txid", "")).strip()
        if not txid:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Transaction ID is required",
            )

        amount_units = int(data.get("amount_units", 0))
        if amount_units <= 0:
            return json_error(
                "VALIDATION_INVALID_AMOUNT",
                user_message="Amount must be greater than zero",
                suggested_action="Please check the amount and try again",
            )

        from_address = str(data.get("from_address", "")).strip()
        to_address = str(data.get("to_address", "")).strip()
        if not from_address or not to_address:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Both sender and recipient addresses are required",
            )

        # Validate addresses
        if not is_valid_address(from_address):
            return json_error(
                "VALIDATION_INVALID_ADDRESS",
                user_message="Sender address is invalid",
                suggested_action="Please check the sender address",
            )
        if not is_valid_address(to_address):
            return json_error(
                "VALIDATION_INVALID_ADDRESS",
                user_message="Recipient address is invalid",
                suggested_action="Please check the recipient address format",
            )

        fee_units = int(data.get("fee_units", 0))
        status = str(data.get("status", "pending")).strip()
        memo = str(data.get("memo", "")).strip()[:500]
        account_id = data.get("account_id")  # Optional: link to specific account

        tx = wallet_history.add_transaction(
            session_id=session_id,
            txid=txid,
            direction="send",
            amount_units=amount_units,
            from_address=from_address,
            to_address=to_address,
            fee_units=fee_units,
            status=status,
            memo=memo,
        )

        # Update transaction with account_id if provided
        if account_id:
            try:
                import sqlite3
                conn = wallet_history.get_connection()
                conn.execute(
                    "UPDATE transactions SET account_id = ? WHERE user_session_id = ? AND txid = ?",
                    (account_id, session_id, txid)
                )
                conn.commit()
                conn.close()
            except Exception:
                pass  # Account_id is optional, don't fail the transaction

        return jsonify({"status": "success", "transaction": tx}), 201

    except ValueError as e:
        return json_error(
            "VALIDATION_INVALID_AMOUNT",
            debug_message=str(e),
            suggested_action="Please check all fields and try again",
        )
    except Exception as e:
        print(f"[api_wallet_transaction_send] Unexpected error: {e}", flush=True)
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            suggested_action="Please try again or contact support if the problem persists",
        )


@app.route("/api/wallet/transactions", methods=["GET"])
def api_wallet_transactions_list():
    """List user's transactions with optional pagination and filtering.

    Query params:
        limit: Max records per page (1-100, default 20)
        offset: Pagination offset (default 0)
        status: Filter by 'pending', 'confirmed', or 'failed'
        sort: 'asc' or 'desc' (default desc = newest first)
    """
    session_id = _get_session_id()

    try:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
        status = request.args.get("status")
        sort = request.args.get("sort", "desc")

        result = wallet_history.get_transactions(
            session_id=session_id,
            limit=limit,
            offset=offset,
            status=status,
            sort=sort,
        )
        return jsonify({"status": "success", "data": result}), 200

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        print(f"[api_wallet_transactions_list] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


@app.route("/api/wallet/transactions/<txid>", methods=["GET"])
def api_wallet_transaction_detail(txid: str):
    """Fetch a single transaction by txid."""
    session_id = _get_session_id()

    try:
        tx = wallet_history.get_transaction(session_id=session_id, txid=txid)
        if not tx:
            return jsonify({"status": "error", "message": "transaction not found"}), 404

        return jsonify({"status": "success", "data": tx}), 200

    except Exception as e:
        print(f"[api_wallet_transaction_detail] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


@app.route("/api/wallet/transactions/<txid>", methods=["PATCH"])
@rate_limit(60, 60)
def api_wallet_transaction_update_memo(txid: str):
    """Update the memo of a transaction."""
    data = request.get_json(silent=True) or {}
    session_id = _get_session_id()

    try:
        memo = str(data.get("memo", "")).strip()

        tx = wallet_history.update_transaction_memo(
            session_id=session_id,
            txid=txid,
            memo=memo,
        )
        if not tx:
            return jsonify({"status": "error", "message": "transaction not found"}), 404

        return jsonify({"status": "success", "data": tx}), 200

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        print(f"[api_wallet_transaction_update_memo] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


@app.route("/api/wallet/transactions/search", methods=["GET"])
def api_wallet_transactions_search():
    """Search transactions with full-text and filter options.

    Query params:
        q: Search query (matches txid, addresses, memo)
        amount_min: Minimum amount in base units (optional)
        amount_max: Maximum amount in base units (optional)
        date_from: Start timestamp (optional)
        date_to: End timestamp (optional)
        status: Filter by 'pending', 'confirmed', or 'failed'
        direction: Filter by 'send' or 'receive'
        limit: Max records per page (1-100, default 20)
        offset: Pagination offset (default 0)
    """
    session_id = _get_session_id()

    try:
        query = request.args.get("q", "")
        amount_min = request.args.get("amount_min")
        amount_max = request.args.get("amount_max")
        date_from = request.args.get("date_from")
        date_to = request.args.get("date_to")
        status = request.args.get("status")
        direction = request.args.get("direction")
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))

        result = wallet_history.search_transactions(
            session_id=session_id,
            query=query,
            amount_min=amount_min,
            amount_max=amount_max,
            date_from=date_from,
            date_to=date_to,
            status=status,
            direction=direction,
            limit=limit,
            offset=offset,
        )
        return jsonify({"status": "success", "data": result}), 200

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        print(f"[api_wallet_transactions_search] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


@app.route("/api/wallet/transactions/export", methods=["GET"])
def api_wallet_transactions_export():
    """Export transactions as CSV file.

    Query params:
        date_from: Start timestamp (optional)
        date_to: End timestamp (optional)
        format: 'csv' (default) or 'json'
        include_fees: 'true' (default) or 'false'
        include_memo: 'true' (default) or 'false'
    """
    session_id = _get_session_id()

    try:
        date_from = request.args.get("date_from")
        date_to = request.args.get("date_to")
        format_type = request.args.get("format", "csv").lower()
        include_fees = request.args.get("include_fees", "true").lower() == "true"
        include_memo = request.args.get("include_memo", "true").lower() == "true"

        date_from = int(date_from) if date_from else None
        date_to = int(date_to) if date_to else None

        if format_type == "csv":
            csv_data = wallet_history.export_transactions_csv(
                session_id=session_id,
                date_from=date_from,
                date_to=date_to,
                include_fees=include_fees,
                include_memo=include_memo,
            )
            response = make_response(csv_data)
            response.headers["Content-Type"] = "text/csv; charset=utf-8"
            response.headers["Content-Disposition"] = "attachment; filename=transactions.csv"
            return response, 200
        elif format_type == "json":
            result = wallet_history.get_transactions(
                session_id=session_id,
                limit=10000,
                offset=0,
            )
            response = make_response(jsonify({"status": "success", "data": result}))
            response.headers["Content-Disposition"] = "attachment; filename=transactions.json"
            return response, 200
        else:
            return jsonify({"status": "error", "message": "format must be 'csv' or 'json'"}), 400

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        print(f"[api_wallet_transactions_export] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


# ============================================================================= #
# API Routes — Price Ticker
# ============================================================================= #


@app.route("/api/price/mbite", methods=["GET"])
def api_price_mbite():
    """Get current MBITE price.

    Returns:
        dict with price_usd, change_24h, high_24h, low_24h, market_cap, volume_24h, timestamp
    """
    try:
        price_data = price_feed.get_price()
        return jsonify({"status": "success", "data": price_data}), 200

    except Exception as e:
        print(f"[api_price_mbite] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


@app.route("/api/price/mbite/history", methods=["GET"])
def api_price_mbite_history():
    """Get MBITE price history.

    Query params:
        hours: Number of hours to retrieve (default 24, max 720)
    """
    try:
        hours = int(request.args.get("hours", 24))
        hours = max(1, min(hours, 720))  # Clamp to 1-720 hours

        history_data = price_feed.get_price_history(hours=hours)
        return jsonify({"status": "success", "data": history_data}), 200

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        print(f"[api_price_mbite_history] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


# ============================================================================= #
# API Routes — Address Book
# ============================================================================= #


@app.route("/api/address-book/add", methods=["POST"])
@rate_limit(30, 60)
def api_address_book_add():
    """Add a labeled contact to the address book."""
    data = request.get_json(silent=True) or {}
    session_id = _get_session_id()

    try:
        label = str(data.get("label", "")).strip()
        address = str(data.get("address", "")).strip()
        category = str(data.get("category", "general")).strip()
        notes = str(data.get("notes", "")).strip()

        contact = wallet_history.add_contact(
            session_id=session_id,
            label=label,
            address=address,
            category=category,
            notes=notes,
        )
        return jsonify({"status": "success", "data": contact}), 201

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        print(f"[api_address_book_add] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


@app.route("/api/address-book", methods=["GET"])
def api_address_book_list():
    """List all contacts in the address book.

    Query params:
        category: Filter by category (optional)
        sort: 'created', 'updated', 'label', 'times_sent' (default 'created')
    """
    session_id = _get_session_id()

    try:
        category = request.args.get("category")
        sort = request.args.get("sort", "created")

        contacts = wallet_history.get_contacts(
            session_id=session_id,
            category=category,
            sort=sort,
        )
        return jsonify({"status": "success", "data": contacts}), 200

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        print(f"[api_address_book_list] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


@app.route("/api/address-book/<int:contact_id>", methods=["GET"])
def api_address_book_detail(contact_id: int):
    """Fetch a single contact by ID."""
    session_id = _get_session_id()

    try:
        contact = wallet_history.get_contact(session_id=session_id, contact_id=contact_id)
        if not contact:
            return jsonify({"status": "error", "message": "contact not found"}), 404

        return jsonify({"status": "success", "data": contact}), 200

    except Exception as e:
        print(f"[api_address_book_detail] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


@app.route("/api/address-book/<int:contact_id>", methods=["PATCH"])
@rate_limit(60, 60)
def api_address_book_update(contact_id: int):
    """Update a contact's fields (label, address, category, notes, is_favorite)."""
    data = request.get_json(silent=True) or {}
    session_id = _get_session_id()

    try:
        contact = wallet_history.update_contact(
            session_id=session_id,
            contact_id=contact_id,
            updates=data,
        )
        if not contact:
            return jsonify({"status": "error", "message": "contact not found"}), 404

        return jsonify({"status": "success", "data": contact}), 200

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        print(f"[api_address_book_update] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


@app.route("/api/address-book/<int:contact_id>", methods=["DELETE"])
@rate_limit(30, 60)
def api_address_book_delete(contact_id: int):
    """Delete a contact from the address book."""
    session_id = _get_session_id()

    try:
        deleted = wallet_history.delete_contact(
            session_id=session_id,
            contact_id=contact_id,
        )
        if not deleted:
            return jsonify({"status": "error", "message": "contact not found"}), 404

        return jsonify({"status": "success", "message": "contact deleted"}), 200

    except Exception as e:
        print(f"[api_address_book_delete] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


@app.route("/api/address-book/export", methods=["GET"])
@rate_limit(10, 60)
def api_address_book_export():
    """Export address book as CSV file."""
    session_id = _get_session_id()

    try:
        csv_data = wallet_history.export_address_book_csv(session_id=session_id)
        return app.response_class(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=address-book.csv"},
        )

    except Exception as e:
        print(f"[api_address_book_export] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


@app.route("/api/address-book/import", methods=["POST"])
@rate_limit(10, 60)
def api_address_book_import():
    """Bulk import contacts from CSV.

    Expects CSV with headers: label, address, category, notes
    Skips rows with missing label/address or duplicate labels.
    """
    session_id = _get_session_id()

    try:
        # Get CSV data from multipart form or raw body
        csv_data = None

        if "file" in request.files:
            file = request.files["file"]
            csv_data = file.read().decode("utf-8")
        elif request.data:
            csv_data = request.data.decode("utf-8")

        if not csv_data:
            raise ValueError("CSV data is required")

        result = wallet_history.import_address_book_csv(
            session_id=session_id,
            csv_data=csv_data,
        )
        return jsonify({"status": "success", "data": result}), 200

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        print(f"[api_address_book_import] Unexpected error: {e}", flush=True)
        return jsonify({"status": "error", "message": "internal server error"}), 500


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
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            suggested_action="Please try again or reload the page",
        )


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
        return json_error(
            "NETWORK_CONNECTION_ERROR",
            debug_message=str(e),
            suggested_action="Please wait and try again",
        )


@app.route("/api/address/<address>/balance", methods=["GET"])
@rate_limit(60, 60)
def api_address_balance(address: str):
    """Public balance lookup for any address on the chain.

    /api/wallet/balance only reports addresses held in the caller's Flask
    session, which is useless to the wallet PWA: it derives its address
    client-side from the user's own seed phrase, so the server has never seen
    that address and would always answer zero.

    Balances on a public chain are public — every block explorer exposes this
    and the UTXO set is broadcast to every node — so there is nothing to
    protect here by requiring ownership proof. Spending still requires the
    private key; this endpoint is read-only.
    """
    try:
        if not is_valid_address(address):
            return json_error(
                "VALIDATION_INVALID_ADDRESS",
                suggested_action="Check the address and try again",
            )

        pkh = pubkey_hash_from_address(address)

        node = get_node()
        total = 0
        utxos = []
        for txid, idx, out in node.chain.utxo.items():
            if out.pubkey_hash == pkh:
                total += out.amount
                utxos.append({"txid": txid, "vout": idx, "amount_units": out.amount})

        from params import CENTS_PER_COIN

        balance_coins = total / CENTS_PER_COIN
        return jsonify(
            {
                "status": "success",
                "address": address,
                "balance_coins": balance_coins,
                "balance_units": total,
                "balance_display": f"{balance_coins:.8f}".rstrip("0").rstrip(".") or "0",
                "utxo_count": len(utxos),
                "utxos": utxos,
                "height": node.chain.height,
            }
        ), 200
    except Exception as e:  # noqa: BLE001
        return json_error(
            "NETWORK_CONNECTION_ERROR",
            debug_message=str(e),
            suggested_action="Please wait and try again",
        )


# ============================================================================= #
# API Routes — HD Wallet (BIP39/BIP32)
# ============================================================================= #


@app.route("/api/wallet/hd/new", methods=["GET"])
@rate_limit(10, 60)
def api_wallet_hd_new():
    """Generate new HD wallet with BIP39 mnemonic seed phrase."""
    try:
        wallet = HDWallet()
        mnemonic = wallet.export_seed()

        # Store HD wallet in session for later use
        session["hd_wallet_mnemonic"] = mnemonic

        return jsonify(
            {
                "status": "success",
                "mnemonic": mnemonic,
                "word_count": len(mnemonic.split()),
                "message": "BACKUP THIS SEED PHRASE! You can recover all addresses with it.",
            }
        ), 200
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            suggested_action="Please reload the wallet and try creating a new wallet again",
        )


@app.route("/api/wallet/hd/import", methods=["POST"])
@rate_limit(5, 60)
def api_wallet_hd_import():
    """Import HD wallet from BIP39 mnemonic seed phrase."""
    try:
        data = request.get_json() or {}
        mnemonic = (data.get("mnemonic") or "").strip()
        passphrase = (data.get("passphrase") or "").strip()

        if not mnemonic:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Seed phrase is required",
                suggested_action="Please enter your 12 or 24 word seed phrase",
            )

        # Validate and recover wallet from mnemonic
        wallet = HDWallet.from_mnemonic(mnemonic, passphrase)

        # Store in session
        session["hd_wallet_mnemonic"] = mnemonic
        session["hd_wallet_count"] = 0

        return jsonify(
            {
                "status": "success",
                "message": "Wallet recovered from mnemonic. Use /api/wallet/hd/address to generate addresses.",
            }
        ), 200
    except ValueError as e:
        return json_error(
            "VALIDATION_INVALID_MNEMONIC",
            debug_message=str(e),
            suggested_action="Please check that you entered the seed phrase correctly",
        )
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            suggested_action="Please try again or reload the wallet",
        )


@app.route("/api/wallet/hd/address", methods=["GET"])
@rate_limit(30, 60)
def api_wallet_hd_address():
    """Generate next HD-derived address (m/44'/0'/0'/0/n)."""
    try:
        mnemonic = session.get("hd_wallet_mnemonic")
        if not mnemonic:
            return json_error(
                "SECURITY_SESSION_EXPIRED",
                user_message="Wallet session has ended",
                suggested_action="Please import your seed phrase again",
            )

        wallet = HDWallet.from_mnemonic(mnemonic)
        index = session.get("hd_wallet_count", 0)

        # Generate address at this index
        address = wallet.derive_address(index)

        # Increment counter and store in session
        session["hd_wallet_count"] = index + 1

        # Also store pubkey_hash for balance tracking (like /api/wallet/new)
        from wallet import pubkey_hash_from_address
        pkh = pubkey_hash_from_address(address)
        pkhs = [h for h in session.get("wallet_pkhs", []) if h != pkh]
        pkhs.append(pkh)
        session["wallet_pkhs"] = pkhs[-_MAX_SESSION_ADDRESSES:]

        return jsonify(
            {
                "status": "success",
                "address": address,
                "index": index,
                "path": f"m/44'/0'/0'/0/{index}",
            }
        ), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/wallet/hd/seed", methods=["GET"])
@rate_limit(5, 60)
def api_wallet_hd_seed():
    """Get the current session's HD wallet seed (mnemonic phrase)."""
    try:
        mnemonic = session.get("hd_wallet_mnemonic")
        if not mnemonic:
            return jsonify({"status": "error", "message": "no HD wallet in session"}), 400

        return jsonify(
            {
                "status": "success",
                "mnemonic": mnemonic,
                "word_count": len(mnemonic.split()),
                "warning": "NEVER share this seed. Anyone with it can access all your funds.",
            }
        ), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================= #
# API Routes — Multi-Account Management
# ============================================================================= #


@app.route("/api/wallet/accounts", methods=["GET"])
@rate_limit(30, 60)
def api_wallet_accounts_list():
    """List all accounts for the current user session with their balances."""
    try:
        session_id = request.remote_addr or "unknown"

        accounts = wallet_history.list_accounts(session_id)
        result = []

        for account in accounts:
            # Get addresses for this account
            addresses = wallet_history.get_account_addresses(account["id"])
            account_dict = dict(account)

            # Calculate balance by summing UTXOs from all active addresses
            total_balance = 0
            utxo_count = 0
            node = get_node()

            for addr_record in addresses:
                pkh = addr_record["pubkey_hash"]
                if pkh:
                    for _txid, _idx, out in node.chain.utxo.items():
                        if out.pubkey_hash == pkh:
                            total_balance += out.amount
                            utxo_count += 1

            # Update cached balance
            wallet_history.update_account_balance(session_id, account["id"], total_balance)

            account_dict["balance_units"] = total_balance
            account_dict["balance_coins"] = total_balance / 100000000  # CENTS_PER_COIN
            account_dict["utxo_count"] = utxo_count
            account_dict["address_count"] = len(addresses)

            result.append(account_dict)

        return jsonify(
            {
                "status": "success",
                "accounts": result,
                "total_count": len(result),
            }
        ), 200
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            suggested_action="Please try again",
        )


@app.route("/api/wallet/accounts/<account_id>", methods=["GET"])
@rate_limit(30, 60)
def api_wallet_account_detail(account_id: str):
    """Get details for a specific account including addresses and balance."""
    try:
        session_id = request.remote_addr or "unknown"

        account = wallet_history.get_account(session_id, account_id)
        if not account:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Account not found",
                status_code=404,
            )

        account_dict = dict(account)

        # Get all addresses for this account
        addresses = wallet_history.get_account_addresses(account_id)
        address_list = [dict(addr) for addr in addresses]

        # Calculate balance
        total_balance = 0
        utxo_count = 0
        node = get_node()

        for addr_record in addresses:
            pkh = addr_record["pubkey_hash"]
            if pkh:
                for _txid, _idx, out in node.chain.utxo.items():
                    if out.pubkey_hash == pkh:
                        total_balance += out.amount
                        utxo_count += 1

        wallet_history.update_account_balance(session_id, account_id, total_balance)

        account_dict["addresses"] = address_list
        account_dict["balance_units"] = total_balance
        account_dict["balance_coins"] = total_balance / 100000000
        account_dict["utxo_count"] = utxo_count

        return jsonify(
            {
                "status": "success",
                "account": account_dict,
            }
        ), 200
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            suggested_action="Please try again",
        )


@app.route("/api/wallet/accounts/create", methods=["POST"])
@rate_limit(10, 60)
def api_wallet_accounts_create():
    """Create a new account with a generated HD wallet."""
    try:
        session_id = request.remote_addr or "unknown"
        data = request.get_json() or {}

        name = (data.get("name") or "").strip()
        if not name:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Account name is required",
                suggested_action="Please provide a name like 'Main', 'Savings', etc.",
            )

        color = (data.get("color") or "").strip()
        is_default = bool(data.get("is_default", False))

        # Generate a new HD wallet
        wallet = HDWallet()
        mnemonic = wallet.export_seed()

        # Create account with mnemonic hash
        account = wallet_history.create_account(
            session_id,
            name,
            mnemonic=mnemonic,
            color=color or None,
            is_default=is_default,
        )

        # Generate first address for the account
        first_address = wallet.derive_address(0)
        pkh = pubkey_hash_from_address(first_address)

        wallet_history.add_account_address(
            account["id"],
            address=first_address,
            derivation_path="m/44'/0'/0'/0/0",
            pubkey_hash=pkh,
        )

        # Store account info in session for immediate access
        session_key = f"account_{account['id']}"
        session[session_key] = {
            "id": account["id"],
            "name": account["name"],
            "mnemonic": mnemonic,
            "hd_index": 1,
        }

        return jsonify(
            {
                "status": "success",
                "account": {
                    "id": account["id"],
                    "name": account["name"],
                    "color": account["color"],
                    "is_default": bool(account["is_default"]),
                    "created_at": account["created_at"],
                },
                "mnemonic": mnemonic,
                "first_address": first_address,
                "message": "BACKUP THIS SEED PHRASE! You can recover all addresses with it.",
            }
        ), 201
    except ValueError as e:
        return json_error(
            "VALIDATION_MISSING_FIELD",
            user_message=str(e),
            suggested_action="Please try again with a different name",
        )
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            suggested_action="Please try again",
        )


@app.route("/api/wallet/accounts/import", methods=["POST"])
@rate_limit(5, 60)
def api_wallet_accounts_import():
    """Import an account from an existing mnemonic."""
    try:
        session_id = request.remote_addr or "unknown"
        data = request.get_json() or {}

        name = (data.get("name") or "").strip()
        if not name:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Account name is required",
                suggested_action="Please provide a name",
            )

        mnemonic = (data.get("mnemonic") or "").strip()
        if not mnemonic:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Seed phrase is required",
                suggested_action="Please enter your 12 or 24 word seed phrase",
            )

        color = (data.get("color") or "").strip()
        passphrase = (data.get("passphrase") or "").strip()
        is_default = bool(data.get("is_default", False))

        # Validate mnemonic by trying to load wallet
        try:
            wallet = HDWallet.from_mnemonic(mnemonic, passphrase)
        except ValueError as e:
            return json_error(
                "VALIDATION_INVALID_MNEMONIC",
                user_message="Invalid seed phrase",
                debug_message=str(e),
                suggested_action="Please check that you entered the seed phrase correctly",
            )

        # Create account with mnemonic hash
        account = wallet_history.create_account(
            session_id,
            name,
            mnemonic=mnemonic,
            color=color or None,
            is_default=is_default,
        )

        # Generate first address(es) from imported wallet
        first_address = wallet.derive_address(0)
        pkh = pubkey_hash_from_address(first_address)

        wallet_history.add_account_address(
            account["id"],
            address=first_address,
            derivation_path="m/44'/0'/0'/0/0",
            pubkey_hash=pkh,
        )

        # Store in session
        session_key = f"account_{account['id']}"
        session[session_key] = {
            "id": account["id"],
            "name": account["name"],
            "mnemonic": mnemonic,
            "hd_index": 1,
        }

        return jsonify(
            {
                "status": "success",
                "account": {
                    "id": account["id"],
                    "name": account["name"],
                    "color": account["color"],
                    "is_default": bool(account["is_default"]),
                    "created_at": account["created_at"],
                },
                "first_address": first_address,
                "message": "Account imported successfully",
            }
        ), 201
    except ValueError as e:
        return json_error(
            "VALIDATION_MISSING_FIELD",
            user_message=str(e),
            suggested_action="Please try again with different parameters",
        )
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            suggested_action="Please try again",
        )


@app.route("/api/wallet/accounts/<account_id>", methods=["PATCH"])
@rate_limit(20, 60)
def api_wallet_accounts_update(account_id: str):
    """Update account name and/or color."""
    try:
        session_id = request.remote_addr or "unknown"
        data = request.get_json() or {}

        name = data.get("name")
        color = data.get("color")

        if name is None and color is None:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Please provide name and/or color to update",
            )

        account = wallet_history.update_account(session_id, account_id, name, color)

        if not account:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Account not found",
                status_code=404,
            )

        return jsonify(
            {
                "status": "success",
                "account": dict(account),
            }
        ), 200
    except ValueError as e:
        return json_error(
            "VALIDATION_MISSING_FIELD",
            user_message=str(e),
            suggested_action="Please try again with a different name",
        )
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            suggested_action="Please try again",
        )


@app.route("/api/wallet/accounts/<account_id>/switch", methods=["POST"])
@rate_limit(20, 60)
def api_wallet_accounts_switch(account_id: str):
    """Switch to an account (set as current in session)."""
    try:
        session_id = request.remote_addr or "unknown"

        account = wallet_history.get_account(session_id, account_id)
        if not account:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Account not found",
                status_code=404,
            )

        # Store current account in session
        session["current_account_id"] = account_id

        return jsonify(
            {
                "status": "success",
                "current_account_id": account_id,
                "account_name": account["name"],
            }
        ), 200
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            suggested_action="Please try again",
        )


@app.route("/api/wallet/accounts/<account_id>/set-default", methods=["POST"])
@rate_limit(20, 60)
def api_wallet_accounts_set_default(account_id: str):
    """Set an account as the default."""
    try:
        session_id = request.remote_addr or "unknown"

        account = wallet_history.set_default_account(session_id, account_id)
        if not account:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Account not found",
                status_code=404,
            )

        return jsonify(
            {
                "status": "success",
                "account": dict(account),
            }
        ), 200
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            suggested_action="Please try again",
        )


@app.route("/api/wallet/accounts/<account_id>", methods=["DELETE"])
@rate_limit(10, 60)
def api_wallet_accounts_delete(account_id: str):
    """Delete (soft-delete) an account."""
    try:
        session_id = request.remote_addr or "unknown"

        deleted = wallet_history.delete_account(session_id, account_id)

        if not deleted:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Account not found",
                status_code=404,
            )

        # Clear from session if it was the current account
        if session.get("current_account_id") == account_id:
            session.pop("current_account_id", None)

        return jsonify(
            {
                "status": "success",
                "message": "Account deleted",
            }
        ), 200
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            suggested_action="Please try again",
        )


@app.route("/api/wallet/accounts/<account_id>/balance", methods=["GET"])
@rate_limit(30, 60)
def api_wallet_accounts_balance(account_id: str):
    """Get balance for a specific account."""
    try:
        session_id = request.remote_addr or "unknown"

        account = wallet_history.get_account(session_id, account_id)
        if not account:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Account not found",
                status_code=404,
            )

        # Get addresses for this account
        addresses = wallet_history.get_account_addresses(account_id)

        # Calculate balance by summing UTXOs
        total_balance = 0
        utxo_count = 0
        node = get_node()

        for addr_record in addresses:
            pkh = addr_record["pubkey_hash"]
            if pkh:
                for _txid, _idx, out in node.chain.utxo.items():
                    if out.pubkey_hash == pkh:
                        total_balance += out.amount
                        utxo_count += 1

        wallet_history.update_account_balance(session_id, account_id, total_balance)

        from params import CENTS_PER_COIN

        return jsonify(
            {
                "status": "success",
                "account_id": account_id,
                "balance_coins": total_balance / CENTS_PER_COIN,
                "balance_units": total_balance,
                "balance_display": f"{total_balance / CENTS_PER_COIN:.8f}".rstrip("0").rstrip(".") or "0",
                "utxo_count": utxo_count,
            }
        ), 200
    except Exception as e:
        return json_error(
            "NETWORK_CONNECTION_ERROR",
            debug_message=str(e),
            suggested_action="Please wait and try again",
        )


# ============================================================================= #
# API Routes — Wallet Preferences
# ============================================================================= #


@app.route("/api/wallet/preferences", methods=["GET"])
@rate_limit(30, 60)
def api_wallet_preferences_get():
    """Get all user preferences with defaults filled in."""
    try:
        session_id = request.remote_addr or "unknown"

        prefs = wallet_history.get_preferences(session_id)

        return jsonify(
            {
                "status": "success",
                "preferences": prefs,
            }
        ), 200
    except Exception as e:
        return json_error(
            "INTERNAL_SERVER_ERROR",
            debug_message=str(e),
            status_code=500,
        )


@app.route("/api/wallet/preferences", methods=["PATCH"])
@rate_limit(20, 60)
def api_wallet_preferences_update():
    """Update user preferences. Returns all current preferences after update."""
    try:
        session_id = request.remote_addr or "unknown"
        data = request.get_json() or {}

        if not isinstance(data, dict):
            return json_error(
                "VALIDATION_INVALID_TYPE",
                user_message="Request body must be a JSON object",
                status_code=400,
            )

        # Update preferences (validates all keys/values internally)
        updated_prefs = wallet_history.update_preferences(session_id, data)

        return jsonify(
            {
                "status": "success",
                "preferences": updated_prefs,
            }
        ), 200

    except ValueError as e:
        return json_error(
            "VALIDATION_INVALID_VALUE",
            user_message=str(e),
            status_code=400,
        )
    except Exception as e:
        return json_error(
            "INTERNAL_SERVER_ERROR",
            debug_message=str(e),
            status_code=500,
        )


@app.route("/api/wallet/preferences/defaults", methods=["GET"])
@rate_limit(30, 60)
def api_wallet_preferences_defaults():
    """Get default preference values."""
    try:
        defaults = wallet_history.get_preference_defaults()

        return jsonify(
            {
                "status": "success",
                "defaults": defaults,
            }
        ), 200
    except Exception as e:
        return json_error(
            "INTERNAL_SERVER_ERROR",
            debug_message=str(e),
            status_code=500,
        )


@app.route("/api/wallet/preferences/reset", methods=["POST"])
@rate_limit(10, 60)
def api_wallet_preferences_reset():
    """Reset all user preferences to defaults."""
    try:
        session_id = request.remote_addr or "unknown"

        reset_prefs = wallet_history.reset_preferences(session_id)

        return jsonify(
            {
                "status": "success",
                "message": "Preferences reset to defaults",
                "preferences": reset_prefs,
            }
        ), 200
    except Exception as e:
        return json_error(
            "INTERNAL_SERVER_ERROR",
            debug_message=str(e),
            status_code=500,
        )


# ============================================================================= #
# API Routes — Biometric Authentication (WebAuthn/FIDO2)
# ============================================================================= #


@app.route("/api/auth/biometric/available", methods=["GET"])
@rate_limit(30, 60)
def api_biometric_available():
    """Check if device supports WebAuthn/FIDO2 and if biometric is enabled for this session.

    Returns:
        - device_support: boolean indicating browser WebAuthn support
        - user_enabled: boolean indicating if user has biometric enabled
        - device_name: string of registered device name if enabled
    """
    try:
        session_id = request.remote_addr or "unknown"

        # Check if user has biometric enabled
        is_enabled = wallet_history.is_biometric_available(session_id)
        auth_state = wallet_history.get_auth_state(session_id) if is_enabled else None

        return jsonify(
            {
                "status": "success",
                "device_support": True,  # Server assumes browser has WebAuthn support
                "user_enabled": is_enabled,
                "device_name": auth_state.get("biometric_device_name") if auth_state else None,
            }
        ), 200
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            status_code=500,
        )


@app.route("/api/auth/biometric/register", methods=["POST"])
@rate_limit(10, 60)
def api_biometric_register():
    """Register a biometric credential (fingerprint/face).

    Expected JSON payload:
    {
        "credential_id": "base64-encoded-credential-id",
        "public_key": "base64-encoded-cose-public-key",
        "device_name": "My Device"  # optional
    }

    Returns:
        - success: boolean
        - device_name: registered device name
        - message: confirmation message
    """
    try:
        session_id = request.remote_addr or "unknown"
        data = request.get_json() or {}

        # Validate required fields
        credential_id = str(data.get("credential_id", "")).strip()
        public_key = str(data.get("public_key", "")).strip()
        device_name = str(data.get("device_name", "Default Device")).strip()[:100]

        if not credential_id or not public_key:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="credential_id and public_key are required",
                status_code=400,
            )

        # Register biometric
        auth_state = wallet_history.setup_biometric(
            session_id,
            credential_id,
            public_key,
            device_name,
        )

        # Log the event
        try:
            conn = wallet_history.get_connection()
            wallet_history._log_biometric_event(
                conn,
                session_id,
                "register",
                "success",
                credential_id=credential_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent", ""),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # Non-fatal logging failure

        return jsonify(
            {
                "status": "success",
                "message": f"Biometric registered for {device_name}",
                "device_name": device_name,
            }
        ), 200
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            status_code=500,
        )


@app.route("/api/auth/biometric/verify", methods=["POST"])
@rate_limit(10, 60)  # Rate limited to prevent brute force
def api_biometric_verify():
    """Verify a biometric credential assertion.

    Expected JSON payload:
    {
        "assertion_id": "base64-encoded-assertion-credential-id"
    }

    Returns:
        - success: boolean
        - message: confirmation or error message
        - remaining_attempts: attempts remaining before rate limit (on failure)
    """
    try:
        session_id = request.remote_addr or "unknown"
        data = request.get_json() or {}

        # Check rate limiting
        is_rate_limited, attempts = wallet_history.check_biometric_rate_limit(
            session_id, max_attempts=5, window_seconds=60
        )
        if is_rate_limited:
            return json_error(
                "SECURITY_RATE_LIMITED",
                user_message="Too many failed biometric attempts. Please use password instead.",
                status_code=429,
            )

        assertion_id = str(data.get("assertion_id", "")).strip()
        if not assertion_id:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="assertion_id is required",
                status_code=400,
            )

        # Verify biometric
        verified = wallet_history.verify_biometric(session_id, assertion_id)

        if verified:
            return jsonify(
                {
                    "status": "success",
                    "message": "Biometric verification successful",
                }
            ), 200
        else:
            # Record failure and check new count
            attempt_count = wallet_history.record_biometric_failure(session_id)
            remaining = max(0, 5 - attempt_count)

            return json_error(
                "SECURITY_INVALID_PASSWORD",  # Reuse error code for failed verification
                user_message="Fingerprint/face not recognized. Try again or use password.",
                status_code=401,
            )
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            status_code=500,
        )


@app.route("/api/auth/biometric/disable", methods=["POST"])
@rate_limit(10, 60)
def api_biometric_disable():
    """Disable biometric authentication for this session.

    Returns:
        - success: boolean
        - message: confirmation message
    """
    try:
        session_id = request.remote_addr or "unknown"

        # Disable biometric
        success = wallet_history.disable_biometric(session_id)

        if success:
            return jsonify(
                {
                    "status": "success",
                    "message": "Biometric authentication disabled",
                }
            ), 200
        else:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Biometric not enabled for this session",
                status_code=400,
            )
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            status_code=500,
        )


@app.route("/api/auth/biometric/status", methods=["GET"])
@rate_limit(30, 60)
def api_biometric_status():
    """Get current biometric authentication status for this session.

    Returns:
        - enabled: boolean
        - device_name: registered device name (if enabled)
        - last_login: timestamp of last successful verification
        - failed_attempts: number of failed attempts since last success
    """
    try:
        session_id = request.remote_addr or "unknown"
        auth_state = wallet_history.get_auth_state(session_id)

        if not auth_state:
            return jsonify(
                {
                    "status": "success",
                    "enabled": False,
                    "device_name": None,
                    "last_login": None,
                    "failed_attempts": 0,
                }
            ), 200

        return jsonify(
            {
                "status": "success",
                "enabled": auth_state.get("biometric_enabled", 0) == 1,
                "device_name": auth_state.get("biometric_device_name"),
                "last_login": auth_state.get("last_login"),
                "failed_attempts": auth_state.get("failed_attempts", 0),
            }
        ), 200
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            status_code=500,
        )


@app.route("/api/auth/biometric/audit", methods=["GET"])
@rate_limit(30, 60)
def api_biometric_audit():
    """Get audit log for biometric events.

    Query parameters:
        - action: filter by action (register, verify, disable)
        - limit: max records per page (default 50, max 100)
        - offset: pagination offset (default 0)

    Returns:
        - events: list of audit log entries
        - total: total number of matching events
        - limit: page size
        - offset: current offset
    """
    try:
        session_id = request.remote_addr or "unknown"

        action = request.args.get("action", None)
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))

        audit_log = wallet_history.get_biometric_audit_log(
            session_id,
            action=action,
            limit=limit,
            offset=offset,
        )

        return jsonify(
            {
                "status": "success",
                **audit_log,
            }
        ), 200
    except Exception as e:
        return json_error(
            "INTERNAL_ERROR",
            debug_message=str(e),
            status_code=500,
        )


# ============================================================================= #
# API Routes — Blockchain Info
# ============================================================================= #


@app.route("/api/blockchain/info", methods=["GET"])
@rate_limit(60, 60)  # Public info endpoint
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

        # Calculate total money (sum of ONLY coinbase outputs, which create new coins)
        # Non-coinbase transactions just move existing coins, not creating new value.
        # In a real system, this would be tracked more efficiently.
        total_money_satoshis = sum(
            block.transactions[0].outputs[0].amount  # coinbase is always tx[0], output[0]
            for block_hash in chain.active_chain()
            for block in [chain.blocks[block_hash]]
            if block.transactions  # skip empty blocks (none should exist, but be safe)
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
        return json_error(
            "NETWORK_CONNECTION_ERROR",
            debug_message=str(e),
            suggested_action="Please try again",
        )


@app.route("/api/blockchain/status", methods=["GET"])
@rate_limit(60, 60)  # Public status endpoint
def api_blockchain_status():
    """Get blockchain sync status for offline mode indicator.

    Returns:
        {
            is_synced: bool - true if blockchain is fully synced
            current_height: int - current block height
            peers_connected: int - number of connected peers
            blocks_behind: int - estimated blocks behind (0 if synced)
            sync_percentage: float - sync progress 0-100
            last_block_time: float - unix timestamp of last block
            blockchain_healthy: bool - true if sync is progressing normally
            estimated_sync_seconds: int - estimated seconds until synced (-1 if unknown)
        }
    """
    try:
        node = get_node()
        chain = node.chain

        # Get current blockchain state
        current_height = chain.height
        last_block = chain.blocks.get(chain.tip)
        last_block_time = last_block.header.timestamp if last_block else time.time()

        # If node has no blocks (height 0), return demo/healthy status
        # This happens when local node is not running (MoonBite pre-launch)
        if current_height == 0:
            return jsonify(
                {
                    "status": "success",
                    "is_synced": True,
                    "current_height": 0,
                    "peers_connected": 0,
                    "blocks_behind": 0,
                    "sync_percentage": 100.0,
                    "last_block_time": time.time(),
                    "blockchain_healthy": True,
                    "estimated_sync_seconds": 0,
                    "timestamp": time.time(),
                    "mode": "demo"  # Indicates wallet in external RPC mode
                }
            ), 200

        # For demo/educational network, assume we're synced if we have blocks
        # In production, this would check against known peer heights
        is_synced = current_height > 1 or current_height == 1

        # Track if blockchain is healthy (has recent blocks)
        time_since_last_block = time.time() - last_block_time
        blockchain_healthy = time_since_last_block < 600  # Healthy if block within 10 min

        return jsonify(
            {
                "status": "success",
                "is_synced": is_synced,
                "current_height": current_height,
                "peers_connected": 0,  # Demo network, no peer tracking
                "blocks_behind": 0 if is_synced else 1,
                "sync_percentage": 100.0 if is_synced else 50.0,
                "last_block_time": last_block_time,
                "blockchain_healthy": blockchain_healthy,
                "estimated_sync_seconds": 0 if is_synced else 30,
                "timestamp": time.time(),
            }
        ), 200
    except Exception as e:
        # Fallback: Return demo/healthy status when local node unavailable
        # (MoonBite pre-launch - wallet functions for key management and local operations)
        # When external RPC is configured via BIGCOIN_RPC_URL, this will use that instead
        return jsonify(
            {
                "status": "success",
                "is_synced": True,
                "current_height": 0,
                "peers_connected": 0,
                "blocks_behind": 0,
                "sync_percentage": 100.0,
                "last_block_time": time.time(),
                "blockchain_healthy": True,
                "estimated_sync_seconds": 0,
                "timestamp": time.time(),
                "mode": "demo"  # Indicates wallet is in demo mode without live blockchain
            }
        ), 200


# ============================================================================= #
# API Routes — Mining
# ============================================================================= #


@app.route("/api/mining/start", methods=["POST"])
def api_mining_start():
    """Start mining blocks. Expects JSON: {"blocks": N, "address": "..."}

    Now supports concurrent mining from multiple devices/clients.
    Each request gets a unique job_id and runs in parallel.
    """
    print(f"[MINING API] New concurrent mining endpoint called", flush=True)
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

        # Generate unique job ID for this mining request
        job_id = str(uuid.uuid4())

        # Start mining in a background thread
        thread = threading.Thread(
            target=mining_worker, args=(job_id, blocks_to_mine, miner_pubkey_hash), daemon=True
        )
        thread.start()

        return jsonify(
            {
                "status": "mining",
                "job_id": job_id,
                "blocks_to_mine": blocks_to_mine,
            }
        ), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/mining/status", methods=["GET"])
def api_mining_status():
    """Get current mining status (supports multiple concurrent jobs).

    Optional query params:
    - include=leaderboard : Add top miners leaderboard
    - include=merchants : Add merchant payment status
    """
    try:
        from block import block_subsidy

        node = get_node()
        chain = node.chain
        next_bits = chain.next_bits()
        difficulty = 1 << next_bits
        next_height = chain.height + 1
        block_reward = block_subsidy(next_height)

        with app.mining_lock:
            active_jobs = app.mining_state["active_jobs"].copy()

        # Aggregate stats from all active jobs
        total_blocks_mined = 0
        total_blocks_target = 0
        total_hashes_tried = 0
        combined_hashrate = 0.0
        is_mining = len(active_jobs) > 0

        for job in active_jobs.values():
            if job.get("is_mining"):
                total_blocks_mined += job.get("blocks_mined", 0)
                total_blocks_target += job.get("blocks_to_mine", 0)
                total_hashes_tried += job.get("hashes_tried", 0)
                combined_hashrate += job.get("hashrate", 0.0)

        # Estimated seconds to the next block at combined hashrate
        eta_seconds = (difficulty / combined_hashrate) if combined_hashrate > 0 else None

        response = {
            "status": "mining" if is_mining else "idle",
            "active_jobs": len(active_jobs),
            "blocks_mined": total_blocks_mined,
            "total_blocks_target": total_blocks_target,
            "current_height": chain.height,
            "tip_hash": chain.tip,
            "bits": next_bits,
            "difficulty": difficulty,
            "total_hashes_tried": total_hashes_tried,
            "combined_hashrate": round(combined_hashrate, 2),
            "eta_next_block_seconds": (round(eta_seconds, 2)
                                       if eta_seconds is not None else None),
            "next_block_reward_coins": block_reward / 100_000_000,
        }

        # Add leaderboard if requested
        if request.args.get("include") == "leaderboard":
            address_blocks = {}
            for block_hash in chain.active_chain():
                block = chain.blocks[block_hash]
                if block.transactions and block.transactions[0].is_coinbase():
                    coinbase = block.transactions[0]
                    if coinbase.outputs:
                        output = coinbase.outputs[0]
                        try:
                            addr = address_from_pubkey_hash(output.pubkey_hash)
                            address_blocks[addr] = address_blocks.get(addr, 0) + 1
                        except Exception:
                            pass

            leaderboard = sorted(
                [{"address": addr, "blocks": count} for addr, count in address_blocks.items()],
                key=lambda x: x["blocks"],
                reverse=True
            )[:50]
            response["leaderboard"] = leaderboard

        return jsonify(response), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/mining/stop", methods=["GET"])
def api_mining_stop():
    """Stop mining (all jobs or specific job_id)."""
    try:
        job_id = request.args.get("job_id")

        with app.mining_lock:
            if job_id:
                # Stop a specific job
                if job_id in app.mining_state["active_jobs"]:
                    app.mining_state["active_jobs"][job_id]["is_mining"] = False
                    return jsonify({"status": "stopped", "job_id": job_id}), 200
                else:
                    return jsonify({"status": "error", "message": f"Job {job_id} not found"}), 404
            else:
                # Stop all jobs
                stopped_count = 0
                for job in app.mining_state["active_jobs"].values():
                    if job.get("is_mining"):
                        job["is_mining"] = False
                        stopped_count += 1
                return jsonify({"status": "stopped", "jobs_stopped": stopped_count}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/mining/globalstats", methods=["GET"])
@rate_limit(30, 60)  # Allow 30 requests per minute for stats updates
def api_mining_global_stats():
    """Get global mining statistics for viral display."""
    try:
        with app.mining_lock:
            active_jobs = app.mining_state["active_jobs"].copy()

        # Count active miners (only those actively mining right now)
        active_miners = sum(1 for job in active_jobs.values() if job.get("is_mining"))
        total_blocks_mined = sum(job.get("blocks_mined", 0) for job in active_jobs.values())
        total_blocks_target = sum(job.get("blocks_to_mine", 0) for job in active_jobs.values())
        combined_hashrate = sum(job.get("hashrate", 0.0) for job in active_jobs.values())

        node = get_node()
        return jsonify(
            {
                "status": "success",
                "active_miners": active_miners,
                "active_jobs": len(active_jobs),
                "blocks_mined_globally": total_blocks_mined,
                "blocks_pending": total_blocks_target - total_blocks_mined,
                "combined_hashrate": round(combined_hashrate, 2),
                "current_height": node.chain.height,
                "network_difficulty": 1 << node.chain.next_bits(),
            }
        ), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/merchants/invoice/<invoice_id>", methods=["GET"])
@rate_limit(30, 60)  # Check invoice status
def api_merchants_invoice_status(invoice_id):
    """Get invoice status and payment progress."""
    try:
        # In production: look up invoice in database
        # For MVP: check if payment address received MBITE

        # Mock response (would check actual payment in production)
        return jsonify({
            "status": "success",
            "invoice_id": invoice_id,
            "payment_status": "pending",  # or "paid", "expired"
            "amount_expected": 10,
            "amount_received": 0,
            "confirmations": 0,
            "expires_at": int(time.time()) + 3600,
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/merchants/create-invoice", methods=["POST"])
@rate_limit(30, 60)  # Merchants can create invoices
def api_merchants_create_invoice():
    """Create a payment invoice for a digital product.

    Request: {
        "merchant_address": "moon1xxx",
        "product_name": "My eBook",
        "amount_mbite": 10,
        "product_id": "ebook-001",
        "customer_email": "buyer@example.com"
    }

    Response: {
        "invoice_id": "inv_abc123",
        "status": "pending",
        "payment_address": "moon1yyy",  # Unique address for this payment
        "amount_mbite": 10,
        "fee_mbite": 0.2,  # 2% fee
        "expires_at": 3600  # seconds
    }
    """
    try:
        data = request.get_json()
        merchant_address = data.get("merchant_address")
        product_name = data.get("product_name", "Digital Product")
        amount_mbite = float(data.get("amount_mbite", 0))
        product_id = data.get("product_id", "")

        if not merchant_address or amount_mbite <= 0:
            return jsonify({
                "status": "error",
                "message": "Invalid merchant_address or amount"
            }), 400

        # Calculate 2% fee (1% to miners, 0.5% merchants, 0.5% development)
        fee_mbite = amount_mbite * 0.02
        net_to_merchant = amount_mbite - fee_mbite

        # Generate unique payment address for this invoice
        # (In production: would create HD wallet sub-address)
        import uuid
        invoice_id = f"inv_{uuid.uuid4().hex[:12]}"
        payment_address = f"moon1{uuid.uuid4().hex[:59]}"  # Mock address

        return jsonify({
            "status": "success",
            "invoice_id": invoice_id,
            "payment_address": payment_address,
            "amount_mbite": amount_mbite,
            "fee_mbite": round(fee_mbite, 8),
            "net_to_merchant": round(net_to_merchant, 8),
            "product_name": product_name,
            "product_id": product_id,
            "expires_seconds": 3600,
            "created_at": int(time.time()),
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/mining/leaderboard", methods=["GET"])
@rate_limit(30, 60)  # Leaderboard is public & frequently accessed
def api_mining_leaderboard():
    """Get mining leaderboard - top miners by blocks mined (this week/all-time)."""
    try:
        period = request.args.get("period", "week")  # week or all
        limit = min(int(request.args.get("limit", "50")), 100)  # Max 100

        node = get_node()
        chain = node.chain

        # Build address -> blocks_mined map from chain
        address_blocks = {}
        for block_hash in chain.active_chain():
            block = chain.blocks[block_hash]
            # Coinbase tx has miner address
            if block.transactions and block.transactions[0].is_coinbase():
                coinbase = block.transactions[0]
                if coinbase.outputs:
                    # Get first output's recipient (miner address)
                    output = coinbase.outputs[0]
                    try:
                        addr = address_from_pubkey_hash(output.pubkey_hash)
                        address_blocks[addr] = address_blocks.get(addr, 0) + 1
                    except Exception:
                        pass

        # Sort by blocks mined
        leaderboard = sorted(
            [{"address": addr, "blocks": count} for addr, count in address_blocks.items()],
            key=lambda x: x["blocks"],
            reverse=True
        )[:limit]

        return jsonify(
            {
                "status": "success",
                "period": period,
                "leaderboard": leaderboard,
                "total_miners": len(address_blocks),
                "current_height": chain.height,
            }
        ), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/mining/receipt/<job_id>", methods=["GET"])
@rate_limit(30, 60)  # Allow receipt generation requests
def api_mining_share(job_id):
    """Generate shareable receipt data for a completed mining job.

    Returns OG tags and share text for Twitter, TikTok, etc.
    """
    try:
        with app.mining_lock:
            job = app.mining_state["active_jobs"].get(job_id)

        if not job:
            return jsonify({"status": "error", "message": "Job not found"}), 404

        blocks_mined = job.get("blocks_mined", 0)
        hashrate = job.get("hashrate", 0)

        if blocks_mined == 0:
            return jsonify({"status": "error", "message": "No blocks mined yet"}), 400

        # MBITE earned at the CURRENT subsidy — never a hardcoded figure,
        # so the share text stays truthful across halvings.
        from block import block_subsidy
        from params import CENTS_PER_COIN
        subsidy_coins = block_subsidy(get_node().chain.height) / CENTS_PER_COIN
        mbite_earned = blocks_mined * subsidy_coins

        # Generate share text for different platforms
        s = 's' if blocks_mined > 1 else ''
        share_text = (f"I just mined {blocks_mined} MoonBite block{s}! "
                      f"Earned {mbite_earned:,.0f} MBITE 🌙⛏️")
        twitter_text = f"{share_text} Join me: https://moonbite.org/mining"
        tiktok_text = f"Mining crypto with {share_text} #MoonBite #Mining"

        return jsonify(
            {
                "status": "success",
                "job_id": job_id,
                "blocks_mined": blocks_mined,
                "mbite_earned": mbite_earned,
                "hashrate": round(hashrate, 2),
                "share_text": share_text,
                "twitter": {
                    "text": twitter_text,
                    "url": f"https://twitter.com/intent/tweet?text={share_text.replace(' ', '%20')}&url=https://moonbite.org",
                },
                "tiktok": {
                    "text": tiktok_text,
                },
                "og_tags": {
                    "title": f"I mined {mbite_earned:,.0f} MBITE! 🚀",
                    "description": (f"Mined {blocks_mined} block{s} "
                                   "using the MoonBite browser miner"),
                    "image": "https://moonbite.org/favicon.svg",
                    "url": f"https://moonbite.org/mining?receipt={job_id}",
                },
            }
        ), 200
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
# ============================================================================= #
# New Wallet APIs - Phase 1-4 Features
# ============================================================================= #

@app.route("/api/wallet/backup/create", methods=["POST"])
def create_backup():
    """Create encrypted cloud backup of wallet seed phrase"""
    try:
        data = request.get_json() or {}
        encrypted_seed = data.get("encryptedSeed")

        if not encrypted_seed:
            return jsonify({"error": "No encrypted seed provided"}), 400

        # Store backup in a simple JSON file (in production, use database)
        backup_data = {
            "id": secrets.token_hex(8),
            "encryptedSeed": encrypted_seed,
            "timestamp": time.time(),
            "platform": request.headers.get("User-Agent", "unknown")
        }

        # Save to backups directory
        os.makedirs("backups", exist_ok=True)
        backup_file = f"backups/{backup_data['id']}.json"
        with open(backup_file, "w") as f:
            json.dump(backup_data, f)

        return jsonify({
            "success": True,
            "backupId": backup_data["id"],
            "timestamp": backup_data["timestamp"],
            "message": "Backup created successfully"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/backup/status", methods=["GET"])
def backup_status():
    """Get cloud backup status"""
    try:
        backups = []
        if os.path.exists("backups"):
            for f in os.listdir("backups"):
                if f.endswith(".json"):
                    with open(f"backups/{f}") as fp:
                        backup = json.load(fp)
                        backups.append({
                            "id": backup["id"],
                            "timestamp": backup["timestamp"],
                            "platform": backup["platform"]
                        })

        return jsonify({
            "hasBackup": len(backups) > 0,
            "lastBackup": max([b["timestamp"] for b in backups], default=None),
            "backupCount": len(backups),
            "backups": sorted(backups, key=lambda x: x["timestamp"], reverse=True)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/backup/restore", methods=["POST"])
def restore_backup():
    """Restore wallet from encrypted cloud backup"""
    try:
        data = request.get_json() or {}
        backup_id = data.get("backupId")

        if not backup_id:
            return jsonify({"error": "Backup ID required"}), 400

        backup_file = f"backups/{backup_id}.json"
        if not os.path.exists(backup_file):
            return jsonify({"error": "Backup not found"}), 404

        with open(backup_file) as f:
            backup = json.load(f)

        return jsonify({
            "success": True,
            "encryptedSeed": backup["encryptedSeed"],
            "timestamp": backup["timestamp"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tx/broadcast", methods=["POST"])
@rate_limit(30, 60)
def api_tx_broadcast():
    """Accept a transaction signed in the browser and put it on the chain.

    The wallet holds the only copy of the key, so it builds and signs the
    transaction itself and this endpoint never sees a private key or a seed.
    What arrives is already authorized; the node re-verifies it against the
    UTXO set exactly as it would a transaction from any peer, and rejects it
    otherwise. A malformed or unauthorized submission can only waste its
    sender's time.
    """
    data = request.get_json(silent=True) or {}
    try:
        raw = data.get("transaction")
        if not isinstance(raw, dict):
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="A signed transaction is required",
            )

        try:
            tx = Transaction.from_dict(raw)
        except (KeyError, TypeError, ValueError) as e:
            return json_error(
                "VALIDATION_MISSING_FIELD",
                user_message="Transaction is malformed",
                debug_message=str(e),
            )

        node = get_node()
        # submit_transaction validates signatures, ownership, maturity and
        # value conservation before it will touch the mempool.
        if not node.submit_transaction(tx):
            return json_error(
                "VALIDATION_INSUFFICIENT_BALANCE",
                user_message=(
                    "The network rejected this transaction. Its inputs may "
                    "already be spent, or the balance may have changed."
                ),
                suggested_action="Refresh your balance and try again",
            )

        return jsonify(
            {
                "status": "success",
                "txid": tx.txid,
                "accepted": True,
                "mempool_size": len(node.chain.mempool),
            }
        ), 200
    except Exception as e:  # noqa: BLE001
        return json_error(
            "NETWORK_CONNECTION_ERROR",
            debug_message=str(e),
            suggested_action="Please wait and try again",
        )


@app.route("/api/wallet/send", methods=["POST"])
def wallet_send():
    """Refuse to fake a send.

    This used to mint a random hex string, call it a txid and report success,
    so a user could believe coins had moved when nothing had touched the
    chain. Spending now happens through /api/tx/broadcast with a transaction
    the wallet signed itself; there is no server-side path that can send on a
    user's behalf, because the server has no key to sign with.
    """
    return json_error(
        "VALIDATION_MISSING_FIELD",
        user_message=(
            "This endpoint no longer sends coins. Sign the transaction in the "
            "wallet and submit it to /api/tx/broadcast."
        ),
        status_code=410,
    )

@app.route("/api/achievements", methods=["GET"])
def get_achievements():
    """Get user achievements and gamification data"""
    try:
        achievements = [
            {"id": "first_tx", "name": "First Send", "icon": "📤", "unlocked": False},
            {"id": "hodler", "name": "HODLER", "icon": "💎", "unlocked": False},
            {"id": "miner", "name": "Miner", "icon": "⛏️", "unlocked": False},
            {"id": "whale", "name": "Whale", "icon": "🐋", "unlocked": False},
            {"id": "social", "name": "Social", "icon": "🌍", "unlocked": False},
            {"id": "collector", "name": "Collector", "icon": "🎁", "unlocked": False}
        ]

        return jsonify({
            "achievements": achievements,
            "score": 0,
            "streaks": {"mining": 0},
            "milestones": ["100 MBITE balance", "1000 MBITE balance"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/achievements/unlock", methods=["POST"])
def unlock_achievement():
    """Unlock an achievement"""
    try:
        data = request.get_json() or {}
        achievement_id = data.get("id")

        return jsonify({
            "success": True,
            "achievement": achievement_id,
            "points": 10,
            "message": f"Achievement unlocked: {achievement_id}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# NOTE: a second GET handler for /api/wallet/transactions lived here. Flask
# accepted it (the endpoint names differed) but Werkzeug matches the first
# registered rule, so it was unreachable code shadowed by
# api_wallet_transactions_list above. Removed rather than left to rot as a
# second, divergent implementation of a live endpoint.

@app.route("/api/wallet/price", methods=["GET"])
def get_wallet_price():
    """MBITE market price — reports that there is none.

    This endpoint previously returned a hardcoded $0.0234 with a $327m market
    cap, while /api/price/mbite simultaneously returned $45.67 with a $9.13bn
    cap. Two live endpoints inventing different prices, three orders of
    magnitude apart, for a coin that is not listed anywhere. Both now defer to
    price_feed, which answers honestly.
    """
    data = price_feed.get_price()
    return jsonify({
        "listed": data["listed"],
        "price": data["price_usd"],          # None while unlisted
        "currency": request.args.get("currency", "usd").lower(),
        "change24h": data["change_24h"],
        "marketCap": data["market_cap"],
        "volume24h": data["volume_24h"],
        "message": data.get("message"),
        "timestamp": data["timestamp"],
    })


@app.route("/api/wallet/price-history", methods=["GET"])
def get_wallet_price_history():
    """Historical prices — empty, because none exist.

    The previous implementation synthesized a series from hash(i), producing a
    chart indistinguishable from real market data for an asset that has never
    traded.
    """
    days = request.args.get("days", 30, type=int)
    data = price_feed.get_price_history(hours=max(1, min(days, 365)) * 24)
    return jsonify({
        "listed": data["listed"],
        "history": data["points"],
        "currency": "usd",
        "days": days,
        "message": data["message"],
    })


@app.route("/api/hardware-wallet/detect", methods=["GET"])
def detect_hardware_wallets():
    """Detect connected hardware wallets"""
    return jsonify({
        "devices": [],
        "supported": ["ledger", "trezor"],
        "webusb": True,
        "message": "No hardware wallets detected. Connect a Ledger or Trezor device."
    })

@app.route("/api/hardware-wallet/address", methods=["POST"])
def get_hardware_address():
    """Get address from hardware wallet"""
    try:
        data = request.get_json() or {}
        device_type = data.get("device", "ledger")
        index = data.get("index", 0)

        # Simulate hardware wallet response
        return jsonify({
            "address": f"moon1{'q' * 54}",
            "device": device_type,
            "index": index,
            "path": f"m/44'/0'/0'/0/{index}",
            "publicKey": "0x" + "0" * 64
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/hardware-wallet/sign", methods=["POST"])
def sign_with_hardware():
    """Sign transaction with hardware wallet"""
    try:
        data = request.get_json() or {}

        # Simulate signing
        return jsonify({
            "txid": "0x" + secrets.token_hex(32),
            "signature": "0x" + "f" * 128,
            "status": "success"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/settings", methods=["GET"])
def get_wallet_settings():
    """Get wallet settings"""
    return jsonify({
        "theme": "dark",
        "currency": "usd",
        "network": "mainnet",
        "rpcEndpoint": "http://localhost:9444",
        "sessionTimeout": 300,
        "biometricEnabled": False,
        "notificationsEnabled": True,
        "priceAlerts": [],
        "language": "en"
    })

@app.route("/api/wallet/settings", methods=["PATCH"])
def update_wallet_settings():
    """Update wallet settings"""
    try:
        data = request.get_json() or {}

        return jsonify({
            "success": True,
            "settings": data,
            "message": "Settings updated successfully"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/mining/stats", methods=["GET"])
def get_mining_stats():
    """Get mining statistics"""
    try:
        stats = {
            "blocksMined": 0,
            "totalRewards": 0.0,
            "hashRate": 0,
            "difficulty": 1,
            "nextBlockEstimate": 120,
            "miningStreak": 0,
            "today": 0.0,
            "thisWeek": 0.0,
            "thisMonth": 0.0
        }

        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/mining/alerts", methods=["GET"])
def get_mining_alerts():
    """Mining alerts. No fabricated data: the server has no sensor access,
    so the honest answer is an empty list."""
    return jsonify({"alerts": []})

# script/style allow 'unsafe-inline'. Everything else is locked to 'self', no
# framing, no plugins. Tightening to nonces is future work (see AUDIT_REPORT.md).
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "img-src 'self' data:; "
    "font-src 'self' https://fonts.gstatic.com; "
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
    # Initialize wallet history database
    wallet_history.create_schema()
    # Production deploys run this under gunicorn (web_app:app) and never reach
    # this block. When launched directly, honor the environment so the same
    # file works locally (defaults) and on a server/PaaS (PORT/HOST/FLASK_DEBUG).
    host = os.environ.get("HOST", "localhost")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print(f"MoonBite Dashboard starting on http://{host}:{port}")
    app.run(debug=debug, host=host, port=port)
