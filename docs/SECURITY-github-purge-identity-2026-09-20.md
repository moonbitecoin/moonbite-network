# GitHub Support request — purge old commit SHAs after identity rewrite

Send this to GitHub Support at https://support.github.com/contact (category:
"I want to remove sensitive data"), signed in as the account that owns the
repo (moonbitecoin).

---

**Subject:** Purge pre-rewrite commit SHAs (leaked personal email/handle) from moonbitecoin/MoonBite-Coin

**Body:**

I rewrote the git history of my public repository moonbitecoin/MoonBite-Coin
to remove personal identifying information (a real email address and a
GitHub handle tied to my real name) that was committed as the author/committer
of the two earliest commits. I force-pushed the rewritten history to `main`,
`wallet-rebuild`, and the tag `v0.2.0`.

The old commits are no longer reachable from any ref in the repository, but I
understand GitHub retains unreferenced objects and their SHAs may still be
fetchable directly. Please purge the following pre-rewrite commit SHAs (and
any cached views, PR/commit-comment references, or search index entries tied
to them) from moonbitecoin/MoonBite-Coin:

- `f0a496532ff0fa8505f1ff0ee6425330819c0658` (old main tip, pre-rewrite)
- `000b69071d3449985414abe20bb410e971f28720` (old initial-import commit — this
  one is the primary target: its author/committer field contains the personal
  email and handle)
- `7bf9d1eee68cae52e0b879fc12a873752437cbe8` (old second commit, same issue)
- `a96bc4ce0998a82247da3228c1178657bb37eec0` (old wallet-rebuild tip, pre-rewrite)
- `6b99a9a056b8235d10ef70727bce65ec686c80c3` (old v0.2.0 tag target, pre-rewrite)

I control this account. Please confirm once these are no longer retrievable
via `raw.githubusercontent.com` or `github.com/moonbitecoin/MoonBite-Coin/commit/<sha>`
by direct SHA.

Thank you.

---

## Verify afterward

    curl -s -o /dev/null -w "%{http_code}\n" \
      https://github.com/moonbitecoin/MoonBite-Coin/commit/000b69071d3449985414abe20bb410e971f28720

Should return 404 once purged (it will still 200 until GitHub actually purges
the cache — force-pushing alone does not remove it).

## Anyone else with a clone or fork

Confirmed via the GitHub API on 2026-09-20: this repo has 0 forks, so no
other repository needs to be named in the purge request. Anyone who cloned
it directly (not via fork) still has the old history in their local clone
until they re-clone or hard-reset to the new `origin/main` — there's no way
to force that from GitHub's side, it's only a concern if you know of specific
clones out there.
