"""Reactor address-network guardrail (explorer POST /api/mine).

A well-formed address for the WRONG network (e.g. a tmoon1… testnet address
sent to a mainnet node) is the common reactor footgun. The node rejects it with
a bare "invalid address"; these tests assert the explorer instead explains the
real problem — which network the address is for vs. which the node runs.

The explorer package uses bare imports (``import config``), so we add its dir to
sys.path and drive the route with a fake RPC client. No real node is used.
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
import config  # noqa: E402


class FakeClient:
    """Minimal RpcClient stand-in: rejects any address, reports a fixed chain."""

    def __init__(self, chain="main"):
        self._chain = chain

    def is_demo(self):
        return False

    def validateaddress(self, address):
        return {"isvalid": False}  # every address "invalid" -> guardrail path

    def getblockchaininfo(self):
        return {"chain": self._chain}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(config, "MINING_ENABLED", True)
    app = Flask(__name__)
    app.register_blueprint(api.api)
    return app.test_client()


def _mine(client, address):
    return client.post("/api/mine", json={"address": address})


def test_testnet_address_on_mainnet_node_explains_mismatch(client, monkeypatch):
    monkeypatch.setattr(api, "_client", lambda: FakeClient(chain="main"))
    r = _mine(client, "tmoon1qexampletestnetaddress")
    assert r.status_code == 400
    msg = r.get_json()["error"]
    assert "wrong network" in msg
    assert "testnet address" in msg and "mainnet" in msg
    assert "moon1" in msg  # tells them what to use


def test_regtest_address_on_mainnet_node_explains_mismatch(client, monkeypatch):
    monkeypatch.setattr(api, "_client", lambda: FakeClient(chain="main"))
    r = _mine(client, "rmoon1qexampleregtestaddr")
    assert r.status_code == 400
    assert "regtest address" in r.get_json()["error"]


def test_unrecognized_address_falls_back_to_generic(client, monkeypatch):
    monkeypatch.setattr(api, "_client", lambda: FakeClient(chain="main"))
    r = _mine(client, "totally-not-an-address")
    assert r.status_code == 400
    assert r.get_json()["error"] == "invalid MoonBite address"


def test_pure_classifier_matrix():
    assert api._classify_address_network("tmoon1abc") == "test"
    assert api._classify_address_network("rmoon1abc") == "regtest"
    assert api._classify_address_network("moon1abc") == "main"
    assert api._classify_address_network("???") is None
    # No mismatch when the address matches the node's chain.
    assert api._wrong_network_hint("moon1abc", "main") is None
    assert api._wrong_network_hint("tmoon1abc", "main") is not None
