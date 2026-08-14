# Cryptocurrency Wallet Quick Reference Guide

---

## AT-A-GLANCE COMPARISON TABLE

| Wallet | Best For | Security | UX | DeFi | Privacy | Ease |
|--------|----------|----------|-----|------|---------|------|
| **MetaMask** | DeFi Trading | ★★★★☆ | ★★★★★ | ★★★★★ | ★★☆☆☆ | ★★★★★ |
| **Trust Wallet** | Mobile Users | ★★★★☆ | ★★★★★ | ★★★★☆ | ★★☆☆☆ | ★★★★★ |
| **Ledger Live** | Maximum Security | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★☆☆ | ★★★★☆ |
| **Trezor** | Privacy + Security | ★★★★★ | ★★★☆☆ | ★★☆☆☆ | ★★★★★ | ★★★☆☆ |
| **BlueWallet** | Bitcoin Privacy | ★★★★★ | ★★★★☆ | ☆☆☆☆☆ | ★★★★★ | ★★★★☆ |
| **Phantom** | Solana/DeFi | ★★★★☆ | ★★★★★ | ★★★★★ | ★★☆☆☆ | ★★★★★ |
| **Exodus** | Beginners | ★★★☆☆ | ★★★★★ | ★★★☆☆ | ★★☆☆☆ | ★★★★★ |
| **Atomic Wallet** | Multi-Chain | ★★★★☆ | ★★★★☆ | ★★★☆☆ | ★★★☆☆ | ★★★★☆ |
| **Electrum** | Power Users | ★★★★★ | ★★★☆☆ | ☆☆☆☆☆ | ★★★★★ | ★★☆☆☆ |
| **Coinbase Wallet** | Institutions | ★★★★☆ | ★★★★☆ | ★★★★☆ | ★★☆☆☆ | ★★★★☆ |

---

## CRITICAL FEATURES CHECKLIST

### Must-Have Features
- [ ] Non-custodial (user controls keys)
- [ ] Hardware wallet support
- [ ] Seed phrase backup (12/24 words)
- [ ] Seed phrase verification
- [ ] Recovery from seed phrase
- [ ] Biometric authentication
- [ ] PIN/password protection
- [ ] Encryption at rest
- [ ] Portfolio balance tracking
- [ ] Transaction history

**Score:** Each wallet should have ✓ for all items above

---

## SECURITY TIER CLASSIFICATION

### Tier 1: Maximum Security (Institutional/Large Holdings)
**Recommended Setup:**
- Hardware wallet: Ledger Nano S Plus or Trezor Model T
- Software: Ledger Live or Trezor Suite
- Setup: Air-gapped signing + multi-signature (2-of-3)
- Storage: Cold storage, geographically distributed backups
- Recovery: Multiple backup locations, tested recovery plan

**Wallets:** Ledger Live, Trezor, Electrum (with hardware wallet)

**Cost:** $100-$500 (hardware + setup)
**Security Level:** 99.9%
**Recovery Time:** 1-2 weeks (if all backups lost)

### Tier 2: High Security (Active Traders/Serious Investors)
**Recommended Setup:**
- Hardware wallet + software wallet backup
- Multi-chain support (Ethereum, Bitcoin, Solana)
- Custom RPC nodes preferred
- Regular transaction audits
- Cold storage for 80%+ of holdings

**Wallets:** MetaMask + Ledger, Trust Wallet + Trezor

**Cost:** $0-$150
**Security Level:** 99%
**Recovery Time:** Minutes-to-hours

### Tier 3: Standard Security (Regular Users)
**Recommended Setup:**
- Non-custodial software wallet
- Strong password + biometric
- Seed phrase backed up securely
- Tested recovery procedure
- Hot wallet for 20-30% of holdings

**Wallets:** MetaMask, Trust Wallet, Phantom, Coinbase Wallet

**Cost:** Free
**Security Level:** 95%
**Recovery Time:** Minutes (with seed phrase)

### Tier 4: Basic Security (Beginners)
**Recommended Setup:**
- User-friendly wallet (Exodus, Coinbase Wallet)
- Guided backup process
- Small amounts only ($100-$1000)
- Biometric security enabled

**Wallets:** Exodus, Coinbase Wallet, mobile-only

**Cost:** Free
**Security Level:** 90%
**Recovery Time:** Minutes

---

## USE CASE DECISION TREE

### "I want to trade on DeFi protocols"
→ **Use MetaMask or Phantom**
- MetaMask: Ethereum/L2 focused
- Phantom: Solana focused
- Setup time: 5 minutes
- Cost: Free

### "I want maximum Bitcoin privacy"
→ **Use BlueWallet or Electrum**
- BlueWallet: User-friendly, CoinJoin easy
- Electrum: Advanced features, air-gapped possible
- Setup time: 10-20 minutes
- Privacy cost: Slightly longer transactions

