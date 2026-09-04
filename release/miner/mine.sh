#!/usr/bin/env bash
# MoonBite solo miner - Linux & macOS.
#
# Solo and pool-free: this runs a full MoonBite node on your machine and mines
# straight to YOUR wallet address. No pool, no account, no middleman.
#
#   ./mine.sh moon1yourwalletaddress   mine rewards to your wallet
#   ./mine.sh                          use the saved address (or ask you for one)
#   ./mine.sh address                  print the reward address in use
#   ./mine.sh stop                     stop the node
#
# Get your address from the MoonBite wallet app (or moonbite.org/wallet):
# create a wallet, open Receive, and copy the moon1... address.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON="$HERE/moonbited";     [ -x "$DAEMON" ] || DAEMON="$(command -v moonbited || true)"
CLIBIN="$HERE/moonbite-cli";  [ -x "$CLIBIN" ] || CLIBIN="$(command -v moonbite-cli || true)"
[ -x "$DAEMON" ] || { echo "moonbited not found next to this script or on PATH." >&2; exit 1; }

DATADIR="${MOONBITE_DATADIR:-$HOME/.moonbite}"
CONF="$DATADIR/moonbite.conf"
REWARD_FILE="$DATADIR/reward-address.txt"
cli() { "$CLIBIN" -datadir="$DATADIR" -conf="$CONF" "$@"; }
node_pid() { pgrep -f "moonbited -datadir=$DATADIR" 2>/dev/null | head -1; }

is_addr() { case "$1" in moon1[0-9a-z]*) [ ${#1} -ge 26 ] && [ ${#1} -le 90 ];; *) return 1;; esac; }

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
# Live MoonBite seed node - how your miner finds the network.
addnode=67.205.154.64:9444
CONF
  chmod 600 "$CONF"
}

wait_rpc() {
  local i; for i in $(seq 1 60); do cli getblockcount >/dev/null 2>&1 && return 0; sleep 2; done
  echo "node did not start (check $DATADIR/debug.log)" >&2; return 1
}
start_node() {
  cli getblockcount >/dev/null 2>&1 && return 0
  write_conf
  "$DAEMON" -datadir="$DATADIR" -conf="$CONF" -daemon >/dev/null
  wait_rpc
}

# Where mining rewards go. Priority: CLI arg, env, saved file, prompt, then a
# local node wallet as a last resort (with a clear warning).
resolve_reward_address() {
  local cand="${1:-}"
  if [ -n "$cand" ] && is_addr "$cand"; then printf '%s' "$cand" > "$REWARD_FILE"; echo "$cand"; return; fi
  if [ -n "${MOONBITE_ADDRESS:-}" ] && is_addr "$MOONBITE_ADDRESS"; then printf '%s' "$MOONBITE_ADDRESS" > "$REWARD_FILE"; echo "$MOONBITE_ADDRESS"; return; fi
  if [ -s "$REWARD_FILE" ]; then local a; a=$(cat "$REWARD_FILE"); if is_addr "$a"; then echo "$a"; return; fi; fi
  if [ -t 0 ]; then
    echo "Paste the MoonBite wallet address to receive your mining rewards" >&2
    echo "(from the wallet app / moonbite.org/wallet - Receive tab, moon1...):" >&2
    local a; read -r a
    if is_addr "$a"; then printf '%s' "$a" > "$REWARD_FILE"; echo "$a"; return; fi
    echo "That did not look like a moon1 address." >&2; exit 1
  fi
  # Non-interactive, no address: fall back to a local node wallet.
  cli createwallet wallet >/dev/null 2>&1 || cli loadwallet wallet >/dev/null 2>&1 || true
  local a; a=$(cli -rpcwallet=wallet getnewaddress "mining"); printf '%s' "$a" > "$REWARD_FILE"
  echo "$a"
}

case "${1:-mine}" in
  address)
    start_node; echo "Rewards go to: $(resolve_reward_address)"
    ;;
  stop)
    pkill -f "moonbite-cli.*generatetoaddress" 2>/dev/null || true
    cli stop 2>/dev/null || true
    for _ in $(seq 1 20); do [ -z "$(node_pid)" ] && break; sleep 2; done
    p=$(node_pid); [ -n "$p" ] && kill "$p" 2>/dev/null || true
    for _ in $(seq 1 10); do [ -z "$(node_pid)" ] && break; sleep 1; done
    p=$(node_pid); [ -n "$p" ] && kill -9 "$p" 2>/dev/null || true
    echo "stopped."
    ;;
  mine|*)
    ARG=""; case "${1:-}" in moon1*) ARG="$1";; esac
    start_node
    ADDR=$(resolve_reward_address "$ARG")
    echo "======================================================================"
    echo " MoonBite solo miner"
    echo " Rewards to: $ADDR"
    echo " Ctrl-C to stop. Coins are spendable 100 blocks after they are mined."
    echo "======================================================================"
    trap 'echo; echo "Miner stopped. Node still running - ./mine.sh stop to shut it down."; exit 0' INT
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
      OUT=$(cli generatetoaddress 1 "$ADDR" "${MAXTRIES:-100000}" 2>/dev/null || true)
      if printf '%s' "$OUT" | grep -q '"[0-9a-f]\{64\}"'; then
        FOUND=$((FOUND+1))
        echo "  BLOCK FOUND!  height $(cli getblockcount)   (you have found $FOUND this session)   peers $(cli getconnectioncount)"
      fi
      sleep 1
    done
    ;;
esac
