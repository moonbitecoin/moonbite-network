"""MAX BOUNTY AUDITOR — regression guard for explorer POST /api/mine.

Finding: the explorer's mining relay had NO per-client rate limit, so a single
IP could poll it without bound and lean on the node's PoW budget. It now wears
the same in-process limiter as /tx/broadcast. These tests assert the SECURE
behaviour — a burst from one client is throttled, while CORS preflight is not —
so any regression re-opens the finding as a failing test. No real node is used.

Run:  python -m pytest tests/security/test_poc_mine_ratelimit.py -v
"""

import os
import sys

import pytest
from flask import Flask

_EXPLORER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "explorer",
)
if _EXPLORER_DIR not in sys.path:
    sys.path.insert(0, _EXPLORER_DIR)

import api  # noqa: E402
import config  # noqa: E402


class MiningClient:
    """RpcClient stand-in whose address is valid and whose node always mines."""

    def is_demo(self):
        return False

    def validateaddress(self, address):
        return {"isvalid": True}

    def getblockcount(self):
        return 100

    def generatetoaddress(self, n, address, maxtries):
        return ["ab" * 32]


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(config, "MINING_ENABLED", True)
    monkeypatch.setattr(api, "_client", lambda: MiningClient())
    api._rl_hits.clear()
    app = Flask(__name__)
    app.register_blueprint(api.api)
    yield app.test_client()
    api._rl_hits.clear()


def test_mine_endpoint_is_rate_limited(client):
    """10/60 cap: a 15-request burst from one client yields at most 10 successes
    and at least one 429 (with a Retry-After hint) — the flood is throttled."""
    statuses = []
    saw_retry_after = False
    for _ in range(15):
        r = client.post("/api/mine", json={"address": "moon1validlooking"})
        statuses.append(r.status_code)
        if r.status_code == 429:
            saw_retry_after = saw_retry_after or bool(r.headers.get("Retry-After"))

    assert 429 in statuses, "/api/mine is NOT rate limited — regression!"
    assert statuses.count(200) <= 10
    assert saw_retry_after, "429 response is missing a Retry-After header"


def test_mine_cors_preflight_is_not_throttled(client):
    """A browser miner sends an OPTIONS preflight before each POST. Preflights
    must NOT consume the client's quota, so 20 of them all succeed (204)."""
    for _ in range(20):
        r = client.open("/api/mine", method="OPTIONS")
        assert r.status_code == 204