### "I hold large amounts ($100k+)"
→ **Use Ledger Live + Ledger Hardware**
- Setup time: 30 minutes
- Cost: $60-$150
- Security improvement: 100x vs software
- Recovery: Hardware backup essential

### "I'm a beginner with $500-$5000"
→ **Use Trust Wallet or Coinbase Wallet**
- Setup time: 5 minutes
- Cost: Free
- Security: Adequate for this amount
- UX: Excellent, very intuitive

### "I need multi-signature security"
→ **Use Trezor (2-of-3) or Electrum + Hardware**
- Setup time: 1-2 hours
- Cost: $100-$300
- Security: Highest available
- Complexity: Significant

### "I want to use NFTs and DeFi"
→ **Use MetaMask or Trust Wallet**
- MetaMask: Web3 DeFi dominance
- Trust Wallet: Mobile NFT support
- Setup time: 5 minutes
- Cost: Gas fees vary ($5-$500+ per tx)

### "I'm an institution managing client funds"
→ **Use Ledger Live + Multi-Sig Setup**
- Ledger Live: Full compliance, tax reporting
- Multi-sig: Prevents single person theft
- Setup time: 1-2 weeks (legal + technical)
- Cost: $5000+
- Compliance: Full OFAC screening, KYC logs

---

## FEATURE REQUIREMENT MATRIX

### For Each Feature, Rate Your Need (1-5)
**5 = Absolutely must have**
**1 = Nice to have**

#### Security Features
- [ ] 5 4 3 2 1 - Hardware wallet support
- [ ] 5 4 3 2 1 - Air-gapped signing
- [ ] 5 4 3 2 1 - Multi-signature
- [ ] 5 4 3 2 1 - 2FA support
- [ ] 5 4 3 2 1 - Passphrase support
- [ ] 5 4 3 2 1 - Encrypted key export

#### Functionality Features
- [ ] 5 4 3 2 1 - DeFi/Swap integration
- [ ] 5 4 3 2 1 - Staking support
- [ ] 5 4 3 2 1 - NFT support
- [ ] 5 4 3 2 1 - Multi-chain support
- [ ] 5 4 3 2 1 - Smart contract interaction

#### Privacy Features
- [ ] 5 4 3 2 1 - CoinJoin/mixing
- [ ] 5 4 3 2 1 - Tor support
- [ ] 5 4 3 2 1 - Private RPC
- [ ] 5 4 3 2 1 - No IP logging
- [ ] 5 4 3 2 1 - Privacy coins support

#### UX Features
- [ ] 5 4 3 2 1 - Mobile app
- [ ] 5 4 3 2 1 - Desktop app
- [ ] 5 4 3 2 1 - Browser extension
- [ ] 5 4 3 2 1 - Dark mode
- [ ] 5 4 3 2 1 - Multi-language

#### Analytics Features
- [ ] 5 4 3 2 1 - Price charts
- [ ] 5 4 3 2 1 - Tax reporting export
- [ ] 5 4 3 2 1 - Spending analytics
- [ ] 5 4 3 2 1 - Transaction history export

**Total Your Scores:** Sum across all features
- **80-100:** Look for comprehensive solution (MetaMask, Trust Wallet, Ledger Live)
- **50-79:** Look for specialist solution (Phantom, Trezor, BlueWallet)
- **20-49:** Look for simple, beginner-friendly (Exodus, Coinbase Wallet)

---

## SETUP GUIDES BY WALLET

### MetaMask Setup (5 minutes)
1. Download Chrome extension or mobile app
2. Click "Create Wallet"
3. Set password
4. Save seed phrase (write down!)
5. Confirm seed words
6. Done! Wallet ready to use

**First Transaction:** Add funds via exchange or bridge

### Ledger Setup (30 minutes)
1. Buy Ledger Nano S Plus (~$70)
2. Download Ledger Live desktop/mobile
3. Connect device via USB
4. Initialize device (PIN + backup)
5. Write down 24-word recovery phrase
6. Install Bitcoin, Ethereum apps on device
7. Generate addresses in Ledger Live
8. Send funds to generated addresses

**Best for:** Large holdings, serious investors

### Trezor Setup (30 minutes)
1. Buy Trezor Model T (~$150)
2. Go to trezor.io (bookmark this!)
3. Initialize device
4. Set PIN
5. Write down 12/24-word recovery phrase
6. Access trezor.io/app to manage wallets
7. Connect to MetaMask for DeFi

**Best for:** Bitcoin maximalists, privacy advocates

### BlueWallet Setup (5 minutes - Bitcoin Only)
1. Download iOS or Android app
2. Tap "Create Wallet"
3. Select wallet type (standard/hot/watch-only)
4. Write down seed phrase
5. Confirm seed words
6. Done!

