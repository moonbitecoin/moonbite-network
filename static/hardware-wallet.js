/**
 * Hardware Wallet Integration
 * Supports Ledger, Trezor, and other HW wallets via WebUSB
 */

const HardwareWallet = (() => {
    const LEDGER_VENDOR_ID = 0x2c97;
    const TREZOR_VENDOR_ID = 0x534c;

    /**
     * Detect connected hardware wallets
     */
    async function detectWallets() {
        const devices = [];

        try {
            // Request access to USB devices
            if (!navigator.usb) {
                return {
                    error: 'WebUSB not supported in this browser',
                    devices: []
                };
            }

            const usbDevices = await navigator.usb.getDevices();

            for (const device of usbDevices) {
                if (device.vendorId === LEDGER_VENDOR_ID) {
                    devices.push({
                        type: 'ledger',
                        name: `${device.productName} (${device.serialNumber})`,
                        device: device,
                        status: 'ready'
                    });
                } else if (device.vendorId === TREZOR_VENDOR_ID) {
                    devices.push({
                        type: 'trezor',
                        name: `${device.productName} (${device.serialNumber})`,
                        device: device,
                        status: 'ready'
                    });
                }
            }
        } catch (error) {
            console.error('USB detection error:', error);
        }

        return { devices, error: null };
    }

    /**
     * Request permission to access a device
     */
    async function requestDevice() {
        try {
            if (!navigator.usb) {
                return { error: 'WebUSB not supported' };
            }

            const device = await navigator.usb.requestDevice({
                filters: [
                    { vendorId: LEDGER_VENDOR_ID },
                    { vendorId: TREZOR_VENDOR_ID }
                ]
            });

            return {
                device,
                type: device.vendorId === LEDGER_VENDOR_ID ? 'ledger' : 'trezor'
            };
        } catch (error) {
            return { error: 'User denied device access' };
        }
    }

    /**
     * Get address from Ledger wallet
     */
    async function getLedgerAddress(device, index = 0) {
        try {
            // In production, use @ledgerhq/hw-app-btc
            // This is a simulation for demo purposes

            // Derive path m/44'/0'/0'/0/index (BIP-44 for Bitcoin/Litecoin)
            const path = `m/44'/0'/0'/0/${index}`;

            return {
                address: `moon1${'q'.repeat(54)}`, // Simulated address
                path: path,
                publicKey: '0x' + '0'.repeat(64),
                source: 'ledger'
            };
        } catch (error) {
            return { error: `Failed to get address: ${error.message}` };
        }
    }

    /**
     * Get address from Trezor wallet
     */
    async function getTrezorAddress(device, index = 0) {
        try {
            // In production, use TrezorConnect
            const path = `m/44'/0'/0'/0/${index}`;

            return {
                address: `moon1${'a'.repeat(54)}`, // Simulated address
                path: path,
                publicKey: '0x' + 'a'.repeat(64),
                source: 'trezor'
            };
        } catch (error) {
            return { error: `Failed to get address: ${error.message}` };
        }
    }

    /**
     * Sign transaction with hardware wallet
     */
    async function signTransaction(device, txData) {
        try {
            const walletType = device.vendorId === LEDGER_VENDOR_ID ? 'ledger' : 'trezor';

            // Simulate signing - in production use actual SDK
            const signature = {
                r: '0x' + '0'.repeat(64),
                s: '0x' + '1'.repeat(64),
                v: 27
            };

            return {
                signature,
                txid: '0x' + 'f'.repeat(64),
                source: walletType
            };
        } catch (error) {
            return { error: `Failed to sign transaction: ${error.message}` };
        }
    }

    /**
     * Get wallet info
     */
    async function getWalletInfo(device) {
        try {
            const walletType = device.vendorId === LEDGER_VENDOR_ID ? 'ledger' : 'trezor';

            return {
                type: walletType,
                status: 'connected',
                firmwareVersion: '2.1.0', // Simulated
                addressCount: 5,
                supportedCoins: ['bitcoin', 'litecoin', 'ethereum'],
                requiresPin: true,
                requiresPassphrase: false
            };
        } catch (error) {
            return { error: 'Failed to get wallet info' };
        }
    }

    /**
     * Close connection to hardware wallet
     */
    async function closeConnection(device) {
        try {
            if (device.opened) {
                await device.close();
            }
            return { success: true };
        } catch (error) {
            return { error: `Failed to close connection: ${error.message}` };
        }
    }

    return {
        detectWallets,
        requestDevice,
        getLedgerAddress,
        getTrezorAddress,
        signTransaction,
        getWalletInfo,
        closeConnection,
        SUPPORTED_TYPES: ['ledger', 'trezor']
    };
})();
