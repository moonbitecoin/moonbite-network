MoonBite Reactor — desktop miner
================================

A cinematic front-end for mining the live MoonBite (MBITE) chain. The
network node does the real proof-of-work; you just supply the address that
should receive the block rewards and watch the reactor run.

RUN IT
------
  * Windows (packaged .exe):  double-click  MoonBite-Reactor.exe
  * From source (any OS):     double-click  Start-MoonBite-Reactor.bat
                              or run:        python moonbite_reactor.py

Then paste your MoonBite reward address (moon1… or M…) and press
"Start Reactor". Blocks you mine pay straight to that address.

OPTIONS (source / command line)
--------------------------------
  --port 7801           local UI port
  --explorer <url>      point at a different node/explorer
  --no-browser          serve only, don't open a window (for testing)

WHAT IT DOES / DOESN'T DO
-------------------------
  * Sends only a mine request ({"address": ...}) to the public explorer.
  * Never sees, asks for, or stores a private key or seed phrase.
  * Your address is remembered locally (browser localStorage) for convenience.
  * Non-custodial. Pre-mainnet — coins carry no market value yet.

Requires nothing but the bundled files (packaged build) or Python 3
(source build). Standard library only.
