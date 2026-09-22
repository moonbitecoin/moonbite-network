#!/usr/bin/env python3
"""MoonBite CPU Miner -- one command, any laptop, real proof-of-work.

This is a standalone miner, separate from the wallet. It runs a MoonBite full
node on THIS machine, connects it to the network seeds, and mines with your
CPU to the reward address you give it. The node performs the RandomX
proof-of-work, so this is genuine mining -- no browser tricks, no server doing
the work for you.

    python moonbite-miner.py --address moon1yourrewardaddress

If you leave off --address it will ask. Everything else has sane defaults.

What it does, plainly:
  1. finds the moonbited node binary (or tells you where to get it),
  2. writes a minimal config that dials the seeds,
  3. starts the node and waits for it to sync the chain,
  4. mines to your address and prints blocks found + a live rate,
  5. stops the node cleanly when you press Ctrl+C.

Honest requirements:
  * RandomX needs about 3.3 GB of free RAM. A normal laptop is fine; a tiny
    cloud box is not (it will be killed by the OS).
  * The first run downloads and verifies the chain before mining can start.
    That can take a while; leave it running.
  * Your reward address is the ONLY thing that decides where coins go. This
    program never asks for, sees, or stores a seed phrase or private key.

Standard library only -- no pip install.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import platform
import secrets
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

APP_NAME = "MoonBite CPU Miner"
DEFAULT_SEEDS = "67.205.154.64:9444"
DEFAULT_RPC_PORT = 9445
RANDOMX_MIN_RAM_GB = 3.3

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


# --------------------------------------------------------------------------- #
# Minimal JSON-RPC client (same shape as miner/moonbite_miner.py)
# --------------------------------------------------------------------------- #
class RpcError(Exception):
    pass


class Rpc:
    def __init__(self, port, user, password, timeout=30):
        self.url = f"http://127.0.0.1:{port}/"
        self.user, self.password, self.timeout = user, password, timeout
        self._id = 0

    def call(self, method, *params):
        self._id += 1
        payload = json.dumps(
            {"jsonrpc": "1.0", "id": self._id, "method": method, "params": list(params)}
        ).encode()
        req = urllib.request.Request(self.url, data=payload)
        req.add_header("Content-Type", "application/json")
        token = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                err = json.loads(exc.read().decode()).get("error")
                if err:
                    raise RpcError(err.get("message", str(err)))
            except (ValueError, AttributeError):
                pass
            raise RpcError(f"node returned HTTP {exc.code}")
        except (TimeoutError, urllib.error.URLError, ConnectionError, OSError) as exc:
            raise RpcError(f"node not reachable yet ({getattr(exc, 'reason', exc)})")
        if data.get("error"):
            raise RpcError(data["error"].get("message", str(data["error"])))
        return data.get("result")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def say(msg=""):
    print(msg, flush=True)


def die(msg, code=1):
    print(f"\n  ERROR: {msg}\n", file=sys.stderr)
    sys.exit(code)


def is_windows():
    return os.name == "nt"


def node_binary(explicit):
    """Locate the moonbited node binary. Order: --node, env, next to this app,
    the repo's release dir, then PATH."""
    exe = "moonbited.exe" if is_windows() else "moonbited"
    candidates = []
    if explicit:
        candidates.append(explicit)
    if os.environ.get("MOONBITE_NODE"):
        candidates.append(os.environ["MOONBITE_NODE"])
    candidates += [
        os.path.join(HERE, exe),
        os.path.join(HERE, "bin", exe),
        os.path.join(REPO, "release", "miner", exe),
        os.path.join(REPO, "release", "bin", exe),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    found = shutil.which("moonbited") or shutil.which(exe)
    return found


def default_datadir():
    if is_windows():
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "MoonBite")
    if platform.system() == "Darwin":
        return os.path.expanduser("~/Library/Application Support/MoonBite")
    return os.path.expanduser("~/.moonbite")


