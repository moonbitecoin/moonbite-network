#!/usr/bin/env bash
# ============================================================================
# MoonBite seed-node provisioner for a fresh Ubuntu 22.04 VPS.
# Run as root:   sudo bash setup-seednode.sh /path/to/moonbited /path/to/moonbite-cli
# Installs binaries, creates a dedicated user, config, systemd service, firewall.
# ============================================================================
set -euo pipefail

MOONBITED_SRC="${1:-./moonbited}"
MOONBITECLI_SRC="${2:-./moonbite-cli}"

echo "==> [1/7] Sanity checks"
[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo)."; exit 1; }
[ -f "$MOONBITED_SRC" ] || { echo "moonbited not found at $MOONBITED_SRC"; exit 1; }
[ -f "$MOONBITECLI_SRC" ] || { echo "moonbite-cli not found at $MOONBITECLI_SRC"; exit 1; }

echo "==> [2/7] Install runtime deps"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq libboost-system1.74.0 libboost-filesystem1.74.0 \
    libboost-thread1.74.0 libevent-2.1-7 libevent-pthreads-2.1-7 \
    libdb5.3++ libminiupnpc17 libnatpmp1 libzmq5 libfmt8 ufw >/dev/null 2>&1 || true

echo "==> [3/7] Install binaries to /usr/local/bin"
install -m 0755 "$MOONBITED_SRC"   /usr/local/bin/moonbited
install -m 0755 "$MOONBITECLI_SRC" /usr/local/bin/moonbite-cli

echo "==> [4/7] Create moonbite user + directories"
id -u moonbite >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin moonbite
install -d -o moonbite -g moonbite -m 0750 /var/lib/moonbite
install -d -m 0755 /etc/moonbite

echo "==> [5/7] Install config (generates random RPC credentials)"
RPCUSER="big_$(head -c6 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')"
RPCPASS="$(head -c48 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')"
if [ ! -f /etc/moonbite/moonbite.conf ]; then
  sed -e "s/CHANGE_ME_user/${RPCUSER}/" \
      -e "s/CHANGE_ME_LONG_RANDOM_64_CHARS/${RPCPASS}/" \
      "$(dirname "$0")/moonbite.conf" > /etc/moonbite/moonbite.conf
  chown root:moonbite /etc/moonbite/moonbite.conf
  chmod 0640 /etc/moonbite/moonbite.conf
  echo "    Generated RPC user: ${RPCUSER}  (password stored in /etc/moonbite/moonbite.conf)"
else
  echo "    /etc/moonbite/moonbite.conf already exists — left untouched."
fi

echo "==> [6/7] Install systemd service"
install -m 0644 "$(dirname "$0")/moonbited.service" /etc/systemd/system/moonbited.service
systemctl daemon-reload
systemctl enable moonbited
systemctl restart moonbited

echo "==> [7/7] Firewall: open P2P 9444, keep RPC private"
ufw allow 9444/tcp comment "MoonBite P2P" >/dev/null 2>&1 || true
ufw --force enable >/dev/null 2>&1 || true

echo
echo "Done. Check status with:  systemctl status moonbited"
echo "Tail logs with:           journalctl -u moonbited -f"
echo "Query the node with:      moonbite-cli -conf=/etc/moonbite/moonbite.conf getpeerinfo"
echo
echo "Report this host's PUBLIC IP to the other seed operators, and add it to"
echo "chainparams.cpp vSeeds / vFixedSeeds before mainnet launch."
