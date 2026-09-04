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

First get your address: open the MoonBite wallet (the app, or
moonbite.org/wallet), create a wallet, go to **Receive**, and copy your
`moon1...` address. Then point the miner at it so rewards land in your wallet:

**Linux / macOS**
```bash
./mine.sh moon1youraddress
```

**Windows (PowerShell)**
```powershell
.\mine.ps1 moon1youraddress
```

The script starts your node, connects to the network, waits until it is fully
synced, then mines to that address. Run it again later without the address and
it reuses the one you saved. Leave it running; each block it finds is printed,
and the reward appears in your wallet after it matures.

## Data directory

Your node and wallet live in `~/.moonbite` (Linux/macOS) or
`%USERPROFILE%\.moonbite` (Windows). Set `MOONBITE_DATADIR` before running
the script to put them somewhere else.

## The wallet app

The MoonBite desktop wallet is a separate download - it is the same wallet as
moonbite.org/wallet, in its own window (self-custody, 12-word recovery phrase).
Get it from moonbite.org/wallet (Download) or moonbite.org/download/wallet.
You don't need it to mine: create a wallet there, copy your address, and pass
it to this miner.


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
