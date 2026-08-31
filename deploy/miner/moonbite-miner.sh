#!/usr/bin/env bash
# Run a MoonBite full node and mine on it.
#
# The seed nodes cannot do this themselves. RandomX asks for roughly 3.3 GB of
# address space; the DigitalOcean seed has 458 MB (plus 2 GB of swap, which is
# not enough - it was still OOM-killed) and the Railway container is smaller.
# So mining has to live on a machine with real memory, and that machine talks
# to the seeds over ordinary P2P.
#
#   ./moonbite-miner.sh start     bring the node up and connect to the seeds
#   ./moonbite-miner.sh mine [N]  mine N blocks (default: forever)
#   ./moonbite-miner.sh status    height, peers, wallet balance
#   ./moonbite-miner.sh stop      stop the node
#
# Env:
#   MOONBITE_SRC      directory holding litecoind/litecoin-cli (built binaries)
#   MOONBITE_DATADIR  chain data + wallet          (default ~/.moonbite)
#   MOONBITE_SEEDS    comma-separated host:port    (default: the two live seeds)
set -euo pipefail

SRC="${MOONBITE_SRC:-/root/bigcoin-core/src}"
DATADIR="${MOONBITE_DATADIR:-/root/.moonbite}"
CONF="$DATADIR/moonbite.conf"
SEEDS="${MOONBITE_SEEDS:-67.205.154.64:9444,hayabusa.proxy.rlwy.net:14389}"
WALLET=miner

DAEMON="$SRC/litecoind"
CLIBIN="$SRC/litecoin-cli"
cli() { "$CLIBIN" -datadir="$DATADIR" -conf="$CONF" "$@"; }

write_conf() {
  mkdir -p "$DATADIR"
  # Preserve the RPC password across restarts; regenerating it would orphan any
  # running process still holding the old one.
  local pw
  # First run has no conf, so sed fails; under `set -e` an unguarded
  # assignment from a failing substitution kills the script silently.
  pw=$(sed -n 's/^rpcpassword=//p' "$CONF" 2>/dev/null | head -1) || true
  [ -z "$pw" ] && pw=$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')
  {
    echo "server=1"
    echo "listen=1"
    echo "txindex=1"
    echo "dbcache=1024"
    echo "port=9444"
    echo "rpcport=9445"
    echo "rpcuser=moonminer"
    echo "rpcpassword=$pw"
    # This host is typically behind NAT, so it dials the seeds rather than
    # waiting to be dialled.
    local s
    for s in ${SEEDS//,/ }; do echo "addnode=$s"; done
  } > "$CONF"
  chmod 600 "$CONF"
}

# Find the daemon by its command line, not its process name. Core renames its
# main thread once shutdown is requested ("b-shutoff"), so `pgrep -x litecoind`
# stops matching a daemon that is still very much alive - and every kill aimed
# that way misses silently while the process keeps running.
node_pid() { pgrep -f "litecoind -datadir=$DATADIR" | head -1; }

wait_rpc() {
  local i
  for i in $(seq 1 60); do
    cli getblockcount >/dev/null 2>&1 && return 0
    sleep 2
  done
  echo "node did not answer RPC within 120s" >&2
  return 1
}

ensure_wallet() {
  cli createwallet "$WALLET" >/dev/null 2>&1 || cli loadwallet "$WALLET" >/dev/null 2>&1 || true
  cli -rpcwallet="$WALLET" getwalletinfo >/dev/null 2>&1
}

mining_address() {
  # A stable address, so every block in a run pays the same place and the
  # coinbase history is one auditable line rather than a scatter of addresses.
  local f="$DATADIR/mining-address.txt"
  if [ -s "$f" ]; then cat "$f"; return; fi
  local a; a=$(cli -rpcwallet="$WALLET" getnewaddress "mining")
  echo "$a" > "$f"
  echo "$a"
}

case "${1:-status}" in
  start)
    [ -x "$DAEMON" ] || { echo "no daemon at $DAEMON (set MOONBITE_SRC)" >&2; exit 1; }
    if cli getblockcount >/dev/null 2>&1; then echo "already running"; else
      write_conf
      "$DAEMON" -datadir="$DATADIR" -conf="$CONF" -daemon >/dev/null
      wait_rpc
    fi
    ensure_wallet
    echo "node up   : height $(cli getblockcount), peers $(cli getconnectioncount)"
    echo "mining to : $(mining_address)"
    ;;

  mine)
    wait_rpc
    ensure_wallet
    ADDR=$(mining_address)
    TARGET="${2:-0}"          # 0 = keep going
    echo "mining to $ADDR (target: ${TARGET:-forever})"
    N=0
    while :; do
      H0=$(cli getblockcount)
      # One block per call, with a BOUNDED try budget. generatetoaddress holds
      # cs_main for the whole call, so a large budget does not "mine harder" -
      # it makes one call monopolise the node for hours: RPC stops answering,
      # net processing starves, and the node starts timing out its own peers.
      # Keep each call short and let the loop supply the persistence. A call
      # that finds nothing is normal, not an error.
      #
      # Measured on this host: ~496 H/s across 11 cores. A block at the
      # minimum difficulty (0.000244) needs ~1,048,576 hashes, so expect
      # roughly 35 minutes per block. 100k tries is ~3.5 minutes per call
      # with about a 1-in-10 hit rate, which keeps RPC responsive between
      # attempts instead of locking the node for the whole search.
      cli generatetoaddress 1 "$ADDR" "${MAXTRIES:-100000}" >/dev/null 2>&1 || true
      H1=$(cli getblockcount)
      if [ "$H1" -gt "$H0" ]; then
        N=$((N + 1))
        echo "  height $H1  (mined $N this run)  peers $(cli getconnectioncount)"
      fi
      [ "$TARGET" != "0" ] && [ "$N" -ge "$TARGET" ] && { echo "done: $N block(s)"; break; }
      sleep 1
    done
    ;;

  status)
    if ! cli getblockcount >/dev/null 2>&1; then echo "node not running"; exit 1; fi
    echo "height : $(cli getblockcount)"
    echo "tip    : $(cli getbestblockhash)"
    echo "peers  : $(cli getconnectioncount)"
    ensure_wallet
    echo "address: $(mining_address)"
    echo "balance: $(cli -rpcwallet="$WALLET" getbalances | tr -d '\n ' | head -c 200)"
    ;;

  stop)
    cli stop 2>/dev/null || true
    for _ in $(seq 1 20); do [ -z "$(node_pid)" ] && break; sleep 2; done
    # A long-running generatetoaddress holds cs_main and will not answer the
    # stop RPC, so fall back to the PID.
    PID=$(node_pid)
    if [ -n "$PID" ]; then echo "not responding to stop; killing $PID"; kill -9 "$PID"; sleep 3; fi
    rm -f "$DATADIR/.lock"
    echo "stopped"
    ;;

  *) sed -n '3,20p' "$0"; exit 1 ;;
esac
