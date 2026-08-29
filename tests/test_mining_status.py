"""/api/mining/status must eventually say mining has stopped.

A finished job used to stay in the active-jobs dict forever, and the endpoint
derived "am I mining?" from that dict's size. So the first job pinned the
status at "mining" for the life of the process: any client polling "is it done
yet?" waited forever, and the dict grew by one entry per job.
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import web_app  # noqa: E402


@pytest.fixture
def client():
    web_app.app.config["TESTING"] = True
    with web_app.app.mining_lock:
        web_app.app.mining_state["active_jobs"].clear()
    with web_app.app.test_client() as c:
        yield c
    with web_app.app.mining_lock:
        web_app.app.mining_state["active_jobs"].clear()


def _status(client):
    res = client.get("/api/mining/status")
    assert res.status_code == 200
    return res.get_json()


def _add_job(job_id, **overrides):
    """Insert a job directly, so these tests do not depend on real mining."""
    job = {
        "is_mining": True,
        "blocks_to_mine": 5,
        "blocks_mined": 0,
        "hashes_tried": 0,
        "hashrate": 0.0,
    }
    job.update(overrides)
    with web_app.app.mining_lock:
        web_app.app.mining_state["active_jobs"][job_id] = job
    return job


def test_idle_when_no_jobs(client):
    s = _status(client)
    assert s["status"] == "idle"
    assert s["mining"] is False
    assert s["active_jobs"] == 0


def test_reports_mining_while_a_job_runs(client):
    _add_job("running", blocks_mined=2, hashrate=1234.5)
    s = _status(client)
    assert s["status"] == "mining"
    assert s["mining"] is True
    assert s["active_jobs"] == 1
    assert s["blocks_mined"] == 2
    assert s["combined_hashrate"] == 1234.5


def test_returns_to_idle_once_the_job_finishes(client):
    """The regression: a finished job must not keep the status at "mining"."""
    _add_job("done", is_mining=False, blocks_mined=5, finished_at=time.time())
    s = _status(client)
    assert s["mining"] is False
    assert s["status"] == "idle"
    assert s["active_jobs"] == 0


def test_final_block_count_survives_completion(client):
    # A UI polling just after the last block should still see the total, not a
    # sudden zero, so counters include recently finished jobs.
    _add_job("done", is_mining=False, blocks_mined=5, hashes_tried=99,
             finished_at=time.time())
    s = _status(client)
    assert s["blocks_mined"] == 5
    assert s["total_hashes_tried"] == 99
    assert s["retained_jobs"] == 1


def test_finished_jobs_are_eventually_pruned(client):
    _add_job("stale", is_mining=False, blocks_mined=5,
             finished_at=time.time() - web_app._FINISHED_JOB_RETENTION_SEC - 1)
    s = _status(client)
    assert s["retained_jobs"] == 0, "a long-finished job should be dropped"
    with web_app.app.mining_lock:
        assert "stale" not in web_app.app.mining_state["active_jobs"]


def test_a_running_job_is_never_pruned(client):
    _add_job("long", is_mining=True,
             finished_at=time.time() - web_app._FINISHED_JOB_RETENTION_SEC - 1)
    s = _status(client)
    assert s["mining"] is True
    assert s["active_jobs"] == 1


def test_finished_job_does_not_inflate_hashrate(client):
    # Hashrate is instantaneous: a job that stopped contributes nothing.
    _add_job("running", hashrate=100.0)
    _add_job("done", is_mining=False, hashrate=900.0, finished_at=time.time())
    assert _status(client)["combined_hashrate"] == 100.0


def test_total_blocks_alias_is_present(client):
    # mining.html reads total_blocks; it drove a progress bar that always
    # showed 0% because the endpoint only returned total_blocks_target.
    _add_job("running", blocks_to_mine=7)
    s = _status(client)
    assert s["total_blocks"] == 7
    assert s["total_blocks_target"] == 7


def test_leaderboard_include_still_works(client):
    s = client.get("/api/mining/status?include=leaderboard").get_json()
    assert s["status"] in ("idle", "mining")
    assert isinstance(s["leaderboard"], list)
