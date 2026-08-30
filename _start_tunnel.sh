#!/usr/bin/env bash
# Start a Cloudflare *quick* tunnel (free *.trycloudflare.com host, no login,
# no domain) in front of the loopback read-only RPC proxy on 127.0.0.1:9350.
set -e
LOG=/tmp/cftunnel.log

# Stop any prior tunnel.
pkill -f "cloudflared tunnel" 2>/dev/null && sleep 1 || true
rm -f "$LOG"

# Launch detached so it outlives this shell.
setsid nohup cloudflared tunnel --no-autoupdate \
  --url http://127.0.0.1:9350 >"$LOG" 2>&1 < /dev/null &
disown 2>/dev/null || true

# Wait for the assigned hostname to appear in the log.
URL=""
for i in $(seq 1 30); do
  sleep 2
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)
  [ -n "$URL" ] && break
done

echo "=== tunnel log tail ==="
tail -12 "$LOG" 2>/dev/null || echo "(no log)"
echo "=== result ==="
if [ -n "$URL" ]; then
  echo "TUNNEL_URL=$URL"
else
  echo "TUNNEL_URL=NOT_FOUND"
fi
