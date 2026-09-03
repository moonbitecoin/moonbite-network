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

Verify what you downloaded (sha256):
  moonbite-miner-windows-x86_64.zip   9de9ce468c378f30c66fe97728adb95f9046c5ef88c8f570cb2711cac27046ad
  moonbite-miner-linux-x86_64.tar.gz  a9f97af63dac2892ed0601f1864b71c4d75f27a2f36e8d291176924f19ff2eb0

Binaries built before 3 September 2026 belong to an earlier chain and will
not connect to the current network.
