# MoonBite Flutter Wallet - Quick Start

A **non-custodial** MoonBite (MBITE) wallet. Keys are generated and stored
on-device; the app only reads chain state and relays signed transactions.

## 1. Prerequisites Check

Ensure you have Flutter installed:
```bash
flutter --version
flutter doctor
```

If Flutter is NOT installed, download from: https://flutter.dev/docs/get-started/install

## 2. Install Dependencies (One-time)

```bash
cd C:/Users/%USERNAME%/Desktop/BigCoinBB/mobile
flutter pub get
```

> The API models in `lib/models/chain_models.dart` are hand-written — no
> `build_runner` / code generation step is required.

## 3. Backend / Explorer

No local server is needed. The app defaults to the hosted node:
```
https://moonbite-production.up.railway.app
```
To use a different node, edit `defaultBaseUrl` in `lib/services/chain_service.dart`.

## 4. Run the App

### Android Emulator / iOS Simulator
```bash
flutter run
```

### Physical Device (Android/iOS)
1. Connect device via USB
2. Enable USB debugging (Android) or Trust computer (iOS)
3. Run: `flutter run`

On first launch you'll go through onboarding to **create or import a seed phrase**.
Back it up — there is no server-side recovery.

## 5. Troubleshooting

### Explorer URL not working?
Edit `mobile/lib/services/chain_service.dart`:
```dart
static const String defaultBaseUrl = 'https://your-node.example';
```
or call `chainService.setBaseUrl('https://your-node.example')` at runtime.

### Flutter not found?
Add Flutter to PATH or use the full path:
```bash
/path/to/flutter/bin/flutter run
```

### Clean rebuild
```bash
flutter clean
flutter pub get
flutter run
```

## App Screens

**Onboarding** - Create or import a BIP39 seed phrase (on-device)

**Wallet** - Address, receive, and balance
- View address and QR code
- Confirmed / unconfirmed / total balance
- UTXO count

**Send** - Build, sign (on-device), and broadcast a payment

**Blockchain** - Chain status
- Chain, blocks, best block hash
- Difficulty, mempool size, connections

## API Endpoints Used

Read/relay only — all against the explorer base URL:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/status` | GET | Chain tip + node summary |
| `/api/address/<a>/utxos` | GET | Spendable outputs |
| `/api/address/<a>/balance` | GET | Confirmed/unconfirmed/total balance |
| `/api/fee` | GET | Suggested fee rate (MBITE/kB) |
| `/api/tx/broadcast` | POST | Relay a signed raw tx (`{rawtx}`) |
| `/api/tx/<txid>` | GET | Decoded transaction JSON |

Balance shape: `{address, confirmed, unconfirmed, total, utxo_count, demo}`
(amounts in whole MBITE).

## Build for Release

### Android APK
```bash
flutter build apk --release
# Output: build/app/outputs/flutter-apk/app-release.apk
```

### iOS App Bundle
```bash
flutter build ios --release
# Output: build/ios/iphoneos/Runner.app
```

## Important Notes

- Non-custodial: keys and seed phrase never leave the device
- No mining or wallet-generation server endpoints — that logic is on-device
- Requires Flutter SDK 3.0.0 or later
- Default explorer URL: `https://moonbite-production.up.railway.app`
- Pre-mainnet: `demo: true` in responses means placeholder chain data

## File Structure

```
mobile/
├── pubspec.yaml                  # Project manifest & dependencies
├── lib/
│   ├── main.dart                 # App entry & routing (onboarding vs home)
│   ├── services/
│   │   └── chain_service.dart    # Read/relay HTTP client (never sees keys)
│   ├── models/
│   │   └── chain_models.dart     # ChainStatus, Utxo, WalletBalance (hand-written)
│   ├── wallet/                   # On-device key layer (BIP39, signing, secure store)
│   └── screens/
│       ├── onboarding_screen.dart
│       ├── home_screen.dart
│       ├── wallet_screen.dart
│       ├── send_screen.dart
│       └── blockchain_screen.dart
└── android/ & ios/               # Native projects
```

## Next Steps

1. Install Flutter SDK
2. `cd mobile && flutter pub get`
3. `flutter run` to launch
4. Complete onboarding (create/import seed phrase) and back it up
5. Test wallet, send, and blockchain screens
