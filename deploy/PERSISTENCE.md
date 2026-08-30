# Persistent storage

A container's filesystem is discarded on every redeploy. Without a mounted
volume, MoonBite's durable state goes with it:

| File                  | What is lost                                    |
|-----------------------|-------------------------------------------------|
| `chain.db`            | Every block. The chain restarts at height 0 and every balance goes to zero. |
| `wall.db`             | Every certificate on `/wall`.                   |
| `wallet_history.db`   | Transaction history, address books, preferences. |

The chain is the one that matters. A coin whose entire history is deleted by
its own deploy is not a coin.

## What the application expects

One directory. Everything durable lives in it, resolved in this order:

1. `MOONBITE_DATA_DIR` if set.
2. `/data` if that directory exists — the conventional mount point.
3. Otherwise the application directory, which is the local-development case.

So on a host where a volume is mounted at `/data`, there is nothing to
configure: the files land on the volume by themselves. Chain persistence also
switches on automatically when a volume is detected, and stays off locally so
tests and development still get a clean in-memory chain.

## Railway

1. Open the service, then **Settings → Volumes → Add Volume**.
2. Set the mount path to **`/data`**.
3. Size it for the chain. Blocks accumulate and are never pruned: at ~1 KB per
   block and 144 blocks a day, a year is roughly 50 MB. 1 GB is ample and
   leaves room for the wall and wallet history.
4. Redeploy. `/data` now exists, so the app uses it with no further settings.

To confirm it took, check the deploy logs after a restart:

```
Replayed N persisted block(s); height=N
```

That line only appears when blocks were loaded from disk. If the height is 0
after a redeploy that had mined blocks, the volume is not mounted where the app
is looking.

## Other hosts

Mount any persistent disk and point the app at it:

```bash
MOONBITE_DATA_DIR=/var/lib/moonbite
```

The directory is created if missing. Individual files can still be redirected
with `MOONBITE_CHAIN_DB`, `MOONBITE_WALL_DB` and
`MOONBITE_WALLET_HISTORY_DB`, which override the data directory — useful for
putting the chain on a different disk from everything else.

## Backups

A volume protects against redeploys, not against deletion or corruption. The
databases are ordinary SQLite files, so the standard tooling works:

```bash
sqlite3 /data/chain.db ".backup '/data/backup/chain-$(date +%F).db'"
```

Use `.backup` rather than copying the file: these run in WAL mode, and a
plain `cp` of a live database can capture a torn write.

## Migrating existing data

Databases used to be committed to git, so a deployment may already hold data
written before this change. Copy it onto the volume once, before the first
deploy that uses it:

```bash
railway run cp wall.db wallet_history.db /data/
```

Afterwards the copies beside the code are ignored — the app reads only the
volume.
