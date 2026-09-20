#!/bin/bash
# MoonBite seed node #2 - one-shot setup for a fresh Ubuntu 22.04+ VPS.
#
#   curl -fsSL https://moonbite.org/downloads/setup-seed2.sh | bash
#   (or: scp this file up, then: bash setup-seed2.sh)
#
# Turns the box into a hardened public seed node peered with seed #1.
# Carries the fixes from the 2026-09-19 seed-1 outage: generous fd limit,
# no noban-for-the-world whitelist, and automatic -reindex-chainstate
# recovery when the daemon dies of block-database corruption.
set -euo pipefail

SEED1=67.205.154.64:9444
DATADIR=/var/lib/moonbite
CONF=/etc/moonbite/moonbite.conf
BINDIR=/opt/moonbite/bin

[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }

echo "== swap (RandomX validation needs headroom on small boxes) =="
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q "/swapfile" /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

echo "== binaries (the public miner bundle ships moonbited + cli + libfmt, \$ORIGIN rpath) =="
mkdir -p "$BINDIR"
curl -fsSL https://moonbite.org/download/linux -o /tmp/mb.tar.gz
tar -xzf /tmp/mb.tar.gz -C /tmp
d=$(find /tmp -maxdepth 1 -type d -name "moonbite-miner*" | head -1)
install -m 755 "$d/moonbited" "$d/moonbite-cli" "$BINDIR"/
cp "$d"/libfmt.so.8 "$BINDIR"/ 2>/dev/null || true

echo "== user + dirs =="
id moonbite &>/dev/null || useradd -r -m -s /usr/sbin/nologin moonbite
mkdir -p "$DATADIR" /etc/moonbite
chown moonbite:moonbite "$DATADIR"

echo "== config =="
PW=$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')
umask 077
cat > "$CONF" <<EOF
server=1
daemon=1
listen=1
txindex=1
dbcache=128
port=9444
bind=0.0.0.0
maxconnections=125
discover=1
# Peer with seed #1. Two seeds = no single point of failure.
addnode=$SEED1
rpcport=9445
rpcbind=127.0.0.1
rpcallowip=127.0.0.1
rpcuser=moonseed2
rpcpassword=$PW
shrinkdebugfile=1
# NOTE: deliberately NO whitelist=noban@0.0.0.0/0 - that setting on seed #1
# let any peer misbehave unbanned and contributed to the Sep 19 outage.
EOF
umask 022
chown root:moonbite "$CONF" && chmod 640 "$CONF"

echo "== start wrapper with corruption auto-recovery =="
cat > /usr/local/bin/moonbited-exec.sh <<EOF
#!/bin/bash
FLAG=$DATADIR/.reindex_needed
EXTRA=""
if [ -f "\$FLAG" ]; then EXTRA="-reindex-chainstate"; rm -f "\$FLAG"; fi
exec $BINDIR/moonbited -daemon -pid=/run/moonbited/moonbited.pid \\
  -conf=$CONF -datadir=$DATADIR \$EXTRA
EOF
chmod +x /usr/local/bin/moonbited-exec.sh

cat > /etc/systemd/system/moonbited-recover.service <<EOF
[Unit]
Description=Flag MoonBite chainstate reindex after DB corruption

[Service]
Type=oneshot
ExecStart=/bin/bash -c "tail -n 80 $DATADIR/debug.log | grep -q \\"Corrupted block database\\" && { touch $DATADIR/.reindex_needed; chown moonbite:moonbite $DATADIR/.reindex_needed; } || true"
EOF

cat > /etc/systemd/system/moonbited.service <<EOF
[Unit]
Description=MoonBite Core daemon (seed node 2)
OnFailure=moonbited-recover.service
After=network-online.target
Wants=network-online.target

[Service]
Type=forking
User=moonbite
Group=moonbite
ExecStart=/usr/local/bin/moonbited-exec.sh
ExecStop=$BINDIR/moonbite-cli -conf=$CONF -datadir=$DATADIR stop
PIDFile=/run/moonbited/moonbited.pid
RuntimeDirectory=moonbited
Restart=on-failure
RestartSec=10
TimeoutStopSec=120
LimitNOFILE=16384
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=$DATADIR

[Install]
WantedBy=multi-user.target
EOF

echo "== firewall =="
if command -v ufw >/dev/null; then ufw allow 9444/tcp >/dev/null || true; fi

systemctl daemon-reload
systemctl enable --now moonbited

echo "== waiting for RPC =="
for i in $(seq 1 60); do
  "$BINDIR/moonbite-cli" -conf="$CONF" -datadir="$DATADIR" getblockcount &>/dev/null && break
  sleep 2
done
H=$("$BINDIR/moonbite-cli" -conf="$CONF" -datadir="$DATADIR" getblockcount 2>/dev/null || echo "?")
IP=$(curl -fsS -4 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
echo
echo "=============================================="
echo " Seed 2 is up. Height: $H (syncing from $SEED1)"
echo " Public address:  $IP:9444"
echo " NEXT STEP: add 'addnode=$IP:9444' to seed 1's"
echo " /etc/moonbite/moonbite.conf and to the miner"
echo " scripts, so the network knows both seeds."
echo "=============================================="
