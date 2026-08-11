/**
 * QR Code Utilities for MoonBite Wallet
 * Generates and reads QR codes for addresses and seed phrases
 */

const QRUtils = (() => {
    /**
     * Generate QR code canvas element
     * Uses data URL encoding for addresses/seeds
     */
    function generateQRCode(text, size = 200) {
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;

        // Simplified QR encoding - in production use qrcode.js library
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, size, size);

        // Create pattern based on text
        const hash = hashText(text);
        const pixelSize = size / 32;

        ctx.fillStyle = '#000000';
        for (let i = 0; i < hash.length; i++) {
            if (parseInt(hash[i], 16) % 2 === 0) {
                const row = Math.floor(i / 8);
                const col = i % 8;
                ctx.fillRect(col * pixelSize * 4, row * pixelSize * 4, pixelSize * 3, pixelSize * 3);
            }
        }

        return canvas;
    }

    /**
     * Hash text to generate consistent QR-like pattern
     */
    function hashText(text) {
        let hash = 0;
        for (let i = 0; i < text.length; i++) {
            const char = text.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32bit integer
        }
        return Math.abs(hash).toString(16).padStart(32, '0');
    }

    /**
     * Request camera permission and start scanning
     */
    async function startQRScanner(onDetect, onError) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' }
            });

            return {
                stop: () => {
                    stream.getTracks().forEach(track => track.stop());
                },
                stream: stream
            };
        } catch (error) {
            onError('Camera permission denied or not available');
            return null;
        }
    }

    /**
     * Validate address format (MoonBite bech32)
     */
    function validateAddress(address) {
        // MoonBite uses bech32 with prefix 'moon1'
        if (!address.startsWith('moon1')) {
            return { valid: false, error: 'Address must start with moon1' };
        }

        if (address.length !== 62) {
            return { valid: false, error: 'Invalid address length' };
        }

        // Basic bech32 validation
        const validChars = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l';
        for (let i = 5; i < address.length; i++) {
            if (!validChars.includes(address[i].toLowerCase())) {
                return { valid: false, error: 'Invalid address characters' };
            }
        }

        return { valid: true };
    }

    /**
     * Create printable paper wallet HTML
     */
    function generatePaperWallet(mnemonic, address) {
        const words = mnemonic.split(' ');
        const html = `
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>MoonBite Paper Wallet</title>
                <style>
                    body {
                        font-family: monospace;
                        padding: 20px;
                        max-width: 800px;
                        margin: 0 auto;
                    }
                    .header { text-align: center; margin-bottom: 30px; }
                    .section { margin-bottom: 30px; page-break-inside: avoid; }
                    .warning {
                        color: red;
                        font-weight: bold;
                        border: 2px solid red;
                        padding: 10px;
                        margin: 20px 0;
                    }
                    .words {
                        display: grid;
                        grid-template-columns: 1fr 1fr;
                        gap: 10px;
                        font-size: 16px;
                        line-height: 1.8;
                    }
                    .address {
                        word-break: break-all;
                        font-size: 12px;
                        background: #f0f0f0;
                        padding: 10px;
                        border-radius: 5px;
                    }
                    .qr-placeholder {
                        width: 200px;
                        height: 200px;
                        border: 1px solid #000;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin: 20px auto;
                        text-align: center;
                    }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🌙 MoonBite Paper Wallet</h1>
                    <p>Generated: ${new Date().toLocaleString()}</p>
                </div>

                <div class="warning">
                    ⚠️ SECURITY WARNING ⚠️<br>
                    KEEP THIS DOCUMENT IN A SAFE PLACE<br>
                    DO NOT SHARE YOUR SEED PHRASE<br>
                    ANYONE WITH YOUR SEED CAN ACCESS YOUR FUNDS
                </div>

                <div class="section">
                    <h2>Your 12-Word Seed Phrase</h2>
                    <p>Write these words down in order. This is the ONLY way to recover your wallet.</p>
                    <div class="words">
                        ${words.map((w, i) => `<div>${i + 1}. ${w}</div>`).join('')}
                    </div>
                </div>

                <div class="section">
                    <h2>Seed Phrase QR Code</h2>
                    <div class="qr-placeholder">[QR Code Here]</div>
                </div>

                <div class="section">
                    <h2>Your Wallet Address</h2>
                    <p>Use this address to receive funds:</p>
                    <div class="address">${address}</div>
                    <div class="qr-placeholder">[Address QR Code]</div>
                </div>

                <div class="section">
                    <h2>Storage Instructions</h2>
                    <ol>
                        <li>Print this document</li>
                        <li>Store in a safe place (safe, safe deposit box, etc.)</li>
                        <li>Keep separate from this device</li>
                        <li>Do NOT take screenshots</li>
                        <li>Do NOT store digitally without encryption</li>
                        <li>Test recovery on a different device before relying on it</li>
                    </ol>
                </div>

                <div class="warning">
                    This document contains sensitive information.<br>
                    Treat it like cash or valuables.
                </div>
            </body>
            </html>
        `;
        return html;
    }

    return {
        generateQRCode,
        startQRScanner,
        validateAddress,
        generatePaperWallet
    };
})();
