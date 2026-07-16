# Using the MoonBite Wallet

MoonBite ships two wallet front-ends over the same wallet engine:

- **`moonbite-qt`** — graphical (GUI) wallet, good for everyday use.
- **`moonbited` + `moonbite-cli`** — headless daemon plus command-line client, good
  for servers, integrations, and scripting.

Both use the standard Bitcoin/Litecoin Core JSON-RPC interface.

---

## Address formats

MoonBite supports two address styles:

| Type              | Looks like                    | Notes                          |
|-------------------|-------------------------------|--------------------------------|
| Base58 (legacy/P2SH) | starts with `B` (e.g. `B7f...`) | address prefix is `B`       |
| Bech32 (native SegWit) | `big1...`                  | bech32 HRP is `big`, lowercase |

Prefer `big1...` (bech32) addresses where supported — they are cheaper to spend
and have better error detection. Legacy `B...` addresses remain valid.

---

## Installing and running

### GUI

Download/build `moonbite-qt`, then launch it. On first run it creates a data
directory and (optionally) a wallet. Just run:

```bash
moonbite-qt
```

### Daemon + CLI

Start the background daemon:

```bash
moonbited -daemon -server \
  -rpcuser=youruser -rpcpassword=yourpass
```

Then talk to it with the CLI:

```bash
moonbite-cli getblockchaininfo
```

(For a persistent config file instead of command-line flags, see
[NODE_SETUP.md](NODE_SETUP.md).)

---

## Creating a new address

```bash
moonbite-cli getnewaddress
# -> big1qexampleaddressxxxxxxxxxxxxxxxxxxxxx
```

You can label addresses and request a specific type:

```bash
moonbite-cli getnewaddress "savings"            # labeled
moonbite-cli getnewaddress "" "bech32"          # force bech32 (big1...)
moonbite-cli getnewaddress "" "legacy"          # force legacy (B...)
```

In the GUI, use **Receive -> Request payment** to generate an address.

---

## Checking your balance

```bash
moonbite-cli getbalance            # confirmed spendable balance
moonbite-cli getbalances           # detailed: trusted / untrusted / immature
moonbite-cli getwalletinfo         # wallet-wide info
```

- **Immature balance** = mined coinbase rewards still waiting for 100
  confirmations.
- **Untrusted pending** = incoming unconfirmed transactions.

---

## Sending MBITE

```bash
moonbite-cli sendtoaddress "<address>" <amount>
```

Example:

```bash
moonbite-cli sendtoaddress "big1qrecipientxxxxxxxxxxxxxxxxxxxxxxxxxx" 12.5
```

Useful options:

```bash
# subtract the fee from the amount sent (recipient receives amount - fee)
moonbite-cli sendtoaddress "<addr>" 12.5 "" "" true

# set a specific fee rate (MBITE/kvB) for one send
moonbite-cli -named sendtoaddress address="<addr>" amount=12.5 fee_rate=0.0001
```

Always double-check the destination address before sending. **Transactions are
irreversible** once confirmed.

---

## Backing up your wallet

MoonBite (like modern Bitcoin/Litecoin Core) can use either legacy `wallet.dat`
BerkeleyDB wallets or newer **descriptor** wallets. Back up whichever you have.

### Safe on-disk backup (works for any wallet type)

```bash
moonbite-cli backupwallet "/secure/path/moonbite-wallet-backup.dat"
```

This produces a consistent copy even while the wallet is in use. Store it
somewhere safe and offline.

### Descriptor / private-key export

For descriptor wallets you can export the descriptors (which contain the keys):

```bash
moonbite-cli listdescriptors true    # includes private keys — handle with care!
```

Keep any exported descriptors or keys **encrypted and offline.** Anyone with them
can spend your coins.

### GUI backup

**File -> Backup Wallet...** writes a `wallet.dat` copy you can store safely.

---

## Encrypting your wallet

Encrypt the wallet so a passphrase is required to spend:

```bash
moonbite-cli encryptwallet "a-long-strong-passphrase"
```

After encrypting:

- The wallet daemon restarts and the old unencrypted keys are gone.
- **Make a fresh backup after encrypting** (the keypool changes).
- To spend, unlock temporarily:

```bash
# unlock for 60 seconds
moonbite-cli walletpassphrase "a-long-strong-passphrase" 60

# change the passphrase later
moonbite-cli walletpassphrasechange "old-pass" "new-pass"
```

In the GUI, use **Settings -> Encrypt Wallet**.

> If you forget your passphrase, **there is no recovery.** The coins are lost.

---

## CRITICAL: seed and backup safety

**Your keys, your coins. Lost keys = lost coins forever.**

There is no company, admin, or "forgot password" link that can restore access to
a MoonBite wallet. The rules that make MoonBite trustless also mean **you** are
fully responsible for your keys.

Follow these rules:

1. **Back up immediately** — right after creating (and again after encrypting)
   your wallet. Use `backupwallet` or the GUI backup.
2. **Keep multiple copies** in separate physical locations (e.g. an encrypted USB
   drive and a printed/handwritten copy in a safe).
3. **Never store keys or backups in plaintext** in cloud storage, email, chat, or
   screenshots.
4. **Guard your encryption passphrase** as carefully as the wallet itself — losing
   it is the same as losing the wallet.
5. **Test your backup** by restoring it on a spare/offline machine before you rely
   on it.
6. **Beware malware and phishing.** Anyone who obtains your `wallet.dat`,
   descriptors, or private keys can drain your funds instantly and irreversibly.

If in doubt, assume that a lost or leaked backup means lost or stolen coins. Act
accordingly.
