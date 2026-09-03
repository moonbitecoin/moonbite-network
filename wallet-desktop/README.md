# MoonBite Wallet — desktop app

The desktop wallet is the MoonBite web wallet in a native window, so it is the
exact same self-custody wallet: BIP39 12-word recovery phrase, real P2WPKH
addresses, on-device keys.

`moonbite-wallet-desktop.py` wraps https://moonbite.org/wallet with pywebview
(Edge WebView2 on Windows). Build a standalone exe:

    pip install pywebview pyinstaller
    pyinstaller --noconsole --onefile --name moonbite-wallet --collect-all webview moonbite-wallet-desktop.py

The Windows download bundle (release/miner) ships the built moonbite-wallet.exe.
