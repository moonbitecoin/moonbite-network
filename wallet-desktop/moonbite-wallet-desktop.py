#!/usr/bin/env python3
"""MoonBite Wallet — desktop app.

A native window hosting the MoonBite web wallet, so the desktop app is the
exact same wallet, unchanged. Uses the OS WebView (Edge WebView2 on Windows).
"""
import webview

WALLET_URL = "https://moonbite.org/wallet"

if __name__ == "__main__":
    webview.create_window(
        "MoonBite Wallet",
        WALLET_URL,
        width=460,
        height=820,
        min_size=(380, 600),
        background_color="#0B0D12",
    )
    webview.start()