**Optional:** Enable CoinJoin for privacy

### Phantom Setup (5 minutes - Solana Focused)
1. Download browser extension (Chrome/Firefox)
2. Click "Create New Wallet"
3. Set password
4. Save recovery phrase
5. Confirm seed words
6. Approve dApps as needed

**Best for:** Solana traders

---

## COST ANALYSIS

### Hardware Costs
- Ledger Nano S Plus: $60 (cheapest)
- Ledger Nano X: $150 (Bluetooth)
- Ledger Nano S: $50 (outdated)
- Trezor Model T: $150 (best privacy)
- Trezor Model One: $100 (basic)

### Annual Software Costs
- MetaMask: Free
- Trust Wallet: Free
- Ledger Live: Free (premium = $9.99/month)
- Trezor: Free
- BlueWallet: Free
- Phantom: Free
- Exodus: Free
- Atomic Wallet: Free
- Electrum: Free
- Coinbase Wallet: Free

### Transaction Costs (Ethereum Example)
**Current Gas Prices (2025):**
- Simple transfer: $2-10 (depending on network load)
- Token approval + swap: $10-50
- Smart contract interaction: $20-200

**Ways to Reduce:**
1. Use Layer 2 (Arbitrum, Optimism) - 50-100x cheaper
2. Use Polygon - 1000x cheaper than Ethereum
3. Use Solana - <$0.01 per transaction
4. Wait for low gas (use gas alerts)
5. Use Limit Orders (set max gas price)

---

## SECURITY INCIDENT RESPONSE CHECKLIST

### "I think my wallet is compromised"
1. [ ] Stop all transactions immediately
2. [ ] Check transaction history for unauthorized transactions
3. [ ] Note the transaction hash and amount
4. [ ] Check blockchain explorer (etherscan.io)
5. [ ] Generate new address in same wallet
6. [ ] Move remaining funds to new address
7. [ ] Create new wallet if possible
8. [ ] Report to wallet provider
9. [ ] File police report (for records)
10. [ ] Monitor old address for 30 days

**Time to act:** Minutes (not hours)

### "I lost my seed phrase"
1. [ ] Create new wallet immediately
2. [ ] Generate new seed phrase
3. [ ] Do NOT attempt to recover old wallet
4. [ ] Transfer funds to new wallet
5. [ ] Treat old wallet as permanently inaccessible
6. [ ] Update all security systems

**Cost:** Whatever balance was on old wallet (potentially total loss)

### "I think I was scammed"
1. [ ] Stop all communication with scammer
2. [ ] Verify wallet address on blockchain explorer
3. [ ] Check if transaction is reversible (depends on coin)
4. [ ] Report to platform (if applicable)
5. [ ] Document all evidence (screenshots, transaction hashes)
6. [ ] Report to law enforcement
7. [ ] Monitor address for return transactions

**Recovery chances:** Very low (transactions are immutable)

---

## COMMON MISTAKES & HOW TO AVOID

### Mistake #1: Using Same Password Everywhere
- ❌ All accounts have password: "MyPassword123"
- ✓ Use unique password for each wallet
- ✓ Use password manager (1Password, Bitwarden)

### Mistake #2: Not Verifying Backup
- ❌ Backed up seed phrase, never tested recovery
- ✓ Test recovery on new device (using test amount)
- ✓ Verify every word is correct
- ✓ Test recovery every 6 months

### Mistake #3: Storing Seed Phrase Digitally
- ❌ Seed phrase in email, cloud drive, or screenshot
- ✓ Write on paper with pen
- ✓ Store in fireproof safe or safety deposit box
- ✓ Multiple locations geographically distributed

### Mistake #4: Clicking Unknown Links
- ❌ "Verify your wallet" email (phishing)
- ❌ "Claim free airdrop" links (malware)
- ❌ "Confirm transaction" browser notifications
- ✓ Go directly to official websites (bookmark them)
- ✓ Never trust unsolicited links or messages
- ✓ Verify URLs carefully (look for typos)

### Mistake #5: Granting Unlimited Approvals
- ❌ "Approve unlimited spending" (token swaps)
- ✓ Set spending limit to amount needed
- ✓ Revoke approvals after use (etherscan.io)
- ✓ Use "Approve once" when available

### Mistake #6: Not Using Hardware Wallet for Large Amounts
- ❌ Software wallet with $500k+ holdings
- ✓ Hardware wallet for amounts > $10k
- ✓ Multi-sig for amounts > $100k
- ✓ Cold storage for long-term holdings

### Mistake #7: Ignoring Security Updates
- ❌ Using outdated wallet version
- ✓ Enable auto-updates for mobile apps
- ✓ Check for updates monthly on desktop
- ✓ Immediate update for security patches

