"""MyCoin Web App Tests — Flask application test suite.

Tests for the Flask web dashboard including:
  - Wallet API endpoints (new address generation, balance checking)
  - Blockchain info endpoints (height, tip hash, transaction count)
  - Mining endpoints (start, stop, status)
  - Transaction listing
  - Error handling
"""

import pytest
import json
from web_app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config["TESTING"] = True
    # Reset global state between tests
    app.mining_state = {
        "is_mining": False,
        "blocks_to_mine": 0,
        "blocks_mined": 0,
        "current_block_height": 0,
        "mining_address": None,
        "mining_thread": None,
        "hashes_tried": 0,
        "hashrate": 0.0,
        "started_at": 0.0,
    }
    app.node = None
    app.generated_addresses = {}
    with app.test_client() as client:
        yield client


# ============================================================================= #
# Page Rendering Tests
# ============================================================================= #


class TestPageRendering:
    """Test that HTML pages render correctly."""

    def test_index_page(self, client):
        """Test GET / returns the MoonBite marketing home page."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"MoonBite" in response.data

    def test_wallet_page(self, client):
        """Test GET /wallet returns wallet page."""
        response = client.get("/wallet")
        assert response.status_code == 200
        assert b"Wallet" in response.data
        assert b"Generate New Address" in response.data

    def test_mining_page(self, client):
        """Test GET /mining returns mining page."""
        response = client.get("/mining")
        assert response.status_code == 200
        assert b"Mining" in response.data
        assert b"Number of Blocks to Mine" in response.data


# ============================================================================= #
# Wallet API Tests
# ============================================================================= #


class TestWalletAPI:
    """Test wallet-related API endpoints."""

    def test_wallet_new_success(self, client):
        """Test GET /api/wallet/new generates a valid address."""
        response = client.get("/api/wallet/new")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "success"
        assert "address" in data
        assert "pubkey_hash" in data
        assert "pubkey" in data

        # Address should be a non-empty string
        address = data["address"]
        assert isinstance(address, str)
        assert len(address) > 10
        # MoonBite addresses are bech32 with the "moon" HRP.
        assert address.startswith("moon1")

    def test_wallet_new_multiple_calls(self, client):
        """Test multiple address generations produce different addresses."""
        response1 = client.get("/api/wallet/new")
        response2 = client.get("/api/wallet/new")

        data1 = response1.get_json()
        data2 = response2.get_json()

        # Addresses should be different (with very high probability)
        assert data1["address"] != data2["address"]
        assert data1["pubkey_hash"] != data2["pubkey_hash"]

    def test_wallet_balance_initial(self, client):
        """Test GET /api/wallet/balance returns initial balance structure."""
        response = client.get("/api/wallet/balance")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "success"
        assert "balance_units" in data
        assert "balance_coins" in data
        assert "balance_display" in data
        assert "utxo_count" in data

        # Initially no addresses, so balance should be 0
        assert isinstance(data["balance_units"], int)
        assert isinstance(data["balance_coins"], (int, float))
        assert isinstance(data["balance_display"], str)
        assert isinstance(data["utxo_count"], int)

    def test_wallet_balance_after_mining(self, client):
        """Test that balance increases after mining a block."""
        # Generate an address
        addr_response = client.get("/api/wallet/new")
        address = addr_response.get_json()["address"]

        # Check initial balance
        balance_before = client.get("/api/wallet/balance").get_json()
        initial_satoshis = balance_before["balance_units"]

        # Mine a block to that address
        mine_response = client.post(
            "/api/mining/start",
            data=json.dumps({"blocks": 1, "address": address}),
            content_type="application/json",
        )
        assert mine_response.status_code == 200

        # Wait for mining to complete by polling status
        import time
        for _ in range(60):  # Up to 30 seconds
            status = client.get("/api/mining/status").get_json()
            if status["status"] != "mining":
                break
            time.sleep(0.5)

        # Check balance after mining
        balance_after = client.get("/api/wallet/balance").get_json()
        final_satoshis = balance_after["balance_units"]

        # Balance should have increased (coinbase reward received)
        assert final_satoshis > initial_satoshis


# ============================================================================= #
# Blockchain API Tests
# ============================================================================= #


class TestBlockchainAPI:
    """Test blockchain info endpoints."""

    def test_blockchain_info_structure(self, client):
        """Test GET /api/blockchain/info returns expected structure."""
        response = client.get("/api/blockchain/info")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "success"
        assert "height" in data
        assert "tip_hash" in data
        assert "total_money_satoshis" in data
        assert "total_money_coins" in data
        assert "tx_count" in data
        assert "mempool_size" in data

    def test_blockchain_info_genesis_state(self, client):
        """Test blockchain info reflects genesis state initially."""
        response = client.get("/api/blockchain/info")
        data = response.get_json()

        # Genesis block is height 0
        assert data["height"] == 0
        # Tip hash should be a valid hex string
        assert isinstance(data["tip_hash"], str)
        assert len(data["tip_hash"]) == 64  # SHA256 hex digest length

    def test_blockchain_info_after_mining(self, client):
        """Test blockchain info updates after mining a block."""
        # Get initial height
        initial_info = client.get("/api/blockchain/info").get_json()
        initial_height = initial_info["height"]

        # Generate an address and mine
        addr_response = client.get("/api/wallet/new")
        address = addr_response.get_json()["address"]

        mine_response = client.post(
            "/api/mining/start",
            data=json.dumps({"blocks": 1, "address": address}),
            content_type="application/json",
        )

        # Wait for mining to complete
        import time
        for _ in range(60):
            status = client.get("/api/mining/status").get_json()
            if status["status"] != "mining":
                break
            time.sleep(0.5)

        # Get updated info
        updated_info = client.get("/api/blockchain/info").get_json()
        updated_height = updated_info["height"]

        # Height should have increased
        assert updated_height > initial_height
        # Tip hash should have changed
        assert updated_info["tip_hash"] != initial_info["tip_hash"]


# ============================================================================= #
# Mining API Tests
# ============================================================================= #


class TestMiningAPI:
    """Test mining-related API endpoints."""

    def test_mining_start_valid(self, client):
        """Test POST /api/mining/start with valid parameters."""
        # Generate an address first
        addr_response = client.get("/api/wallet/new")
        address = addr_response.get_json()["address"]

        # Start mining
        response = client.post(
            "/api/mining/start",
            data=json.dumps({"blocks": 1, "address": address}),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "mining"
        assert data["blocks_to_mine"] == 1

    def test_mining_start_missing_address(self, client):
        """Test POST /api/mining/start with missing address returns 400."""
        response = client.post(
            "/api/mining/start",
            data=json.dumps({"blocks": 1}),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"

    def test_mining_start_invalid_address(self, client):
        """Test POST /api/mining/start with invalid address returns 400."""
        response = client.post(
            "/api/mining/start",
            data=json.dumps({"blocks": 1, "address": "invalid_address"}),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert "Invalid address" in data["message"]

    def test_mining_start_invalid_blocks(self, client):
        """Test POST /api/mining/start with invalid blocks count returns 400."""
        # Generate an address
        addr_response = client.get("/api/wallet/new")
        address = addr_response.get_json()["address"]

        # Try to mine 0 blocks
        response = client.post(
            "/api/mining/start",
            data=json.dumps({"blocks": 0, "address": address}),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_mining_status_idle(self, client):
        """Test GET /api/mining/status when not mining."""
        response = client.get("/api/mining/status")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "idle"
        assert "blocks_mined" in data
        assert "total_blocks" in data
        assert "current_height" in data

    def test_mining_status_during_mining(self, client):
        """Test GET /api/mining/status while mining is active."""
        # Generate an address
        addr_response = client.get("/api/wallet/new")
        address = addr_response.get_json()["address"]

        # Start mining
        client.post(
            "/api/mining/start",
            data=json.dumps({"blocks": 1, "address": address}),
            content_type="application/json",
        )

        # Check status immediately
        status_response = client.get("/api/mining/status")
        assert status_response.status_code == 200
        data = status_response.get_json()

        # Should be mining or idle (depending on timing)
        assert data["status"] in ("mining", "idle")
        assert "current_height" in data

    def test_mining_stop(self, client):
        """Test GET /api/mining/stop stops mining."""
        # Generate an address
        addr_response = client.get("/api/wallet/new")
        address = addr_response.get_json()["address"]

        # Start mining
        client.post(
            "/api/mining/start",
            data=json.dumps({"blocks": 5, "address": address}),
            content_type="application/json",
        )

        # Stop mining
        response = client.get("/api/mining/stop")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "stopped"


# ============================================================================= #
# Transaction API Tests
# ============================================================================= #


class TestTransactionAPI:
    """Test transaction-related API endpoints."""

    def test_transactions_list_empty(self, client):
        """Test GET /api/transactions returns list structure."""
        response = client.get("/api/transactions")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "success"
        assert "transactions" in data
        assert isinstance(data["transactions"], list)

    def test_transactions_after_mining(self, client):
        """Test transactions list updates after mining."""
        # Generate an address
        addr_response = client.get("/api/wallet/new")
        address = addr_response.get_json()["address"]

        # Mine a block
        client.post(
            "/api/mining/start",
            data=json.dumps({"blocks": 1, "address": address}),
            content_type="application/json",
        )

        # Wait for mining to complete
        import time
        for _ in range(60):
            status = client.get("/api/mining/status").get_json()
            if status["status"] != "mining":
                break
            time.sleep(0.5)

        # Get transactions
        response = client.get("/api/transactions")
        data = response.get_json()

        assert data["status"] == "success"
        # Should have at least the coinbase transaction from the mined block
        assert len(data["transactions"]) > 0

    def test_mempool_endpoint_shape(self, client):
        """GET /api/mempool returns the pending-tx shape the wallet page expects."""
        response = client.get("/api/mempool")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "success"
        assert isinstance(data["transactions"], list)
        # Every entry must carry the fields renderMempool() reads.
        for tx in data["transactions"]:
            assert {"txid", "inputs", "outputs", "total_out_cents"} <= tx.keys()


# ============================================================================= #
# Error Handling Tests
# ============================================================================= #


class TestErrorHandling:
    """Test error handling."""

    def test_404_not_found(self, client):
        """Test 404 error for invalid routes."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
        data = response.get_json()
        assert data["status"] == "error"

    def test_cors_allows_listed_origin(self, client):
        """An allow-listed origin is echoed back (never a wildcard)."""
        response = client.get(
            "/api/blockchain/info", headers={"Origin": "https://moonbite.org"}
        )
        assert response.headers.get("Access-Control-Allow-Origin") == "https://moonbite.org"
        assert response.headers.get("Access-Control-Allow-Origin") != "*"

    def test_cors_rejects_unlisted_origin(self, client):
        """An unknown origin gets no CORS header, so cross-origin access is blocked."""
        response = client.get(
            "/api/blockchain/info", headers={"Origin": "https://evil.example"}
        )
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_json_content_type(self, client):
        """Test that API responses have correct content type."""
        response = client.get("/api/blockchain/info")
        assert "application/json" in response.content_type

    def test_oversized_body_rejected_413(self, client):
        """A hostile over-sized POST body is refused with 413 rather than being
        buffered + parsed. Guards against the memory-exhaustion DoS where one
        multi-hundred-MB request spikes the worker past 1 GB RAM."""
        cap = app.config["MAX_CONTENT_LENGTH"]
        assert cap is not None and cap <= 1024 * 1024  # sane cap is configured
        oversized = b'{"email":"a@b.co","source":"' + b"X" * (cap + 1) + b'"}'
        response = client.post(
            "/api/notify",
            data=oversized,
            content_type="application/json",
        )
        assert response.status_code == 413
        assert response.get_json()["status"] == "error"

    def test_normal_body_still_accepted(self, client):
        """A legitimately small body is unaffected by the cap."""
        response = client.post(
            "/api/notify",
            json={"email": "real.user@example.com", "source": "test"},
        )
        # Not a 413 — the cap only rejects over-sized payloads.
        assert response.status_code != 413


