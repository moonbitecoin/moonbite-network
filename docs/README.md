# MoonBite (MBITE) — Operator & Integration Docs

MoonBite is an experimental, mineable cryptocurrency: a Scrypt proof-of-work fork
in the Litecoin/Bitcoin Core lineage. It uses the standard Bitcoin/Litecoin Core
JSON-RPC interface, so most existing tooling and integrations work with minimal
changes.

At a glance:

| Parameter        | Value                                   |
|------------------|-----------------------------------------|
| Ticker           | MBITE                                      |
| Algorithm        | Scrypt (PoW)                            |
| Block time       | 2.5 minutes                             |
| Initial reward   | 50 MBITE, halving every 840,000 blocks    |
| Max supply       | 84,000,000 MBITE                          |
| Address prefix   | `B` (base58) / `big1...` (bech32)       |
| Ports            | P2P 9444 (testnet 19555), RPC 9445      |
| Software         | `moonbited`, `moonbite-cli`, `moonbite-qt` |

---

## Documentation index

| Doc | Description |
|-----|-------------|
| [MINING.md](MINING.md) | How to mine MBITE: regtest testing, solo mining, CPU/GPU Scrypt miners, and joining a pool — with an honest note on difficulty and profitability. |
| [WALLET.md](WALLET.md) | Using the wallet: creating addresses, checking balances, sending, backing up, encrypting, and why key/backup safety is critical. |
| [NODE_SETUP.md](NODE_SETUP.md) | Running a full/seed node: sample `moonbite.conf`, firewall & port forwarding, a systemd unit, adding peers, and bootstrapping a launch network. |
| [EXCHANGE_LISTING.md](EXCHANGE_LISTING.md) | What exchanges require to list MBITE: technical readiness, RPC compatibility, a coin info sheet, and the honest business/legal realities. |

---

## Disclaimer

MoonBite is **experimental software**. It may contain bugs, and its network may be
small, unstable, or have very low hash power. Nothing in this documentation is
**financial, investment, legal, or tax advice**. Cryptocurrency mining and
holding carry real risk, including total loss of funds.

**Your keys, your coins — lost keys mean lost coins, forever.** You are solely
responsible for securing your wallet, backups, and passphrases.

Use MoonBite at your own risk.
