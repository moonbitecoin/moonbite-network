#!/usr/bin/env bash
# MoonBite solo miner - Linux & macOS.
#
# Mining is solo and pool-free: this runs a full MoonBite node on your machine
# and mines directly to your own wallet. No pool, no middleman, no account.
# Every block you find pays you, and only you.
#
#   ./mine.sh            start the node and mine
#   ./mine.sh address    just print your mining address
#   ./mine.sh stop       stop the node
#
# Your wallet lives in the data directory below. BACK IT UP - lose it and you
# lose the coins.
set -euo pipefail

# --- locate the binaries (next to this script, or on PATH) ---
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON="$HERE/moonbited";     [ -x "$DAEMON" ] || DAEMON="$(command -v moonbited || true)"
CLIBIN="$HERE/moonbite-cli";  [ -x "$CLIBIN" ] || CLIBIN="$(command -v moonbite-cli || true)"
[ -x "$DAEMON" ] || { echo "moonbited not found next to this script or on PATH." >&2; exit 1; }

DATADIR="${MOONBITE_DATADIR:-$HOME/.moonbite}"
CONF="$DATADIR/moonbite.conf"
WALLET=wallet
cli() { "$CLIBIN" -datadir="$DATADIR" -conf="$CONF" "$@"; }

# Find the running daemon by command line: Core renames its thread on shutdown,
# so a name match misses a process that is still alive.
node_pid() { pgrep -f "moonbited -datadir=$DATADIR" 2>/dev/null | head -1; }

write_conf() {
  mkdir -p "$DATADIR"
  local pw; pw=$(sed -n 's/^rpcpassword=//p' "$CONF" 2>/dev/null | head -1) || true
  [ -z "$pw" ] && pw=$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')
  cat > "$CONF" <<CONF
server=1
listen=1
dbcache=512
rpcuser=moonminer
rpcpassword=$pw
# Live MoonBite seed nodes - how your miner finds the network.
addnode=67.205.154.64:9444
CONF
  chmod 600 "$CONF"
}

wait_rpc() {
  local i; for i in $(seq 1 60); do cli getblockcount >/dev/null 2>&1 && return 0; sleep 2; done
  echo "node did not start (check $DATADIR/debug.log)" >&2; return 1
}

start_node() {
  [ -x "$DAEMON" ] || exit 1
  if cli getblockcount >/dev/null 2>&1; then return 0; fi
  write_conf
  "$DAEMON" -datadir="$DATADIR" -conf="$CONF" -daemon >/dev/null
  wait_rpc
}

ensure_wallet() {
  cli createwallet "$WALLET" >/dev/null 2>&1 || cli loadwallet "$WALLET" >/dev/null 2>&1 || true
}

mining_address() {
  local f="$DATADIR/mining-address.txt"
  if [ -s "$f" ]; then cat "$f"; return; fi
  local a; a=$(cli -rpcwallet="$WALLET" getnewaddress "mining")
  printf '%s' "$a" > "$f"; echo "$a"
}

case "${1:-mine}" in
  address)
    start_node; ensure_wallet; echo "Your mining address: $(mining_address)"
    ;;
  stop)
    # A generatetoaddress call in flight keeps the daemon busy so `cli stop`
    # appears to hang; kill the miner call first, then ask the node to stop.
    pkill -f "moonbite-cli.*generatetoaddress" 2>/dev/null || true
    cli stop 2>/dev/null || true
    for _ in $(seq 1 20); do [ -z "$(node_pid)" ] && break; sleep 2; done
    p=$(node_pid); [ -n "$p" ] && kill "$p" 2>/dev/null || true
    for _ in $(seq 1 10); do [ -z "$(node_pid)" ] && break; sleep 1; done
    p=$(node_pid); [ -n "$p" ] && kill -9 "$p" 2>/dev/null || true
    echo "stopped."
    ;;
  mine)
    start_node; ensure_wallet
    ADDR=$(mining_address)
    echo "======================================================================"
    echo " MoonBite solo miner"
    echo " Mining to: $ADDR"
    echo " Wallet:    $DATADIR/$WALLET   (back this up)"
    echo " Ctrl-C to stop. Coins are spendable 100 blocks after they are mined."
    echo "======================================================================"
    trap 'echo; echo "Miner stopped. Node still running - ./mine.sh stop to shut it down."; exit 0' INT
    # Do not mine until the node has caught up to the network tip. Mining on a
    # stale tip only produces blocks the network rejects (bad-cb-height) and
    # burns CPU. Wait for headers to be reached and IBD to finish.
    echo " Syncing with the network before mining..."
    while :; do
      ibd=$(cli getblockchaininfo 2>/dev/null | sed -n 's/.*"initialblockdownload": *\(true\|false\).*/\1/p' | head -1)
      bl=$(cli getblockcount 2>/dev/null || echo 0)
      hd=$(cli getblockchaininfo 2>/dev/null | sed -n 's/.*"headers": *\([0-9]*\).*/\1/p' | head -1)
      [ "$ibd" = "false" ] && [ -n "$hd" ] && [ "$bl" -ge "$hd" ] && break
      echo "   ...$bl / ${hd:-?} blocks"; sleep 3
    done
    echo " Synced at height $(cli getblockcount). Mining now."
    FOUND=0
    while :; do
      # generatetoaddress returns a JSON array of the hashes it actually found;
      # trust that, not a height delta (the height also moves when a peer's
      # block arrives, which is not a block you mined).
      OUT=$(cli generatetoaddress 1 "$ADDR" "${MAXTRIES:-100000}" 2>/dev/null || true)
      if printf '%s' "$OUT" | grep -q '"[0-9a-f]\{64\}"'; then
        FOUND=$((FOUND+1))
        echo "  BLOCK FOUND!  height $(cli getblockcount)   (you have found $FOUND this session)   peers $(cli getconnectioncount)"
      fi
      sleep 1
    done
    ;;
  *) sed -n '3,12p' "$0"; exit 1 ;;
esac