def free_ram_gb():
    """Best-effort free RAM in GB; None if it cannot be determined portably."""
    try:
        if hasattr(os, "sysconf") and "SC_AVPHYS_PAGES" in os.sysconf_names:
            return (os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")) / 1e9
    except (ValueError, OSError):
        pass
    if is_windows():
        try:
            import ctypes

            class MEMSTAT(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            m = MEMSTAT()
            m.dwLength = ctypes.sizeof(MEMSTAT)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullAvailPhys / 1e9
        except Exception:
            return None
    return None


def write_conf(conf_path, seeds, rpc_port):
    """Write a minimal, private-by-default miner config. Reuse an existing RPC
    password so a restart does not orphan a still-running node."""
    password = None
    if os.path.isfile(conf_path):
        for line in open(conf_path, encoding="utf-8", errors="ignore"):
            if line.startswith("rpcpassword="):
                password = line.split("=", 1)[1].strip()
                break
    password = password or secrets.token_hex(24)

    lines = [
        "# Generated by moonbite-miner.py -- safe to delete; it will be recreated.",
        "server=1",
        "listen=1",
        "txindex=1",
        "dbcache=512",
        "port=9444",
        f"rpcport={rpc_port}",
        "rpcbind=127.0.0.1",
        "rpcallowip=127.0.0.1",
        "rpcuser=moonminer",
        f"rpcpassword={password}",
    ]
    for s in [x.strip() for x in seeds.split(",") if x.strip()]:
        lines.append(f"addnode={s}")

    fd = os.open(conf_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return "moonminer", password


def wait_for_rpc(rpc, timeout=120):
    """Block until the node answers RPC, or time out."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            rpc.call("getblockchaininfo")
            return True
        except RpcError:
            time.sleep(1)
    return False


def wait_for_sync(rpc):
    """Show sync progress until the node is caught up enough to mine."""
    say("  Syncing the chain (first run can take a while)...")
    last = -1
    while True:
        try:
            info = rpc.call("getblockchaininfo")
        except RpcError:
            time.sleep(2)
            continue
        blocks = info.get("blocks", 0)
        headers = info.get("headers", 0)
        ibd = info.get("initialblockdownload", False)
        peers = _peers(rpc)
        if headers and blocks != last:
            pct = (blocks / headers * 100) if headers else 0
            say(f"    height {blocks}/{headers} ({pct:5.1f}%)  peers: {peers}")
            last = blocks
        # Caught up: not in initial download and tip matches known headers.
        if not ibd and headers and blocks >= headers:
            return
        if peers == 0:
            say("    (waiting for peers -- check your internet / firewall)")
        time.sleep(3)


def _peers(rpc):
    try:
        return rpc.call("getconnectioncount")
    except RpcError:
        return 0


def human_rate(blocks, seconds):
    if blocks <= 0 or seconds <= 0:
        return "warming up"
    per_hr = blocks / seconds * 3600
    return f"~{per_hr:.1f} blocks/hour"


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv=None):
    p = argparse.ArgumentParser(
        prog="moonbite-miner",
        description="Standalone MoonBite CPU miner (runs a local node and mines to your address).",
    )
    p.add_argument("--address", default=os.environ.get("MINE_ADDRESS", ""),
                   help="Reward address that receives mined coins (moon1... or M...).")
    p.add_argument("--node", default="", help="Path to the moonbited binary (auto-detected if omitted).")
    p.add_argument("--datadir", default=os.environ.get("MOONBITE_DATADIR", ""),
                   help="Chain data directory (default: per-OS app data dir).")
    p.add_argument("--seeds", default=os.environ.get("MOONBITE_SEEDS", DEFAULT_SEEDS),
                   help="Comma-separated seed host:port list.")
    p.add_argument("--rpc-port", type=int, default=int(os.environ.get("MOONBITE_RPC_PORT", DEFAULT_RPC_PORT)))
    p.add_argument("--blocks", type=int, default=0, help="Stop after N blocks (0 = mine forever).")
    p.add_argument("--maxtries", type=int, default=1_000_000, help="PoW attempts per round.")
    p.add_argument("--skip-sync-wait", action="store_true",
                   help="Start mining as soon as RPC is up (advanced; may mine on a stale tip).")
    args = p.parse_args(argv)

    say("=" * 60)
    say(f"  {APP_NAME}")
    say("=" * 60)

    # 1. Reward address
    address = args.address.strip()
    if not address:
        try:
            address = input("  Your MoonBite reward address (moon1... or M...): ").strip()
        except (EOFError, KeyboardInterrupt):
            die("no address given")
    if not address:
        die("a reward address is required -- that is where your mined coins go")

    # 2. Node binary
    node = node_binary(args.node)
    if not node:
        die("could not find the 'moonbited' node binary.\n"
            "  Download the signed release for your OS from https://moonbite.org/download,\n"
            "  put moonbited(.exe) next to this app (or in a 'bin' folder), or pass --node <path>.")

    # 3. RAM check (advisory only)
    ram = free_ram_gb()
    if ram is not None and ram < RANDOMX_MIN_RAM_GB:
        say(f"  WARNING: only ~{ram:.1f} GB RAM free; RandomX wants ~{RANDOMX_MIN_RAM_GB} GB.")
        say("           Mining may be killed by the OS. Close other apps and retry.")

    # 4. Config
    datadir = args.datadir or default_datadir()
    os.makedirs(datadir, exist_ok=True)
    conf = os.path.join(datadir, "moonbite.conf")
    user, password = write_conf(conf, args.seeds, args.rpc_port)

    say(f"  Node   : {node}")
    say(f"  Data   : {datadir}")
    say(f"  Seeds  : {args.seeds}")
    say(f"  Reward : {address}")
    say(f"  RPC    : 127.0.0.1:{args.rpc_port} (private)")
    say("-" * 60)

    # 5. Start the node as a managed child process (no -daemon: we own it).
    say("  Starting node...")
    proc = subprocess.Popen(
        [node, f"-datadir={datadir}", f"-conf={conf}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    rpc = Rpc(args.rpc_port, user, password)

    def shutdown(*_):
        say("\n  Stopping node...")
        try:
            rpc.call("stop")
        except RpcError:
            proc.terminate()
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
        say("  Stopped. Your coins are on-chain and safe.\n")

    try:
        if not wait_for_rpc(rpc):
            proc.terminate()
            die("node did not come up in time -- check that the binary matches your OS")

        if not args.skip_sync_wait:
            wait_for_sync(rpc)

        say("-" * 60)
        say("  Mining. Press Ctrl+C to stop.\n")
        mined, started = 0, time.time()
        while args.blocks == 0 or mined < args.blocks:
            if proc.poll() is not None:
                die("the node process exited unexpectedly (out of memory?)")
            try:
                hashes = rpc.call("generatetoaddress", 1, address, args.maxtries)
            except RpcError as exc:
                die(f"mining call failed: {exc}\n  (is the reward address valid for this network?)")
            if hashes:
                mined += len(hashes)
                elapsed = time.time() - started
                try:
                    height = rpc.call("getblockcount")
                except RpcError:
                    height = "?"
                for h in hashes:
                    say(f"  [+] block mined  height={height}  hash={h}")
                say(f"      session: {mined} block(s)  ({human_rate(mined, elapsed)})\n")
        say(f"  Done: {mined} block(s) mined.")
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()
    return 0


if __name__ == "__main__":
    # Make Ctrl+C behave the same on Windows and Unix.
    try:
        signal.signal(signal.SIGINT, signal.default_int_handler)
    except (ValueError, OSError):
        pass
    raise SystemExit(main())
