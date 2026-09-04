MoonBite miner downloads
========================

Mining is solo and pool-free: you run a full MoonBite node on your own
machine and it mines straight to your own wallet. No pool, no account, no
third party ever touches your coins.

Downloads (current chain: 2-minute blocks, 10 MBITE per block)

  Windows   https://moonbite.org/download/windows
  Linux     https://moonbite.org/download/linux
  macOS     not built yet - build from source at
            https://github.com/moonbitecoin/moonbite-core

Each bundle contains moonbited (the node), moonbite-cli, the mine script, a
README, and on Windows the moonbite-wallet.exe desktop wallet app. Unzip, then run:

  Windows (PowerShell)   .\mine.ps1
  Linux                  ./mine.sh

That starts the node, connects to the seed, creates a wallet and mines to your
own address. Back up the wallet folder in your data directory
(%USERPROFILE%\.moonbite on Windows, ~/.moonbite on Linux).

Verify what you downloaded (sha256):
  moonbite-miner-windows-x86_64.zip   6491437a0a31d664118cd58e513226b0bef8850a25605c7945701cde71f2a503
  moonbite-miner-linux-x86_64.tar.gz  c28fd28d39965afd28b1e2b7b8403947d066afd37b0a5fc6333317acac1e4a21

Binaries built before 3 September 2026 belong to an earlier chain and will
not connect to the current network.
