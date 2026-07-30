# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for MoonBite Desktop Wallet.

Build with: pyinstaller moonbite.spec

Creates:
- Windows: MoonBite.exe (standalone, ~100MB)
- macOS: MoonBite.app (standalone)
- Linux: MoonBite (AppImage)
"""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'ecdsa', 'mnemonic'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MoonBite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='website/favicon.svg' if Path('website/favicon.svg').exists() else None,
)

app = BUNDLE(
    exe,
    name='MoonBite.app',
    icon='website/favicon.svg' if Path('website/favicon.svg').exists() else None,
    bundle_identifier='org.moonbite.wallet',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
    },
    bootloader_ignore_signals=False,
    skip_notarization=True,
)