### Mistake #8: Sharing Recovery Info
- ❌ Telling friend/family your seed phrase
- ❌ Sharing private key via email
- ❌ Letting someone "help" with recovery
- ✓ Seed phrase is solo secret
- ✓ Never share with anyone, ever
- ✓ Even banks and wallet providers never ask for seed

### Mistake #9: Using Wallet Address as Identity
- ❌ Posting public address on social media
- ✓ If you must post, use watch-only address
- ✓ Better: use fresh address for each payment
- ✓ Don't link wallet to personal identity

### Mistake #10: Ignoring Tax Implications
- ❌ No record keeping of transactions
- ❌ Treating crypto as capital gain only
- ✓ Keep detailed transaction records
- ✓ Report staking/DeFi income as ordinary income
- ✓ Use tax software (Koinly, CoinTracker)
- ✓ Report to tax authorities (IRS, HMRC, etc.)

---

## GLOSSARY

### Key Management Terms
- **Private Key:** Secret number that controls funds; NEVER share
- **Public Key:** Derived from private key; safe to share
- **Address:** Hash of public key; where people send you funds
- **Seed Phrase:** 12-24 words that regenerate all private keys
- **Passphrase:** Extra word added to seed phrase for extra security
- **Mnemonic:** Word-based representation of random number (seed phrase)
- **Deterministic:** Same seed always generates same keys
- **Hierarchical Derivation:** BIP32/44 key generation paths
- **Non-Custodial:** You hold your own keys (vs exchange holding them)

### Security Terms
- **2FA/2FA:** Two-factor authentication (password + code)
- **TOTP:** Time-based one-time password (Google Authenticator)
- **Air-Gapped:** Computer never connected to internet
- **Cold Storage:** Keys stored offline (maximum security)
- **Hot Wallet:** Keys stored on internet-connected device
- **Hardware Wallet:** Device that stores keys and signs transactions
- **Multi-Signature:** Multiple keys required to spend funds
- **Threshold Signature:** m-of-n signatures required (2-of-3, 3-of-5, etc.)

### Blockchain Terms
- **Block:** Container of transactions added to blockchain
- **Confirmation:** Number of blocks added since your transaction
- **Gas:** Fee paid to execute transaction
- **Gwei:** Unit of gas (1 ETH = 1 billion Gwei)
- **RPC:** Remote procedure call; way to interact with blockchain
- **Smart Contract:** Program deployed on blockchain
- **Token:** Currency issued via smart contract
- **DeFi:** Decentralized Finance; non-custodial financial services
- **DEX:** Decentralized Exchange; peer-to-peer token swaps
- **Bridge:** Service connecting two blockchains

### Privacy Terms
- **CoinJoin:** Combine transactions to hide sender-receiver relationship
- **Tor:** The Onion Router; privacy network routing through multiple nodes
- **Privacy Coin:** Coin with privacy features built-in (Monero, Zcash)
- **On-Chain Analysis:** Using blockchain data to identify users
- **KYC:** Know your customer; identity verification
- **AML:** Anti-money laundering; regulatory compliance

---

## RESOURCES & LINKS

### Official Wallet Websites
- MetaMask: https://metamask.io
- Trust Wallet: https://trustwallet.com
- Ledger Live: https://www.ledger.com
- Trezor: https://trezor.io
- BlueWallet: https://bluewallet.io
- Phantom: https://phantom.app
- Exodus: https://www.exodus.com
- Atomic Wallet: https://atomicwallet.io
- Electrum: https://electrum.org
- Coinbase Wallet: https://www.coinbase.com/wallet

### Learning Resources
- **Bitcoin Whitepaper:** https://bitcoin.org/bitcoin.pdf
- **Ethereum Docs:** https://ethereum.org/developers
- **BIP Standards:** https://github.com/bitcoin/bips
- **Ledger Security:** https://www.ledger.com/security
- **Trezor Privacy:** https://trezor.io/privacy

### Security Tools
- **Etherscan:** https://etherscan.io (Ethereum blockchain explorer)
- **Solscan:** https://solscan.io (Solana blockchain explorer)
- **Revoke.cash:** https://revoke.cash (Revoke token approvals)
- **Tenderly:** https://tenderly.co (Transaction simulation)

### Regulatory Compliance
- **IRS Guidance:** https://www.irs.gov/individuals/international-taxpayers/virtual-currency
- **HMRC (UK):** https://www.gov.uk/government/organisations/hm-revenue-customs
- **FATF Standards:** https://www.fatf-gafi.org/

---

## VERSION HISTORY

| Date | Version | Changes |
|------|---------|---------|
| 2025-08-12 | 2.0 | Added scoring matrix, use case decision tree |
| 2025-08-11 | 1.5 | Initial comprehensive analysis |

---

**Note:** This guide reflects information as of August 2025. Wallet features and security measures evolve constantly. Always verify current information on official websites before deciding.
