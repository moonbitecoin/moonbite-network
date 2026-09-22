#!/usr/bin/env bash
# ============================================================================
# MoonBite full/seed-node provisioner for a fresh Ubuntu 22.04/24.04 VPS.
#
# Brings up a permanently-online MoonBite node that auto-connects to every
# seed listed in deploy/seeds.txt, so the network stops being a single host.
#
#   sudo bash setup-node.sh /path/to/moonbited /path/to/moonbite-cli
#   # or fetch prebuilt binaries from a release you uploaded:
#   sudo MOONBITED_URL=https://.../moonbited \
#        MOONBITECLI_URL=https://.../moonbite-cli bash setup-node.sh
#
# Installs binaries, a dedicated user, config (with random RPC creds + the
# seed list), a systemd service, and a firewall that exposes ONLY P2P 9444.
# ============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MOONBITED_SRC="${1:-}"
MOONBITECLI_SRC="${2:-}"
SEEDS_FILE="${SEEDS_FILE:-$HERE/seeds.txt}"
RELEASE_PUB="${RELEASE_PUB:-$HERE/moonbite-release.pub}"
# URL of the signed SHA256SUMS manifest covering the binaries below. Its
# detached signature is expected at <url>.minisig. Set this when fetching
# binaries over the network; local-path installs (args) are trusted as-is.
MOONBITE_SUMS_URL="${MOONBITE_SUMS_URL:-}"

# True once moonbite-release.pub holds a real minisign key (not the placeholder).
_pubkey_configured() {
  [ -f "$RELEASE_PUB" ] || return 1
  grep -qE '^[[:space:]]*RW[A-Za-z0-9+/=]' "$RELEASE_PUB"
}

# mb_verify <file> <sums_file> <name_in_sums>
# Fails closed: when a real release pubkey is configured a valid minisign
# signature over the manifest is REQUIRED; otherwise sha256 integrity only,
# with a loud warning. Never silently skips a signature that is expected.
mb_verify() {
  local file="$1" sums="$2" name="$3" sig="$2.minisig"
  [ -f "$file" ] || { echo "verify: missing $file" >&2; return 1; }
  [ -f "$sums" ] || { echo "verify: missing checksum manifest for $name" >&2; return 1; }
  if _pubkey_configured; then
    command -v minisign >/dev/null 2>&1 || apt-get install -y -qq minisign >/dev/null 2>&1 || true
    command -v minisign >/dev/null 2>&1 || {
      echo "verify: a release key is configured but minisign is unavailable -- refusing to install unverified $name" >&2; return 1; }
    [ -f "$sig" ] || { echo "verify: signature for $(basename "$sums") missing but a release key is configured -- refusing" >&2; return 1; }
    minisign -Vm "$sums" -p "$RELEASE_PUB" -x "$sig" >/dev/null 2>&1 || {
      echo "verify: BAD SIGNATURE on $(basename "$sums") -- refusing $name" >&2; return 1; }
    echo "    signature OK ($(basename "$sums"))"
  else
    echo "    WARNING: no release pubkey configured -- sha256 integrity only, NOT authenticity (see deploy/RELEASE-SIGNING.md)" >&2
  fi
  local want got
  want="$(grep -E "[[:space:]][*]?${name}\$" "$sums" | awk '{print $1}' | head -1)"
  [ -n "$want" ] || { echo "verify: $name not listed in manifest -- refusing" >&2; return 1; }
  got="$(sha256sum "$file" | awk '{print $1}')"
  [ "$want" = "$got" ] || { echo "verify: SHA256 MISMATCH for $name" >&2; echo "  want $want" >&2; echo "  got  $got" >&2; return 1; }
  echo "    sha256 OK ($name)"
}

echo "==> [1/8] Sanity checks"
[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo)."; exit 1; }
[ -f "$HERE/moonbite.conf" ]    || { echo "moonbite.conf missing next to this script."; exit 1; }
[ -f "$HERE/moonbited.service" ]|| { echo "moonbited.service missing next to this script."; exit 1; }
[ -f "$SEEDS_FILE" ]            || { echo "seeds.txt missing ($SEEDS_FILE)."; exit 1; }

echo "==> [2/8] Install runtime deps"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq libboost-system1.74.0 libboost-filesystem1.74.0 \
    libboost-thread1.74.0 libevent-2.1-7 libevent-pthreads-2.1-7 \
    libdb5.3++ libminiupnpc17 libnatpmp1 libzmq5 libfmt8 curl ufw >/dev/null 2>&1 || true

echo "==> [3/8] Obtain moonbited / moonbite-cli binaries"
fetch() { # fetch <url> <dest>
  echo "    downloading $(basename "$2") ..."
  curl -fSL "$1" -o "$2"
  chmod 0755 "$2"
}
if [ -n "$MOONBITED_SRC" ] && [ -f "$MOONBITED_SRC" ]; then
  install -m 0755 "$MOONBITED_SRC"   /usr/local/bin/moonbited
  install -m 0755 "${MOONBITECLI_SRC:?pass moonbite-cli path as 2nd arg}" /usr/local/bin/moonbite-cli
