# GitHub Support request — purge sensitive data from a fork network

Send this to GitHub Support at https://support.github.com/contact (category:
"I want to remove sensitive data"). You must be signed in as the account that
owns the repositories, and you likely need to send it from BOTH accounts, or
name both and confirm you control them.

---

**Subject:** Purge sensitive data (email list) cached across a fork network

**Body:**

I need sensitive data permanently removed from a fork network. A file
containing personal data (email addresses collected via a signup form) was
committed and pushed while the repositories were public. I have removed the
file from the current branches, but the commits remain reachable by SHA across
the fork network and in cached views.

Please purge the following blob/commits from all repositories in the network,
including cached views and the pull-request/commit caches:

- File path: `notify_signups.jsonl`
- Commit SHAs: `5152cd0`, `9f5dce6`, `8eaf21f`
- Repositories in the network:
  - `zaptapagency/MoonBite`  (fork-network root / parent)
  - `moonbitecoin/MoonBite-Coin`  (fork of the above)

I control both accounts. Please confirm once the objects are no longer
retrievable via `raw.githubusercontent.com` by SHA from any member of the
network.

Thank you.

---

## Before or alongside sending this

1. Make `zaptapagency/MoonBite` private, or delete it. (Needs the zaptapagency
   account — the CLI in this project is signed in as moonbitecoin only.)
2. Delete `moonbitecoin/MoonBite-Coin` (the public fork) once the clean private
   repo `moonbitecoin/MoonBite-Coin-Private` holds the purged history.
3. Consider the 1,091 email addresses compromised for the period they were
   public. If any were of real subscribers, a breach notification may be
   appropriate depending on your jurisdiction.

## Verify the blob is gone (run after support confirms)

    curl -s -o /dev/null -w "%{http_code}\n" \
      https://raw.githubusercontent.com/zaptapagency/MoonBite/5152cd0/notify_signups.jsonl
    curl -s -o /dev/null -w "%{http_code}\n" \
      https://raw.githubusercontent.com/moonbitecoin/MoonBite-Coin/5152cd0/notify_signups.jsonl

Both should return 404.