# ============================================================================= #
# Integration Tests
# ============================================================================= #


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_full_mining_flow(self, client):
        """Test complete mining flow: generate address, mine, check balance."""
        # Step 1: Generate an address
        addr_response = client.get("/api/wallet/new")
        assert addr_response.status_code == 200
        address = addr_response.get_json()["address"]

        # Step 2: Mine a block
        mine_response = client.post(
            "/api/mining/start",
            data=json.dumps({"blocks": 1, "address": address}),
            content_type="application/json",
        )
        assert mine_response.status_code == 200

        # Step 3: Wait for mining to complete
        import time
        for _ in range(60):
            status = client.get("/api/mining/status").get_json()
            if status["status"] != "mining":
                break
            time.sleep(0.5)

        # Step 4: Check balance
        balance_response = client.get("/api/wallet/balance")
        assert balance_response.status_code == 200
        balance = balance_response.get_json()
        assert balance["balance_units"] > 0

        # Step 5: Verify blockchain height increased
        info_response = client.get("/api/blockchain/info")
        info = info_response.get_json()
        assert info["height"] >= 1


# ============================================================================= #
# Rate Limiting Tests
# ============================================================================= #


class TestRateLimiting:
    """The rate limiter is auto-disabled under pytest; these tests re-enable it
    around a single request burst to prove the 429 path and API-key bypass."""

    def test_rate_limit_returns_429_after_threshold(self, client):
        import web_app
        web_app._rl_hits.clear()
        web_app._RATE_DISABLED = False
        try:
            # api_wallet_new is capped at 30/60s.
            codes = [client.get("/api/wallet/new").status_code for _ in range(35)]
        finally:
            web_app._RATE_DISABLED = True
            web_app._rl_hits.clear()

        assert codes.count(200) == 30
        assert codes.count(429) == 5
        # Once limited, the response carries a Retry-After header.
        limited = client.get("/api/wallet/new")
        # (limiter now disabled again, so this one succeeds — just assert shape)
        assert limited.status_code in (200, 429)

    def test_api_key_bypasses_rate_limit(self, client):
        import web_app
        web_app._rl_hits.clear()
        web_app._RATE_DISABLED = False
        web_app._API_KEYS = {"testkey"}
        try:
            codes = [
                client.get("/api/wallet/new", headers={"X-API-Key": "testkey"}).status_code
                for _ in range(35)
            ]
        finally:
            web_app._RATE_DISABLED = True
            web_app._API_KEYS = set()
            web_app._rl_hits.clear()

        # A valid key bypasses the cap entirely — no 429s.
        assert codes.count(200) == 35
        assert 429 not in codes


