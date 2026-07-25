"""MAX BOUNTY AUDITOR — web-layer PoCs, now REGRESSION GUARDS.

After the audit fixes landed, each formerly-exploitable test asserts the SECURE
behaviour instead, so any regression re-opens the finding as a failing test. NO
request ever touches the live moonbite.org.

Run:  python -m pytest tests/security/test_poc_web.py -v
"""

import pytest

import web_app


@pytest.fixture()
def client():
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c


# --------------------------------------------------------------------------- #
# FINDING #? path traversal on /downloads/<path:filename>  — PROVE-SAFE
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "payload",
    [
        "../web_app.py",
        "..%2f..%2fweb_app.py",
        "....//web_app.py",
        "%2e%2e/%2e%2e/exchange.py",
        "/etc/passwd",
    ],
)
def test_downloads_traversal_is_blocked(client, payload):
    """send_from_directory must reject any path that escapes website/downloads."""
    resp = client.get(f"/downloads/{payload}", follow_redirects=True)
    body = resp.get_data(as_text=True)
    assert resp.status_code in (400, 403, 404), (
        f"traversal {payload!r} returned {resp.status_code}"
    )
    assert "def api_notify" not in body
    assert "root:x:0:0" not in body


# --------------------------------------------------------------------------- #
# FINDING #1 (FIXED) — X-Forwarded-For spoofing no longer bypasses the limiter
# --------------------------------------------------------------------------- #
def test_xff_spoof_no_longer_bypasses_rate_limit(client, monkeypatch):
    """ProxyFix resolves remote_addr to the hop OUR proxy appended (rightmost),
    which the client cannot forge. We model nginx by appending the attacker's
    real IP as the final XFF hop: rotating the spoofed prefix no longer helps."""
    monkeypatch.setattr(web_app, "_RATE_DISABLED", False)
    web_app._rl_hits.clear()

    real_ip = "198.51.100.9"  # what nginx observes + appends for this attacker
    statuses = []
    for i in range(40):
        r = client.post(
            "/api/notify",
            json={"email": f"a{i}@example.com", "source": "poc"},
            # attacker forges the prefix, nginx appends the true last hop
            headers={"X-Forwarded-For": f"10.0.{i // 256}.{i % 256}, {real_ip}"},
        )
        statuses.append(r.status_code)

    # /api/notify is 10/60 → despite rotation, the attacker IS throttled now.
    assert 429 in statuses, "XFF spoofing STILL bypasses the limit — regression!"
    assert statuses.count(200) <= 10

    web_app._rl_hits.clear()


def test_distinct_real_clients_are_not_throttled_together(client, monkeypatch):
    """A genuinely different client (different real last hop) keeps its own bucket
    — the fix must not lump everyone into one global limit."""
    monkeypatch.setattr(web_app, "_RATE_DISABLED", False)
    web_app._rl_hits.clear()

    ok = 0
    for i in range(8):  # 8 different real clients, 1 request each — none throttled
        r = client.post(
            "/api/notify",
            json={"email": f"c{i}@example.com", "source": "poc"},
            headers={"X-Forwarded-For": f"70.0.0.{i}"},
        )
        ok += (r.status_code == 200)
    assert ok == 8
    web_app._rl_hits.clear()


# --------------------------------------------------------------------------- #
# FINDING #2 (FIXED) — wallet state is per-session, not process-global
# --------------------------------------------------------------------------- #
def test_wallet_balance_is_isolated_per_session():
    """Two separate clients (two session cookies) must NOT see each other's
    generated addresses. Server holds no global cross-user dict anymore."""
    a = web_app.app.test_client()
    b = web_app.app.test_client()

    # Client A generates two addresses.
    for _ in range(2):
        assert a.get("/api/wallet/new").status_code == 200
    with a.session_transaction() as sa:
        a_addrs = set(sa.get("wallet_pkhs", []))
    assert len(a_addrs) == 2

    # Client B generates one — and its session must contain ONLY its own.
    assert b.get("/api/wallet/new").status_code == 200
    with b.session_transaction() as sb:
        b_addrs = set(sb.get("wallet_pkhs", []))
    assert len(b_addrs) == 1
    assert a_addrs.isdisjoint(b_addrs)


# --------------------------------------------------------------------------- #
# FINDING #3 (FIXED) — per-session address set is bounded (no memory-DoS)
# --------------------------------------------------------------------------- #
def test_wallet_addresses_are_capped(client):
    """Generating far more than the cap must not grow state without bound."""
    for _ in range(200):
        client.get("/api/wallet/new")
    with client.session_transaction() as sess:
        stored = sess.get("wallet_pkhs", [])
    assert len(stored) <= web_app._MAX_SESSION_ADDRESSES


# --------------------------------------------------------------------------- #
# FINDING #4 (FIXED) — security headers now present on every response
# --------------------------------------------------------------------------- #
def test_security_headers_present(client):
    r = client.get("/")
    assert r.headers.get("Strict-Transport-Security", "").startswith("max-age=")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "default-src 'self'" in r.headers.get("Content-Security-Policy", "")
    assert r.headers.get("Referrer-Policy")


# --------------------------------------------------------------------------- #
# FINDING #5 (FIXED) — /api/mining/start caps the block count (no CPU-DoS)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "blocks", [10**9, web_app._MAX_MINE_BLOCKS + 1, 0, -5],
)
def test_mining_start_rejects_out_of_range_block_count(client, blocks):
    """An in-range int is fine; anything <=0 or above the cap is refused BEFORE a
    mining thread spins up, so one request can't pin a worker on endless PoW."""
    web_app.app.mining_state["is_mining"] = False
    r = client.post(
        "/api/mining/start",
        json={"address": "moon1validlooking", "blocks": blocks},
    )
    assert r.status_code == 400, f"blocks={blocks!r} was accepted"
    # The guard must reject before mining starts.
    assert web_app.app.mining_state["is_mining"] is False


@pytest.mark.parametrize("blocks", ["100", 1.5, True, None, [1]])
def test_mining_start_rejects_non_integer_block_count(client, blocks):
    """A string/float/bool/None/list 'blocks' is rejected as a type error — it can
    no longer slip past the <=0 check and crash (or mistype) the worker loop."""
    web_app.app.mining_state["is_mining"] = False
    r = client.post(
        "/api/mining/start",
        json={"address": "moon1validlooking", "blocks": blocks},
    )
    assert r.status_code == 400, f"blocks={blocks!r} was accepted"
    assert web_app.app.mining_state["is_mining"] is False


def test_mining_start_accepts_valid_capped_count(client, monkeypatch):
    """Positive control: a legitimate in-range count (the cap itself) is accepted.
    The worker is stubbed so the test asserts the guard, not real PoW."""
    web_app.app.mining_state["is_mining"] = False
    monkeypatch.setattr(web_app, "mining_worker", lambda *a, **k: None)
    addr = client.get("/api/wallet/new").get_json()["address"]

    r = client.post(
        "/api/mining/start",
        json={"address": addr, "blocks": web_app._MAX_MINE_BLOCKS},
    )
    assert r.status_code == 200
    assert r.get_json()["blocks_to_mine"] == web_app._MAX_MINE_BLOCKS

    web_app.app.mining_state["is_mining"] = False  # reset shared state
