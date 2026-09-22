# Release signing & checksum integrity

Fixes audit findings **B2** (stale/mismatched published checksums) and **B3/B5**
(installers run unverified binaries as root). The download channel is threat-model
asset #3 — a compromise here is everyone's keys at once — so binary trust must be
**authenticity** (a signature you pin), not just a checksum sitting next to the file.

This repo now ships the *machinery*. Two things only a human can do remain, and the
channel is not trustworthy until both are done:

1. **Generate and hold the signing key** (offline, passphrase-protected).
2. **Decide the canonical binary set** and stamp its real hashes.

---

## What is already wired

| Piece | File | Behaviour |
|---|---|---|
| Checksum manifest is generated from real artifacts | `deploy/miner/build-windows-bundle.py` | writes `SHA256SUMS.txt` (zip + members); prints the `minisign -Sm` next step; `--stage` copies zip **+ sums + .minisig** together and **refuses to stage unsigned** once a key is configured |
| Drift guard | `deploy/verify-release-checksums.py` | re-hashes everything referenced by `release/SHA256SUMS.txt` and `website/downloads/README.txt`; fails on mismatch or two same-named builds that disagree |
| CI gate | `.github/workflows/ci.yml` | runs the drift guard on every push/PR (currently **red** — see "Fix the values") |
| Node installer verification | `deploy/setup-node.sh` | fetches to a staging dir, `mb_verify`s against the signed manifest, installs only on pass; refuses if a key is set but `MOONBITE_SUMS_URL` is unset |
| Seed installer verification | `deploy/setup-seed2.sh` | verifies the tarball **before** extracting/running as root; key pinned inline (`RELEASE_PUBKEY`) because it is `curl\|bash`'d |
| Pinned public key | `deploy/moonbite-release.pub` | placeholder; installers run sha256-only + loud warning until replaced |

Fail-closed rule: once a real key is present, a **missing or bad signature aborts the
install**. It never silently downgrades.

---

## 1. Key ceremony (do once, on an offline machine)

```bash
# Offline box. minisign: https://jedisct1.github.io/minisign/
minisign -G -p moonbite-release.pub -s moonbite-release.key
```

- `moonbite-release.key` — **secret**. Keep it offline, passphrase-protected. **Never commit it.** (`*.key` is git-ignored; confirm.)
- `moonbite-release.pub` — the public key line (starts `RW…`). Publish it widely so users pin it independently of any one origin:
  1. paste it into `deploy/moonbite-release.pub`, replacing `REPLACE_ME…`;
  2. paste the **same** line into `deploy/setup-seed2.sh` at the `RELEASE_PUBKEY=` marker (grep `RELEASE_PUBKEY`);
  3. add it to the site (`website/`, the download page) and the top-level `README`.

Rotated/compromised key? Publish a new pubkey in all the above and re-sign; revoke by announcement (minisign has no revocation).

---

## 2. Decide the canonical binaries (audit B2 needs your call)

The drift guard is red because the repo currently holds **conflicting builds**:

- `release/bin/*.exe` — the **pre-relaunch** (Sep 3) set. `release/README.md` still
  documents the retired beta genesis `3d053c59…`; these will **not** join relaunched
  mainnet. Almost certainly stale.
- `release/miner/*.exe` — the **Sep 21 relaunch** set (`moonbited.exe` `89ba06a1…`,
  `moonbite-cli.exe` `1b8a3604…`). Untracked, dev-built, unsigned. This is what
  `build-windows-bundle.py` actually packages and the site serves.
- `release/SHA256SUMS.txt` and `website/downloads/README.txt` reference a **mix** of
  the above plus a **stale zip hash** (`6491437a…`; the real zip is `21e42d44…`).

You must decide, per artifact, which build is the real relaunch binary. Do not ship
the `release/bin` set unless you intend the old chain. **Reproducible rebuild from
`moonbite-core` (out of repo) is the right source of truth** — build the relaunch
binaries from a tagged commit, not the dev machine, if at all possible.

Linux hashes (`moonbited`, `moonbite-cli`, `…-linux-x86_64.tar.gz`) cannot be
verified from this Windows checkout — regenerate them on the build box.

---

## 3. Build, sign, stamp, stage (every release)

```bash
# 1. Put the canonical binaries in release/miner/ (windows) and the linux build dir.
# 2. Build the bundle + machine-readable manifest:
python deploy/miner/build-windows-bundle.py            # writes release/dist/{zip,SHA256SUMS.txt}

# 3. Sign the manifest with the offline key:
minisign -Sm release/dist/SHA256SUMS.txt               # -> SHA256SUMS.txt.minisig
#    (do the same for the linux SHA256SUMS-linux.txt)

# 4. Update the human-facing references to the REAL hashes:
#    - release/SHA256SUMS.txt       (canonical set only; drop the stale beta rows)
#    - website/downloads/README.txt (the "verify what you downloaded" block)
#    - release/README.md            (fix the genesis line if it still says 3d053c59)

# 5. Prove they match before publishing:
python deploy/verify-release-checksums.py --strict     # must exit 0

# 6. Stage (copies zip + sums + .minisig into the served download dir):
python deploy/miner/build-windows-bundle.py --stage
#    Publish SHA256SUMS-linux.txt(+.minisig) to website/downloads/ so
#    setup-seed2.sh's SUMS_URL resolves.
```

Then, and only then, commit the canonical binaries / references. Until step 5 is
green, CI stays red and nothing should be advertised as verifiable.

> The pending untracked `release/miner/moonbited.exe` and `moonbite-cli.exe` should
> not be committed or shipped until they are the confirmed canonical build with
> signed sums (this runbook). That was flagged in the audit.

---

## 4. Verify as a user (what the site should tell people)

```bash
minisign -Vm SHA256SUMS.txt -P RW…      # authenticity (paste the published pubkey)
sha256sum -c SHA256SUMS.txt             # integrity of each file
```

Replace the current "compare this hash" prose with "verify this signature" — a bare
checksum next to the binary proves nothing against an origin swap.
