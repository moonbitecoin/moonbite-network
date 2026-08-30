#!/usr/bin/env bash
# Install systemd units so the read-only RPC proxy and the Cloudflare quick
# tunnel come back automatically on every WSL/systemd start (and auto-restart
# if either dies). Self-contained: copies a proxy copy into the Linux fs so it
# does not depend on the /mnt/c mount being ready at boot.
set -e
APP=/root/moonbite-app
CONF=/root/moonbite_main/moonbite.conf
PROXY_SRC=/mnt/c/Users/usman/Desktop/BigCoinBB/explorer/rpc_readonly_proxy.py

# 0) Stop any manually-started proxy/tunnel so systemd can own the port.
pkill -f rpc_readonly_proxy.py 2>/dev/null || true
pkill -f "cloudflared tunnel" 2>/dev/null || true
sleep 1

# 1) Place a self-contained (LF-normalised) copy of the proxy in the Linux fs.
mkdir -p "$APP"
tr -d '\r' < "$PROXY_SRC" > "$APP/rpc_readonly_proxy.py"

# Ensure proxy creds exist (generate once if missing; keep existing otherwise).
if [ ! -f "$APP/.roproxy.env" ]; then
  PP=$(head -c 24 /dev/urandom | base64 | tr -d '/+=' | head -c 32)
  umask 077
  printf 'PROXY_USER=%s\nPROXY_PASSWORD=%s\n' "explorer_ro" "$PP" > "$APP/.roproxy.env"
fi

# 2) Proxy runner: assembles env from node config, execs python as main PID.
cat > "$APP/roproxy-run.sh" <<'EOF'
#!/usr/bin/env bash
set -e
APP=/root/moonbite-app
CONF=/root/moonbite_main/moonbite.conf
. "$APP/.roproxy.env"
export PROXY_BIND=127.0.0.1 PROXY_PORT=9350
export NODE_RPC_URL=http://127.0.0.1:9332/
export NODE_RPC_USER="$(grep -E '^rpcuser=' "$CONF" | head -1 | cut -d= -f2-)"
export NODE_RPC_PASSWORD="$(grep -E '^rpcpassword=' "$CONF" | head -1 | cut -d= -f2-)"
export PROXY_USER PROXY_PASSWORD
exec python3 "$APP/rpc_readonly_proxy.py"
EOF
chmod +x "$APP/roproxy-run.sh"

# 3) Tunnel runner: start quick tunnel, record the assigned URL, wait on it.
cat > "$APP/tunnel-run.sh" <<'EOF'
#!/usr/bin/env bash
set -e
APP=/root/moonbite-app
LOG=/tmp/cftunnel.log
: > "$LOG"
cloudflared tunnel --no-autoupdate --url http://127.0.0.1:9350 >"$LOG" 2>&1 &
CF=$!
URL=""
for i in $(seq 1 30); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)
  [ -n "$URL" ] && break
  sleep 2
done
if [ -n "$URL" ]; then
  printf '%s\n' "$URL" > "$APP/.tunnel_url"
  # Also drop it on the Windows desktop so it is easy to find after a reboot.
  printf '%s\n' "$URL" > /mnt/c/Users/usman/Desktop/BigCoinBB/CURRENT_TUNNEL_URL.txt 2>/dev/null || true
  logger -t moonbite-tunnel "quick tunnel URL: $URL" 2>/dev/null || true
fi
wait "$CF"
EOF
chmod +x "$APP/tunnel-run.sh"

# 4) systemd units.
cat > /etc/systemd/system/moonbite-roproxy.service <<'EOF'
[Unit]
Description=MoonBite read-only RPC proxy (loopback 9350)
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
ExecStart=/root/moonbite-app/roproxy-run.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/moonbite-tunnel.service <<'EOF'
[Unit]
Description=MoonBite Cloudflare quick tunnel -> 127.0.0.1:9350
After=moonbite-roproxy.service network-online.target
Wants=network-online.target
Requires=moonbite-roproxy.service

[Service]
Type=simple
ExecStart=/root/moonbite-app/tunnel-run.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 5) Enable + start now.
systemctl daemon-reload
systemctl enable --now moonbite-roproxy.service
systemctl enable --now moonbite-tunnel.service

sleep 8
echo "=== roproxy status ==="
systemctl --no-pager --lines=2 status moonbite-roproxy.service | head -6 || true
echo "=== tunnel status ==="
systemctl --no-pager --lines=2 status moonbite-tunnel.service | head -6 || true
echo "=== current tunnel URL ==="
cat "$APP/.tunnel_url" 2>/dev/null || echo "(not captured yet)"
