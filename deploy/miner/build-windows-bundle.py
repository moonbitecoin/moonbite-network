#!/usr/bin/env python3
"""Assemble the Windows miner bundle the site serves at /download/windows.

Reproducible: run it anywhere the release binaries exist (a build box, the
droplet) and it produces byte-for-identical contents with a printed manifest,
so what users download is always accountable to a known set of files.

The bundle is deliberately lean - node + CLI + the PowerShell driver + the
README. The desktop wallet (moonbite-wallet.exe) is a SEPARATE download so the
miner stays small and quick to fetch. Everything is placed under one top-level
folder so unzipping is tidy and mine.ps1 finds the two exes beside it.

    python deploy/miner/build-windows-bundle.py [--out DIR] [--stage]

--out    where to write the .zip (default: release/dist)
--stage  also copy the .zip into the app's live download dir so the running
         server serves it immediately (resolved the same way web_app does)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(REPO, "release", "miner")
# The zip is named per-platform; the folder inside is plain "moonbite-miner"
# to match the bundle production already serves, so a rebuild is a drop-in.
ZIP_NAME = "moonbite-miner-windows-x86_64.zip"
BUNDLE_DIR = "moonbite-miner"

# (source filename, arcname inside the top-level folder). Order is fixed so the
# archive is reproducible.
MEMBERS = [
    ("moonbited.exe", "moonbited.exe"),
    ("moonbite-cli.exe", "moonbite-cli.exe"),
    ("mine.ps1", "mine.ps1"),
    ("README.md", "README.md"),
]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(out_dir: str) -> str:
    missing = [s for s, _ in MEMBERS if not os.path.isfile(os.path.join(SRC, s))]
    if missing:
        sys.exit(f"missing release files in {SRC}: {', '.join(missing)}")

    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, ZIP_NAME)

    # Deterministic: fixed member order, fixed timestamps, fixed compression.
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as z:
        for src_name, arc in MEMBERS:
            src = os.path.join(SRC, src_name)
            info = zipfile.ZipInfo(f"{BUNDLE_DIR}/{arc}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            # 0644 for docs/scripts, 0755 for the executables.
            info.external_attr = (0o755 if arc.endswith(".exe") else 0o644) << 16
            with open(src, "rb") as f:
                z.writestr(info, f.read())

    print("built:", zip_path)
    print(f"{'file':32} {'bytes':>12}  sha256")
    for src_name, _ in MEMBERS:
        p = os.path.join(SRC, src_name)
        print(f"{src_name:32} {os.path.getsize(p):>12}  {_sha256(p)}")
    print("-" * 60)
    print(f"{ZIP_NAME:32} {os.path.getsize(zip_path):>12}  {_sha256(zip_path)}")
    return zip_path


def stage(zip_path: str) -> None:
    """Copy the built zip into the dir web_app serves downloads from."""
    sys.path.insert(0, REPO)
    import storage  # noqa: E402  (resolve the same dir the route uses)
    dest_dir = storage.data_path("downloads", "MOONBITE_DOWNLOAD_DIR")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, ZIP_NAME)
    with open(zip_path, "rb") as fsrc, open(dest, "wb") as fdst:
        fdst.write(fsrc.read())
    print("staged ->", dest)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "release", "dist"))
    ap.add_argument("--stage", action="store_true")
    args = ap.parse_args()
    zip_path = build(args.out)
    if args.stage:
        stage(zip_path)


if __name__ == "__main__":
    main()
