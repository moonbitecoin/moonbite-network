"""Guards for the Railway seed-node deployment.

The node service was misconfigured in a way nothing caught: `railway.json`
pointed at `deploy/railway-node/Dockerfile`, which despite its directory name
builds the Flask web app. A node deployed from it had no daemon in it at all.
These tests assert the pieces that made that possible stay fixed.
"""

from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parent.parent / "deploy" / "railway-node"


def _read(name):
    return (DEPLOY / name).read_text(encoding="utf-8")


def test_node_image_exists_and_ships_the_daemon():
    src = _read("Dockerfile.node")
    assert "release/bin/moonbited" in src, "the node image does not copy the daemon"
    assert "entrypoint.sh" in src, "the node image does not use the node entrypoint"


def test_node_image_is_not_the_flask_app():
    """The failure mode: a 'node' that is actually a web server."""
    src = _read("Dockerfile.node")
    assert "requirements-web.txt" not in src
    assert "entrypoint-flask.sh" not in src


def test_node_base_matches_the_binary_toolchain():
    """The binary needs glibc >= 2.34 and Boost 1.74 - that is 22.04, not 24.04."""
    src = _read("Dockerfile.node")
    assert "ubuntu:22.04" in src
    assert "libboost-filesystem1.74.0" in src


def test_flask_dockerfile_says_it_is_not_the_node():
    """It keeps its confusing path, so it must at least announce what it is."""
    src = _read("Dockerfile")
    assert "NOT the seed node" in src


def test_entrypoint_accepts_the_documented_variable_names():
    """DEPLOY.md said BIGCOIN_RPC_*; the script demanded MOONBITE_RPC_* and
    exited. Either spelling must work or the deploy dies on line one."""
    src = _read("entrypoint.sh")
    assert "BIGCOIN_RPC_USER" in src and "BIGCOIN_RPC_PASSWORD" in src


@pytest.mark.parametrize("path", ["blocks", "chainstate", "indexes"])
def test_entrypoint_resets_stale_chain_state(path):
    """A persistent Volume outlives a consensus change; without this the node
    sits on the pre-50-MBITE fork and never syncs."""
    src = _read("entrypoint.sh")
    assert "EXPECTED_GENESIS" in src
    assert f'"$DATADIR"/{path}' in src


def test_entrypoint_reset_does_not_touch_wallets():
    src = _read("entrypoint.sh")
    guard = src[src.index("EXPECTED_GENESIS"):src.index('> "$STAMP"')]
    assert "wallets" not in guard, "the chain reset would delete wallet keys"


def test_deploy_doc_points_at_the_node_image():
    doc = (DEPLOY / "DEPLOY.md").read_text(encoding="utf-8")
    assert "deploy/railway-node/Dockerfile.node" in doc
    assert "release/bin/bigcoind" not in doc, "doc names a binary that no longer exists"