elif [ -n "${MOONBITED_URL:-}" ]; then
  : "${MOONBITECLI_URL:?set MOONBITECLI_URL too}"
  # Download to a staging dir first, verify against the signed manifest, and
  # only then install. A release key + SUMS URL make this authenticity-checked;
  # without them it is sha256-only and refuses to proceed if a key is set.
  if _pubkey_configured && [ -z "$MOONBITE_SUMS_URL" ]; then
    echo "ERROR: a release signing key is configured ($RELEASE_PUB) but MOONBITE_SUMS_URL is unset."
    echo "       Set MOONBITE_SUMS_URL to the signed SHA256SUMS manifest for these binaries."
    exit 1
  fi
  STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
  fetch "$MOONBITED_URL"    "$STAGE/moonbited"
  fetch "$MOONBITECLI_URL"  "$STAGE/moonbite-cli"
  if [ -n "$MOONBITE_SUMS_URL" ]; then
    echo "    verifying against $MOONBITE_SUMS_URL"
    curl -fSL "$MOONBITE_SUMS_URL" -o "$STAGE/SHA256SUMS.txt"
    curl -fSL "$MOONBITE_SUMS_URL.minisig" -o "$STAGE/SHA256SUMS.txt.minisig" 2>/dev/null || true
    mb_verify "$STAGE/moonbited"   "$STAGE/SHA256SUMS.txt" moonbited   || { echo "ABORT: moonbited failed verification"; exit 1; }
    mb_verify "$STAGE/moonbite-cli" "$STAGE/SHA256SUMS.txt" moonbite-cli || { echo "ABORT: moonbite-cli failed verification"; exit 1; }
  else
    echo "    WARNING: MOONBITE_SUMS_URL unset -- installing UNVERIFIED binaries (see deploy/RELEASE-SIGNING.md)" >&2
  fi
  install -m 0755 "$STAGE/moonbited"    /usr/local/bin/moonbited
  install -m 0755 "$STAGE/moonbite-cli" /usr/local/bin/moonbite-cli
elif command -v moonbited >/dev/null 2>&1 && command -v moonbite-cli >/dev/null 2>&1; then
  echo "    using moonbited already on PATH: $(command -v moonbited)"
else
  echo "ERROR: no binaries. Pass paths as args, set MOONBITED_URL/MOONBITECLI_URL,"
  echo "       or place moonbited + moonbite-cli on PATH first."
  exit 1
fi
/usr/local/bin/moonbited -version 2>/dev/null | head -1 || true

echo "==> [4/8] Create moonbite user + directories"
id -u moonbite >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin moonbite
install -d -o moonbite -g moonbite -m 0750 /var/lib/moonbite
install -d -m 0755 /etc/moonbite

echo "==> [5/8] Build config: random RPC creds + seed list"
RPCUSER="mb_$(head -c6 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')"
RPCPASS="$(head -c48 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')"

# Start from the template, but strip its example addnode= / rpc credential lines;
# we regenerate those so the config always matches seeds.txt exactly.
CONF=/etc/moonbite/moonbite.conf
if [ -f "$CONF" ]; then
  echo "    $CONF exists — leaving it untouched (delete it to regenerate)."
else
  grep -viE '^\s*(addnode|rpcuser|rpcpassword)\s*=' "$HERE/moonbite.conf" > "$CONF"
  {
    echo ""
    echo "# --- RPC credentials (auto-generated $(date -u +%FT%TZ)) ---"
    echo "rpcuser=${RPCUSER}"
    echo "rpcpassword=${RPCPASS}"
    echo ""
    echo "# --- Seed peers (generated from seeds.txt) ---"
    grep -vE '^\s*(#|$)' "$SEEDS_FILE" | while read -r seed; do
      [ -n "$seed" ] && echo "addnode=${seed}"
    done
  } >> "$CONF"
  chown root:moonbite "$CONF"
  chmod 0640 "$CONF"
  echo "    Generated RPC user: ${RPCUSER}  (secret stored in $CONF)"
  echo "    Wired $(grep -c '^addnode=' "$CONF") seed peer(s) from seeds.txt."
fi

echo "==> [6/8] Install systemd service"
install -m 0644 "$HERE/moonbited.service" /etc/systemd/system/moonbited.service
systemctl daemon-reload
systemctl enable moonbited >/dev/null 2>&1 || true
systemctl restart moonbited

echo "==> [7/8] Firewall: expose P2P 9444, keep RPC private"
ufw allow 9444/tcp comment "MoonBite P2P" >/dev/null 2>&1 || true
ufw --force enable >/dev/null 2>&1 || true

echo "==> [8/8] Health check"
sleep 5
PUBIP="$(curl -s --max-time 8 ifconfig.me 2>/dev/null || echo YOUR_PUBLIC_IP)"
systemctl is-active --quiet moonbited && echo "    moonbited: active (running)" \
                                      || echo "    moonbited: NOT running — see: journalctl -u moonbited -n50"
moonbite-cli -conf="$CONF" getpeerinfo 2>/dev/null | grep -c '"addr"' \
  | sed 's/^/    connected peers: /' || echo "    (RPC not up yet; give it a minute)"

cat <<DONE

=== DONE ===
Node public IP : ${PUBIP}
P2P port       : 9444   (open)
RPC            : 127.0.0.1:9445 (private)
Status         : systemctl status moonbited
Logs           : journalctl -u moonbited -f
Peers          : moonbite-cli -conf=${CONF} getpeerinfo

NEXT: to make THIS host a permanent seed, append the line
      ${PUBIP}:9444
to deploy/seeds.txt, commit, and re-run setup-node.sh on the other hosts.
DONE
