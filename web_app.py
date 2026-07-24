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

import json
import os
import re
import threading
import time
from typing import Optional

from flask import Flask, jsonify, render_template, request, send_from_directory

# Pragmatic email validation for the listing-notify capture.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
import exchange
import merchants
from node import Node
from transaction import generate_keypair, pubkey_hash
from wallet import address_from_pubkey_hash, is_valid_address, pubkey_hash_from_address

app = Flask(__name__, template_folder="templates", static_folder="static")

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

# Generated addresses for wallet operations (in-memory storage for demo)
app.generated_addresses = {}  # pubkey_hash -> {"address": ..., "pubkey": ...}

# Lock for thread-safe mining operations
app.mining_lock = threading.Lock()


def get_node() -> Node:
    """Get or create the global node instance."""
    if app.node is None:
        app.node = Node("web-app", coinbase_maturity=0)
    return app.node


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


def mining_worker(blocks_to_mine: int, miner_address: str) -> None:
    """Background worker thread for mining blocks."""
    node = get_node()
    app.mining_state["blocks_mined"] = 0
    app.mining_state["current_block_height"] = node.chain.height

    for i in range(blocks_to_mine):
        if not app.mining_state["is_mining"]:
            break

        try:
            block = node.mine_block(miner_address)
            if block is not None:
                app.mining_state["blocks_mined"] = i + 1
                app.mining_state["current_block_height"] = node.chain.height
            else:
                break
        except Exception as e:
            print(f"Mining error: {e}")
            break

    app.mining_state["is_mining"] = False


# ============================================================================= #
# Routes
# ============================================================================= #


@app.route("/")
def home_page():
    """Render the marketing homepage."""
    return render_template("home.html")


@app.route("/dashboard")
def dashboard_page():
    """Render the live network dashboard."""
    return render_template("index.html")


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
    """Cancel an open order — only the maker (by MBITE address) may do so."""
    data = request.get_json(silent=True) or {}
    try:
        order = exchange.cancel_order(order_id, str(data.get("mbite_address", "")))
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
def api_merchant_invoice_create():
    """Raise a non-custodial payment request against a merchant address."""
    data = request.get_json(silent=True) or {}
    try:
        inv = merchants.create_invoice(
            address=data.get("address", ""),
            amount=data.get("amount"),
            received_lookup=received_at_address,
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
        inv = merchants.invoice_status(invoice_id, received_at_address)
        return jsonify({"status": "success", "invoice": inv}), 200
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 404


# ============================================================================= #
# API Routes — Wallet
# ============================================================================= #


@app.route("/api/wallet/new", methods=["GET"])
def api_wallet_new():
    """Generate a new keypair and return address + pubkey_hash."""
    try:
        sk, pubkey_hex = generate_keypair()
        pkh = pubkey_hash(pubkey_hex)
        address = address_from_pubkey_hash(pkh)

        # Store for potential balance checking
        app.generated_addresses[pkh] = {
            "address": address,
            "pubkey": pubkey_hex,
            "pubkey_hash": pkh,
        }

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

        # Check all generated addresses
        for pkh in app.generated_addresses.keys():
            # Iterate through all UTXOs and find those matching this pubkey_hash
            for _txid, _idx, out in node.chain.utxo.items():
                if out.pubkey_hash == pkh:
                    total_balance += out.amount
                    utxo_count += 1

        # Convert satoshis to coins (assuming 100 satoshis = 1 coin)
        # In real Bitcoin: 100,000,000 satoshis = 1 BTC
        # For MyCoin: using simpler 100 satoshis = 1 coin for demo
        balance_coins = total_balance // 100
        balance_cents = (total_balance % 100)

        return jsonify(
            {
                "status": "success",
                "balance_satoshis": total_balance,
                "balance_coins": balance_coins,
                "balance_cents": balance_cents,
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

        return jsonify(
            {
                "status": "success",
                "height": chain.height,
                "tip_hash": chain.tip,
                "total_money_satoshis": total_money_satoshis,
                "total_money_coins": total_money_coins,
                "tx_count": tx_count,
                "mempool_size": len(chain.mempool),
            }
        ), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================= #
# API Routes — Mining
# ============================================================================= #


@app.route("/api/mining/start", methods=["POST"])
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

            if not miner_address or blocks_to_mine <= 0:
                return jsonify(
                    {
                        "status": "error",
                        "message": "Invalid blocks or address",
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
        node = get_node()
        return jsonify(
            {
                "status": "mining" if app.mining_state["is_mining"] else "idle",
                "blocks_mined": app.mining_state["blocks_mined"],
                "total_blocks": app.mining_state["blocks_to_mine"],
                "current_height": node.chain.height,
                "tip_hash": node.chain.tip,
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


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors."""
    return jsonify({"status": "error", "message": "Internal server error"}), 500


# ============================================================================= #
# CORS Headers (educational use — allow all origins)
# ============================================================================= #


@app.after_request
def add_cors_headers(response):
    """Add CORS headers to all responses."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
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
