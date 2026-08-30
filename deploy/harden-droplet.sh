#!/bin/bash
# Infrastructure hardening: persistent SECRET_KEY, and a firewall.
set -eu

DROPIN=/etc/systemd/system/moonbite-dashboard.service.d/persistence.conf

echo "step: SECRET_KEY"
if grep -q "SECRET_KEY=" "$DROPIN" 2>/dev/null; then
    echo "  already set, leaving it alone"
else
    # Without this the app falls back to a random key per start, so every
    # deploy silently invalidates all session cookies.
    KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
    # Append inside the existing [Service] section.
    printf '\n# Signs session cookies. Generated once; a random per-start key\n# invalidates every session on each restart.\nEnvironment=SECRET_KEY=%s\n' "$KEY" >> "$DROPIN"
    chmod 600 "$DROPIN"
    systemctl daemon-reload
    systemctl restart moonbite-dashboard
    sleep 10
    echo "  set (64 hex chars), service restarted"
fi

echo "step: firewall"
if ! command -v ufw >/dev/null 2>&1; then
    echo "  ufw not installed; skipping (install manually if wanted)"
else
    # Allow SSH first — locking ourselves out would be worse than the risk.
    ufw allow 22/tcp   >/dev/null 2>&1 || true
    ufw allow 80/tcp   >/dev/null 2>&1 || true
    ufw allow 443/tcp  >/dev/null 2>&1 || true
    ufw allow 9444/tcp >/dev/null 2>&1 || true   # MoonBite P2P, intentionally public
    ufw --force enable >/dev/null 2>&1 || true
    echo "  rules:"
    ufw status | sed -n '1,12p' | sed 's/^/    /'
fi

echo "step: verify"
echo -n "  dashboard: "; systemctl is-active moonbite-dashboard
echo -n "  moonbited: "; systemctl is-active moonbited
echo -n "  local /wallet: "
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8050/wallet --max-time 15
echo -n "  SECRET_KEY present in env: "
systemctl show -p Environment --value moonbite-dashboard | grep -q 'SECRET_KEY=' && echo yes || echo NO
echo "HARDEN-OK"