# ============================================================================= #
# Phase 2b — verifier trigger endpoint
# ============================================================================= #


class TestVerifierTrigger:
    """POST /api/exchange/verify: operator-only, flag-gated, token-protected."""

    def test_disabled_by_default_returns_403(self, client):
        r = client.post("/api/exchange/verify")
        assert r.status_code == 403
        assert json.loads(r.data)["message"] == "verifier disabled"

    def test_enabled_but_no_token_is_unauthorized(self, client, monkeypatch):
        from explorer import config as ex_config
        monkeypatch.setattr(ex_config, "VERIFIER_ENABLED", True)
        monkeypatch.setenv("VERIFIER_TRIGGER_TOKEN", "s3cret")
        r = client.post("/api/exchange/verify")  # no X-Verifier-Token header
        assert r.status_code == 403
        assert json.loads(r.data)["message"] == "unauthorized"

    def test_enabled_with_bad_token_is_unauthorized(self, client, monkeypatch):
        from explorer import config as ex_config
        monkeypatch.setattr(ex_config, "VERIFIER_ENABLED", True)
        monkeypatch.setenv("VERIFIER_TRIGGER_TOKEN", "s3cret")
        r = client.post("/api/exchange/verify", headers={"X-Verifier-Token": "wrong"})
        assert r.status_code == 403

    def test_authorized_empty_pass_returns_zero_verified(self, client, monkeypatch):
        import exchange
        from explorer import config as ex_config
        monkeypatch.setattr(ex_config, "VERIFIER_ENABLED", True)
        monkeypatch.setenv("VERIFIER_TRIGGER_TOKEN", "s3cret")
        # No swaps to verify => the node is never touched; a clean 200.
        monkeypatch.setattr(exchange, "list_swaps_for_verification", lambda: [])
        r = client.post("/api/exchange/verify", headers={"X-Verifier-Token": "s3cret"})
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["verified"] == 0 and body["results"] == []


