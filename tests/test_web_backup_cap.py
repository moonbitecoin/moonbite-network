"""Backup-store DoS guard (audit rpcweb finding).

/api/wallet/backup/create is an unauthenticated flat-file writer. Before the fix
it had no rate limit and no cap, so a request loop filled the disk and took the
host (and its SQLite DBs) down. These tests pin the two bounds: a per-client rate
limit and a global file-count cap that returns 507 instead of exhausting disk.
"""

import pytest

import web_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)       # isolate the relative backups/ dir
    web_app._rl_hits.clear()          # independent rate-limit state per test
    web_app.app.config["TESTING"] = True
    return web_app.app.test_client()


def _post(client, seed="blob"):
    return client.post("/api/wallet/backup/create", json={"encryptedSeed": seed})


def test_global_cap_returns_507_instead_of_filling_disk(client, monkeypatch):
    monkeypatch.setattr(web_app, "_MAX_BACKUP_FILES", 2)
    assert _post(client, "a").status_code == 200
    assert _post(client, "b").status_code == 200
    r = _post(client, "c")            # store now full
    assert r.status_code == 507
    assert "full" in r.get_json()["error"]


def test_per_client_rate_limited(client, monkeypatch):
    # Rate limiting is globally disabled under pytest (web_app._RATE_DISABLED);
    # turn it back on to exercise the decorator on this route.
    monkeypatch.setattr(web_app, "_RATE_DISABLED", False)
    codes = [_post(client, str(i)).status_code for i in range(6)]
    assert codes[:5] == [200] * 5
    assert codes[5] == 429           # 6th within the window is refused
