#!/usr/bin/env bash
# ============================================================================
# Deploy (or upgrade) the MoonBite seed node on the DigitalOcean droplet.
#
# Run from a machine that holds the droplet SSH key (the WSL build box):
#   deploy/deploy-droplet-node.sh                 # uses release/bin/moonbited
#   deploy/deploy-droplet-node.sh /path/moonbited /path/moonbite-cli
#
# What it does on the droplet (idempotent):
#   1. installs moonbited / moonbite-cli to /usr/local/bin
#   2. if the node's genesis differs from the binary's, moves the old data
#      directory aside (never deleted) so the node restarts on the new chain
#   3. regenerates the addnode= lines in /etc/moonbite/moonbite.conf from
#      deploy/seeds.txt (RPC credentials are preserved)
#   4. restarts the systemd service and prints chain / peer / memory status
#
# Env: VPS (default root@67.205.154.64), SSH_KEY (default ~/.ssh/moonbite_vps)
# ============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
VPS="${VPS:-root@67.205.154.64}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/moonbite_vps}"
DAEMON="${1:-$REPO/release/bin/moonbited}"
CLIBIN="${2:-$REPO/release/bin/moonbite-cli}"
SEEDS="$HERE/seeds.txt"

[ -f "$DAEMON" ] && [ -f "$CLIBIN" ] || { echo "binaries not found: $DAEMON / $CLIBIN" >&2; exit 1; }
[ -f "$SSH_KEY" ] || { echo "ssh key not found: $SSH_KEY" >&2; exit 1; }
SSH=(ssh -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$VPS")

# The genesis hash baked into the binary we are shipping (regtest-free check:
# run it once locally against a throwaway datadir).
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
echo "==> Reading genesis from $DAEMON"
"$DAEMON" -datadir="$TMP" -listen=0 -dnsseed=0 -connect=0 -server -rpcport=29999 -rpcuser=g -rpcpassword=g -daemon=1 >/dev/null
for _ in $(seq 1 30); do
  G=$("$CLIBIN" -datadir="$TMP" -rpcport=29999 -rpcuser=g -rpcpassword=g getblockhash 0 2>/dev/null) && break; sleep 1
done
"$CLIBIN" -datadir="$TMP" -rpcport=29999 -rpcuser=g -rpcpassword=g stop >/dev/null 2>&1 || true
sleep 2
[ -n "${G:-}" ] || { echo "could not read genesis from the binary" >&2; exit 1; }
echo "    genesis: $G"

ADDNODES=$(grep -vE '^\s*(#|$)' "$SEEDS" | sed 's/^/addnode=/')

echo "==> Uploading binaries"
scp -q -i "$SSH_KEY" "$DAEMON" "$VPS:/root/moonbited.new"
scp -q -i "$SSH_KEY" "$CLIBIN" "$VPS:/root/moonbite-cli.new"

echo "==> Installing on $VPS"
"${SSH[@]}" "GENESIS=$G ADDNODES='$ADDNODES' bash -s" <<'REMOTE'
set -euo pipefail
CONF=/etc/moonbite/moonbite.conf
DD=/var/lib/moonbite
CLI="/usr/local/bin/moonbite-cli -conf=$CONF -datadir=$DD"

OLD=$($CLI getblockhash 0 2>/dev/null || echo none)
echo "    running node genesis: $OLD"

# Runtime libraries the release binaries link against (Ubuntu 22.04 names).
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq libboost-system1.74.0 libboost-filesystem1.74.0 \
    libboost-thread1.74.0 libevent-2.1-7 libevent-pthreads-2.1-7 \
    libdb5.3++ libminiupnpc17 libnatpmp1 libzmq5 libsqlite3-0 libfmt8 >/dev/null 2>&1 || true
# The droplet runs Ubuntu 24.04 while the binaries are built on 22.04; the
# 22.04 runtime libraries live in /opt/moonbite/lib (shipped once by
# ship_libs.sh). Point the new binaries at them via rpath.
# (no grep -q here: under pipefail it SIGPIPEs ldd and reads as "false")
if [ -n "$(ldd /root/moonbited.new | grep 'not found')" ] && [ -d /opt/moonbite/lib ]; then
  command -v patchelf >/dev/null || apt-get install -y -qq patchelf >/dev/null 2>&1
  patchelf --set-rpath /opt/moonbite/lib /root/moonbited.new
  patchelf --set-rpath /opt/moonbite/lib /root/moonbite-cli.new
fi
if [ -n "$(ldd /root/moonbited.new | grep 'not found')" ]; then
  echo "missing shared libraries:"; ldd /root/moonbited.new | grep 'not found'; exit 1
fi

systemctl stop moonbited || true
install -m 0755 /root/moonbited.new     /usr/local/bin/moonbited
install -m 0755 /root/moonbite-cli.new  /usr/local/bin/moonbite-cli
rm -f /root/moonbited.new /root/moonbite-cli.new
/usr/local/bin/moonbited --version | head -1

if [ "$OLD" != "$GENESIS" ] && [ -d "$DD/blocks" ]; then
  BK="$DD.old-genesis-${OLD:0:12}-$(date -u +%Y%m%dT%H%M%SZ)"
  echo "    genesis changed -> moving old chain data aside: $BK"
  mkdir -p "$BK"
  for f in blocks chainstate indexes mempool.dat peers.dat anchors.dat banlist.dat fee_estimates.dat; do
    [ -e "$DD/$f" ] && mv "$DD/$f" "$BK/" || true
  done
  chown -R moonbite:moonbite "$BK" "$DD"
fi

# Regenerate addnode= lines from seeds.txt, keep everything else.
sed -i '/^addnode=/d' "$CONF"
printf '%s\n' "$ADDNODES" >> "$CONF"
echo "    seeds: $(grep -c '^addnode=' "$CONF")"

systemctl daemon-reload
systemctl start moonbited
for _ in $(seq 1 60); do $CLI getblockcount >/dev/null 2>&1 && break; sleep 1; done
echo "--- status"
systemctl is-active moonbited
$CLI getblockchaininfo | grep -E '"chain"|"blocks"|"bestblockhash"'
echo "    genesis: $($CLI getblockhash 0)"
echo "    peers:   $($CLI getconnectioncount)"
echo "    rss:     $(ps -o rss= -p "$(pgrep -f '^/usr/local/bin/moonbited' | head -1)") kB"
free -m | sed -n 2,3p
REMOTE
echo "==> Done"
