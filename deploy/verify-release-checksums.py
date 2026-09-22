#!/usr/bin/env python3
"""Fail loudly when a published checksum does not match the artifact it names.

This guard exists because the 2026-09-22 audit (finding B2) found every
published miner checksum stale or wrong after the 2026-09-21 relaunch: the
site told users to verify a hash that never matched the bundle actually being
served, and two different `moonbite-wallet.exe` builds disagreed inside the
repo. A "verify the checksum" instruction that points at the wrong hash is
worse than none -- it manufactures false confidence.

It re-hashes every artifact referenced by the two published manifests:
  - release/SHA256SUMS.txt          (the release manifest)
  - website/downloads/README.txt    (the "verify what you downloaded" block)
and cross-checks that no two same-named artifacts in the tree disagree.

Exit status:
  0  every reference that could be checked matched, no conflicts
  1  a referenced artifact is present but its hash is wrong, OR two same-named
     artifacts disagree (the relaunch-drift smell)
With --strict, a referenced artifact that is MISSING is also fatal (use this in
the release job, where every binary must be present).

Usage:
  python deploy/verify-release-checksums.py [--strict]
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where a referenced basename might physically live. First match is not assumed
# canonical -- we hash ALL matches so we can catch two builds that disagree.
CANDIDATE_DIRS = [
    "release/bin",
    "release/miner",
    "release/dist",
    "website/downloads",
    os.environ.get("MOONBITE_DOWNLOAD_DIR", "data/downloads"),
]

SUMS_MANIFEST = "release/SHA256SUMS.txt"
README_MANIFEST = "website/downloads/README.txt"

_HEX64 = re.compile(r"\b([0-9a-f]{64})\b")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_files(basename: str) -> list[str]:
    """All existing files with this basename across the candidate dirs."""
    hits = []
    for d in CANDIDATE_DIRS:
        p = os.path.join(REPO, d, basename)
        if os.path.isfile(p):
            hits.append(p)
    return hits


def parse_sums(path: str) -> list[tuple[str, str]]:
    """`<hex>  [*]<name>` lines -> [(name, hex)]."""
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([0-9a-fA-F]{64})\s+[*]?(.+)$", line)
        if m:
            out.append((os.path.basename(m.group(2).strip()), m.group(1).lower()))
    return out


def parse_readme(path: str) -> list[tuple[str, str]]:
    """Lines pairing an archive name with a 64-hex hash, in either order."""
    out = []
    for line in open(path, encoding="utf-8"):
        m = _HEX64.search(line)
        if not m:
            continue
        name = None
        for tok in re.split(r"\s+", line.strip()):
            if re.search(r"\.(zip|tar\.gz|tgz|exe|dmg)$", tok):
                name = os.path.basename(tok)
                break
        if name:
            out.append((name, m.group(1).lower()))
    return out


def check(manifest_rel: str, entries: list[tuple[str, str]], strict: bool,
          problems: list[str]) -> None:
    print(f"\n== {manifest_rel} ({len(entries)} referenced artifact(s)) ==")
    for name, want in entries:
        files = find_files(name)
        if not files:
            note = f"MISSING  {name}: not found in tree (recorded {want[:12]}...)"
            print(("FAIL " if strict else "skip ") + note)
            if strict:
                problems.append(f"{manifest_rel}: {note}")
            continue
        hashes = {p: sha256(p) for p in files}
        distinct = set(hashes.values())
        if len(distinct) > 1:
            print(f"FAIL CONFLICT {name}: same name, differing builds in tree:")
            for p, h in hashes.items():
                print(f"       {h[:16]}...  {os.path.relpath(p, REPO)}")
            problems.append(f"{manifest_rel}: {name} has conflicting builds in the repo")
            continue
        got = distinct.pop()
        if got == want:
            print(f"ok   {name}: {got[:16]}...  ({os.path.relpath(files[0], REPO)})")
        else:
            print(f"FAIL MISMATCH {name}:")
            print(f"       recorded {want}")
            print(f"       actual   {got}  ({os.path.relpath(files[0], REPO)})")
            problems.append(f"{manifest_rel}: {name} recorded={want[:12]}... actual={got[:12]}...")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="also fail when a referenced artifact is missing")
    args = ap.parse_args()

    problems: list[str] = []
    for manifest, parser in ((SUMS_MANIFEST, parse_sums),
                             (README_MANIFEST, parse_readme)):
        mpath = os.path.join(REPO, manifest)
        if not os.path.isfile(mpath):
            print(f"note: {manifest} absent, skipping")
            continue
        check(manifest, parser(mpath), args.strict, problems)

    print("\n" + "=" * 60)
    if problems:
        print(f"FAILED: {len(problems)} checksum problem(s):")
        for p in problems:
            print("  - " + p)
        print("\nDo not publish until every published hash matches the artifact "
              "it names. See deploy/RELEASE-SIGNING.md.")
        return 1
    print("OK: all checkable published checksums match; no conflicting builds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
