# Mine MoonBite on your own machine

MoonBite mining is **solo and pool-free**. You run a full MoonBite node on your
own computer and it mines directly to your own wallet. There is no pool, no
website login, no third party that ever touches your coins. Every block you
find pays you, and only you.

> The "miner" on moonbite.org/start is a **visual demo** and does not mine real
> MBITE. Real mining is done here, by the node, using the steps below.

## What you need

- The MoonBite node for your OS (`moonbited` + `moonbite-cli`), placed in this
  folder next to the `mine` script.
- A few GB of free RAM. Mining uses RandomX, a CPU algorithm designed so an
  ordinary computer is competitive and specialised hardware is not.

## Run it

No wallet, no account, nothing to set up first. Just run the script:

**Linux / macOS**
```bash
./mine.sh
```

**Windows (PowerShell)**
```powershell
.\mine.ps1
```

The script starts your node, connects to the network, waits until it is fully
synced, then mines. With no address given it generates one for you, in this
node's own built-in wallet on this machine — it prints that address the first
time, and reuses it on every run after. That address is real and yours; import
it into the wallet app any time you want to spend from it.

Already have a wallet and want rewards to land there directly instead? Pass its
address:

```bash
./mine.sh moon1youraddress        # Linux / macOS
.\mine.ps1 moon1youraddress       # Windows
```

Leave it running; each block it finds is printed, and the reward is spendable
after it matures (below).

## Data directory

Your node and wallet live in `~/.moonbite` (Linux/macOS) or
`%USERPROFILE%\.moonbite` (Windows). Set `MOONBITE_DATADIR` before running
the script to put them somewhere else.

## The wallet app

You do not need this to mine — the miner makes its own address, above. The
MoonBite desktop wallet is a separate download for when you want to spend,
send, or manage coins with a proper interface: the same wallet as
moonbite.org/wallet, in its own window (self-custody, 12-word recovery
phrase). Get it from moonbite.org/wallet (Download) or
moonbite.org/download/wallet, then import the address this miner generated —
or skip that step entirely and just point the miner at a wallet address you
already made there.


## Your coins and your wallet

- Your wallet is stored in your MoonBite data directory (`~/.moonbite` on
  Linux/macOS, `%USERPROFILE%\.moonbite` on Windows).
- **Back up the `wallet` folder.** If you lose it, your coins are gone - no one
  can recover them for you.
- A mined block's reward is spendable **100 blocks** after it is found (this is
  standard coinbase maturity, and protects the chain).

## Speed

The node mines with one RandomX thread per physical CPU core, so a normal
desktop is competitive. Difficulty retargets every 60 blocks (about two hours)
toward a 2-minute block time, and each block pays 10 MBITE.

## Commands

| Command | What it does |
|---|---|
| `./mine.sh` / `.\mine.ps1` | start the node and mine |
| `./mine.sh address` | print your mining address |
| `./mine.sh stop` | stop the node |

## It connects to these seed nodes

Your node reaches the network through the public MoonBite seeds. They are set
for you in the generated `moonbite.conf`; you do not need to configure anything.
