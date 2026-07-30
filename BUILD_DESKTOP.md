# Building MoonBite Desktop Wallet

## Automated Builds (GitHub Actions)

Executables are auto-built for Windows, macOS, and Linux on every tagged release:

```bash
git tag v0.2.0
git push origin v0.2.0
```

Binaries appear in GitHub Releases:
- **Windows**: `MoonBite.exe` (~50-100 MB)
- **macOS**: `MoonBite.dmg` (~150-200 MB)
- **Linux**: `MoonBite` AppImage (~80-120 MB)

## Manual Build (Local)

### 1. Install Python 3.11+

```bash
python --version  # Should be 3.11 or higher
```

### 2. Install dependencies

```bash
pip install -e .
pip install pyinstaller PyQt6
```

### 3. Build executable

```bash
# Windows (creates MoonBite.exe)
pyinstaller moonbite.spec --onefile

# macOS (creates MoonBite.app bundle)
pyinstaller moonbite.spec
hdiutil create -volname MoonBite -srcfolder dist/MoonBite.app -ov -format UDZO MoonBite.dmg

# Linux (creates AppImage)
pip install appimage-builder
pyinstaller moonbite.spec --onefile
```

### 4. Run the application

```bash
# Windows
dist/MoonBite.exe

# macOS
open dist/MoonBite.app

# Linux
./dist/MoonBite
```

## Features

✅ HD Wallet (BIP39/BIP32)
✅ 12-word seed backup
✅ Address generation
✅ Balance checking
✅ Mining (local node)
✅ Transaction history
✅ Blockchain explorer

## System Requirements

- **Windows**: 7, 8, 10, 11 (64-bit)
- **macOS**: 10.13+ (Intel/Apple Silicon)
- **Linux**: Ubuntu 18.04+, Debian 10+, or equivalent

## Security Notes

- Private keys never leave your machine
- Seed phrase is stored locally only
- Uses ECDSA (SECP256k1) for signatures
- All transactions are verified locally
- No remote key server

## Troubleshooting

### "PyQt6 not found"
```bash
pip install PyQt6
```

### "mnemonic not found"
```bash
pip install mnemonic
```

### macOS: "Cannot verify developer"
Right-click app → Open → Click "Open" to bypass Gatekeeper

### Linux: "Permission denied"
```bash
chmod +x dist/MoonBite
./dist/MoonBite
```

## Building for Distribution

1. Update version in `pyproject.toml`
2. Create a git tag: `git tag v0.2.0`
3. Push tag: `git push origin v0.2.0`
4. GitHub Actions builds and uploads to Releases
5. Download from: https://github.com/moonbitecoin/MoonBite-Coin/releases
