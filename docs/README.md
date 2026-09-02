# BigCoin (BIG) — Operator & Integration Docs

MoonBite is an experimental, mineable cryptocurrency: a RandomX proof-of-work fork
in the Litecoin/Bitcoin Core lineage. It uses the standard Bitcoin/Litecoin Core
JSON-RPC interface, so most existing tooling and integrations work with minimal
changes.

At a glance:

| Parameter        | Value                                   |
|------------------|-----------------------------------------|
| Ticker           | MBITE                                    |
| Algorithm        | RandomX (PoW, CPU-optimised)            |
| Block time       | 2 minutes (120 s)                       |
| Difficulty retarget | every 60 blocks (~2 h), 4x clamp     |
| Initial reward   | 10 MBITE, halving every 1,650,000 blocks (~6.27 years) |
| Max supply       | 32,999,999.96 MBITE                     |
| Address prefix   | `M` (base58) / `moon1...` (bech32)      |
| Ports            | P2P 9444 (testnet 19555), RPC 9445      |
| Software         | `bigcoind`, `bigcoin-cli`, `bigcoin-qt` |

---

## Documentation index

| Doc | Description |
|-----|-------------|
| [MINING.md](MINING.md) | How to mine MBITE: regtest testing, solo mining, RandomX miners, and joining a pool — with an honest note on difficulty and profitability. |
| [WALLET.md](WALLET.md) | Using the wallet: creating addresses, checking balances, sending, backing up, encrypting, and why key/backup safety is critical. |
| [NODE_SETUP.md](NODE_SETUP.md) | Running a full/seed node: sample `bigcoin.conf`, firewall & port forwarding, a systemd unit, adding peers, and bootstrapping a launch network. |
| [EXCHANGE_LISTING.md](EXCHANGE_LISTING.md) | What exchanges require to list BIG: technical readiness, RPC compatibility, a coin info sheet, and the honest business/legal realities. |

---

## Disclaimer

BigCoin is **experimental software**. It may contain bugs, and its network may be
small, unstable, or have very low hash power. Nothing in this documentation is
**financial, investment, legal, or tax advice**. Cryptocurrency mining and
holding carry real risk, including total loss of funds.

**Your keys, your coins — lost keys mean lost coins, forever.** You are solely
responsible for securing your wallet, backups, and passphrases.

Use BigCoin at your own risk.
