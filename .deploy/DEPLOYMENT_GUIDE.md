# MoonBite Deployment Guide

## Patches

Two patches are ready, to be applied sequentially:

1. **`0001-WALLET-Redesign-PWA-dashboard-mining-aware-empty-sta.patch`** (21 KB)
   - Latest: Mining-aware, empty-state-first wallet redesign
   - Shows "How to get MBITE" when balance is 0
   - Prominent receive address for new users
   - Brand-compliant: Reserve Palette, Archivo/Inter typography

2. **`0001-CHAIN-MoonBite-mainnet-testnet-regtest-genesis-block.patch`** (19 KB)
   - C++ chain: All 3 genesis blocks baked (MAIN/TESTNET/REGTEST)
   - Treasury zeroed (ADR-007: no protocol revenue)
   - Consensus: 50 MBITE, 330k halving, 33M cap
   - RandomX PoW verified

## To Deploy

### Web App (moonbite)

```bash
# Clone the empty repo
git clone https://github.com/moonbitecoin/moonbite.git
cd moonbite

# Apply the wallet patch (includes all web app files + wallet redesign)
git am path/to/0001-WALLET-Redesign-PWA-dashboard-mining-aware-empty-sta.patch

# Push to GitHub
git remote add origin https://github.com/moonbitecoin/moonbite.git
git branch -M main
git push -u origin main
```

### C++ Chain (moonbite-core)

```bash
# Clone the empty repo
git clone https://github.com/moonbitecoin/moonbite-core.git
cd moonbite-core

# Apply the genesis patch
git am path/to/0001-CHAIN-MoonBite-mainnet-testnet-regtest-genesis-block.patch

# Push to GitHub
git remote add origin https://github.com/moonbitecoin/moonbite-core.git
git branch -M master
git push -u origin master
```

## What's Included

### Web App Patch
- Flask app: 50+ routes, consensus API, first-block ceremony
- Templates: 8 viral pages + wallet PWA + archive + classic index
- Static: Self-hosted fonts (Archivo Black, Inter), CSS, JavaScript
- Docs: 9 ADRs, mining guide, threat model, whitepaper, guidelines
- **Wallet redesign:**
  - Empty state: "How to get MBITE" + 3 paths (Mine, Receive, Testnet)
  - Prominent address display with copy button
  - Progressive reveal: Send/advanced features only after balance > 0
  - Brand-compliant design (Reserve Palette, typography, focus states)

### C++ Chain Patch
- **Genesis blocks (all RandomX-verified):**
  - MAIN: nonce 2744921, hash 2a5ae28180448a88bdd89f2cca926ce6e82d5e8eda787ede03ee244aa0aad4ea
  - TESTNET: nonce 284742, hash 67afe8001e52e947b27d201dd2768839dd79b6cf6d259f123172f4f428a3cd5d
  - REGTEST: nonce 8, hash e5e666e9b7813a408f078a6dd8fb1457c3aed176493b99b2278d85031b259f7d
- Treasury: 0% on all 3 networks (nTreasuryRateBps=0)
- Consensus: 50 MBITE subsidy, 330,000-block halving, 600s target block time
- Binary names: moonbited, moonbite-cli, moonbite-qt, moonbite-tx, moonbite-wallet

## After Deployment

1. **Web:**
   - Test empty state: Wallet shows "How to get MBITE" at 0 balance
   - Test receiving: Generate address, copy to clipboard
   - Deploy to Railway or your host

2. **C++:**
   - Rebuild: `make -j8` to compile with baked genesis
   - Run nodes: `moonbited -mainnet`, `-testnet`, `-regtest`
   - Verify: `getblocktemplate`, `getnetworkinfo` confirm consensus

3. **Integration:**
   - Update pool/mining software to point at new nodes
   - Update web app to connect to live chain
   - Announce mainnet launch

---

Ready to ship. 🚀
