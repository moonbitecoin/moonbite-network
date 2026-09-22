#!/usr/bin/env bash
# MoonBite CPU Miner - one command to start (Linux / macOS).
# Asks for your reward address, then runs a local node and mines to it.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required but was not found." >&2
  echo "Install it from your package manager or https://www.python.org/downloads/." >&2
  exit 1
fi

exec python3 ./moonbite-miner.py "$@"
