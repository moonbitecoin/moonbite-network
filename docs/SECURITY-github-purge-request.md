# GitHub Support — request to purge stale/dangling commits after history rewrite

**Repository:** https://github.com/moonbitecoin/MoonBite-Coin
**Account:** moonbitecoin (owner)
**Current branch HEAD (`main`):** 2c00aa5

## Request

We rewrote this repository's history with `git filter-repo` and force-pushed
`main` to remove sensitive strings from every commit. The old commits are no
longer reachable from any branch, tag, or ref, but their object SHAs may still
be served from GitHub's cache (e.g. `github.com/<owner>/<repo>/commit/<sha>`)
until garbage collection runs.

Please:

1. Run garbage collection / permanently purge all unreachable (dangling) commits
   and their blobs from this repository's storage.
2. Invalidate any cached views of those commit and blob SHAs so they can no
   longer be fetched by direct URL.
3. Confirm there are no remaining forks or network references that could keep
   the old objects alive. (We previously deleted the fork parent and the old
   fork network for this project; please verify none remain.)

## Context

- The rewrite removed a small number of internal wallet addresses and two
  documentation/template files from all history.
- We have already force-pushed the cleaned `main` and deleted the leftover
  `refs/replace/*` refs that filter-repo created.
- This is a follow-up to our earlier support request about removing a leaked
  file from this project's history; please treat it with the same handling.

Thank you.
