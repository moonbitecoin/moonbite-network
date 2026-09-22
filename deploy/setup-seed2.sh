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

# URL of the signed checksum manifest for the linux bundle (+ .minisig beside
# it). Overridable; default assumes the release process publishes it here.
SUMS_URL="${SUMS_URL:-https://moonbite.org/downloads/SHA256SUMS-linux.txt}"

# --- Release signing public key (minisign), baked into this script ----------
# This script is fetched over curl|bash, so the ONLY thing that makes the
# download trustworthy is a key pinned HERE, in the script itself. Replace the
# placeholder during the key ceremony (deploy/RELEASE-SIGNING.md) -- this block
# AND deploy/moonbite-release.pub must carry the same key. Marker: RELEASE_PUBKEY
RELEASE_PUBKEY="REPLACE_ME_WITH_MINISIGN_PUBLIC_KEY"
# ---------------------------------------------------------------------------

[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }

_pubkey_configured() { printf '%s' "$RELEASE_PUBKEY" | grep -qE '^RW[A-Za-z0-9+/=]'; }

# mb_verify <file> <sums> <name> -- fail closed when the pinned key is set.
mb_verify() {
  local file="$1" sums="$2" name="$3" sig="$2.minisig" pub
  [ -f "$file" ] && [ -f "$sums" ] || { echo "verify: missing artifact/manifest for $name" >&2; return 1; }
  if _pubkey_configured; then
    command -v minisign >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq minisign >/dev/null 2>&1; } || true
    command -v minisign >/dev/null 2>&1 || { echo "verify: minisign unavailable but a release key is pinned -- refusing $name" >&2; return 1; }
    [ -f "$sig" ] || { echo "verify: signature for $(basename "$sums") missing but a key is pinned -- refusing" >&2; return 1; }
    pub="$(mktemp)"; printf 'untrusted comment: moonbite release key\n%s\n' "$RELEASE_PUBKEY" > "$pub"
    minisign -Vm "$sums" -p "$pub" -x "$sig" >/dev/null 2>&1 || { rm -f "$pub"; echo "verify: BAD SIGNATURE on $(basename "$sums") -- refusing $name" >&2; return 1; }
    rm -f "$pub"; echo "  signature OK ($(basename "$sums"))"
  else
    echo "  WARNING: no release key pinned in this script -- sha256 integrity only, NOT authenticity (deploy/RELEASE-SIGNING.md)" >&2
  fi
  local want got
  want="$(grep -E "[[:space:]][*]?${name}\$" "$sums" | awk '{print $1}' | head -1)"
  [ -n "$want" ] || { echo "verify: $name not listed in manifest -- refusing" >&2; return 1; }
  got="$(sha256sum "$file" | awk '{print $1}')"
  [ "$want" = "$got" ] || { echo "verify: SHA256 MISMATCH for $name (want $want got $got)" >&2; return 1; }
  echo "  sha256 OK ($name)"
}

echo "== swap (RandomX validation needs headroom on small boxes) =="
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q "/swapfile" /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

echo "== binaries (the public miner bundle ships moonbited + cli + libfmt, \$ORIGIN rpath) =="
mkdir -p "$BINDIR"
curl -fsSL https://moonbite.org/download/linux -o /tmp/mb.tar.gz

# Verify the tarball BEFORE extracting or running anything as root. Fetch the
# signed manifest; if the pinned key is set this is authenticity-checked and
# fails closed, otherwise it is sha256-only with a warning.
if _pubkey_configured || curl -fsSL "$SUMS_URL" -o /tmp/mb.sums 2>/dev/null; then
  curl -fsSL "$SUMS_URL" -o /tmp/mb.sums || { echo "ABORT: cannot fetch checksum manifest $SUMS_URL but a release key is pinned" >&2; exit 1; }
  curl -fsSL "$SUMS_URL.minisig" -o /tmp/mb.sums.minisig 2>/dev/null || true
  mb_verify /tmp/mb.tar.gz /tmp/mb.sums moonbite-miner-linux-x86_64.tar.gz \
    || { echo "ABORT: linux bundle failed verification -- not installing" >&2; exit 1; }
else
  echo "  WARNING: installing UNVERIFIED tarball (no key pinned, no manifest reachable)" >&2
fi

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
