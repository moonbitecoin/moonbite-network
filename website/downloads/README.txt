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
  moonbite-miner-windows-x86_64.zip   accec8d4d512b57f2a9abaf1004d27e49a1a5f046e4e015d810cd2a96b21dbaa
  moonbite-miner-linux-x86_64.tar.gz  ba9433cf738a9eec34f6056230721d782f8b2e9acd5f2419a6eaf25b31ada29d

Binaries built before 3 September 2026 belong to an earlier chain and will
not connect to the current network.
