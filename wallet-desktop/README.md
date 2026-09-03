# MoonBite desktop wallet (Windows)

A self-contained Tkinter GUI over the local MoonBite Core node. Standard library
only — no third-party packages.

- Reads `rpcuser`/`rpcpassword`/`rpcport` from the node's `moonbite.conf` and
  talks JSON-RPC to `moonbited` on `127.0.0.1`.
- Tabs: balance, Receive (address + copy), Send (with encrypted-wallet unlock),
  History. Refreshes every 12 s.
- Encrypt button (password entered in the app, never elsewhere), Unlock, and a
  lock-state indicator.
- MoonBite Reserve palette + moon-and-bars logo drawn on a canvas.

## Run
```
pythonw.exe wallet-desktop\moonbite-wallet.pyw
```
Set `MOONBITE_DATADIR` if the node's data dir is not `D:\MoonBite`.
