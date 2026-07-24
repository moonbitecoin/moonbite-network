#!/usr/bin/env bash
# ============================================================================
# Package the compiled MoonBite node binaries for a GitHub Release, so fresh
# VPS hosts can pull them via setup-node.sh (MOONBITED_URL / MOONBITECLI_URL).
#
# Run inside WSL (where the chain is built):
#     bash deploy/publish-node-binaries.sh
#
# The fork compiles under the upstream names litecoind / litecoin-cli; this
# copies them to the MoonBite names, strips them, and computes checksums.
#
# Override the build tree or version:
#     SRC=/root/bigcoin-core/src TAG=node-v1 bash deploy/publish-node-binaries.sh
# ============================================================================
set -euo pipefail

SRC="${SRC:-/root/bigcoin-core/src}"
TAG="${TAG:-node-v1}"
REPO="${REPO:-moonbitecoin/MoonBite-Coin}"
OUT="${OUT:-$(cd "$(dirname "$0")" && pwd)/dist/$TAG}"

DAEMON_SRC="$SRC/litecoind"
CLI_SRC="$SRC/litecoin-cli"

echo "==> [1/5] Locate compiled binaries"
[ -f "$DAEMON_SRC" ] || { echo "ERROR: $DAEMON_SRC not found. Build the chain first, or set SRC=."; exit 1; }
[ -f "$CLI_SRC" ]    || { echo "ERROR: $CLI_SRC not found. Set SRC= to your build's src/ dir."; exit 1; }

echo "==> [2/5] Stage + rename to MoonBite names"
mkdir -p "$OUT"
install -m 0755 "$DAEMON_SRC" "$OUT/moonbited"
install -m 0755 "$CLI_SRC"    "$OUT/moonbite-cli"

echo "==> [3/5] Strip debug symbols (smaller downloads)"
if command -v strip >/dev/null 2>&1; then
  strip "$OUT/moonbited" "$OUT/moonbite-cli"
  echo "    stripped."
else
  echo "    'strip' not installed (apt-get install binutils) — shipping unstripped."
fi

echo "==> [4/5] Verify they run + resolve shared libs"
"$OUT/moonbited" -version 2>/dev/null | head -1 || echo "    (moonbited -version produced no output; continuing)"
if ldd "$OUT/moonbited" 2>/dev/null | grep -q "not found"; then
  echo "    WARNING: some shared libs are missing on THIS host; target VPS installs them"
  echo "             via setup-node.sh (libboost/libevent/libdb5.3++/libzmq5/...)."
else
  echo "    all shared libs resolve on this host."
fi

echo "==> [5/5] Checksums"
( cd "$OUT" && sha256sum moonbited moonbite-cli | tee SHA256SUMS.txt )

cat <<DONE

=== PACKAGED ===
Output dir : $OUT
Files      : moonbited  moonbite-cli  SHA256SUMS.txt
Sizes      : $(cd "$OUT" && du -h moonbited moonbite-cli | tr '\n' '  ')

NEXT — publish as a GitHub Release (requires 'gh auth login'):

  gh release create $TAG \\
    "$OUT/moonbited" \\
    "$OUT/moonbite-cli" \\
    "$OUT/SHA256SUMS.txt" \\
    --repo $REPO \\
    --title "MoonBite node binaries ($TAG)" \\
    --notes "Linux x86_64 moonbited + moonbite-cli for seed/full nodes. Verify with SHA256SUMS.txt."

Then bring up a new seed node on any fresh Ubuntu VPS:

  sudo MOONBITED_URL=https://github.com/$REPO/releases/download/$TAG/moonbited \\
       MOONBITECLI_URL=https://github.com/$REPO/releases/download/$TAG/moonbite-cli \\
       bash setup-node.sh
DONE
