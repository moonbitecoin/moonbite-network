"""Durable files must land on the volume when there is one.

Getting this wrong is quiet and expensive: files written beside the code look
perfectly fine until a redeploy throws the container away, taking the chain,
the wall and every wallet's history with it.
"""

import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import storage  # noqa: E402
from block import genesis_block  # noqa: E402
from store import BlockStore  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("MOONBITE_DATA_DIR", raising=False)
    monkeypatch.delenv("MOONBITE_WALL_DB", raising=False)
    monkeypatch.delenv("MOONBITE_WALLET_HISTORY_DB", raising=False)


def test_explicit_data_dir_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("MOONBITE_DATA_DIR", str(tmp_path))
    assert storage.data_dir() == str(tmp_path)
    assert storage.data_path("wall.db") == os.path.join(str(tmp_path), "wall.db")
    assert storage.is_persistent() is True


def test_falls_back_to_the_app_directory(monkeypatch):
    # No volume: files belong beside the code, which is what a developer
    # running this locally expects to find.
    monkeypatch.setattr(storage, "_CONVENTIONAL_MOUNT", "/definitely-not-mounted")
    assert storage.data_dir() == storage._APP_DIR
    assert storage.is_persistent() is False


def test_conventional_mount_is_used_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_CONVENTIONAL_MOUNT", str(tmp_path))
    assert storage.data_dir() == str(tmp_path)
    assert storage.is_persistent() is True


def test_per_file_override_beats_the_data_dir(tmp_path, monkeypatch):
    # An existing deployment that sets the old per-file variables must keep
    # working exactly as it did.
    monkeypatch.setenv("MOONBITE_DATA_DIR", str(tmp_path / "vol"))
    target = tmp_path / "elsewhere" / "wall.db"
    monkeypatch.setenv("MOONBITE_WALL_DB", str(target))
    assert storage.data_path("wall.db", "MOONBITE_WALL_DB") == str(target)


def test_missing_parent_directories_are_created(tmp_path, monkeypatch):
    # sqlite's error for a missing directory is "unable to open database
    # file", which names neither the file nor the reason.
    target = tmp_path / "deep" / "nested" / "wall.db"
    monkeypatch.setenv("MOONBITE_WALL_DB", str(target))
    storage.data_path("wall.db", "MOONBITE_WALL_DB")
    assert target.parent.is_dir()


def test_data_dir_is_created_if_absent(tmp_path, monkeypatch):
    target = tmp_path / "not-yet-there"
    monkeypatch.setenv("MOONBITE_DATA_DIR", str(target))
    assert storage.data_dir() == str(target)
    assert target.is_dir()


# --------------------------------------------------------------------------- #
# BlockStore threading
# --------------------------------------------------------------------------- #
def test_block_store_is_writable_from_another_thread(tmp_path):
    """The regression: mining runs in a worker thread.

    The connection is opened wherever the node is first built, so a store that
    refuses cross-thread use raised on every persist. Blocks were mined, never
    stored, and the chain reloaded empty — persistence that silently did
    nothing.
    """
    store = BlockStore(str(tmp_path / "chain.db"))
    block = genesis_block()
    error = {}

    def persist():
        try:
            store.save_block(block, 0)
        except Exception as e:  # noqa: BLE001
            error["e"] = e

    t = threading.Thread(target=persist)
    t.start()
    t.join()

    assert not error, f"cross-thread persist failed: {error.get('e')}"
    assert store.count() == 1
    store.close()


def test_block_store_survives_concurrent_writers(tmp_path):
    store = BlockStore(str(tmp_path / "chain.db"))
    block = genesis_block()
    errors = []

    def hammer():
        for _ in range(20):
            try:
                store.save_block(block, 0)
                store.count()
            except Exception as e:  # noqa: BLE001
                errors.append(e)

    threads = [threading.Thread(target=hammer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent access failed: {errors[:3]}"
    assert store.count() == 1  # same block, upserted
    store.close()


# --------------------------------------------------------------------------- #
# End to end: a redeploy is a new process against the same directory
# --------------------------------------------------------------------------- #
def _run(code, data_dir):
    env = dict(os.environ, MOONBITE_DATA_DIR=str(data_dir), PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO, env=env,
        capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return proc.stdout.strip().splitlines()[-1]


def test_wall_entry_outlives_the_process(tmp_path):
    write = """
import web_app, wall
from wallet import derive_from_seed_phrase
addr = derive_from_seed_phrase('storage persistence test phrase for the wall')['address']
wall.add(address=addr, handle='persisted', country='XX', height=1, reward=50,
         verify_blocks=lambda a: 1)
print('written')
"""
    assert _run(write, tmp_path) == "written"

    read = """
import json, web_app
c = web_app.app.test_client()
d = json.loads(c.get('/api/wall?limit=5').get_data(as_text=True))
print(d['total'])
"""
    assert _run(read, tmp_path) == "1", "the wall forgot across a restart"
