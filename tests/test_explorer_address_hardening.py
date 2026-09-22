"""Explorer address-endpoint hardening (audit rpcweb findings).

The public explorer's /api/address/<addr>/{utxos,balance} routes drove an
unbounded scantxoutset walk on any input, with no rate limit, address check, or
cache — a node-resource DoS. These tests pin the fixes: junk input is rejected
before any scan, repeat lookups are served from a short cache, and the routes
are rate limited.

Same fake-client harness as test_explorer_mine_guardrail.py; no real node.
"""

import os
import sys

import pytest
from flask import Flask

_EXPLORER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "explorer"
)
if _EXPLORER_DIR not in sys.path:
    sys.path.insert(0, _EXPLORER_DIR)

import api  # noqa: E402


class FakeClient:
    """Records scantxoutset calls; treats only moon1… addresses as valid."""

    def __init__(self):
        self.scan_calls = 0
        self.validate_calls = 0

    def is_demo(self):
        return False

    def validateaddress(self, address):
        self.validate_calls += 1
        return {"isvalid": str(address).startswith("moon1")}

    def scantxoutset(self, action, scanobjects):
        self.scan_calls += 1
        return {"success": True, "height": 100, "unspents": []}


@pytest.fixture()
def env(monkeypatch):
    # Reset the module-global limiter + scan cache so tests are independent.
    api._rl_hits.clear()
    api._scan_cache.clear()
    fake = FakeClient()
    monkeypatch.setattr(api, "_client", lambda: fake)
    app = Flask(__name__)
    app.register_blueprint(api.api)
    return app.test_client(), fake


def test_invalid_address_returns_400_without_scanning(env):
    client, fake = env
    r = client.get("/api/address/not-an-address/utxos")
    assert r.status_code == 400
    assert r.get_json()["error"] == "invalid address"
    assert fake.scan_calls == 0  # the expensive walk never ran


def test_valid_address_scans_and_then_caches(env):
    client, fake = env
    a = "moon1qexampleexampleexampleexample"
    r1 = client.get(f"/api/address/{a}/utxos")
    r2 = client.get(f"/api/address/{a}/balance")
    assert r1.status_code == 200 and r2.status_code == 200
    # Second lookup within the TTL is served from cache: only ONE scan total.
    assert fake.scan_calls == 1


def test_rate_limit_trips_on_the_16th_call(env):
    client, fake = env
    a = "moon1qexampleexampleexampleexample"
    codes = [client.get(f"/api/address/{a}/utxos").status_code for _ in range(16)]
    assert codes[:15] == [200] * 15
    assert codes[15] == 429
