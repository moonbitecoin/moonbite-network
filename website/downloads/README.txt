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

Each bundle contains moonbited (the node), moonbite-cli, the mine script and a
README. Unzip, then run:

  Windows (PowerShell)   .\mine.ps1
  Linux                  ./mine.sh

That starts the node, connects to the seed, creates a wallet and mines to your
own address. Back up the wallet folder in your data directory
(%USERPROFILE%\.moonbite on Windows, ~/.moonbite on Linux).

Verify what you downloaded against the checksums published with each GitHub
release: https://github.com/moonbitecoin/MoonBite-Coin/releases

Binaries built before 3 September 2026 belong to an earlier chain and will
not connect to the current network.
