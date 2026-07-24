# MoonBite Mobile Wallet - Flutter

A cross-platform, **non-custodial** mobile wallet for MoonBite (MBITE). Keys are
generated and stored **on-device**; transactions are signed locally. The app only
talks to a read-only explorer API to fetch chain state and relay already-signed
transactions — it never sends your private keys or seed phrase anywhere.

**Non-custodial by design** — your seed phrase and private keys stay in the
device's encrypted secure storage (Keystore/Keychain). Lose the phrase, lose the
coins; there is no server-side recovery.

## Features

- **On-device HD wallet**: BIP39 seed phrase, on-device key derivation and signing
- **Balance & UTXOs**: fetches confirmed / unconfirmed / total balance per address
- **Send**: builds and signs transactions locally, then broadcasts the raw tx
- **Chain info**: chain tip, best block hash, difficulty, mempool, connections
- **Secure unlock**: PIN / biometric via `local_auth`, keys in `flutter_secure_storage`
- **Dark theme**: Material 3 dark UI

## Prerequisites

### Required Software

1. **Flutter SDK** (3.0.0 or later)
   - Download from: https://flutter.dev/docs/get-started/install
   - Ensure Flutter is added to your PATH

2. **Platform-Specific Requirements**:
   - **Android**: Android SDK, Android emulator or physical device
   - **iOS**: Xcode (macOS only), iPhone simulator or physical device

3. **Backend**: an explorer API endpoint. The app defaults to the hosted node at
   `https://moonbite-production.up.railway.app`. No local backend is required —
   the wallet is not tied to `web_app.py`.

## Installation

### 1. Install Flutter

Follow the official Flutter installation guide:
https://flutter.dev/docs/get-started/install

Verify installation:
```bash
flutter --version
flutter doctor
```

### 2. Navigate to Project

```bash
cd C:/Users/%USERNAME%/Desktop/BigCoinBB/mobile
```

### 3. Install Dependencies

```bash
flutter pub get
```

Key dependencies from `pubspec.yaml`:
- `http`: HTTP client for the explorer API
- `provider`: state management
- `bip39`: BIP39 mnemonic seed phrase
- `coinslib`: HD wallet, secp256k1, address encoding, WIF (custom network params)
- `flutter_secure_storage`: encrypted key storage (Keystore/Keychain)
- `local_auth`: PIN / biometric unlock
- `hex`, `bs58check`: script/address encoding helpers
- `qr_flutter`: QR code display

> **Note:** the API data models in `lib/models/chain_models.dart` are hand-written
> (no code generation), so you do **not** need to run `build_runner` for them.

## Running the App

### Android

**Using Emulator:**
```bash
flutter run
```

**Build APK:**
```bash
flutter build apk --release
```
Output: `build/app/outputs/flutter-apk/app-release.apk`

### iOS

**Using Simulator (macOS):**
```bash
flutter run
```

**Build iOS App:**
```bash
flutter build ios --release
```

## Configuration

### Backend / Explorer URL

The default explorer URL is defined in `lib/services/chain_service.dart`:
```dart
static const String defaultBaseUrl =
    'https://moonbite-production.up.railway.app';
```

To point at a different node, either edit that constant or call at runtime:
```dart
chainService.setBaseUrl('https://your-node.example');
```

## Project Structure

```
mobile/
├── pubspec.yaml                     # Flutter project manifest
├── lib/
│   ├── main.dart                    # App entry; routes to onboarding vs home
│   ├── services/
│   │   └── chain_service.dart       # Read/relay HTTP client (NEVER sees keys)
│   ├── models/
│   │   └── chain_models.dart        # ChainStatus, Utxo, WalletBalance (hand-written)
│   ├── wallet/                      # On-device, non-custodial key layer
│   │   ├── wallet_controller.dart   # Wallet state (ChangeNotifier)
│   │   ├── hd_wallet_service.dart   # BIP39/HD derivation
│   │   ├── secure_key_store.dart    # Encrypted key storage
│   │   ├── tx_builder.dart          # Builds & signs transactions locally
│   │   ├── address_script.dart      # Address <-> scriptPubKey
│   │   └── moonbite_network.dart    # MoonBite network params
│   └── screens/
│       ├── onboarding_screen.dart   # Create / import seed phrase
│       ├── home_screen.dart         # Main tabbed shell
│       ├── wallet_screen.dart       # Address, balance, receive
│       ├── send_screen.dart         # Build/sign/broadcast a payment
│       └── blockchain_screen.dart   # Chain status
├── android/                          # Android native project
└── ios/                              # iOS native project
```

## API Endpoints

The app talks to a read-only explorer API (`ChainService`). It reads chain state
and relays signed transactions only — there are **no** wallet-generation or mining
endpoints on the server side (key generation and signing happen on-device).

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/status` | Chain tip + node summary |
| GET | `/api/address/<address>/utxos` | Spendable outputs for an address |
| GET | `/api/address/<address>/balance` | Confirmed / unconfirmed / total balance |
| GET | `/api/fee` | Suggested fee rate (MBITE per kB) |
| POST | `/api/tx/broadcast` | Relay a fully-signed raw transaction (`{rawtx}`) |
| GET | `/api/tx/<txid>` | Decoded transaction JSON |

### Balance response shape (`GET /api/address/<a>/balance`)

```json
{
  "address": "M...",
  "confirmed": 0.0,
  "unconfirmed": 0.0,
  "total": 0.0,
  "utxo_count": 0,
  "demo": true
}
```

Amounts are in whole MBITE (1 MBITE = 1e8 base units). The `demo` flag is `true`
while the explorer is serving placeholder data.

## Troubleshooting

### App won't connect to the explorer
- **Check the URL**: confirm `defaultBaseUrl` in `chain_service.dart` is reachable
- **Check connectivity**: the default node is public over HTTPS; ensure the device is online
- **Point elsewhere**: call `chainService.setBaseUrl(...)` to target another node

### Flutter doctor shows issues
```bash
flutter doctor
```
Follow the instructions to resolve missing dependencies.

### App crashes on startup
- Ensure dependencies installed: `flutter pub get`
- Clean rebuild: `flutter clean && flutter pub get && flutter run`
- Check Logcat (Android) or Xcode console (iOS) for details

### Can't send a transaction
- Confirm the address has confirmed UTXOs (`/api/address/<a>/balance`)
- Confirm the device wallet is unlocked (PIN / biometric)
- A broadcast error surfaces the node's reject reason via `ChainApiException`

## Development Notes

- **Non-custodial**: `ChainService` never receives keys; all signing is in `wallet/`
- **State management**: `provider` — `ChainService` + `WalletController` in `main.dart`
- **Models**: hand-written in `chain_models.dart`; no `build_runner` needed
- **Secure storage**: keys live in `flutter_secure_storage` (Keystore/Keychain)
- **Dark theme**: configured in `main.dart` (Material 3)

## Testing

```bash
flutter test
```

## Security Notes

- The seed phrase shown during onboarding is the **only** backup — there is no
  server-side recovery.
- Private keys never leave the device and are never included in any API request.
- Only fully-signed raw transactions are sent to the network, via `/api/tx/broadcast`.

## License

Educational / pre-mainnet project. Not investment advice; MBITE is not a security.
