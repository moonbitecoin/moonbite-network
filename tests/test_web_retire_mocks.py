"""Retire the fabricated-data mock endpoints on the live site (audit rpcweb).

The plural /api/merchants/* invoice mock returned an unspendable payment address
and /api/hardware-wallet/* returned fake signatures, live in production. They are
now retired (410) in live mode, while the REAL singular /api/merchant/* API stays
live. These tests pin both halves.
"""

import web_app


def test_mock_routes_are_retired():
    assert web_app._is_retired_api("/api/merchants/create-invoice", "POST")
    assert web_app._is_retired_api("/api/merchants/invoice/inv_abc", "GET")
    assert web_app._is_retired_api("/api/hardware-wallet/sign", "POST")
    assert web_app._is_retired_api("/api/hardware-wallet/address", "POST")
    assert web_app._is_retired_api("/api/hardware-wallet/detect", "GET")


def test_real_singular_merchant_api_is_not_retired():
    # The plural prefix must not catch the real singular endpoints.
    assert not web_app._is_retired_api("/api/merchant/invoice", "POST")
    assert not web_app._is_retired_api("/api/merchant/invoices", "GET")
    assert not web_app._is_retired_api("/api/merchant/invoice/inv_abc/qr.svg", "GET")


def test_live_mode_returns_410_for_mock(monkeypatch):
    monkeypatch.setattr(web_app, "_merchant_use_rpc", lambda: True)
    c = web_app.app.test_client()
    assert c.post("/api/merchants/create-invoice", json={}).status_code == 410
    assert c.get("/api/hardware-wallet/detect").status_code == 410