class TestMerchantReceivedLookup:
    """The merchant payment observer, wired to the production node via scantxoutset."""

    class _FakeRpc:
        def __init__(self, total_amount, *, fail=False):
            self.total_amount = total_amount
            self.fail = fail
            self.calls = 0

        def scantxoutset(self, action, scanobjects):
            self.calls += 1
            if self.fail:
                raise RuntimeError("node unreachable")
            return {"success": True, "total_amount": self.total_amount}

    def _reset(self, monkeypatch, fake, *, units_per_coin=100000000):
        import web_app
        import merchants
        monkeypatch.setattr(merchants, "UNITS_PER_COIN", units_per_coin)
        monkeypatch.setattr(web_app, "_get_merchant_rpc", lambda: fake)
        monkeypatch.setattr(web_app, "_MERCHANT_RECV_TTL", 0)  # disable cache
        web_app._merchant_recv_cache.clear()

    def test_selects_rpc_when_node_configured(self, monkeypatch):
        import web_app
        monkeypatch.delenv("DEMO_MODE", raising=False)
        monkeypatch.setenv("BIGCOIN_RPC_USER", "u")
        assert web_app._merchant_use_rpc() is True

    def test_forced_demo_mode_uses_local_chain(self, monkeypatch):
        import web_app
        monkeypatch.setenv("DEMO_MODE", "1")
        monkeypatch.setenv("BIGCOIN_RPC_USER", "u")
        assert web_app._merchant_use_rpc() is False

    def test_scantxoutset_amount_converts_to_base_units(self, monkeypatch):
        import web_app
        fake = self._FakeRpc("2.50000000")
        self._reset(monkeypatch, fake, units_per_coin=100000000)
        # 2.5 coins * 1e8 sats/coin == 250_000_000 base units.
        assert web_app.received_at_address_rpc("moon1abc") == 250000000

    def test_node_error_is_fail_safe_zero(self, monkeypatch):
        import web_app
        fake = self._FakeRpc("9.9", fail=True)
        self._reset(monkeypatch, fake)
        # A node outage must never fabricate a balance -> invoice stays pending.
        assert web_app.received_at_address_rpc("moon1abc") == 0

    def test_result_is_cached_within_ttl(self, monkeypatch):
        import web_app
        fake = self._FakeRpc("1.0")
        self._reset(monkeypatch, fake)
        monkeypatch.setattr(web_app, "_MERCHANT_RECV_TTL", 60)  # long TTL
        web_app._merchant_recv_cache.clear()
        web_app.received_at_address_rpc("moon1abc")
        web_app.received_at_address_rpc("moon1abc")
        assert fake.calls == 1  # second read served from cache
