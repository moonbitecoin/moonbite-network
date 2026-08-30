#!/usr/bin/env bash
set -e
CONF=/root/moonbite_main/moonbite.conf
ENVF=/root/moonbite-app/.roproxy.env
PROXY=/mnt/c/Users/usman/Desktop/BigCoinBB/explorer/rpc_readonly_proxy.py

# Read the real node creds from the node config.
NODE_USER=$(grep -E '^rpcuser=' "$CONF" | head -1 | cut -d= -f2-)
NODE_PASS=$(grep -E '^rpcpassword=' "$CONF" | head -1 | cut -d= -f2-)
if [ -z "$NODE_USER" ] || [ -z "$NODE_PASS" ]; then
  echo "FATAL: could not read node rpcuser/rpcpassword from $CONF"; exit 1
fi

# Generate + persist proxy creds once (so the Railway env stays stable).
if [ ! -f "$ENVF" ]; then
  PU="explorer_ro"
  PP=$(head -c 24 /dev/urandom | base64 | tr -d '/+=' | head -c 32)
  umask 077
  printf 'PROXY_USER=%s\nPROXY_PASSWORD=%s\n' "$PU" "$PP" > "$ENVF"
  echo "generated new proxy creds at $ENVF"
fi
# shellcheck disable=SC1090
. "$ENVF"

# Stop any prior proxy.
pkill -f rpc_readonly_proxy.py 2>/dev/null && sleep 1 || true

# Launch detached.
export PROXY_BIND=127.0.0.1 PROXY_PORT=9350
export NODE_RPC_URL=http://127.0.0.1:9332/
export NODE_RPC_USER="$NODE_USER" NODE_RPC_PASSWORD="$NODE_PASS"
export PROXY_USER PROXY_PASSWORD
setsid nohup python3 "$PROXY" >/tmp/roproxy.log 2>&1 < /dev/null &
disown 2>/dev/null || true
sleep 2

echo "=== proxy log ==="
cat /tmp/roproxy.log
echo "=== listening? ==="
ss -ltn 2>/dev/null | grep ':9350' && echo "PROXY UP on 9350" || echo "PROXY NOT LISTENING"

# Print the caller creds so we can wire Railway (safe: these are the PROXY creds,
# not the node's real password).
echo "=== caller (Railway) creds ==="
echo "PROXY_USER=$PROXY_USER"
echo "PROXY_PASSWORD=$PROXY_PASSWORD"
