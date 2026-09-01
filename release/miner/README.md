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

**Linux / macOS**
```bash
./mine.sh
```

**Windows (PowerShell)**
```powershell
.\mine.ps1
```

That is the whole thing. The script starts your node, connects to the MoonBite
network, creates a wallet, and begins mining to your own address. Leave it
running; each block it finds is printed.

## Your coins and your wallet

- Your wallet is stored in your MoonBite data directory (`~/.moonbite` on
  Linux/macOS, `%USERPROFILE%\.moonbite` on Windows).
- **Back up the `wallet` folder.** If you lose it, your coins are gone - no one
  can recover them for you.
- A mined block's reward is spendable **100 blocks** after it is found (this is
  standard coinbase maturity, and protects the chain).

## Speed

The node mines with one CPU thread. That is deliberate for a fair launch -
nobody starts with an unfair edge. A faster multi-core miner may be released
later; it is not required to mine today.

## Commands

| Command | What it does |
|---|---|
| `./mine.sh` / `.\mine.ps1` | start the node and mine |
| `./mine.sh address` | print your mining address |
| `./mine.sh stop` | stop the node |

## It connects to these seed nodes

Your node reaches the network through the public MoonBite seeds. They are set
for you in the generated `moonbite.conf`; you do not need to configure anything.
