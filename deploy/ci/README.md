# CI: cross-platform release binaries

`release.yml` builds the MoonBite node (`moonbited` + `moonbite-cli`) and the
solo-miner bundle for **Linux, Windows, and both macOS architectures**, and
attaches them to a GitHub Release on every `v*` tag.

## Where it goes

This file builds the **C++ node**, so it lives in the node repo:

```
moonbite-core/.github/workflows/release.yml
```

A copy is kept here in MoonBite-Coin only for visibility and review. The
running workflow must be the one in moonbite-core.

## How it works

- Rebuilds **RandomX v1.2.1** from source for each target and overwrites the
  vendored Linux `librandomx.a`. That version was verified byte-identical to
  the vendored library (same 32-byte-seed hash), so every platform's binary is
  consensus-correct.
- Builds dependencies with the `depends` system, `NO_QT=1` (daemon + cli only).
- **Windows** is cross-compiled from an Ubuntu runner with mingw-w64 (posix
  threads). **macOS** builds natively on GitHub's macOS runners, which carry the
  Apple SDK that cannot be used off Apple hardware - the reason macOS cannot be
  cross-built from Linux.
- Bundles the binaries with `mine.sh` / `mine.ps1` / `README.md` pulled from
  this repo (`release/miner/`), so the miner scripts have one source of truth.
- Publishes all archives plus `SHA256SUMS.txt` to the Release.

## Releasing

```bash
git tag v0.1.0 && git push origin v0.1.0
```

The `build` matrix runs; the `release` job collects the artifacts and creates
the Release. `depends` output is cached per host, so only the first tag pays
the full dependency-build cost.
