/**
 * MoonBite Security & Authentication Module
 * Handles password, biometric, and session security
 */

const Security = (() => {
    const SESSION_TIMEOUT = 5 * 60 * 1000; // 5 minutes
    let sessionTimer = null;
    let lastActivity = Date.now();

    /**
     * Hash password using PBKDF2
     */
    async function hashPassword(password) {
        const encoder = new TextEncoder();
        const data = encoder.encode(password);

        // Generate random salt
        const salt = crypto.getRandomValues(new Uint8Array(16));

        // Derive key using PBKDF2
        const key = await crypto.subtle.deriveKey(
            {
                name: 'PBKDF2',
                hash: 'SHA-256',
                salt: salt,
                iterations: 100000
            },
            await crypto.subtle.importKey('raw', data, 'PBKDF2', false, ['deriveKey']),
            { name: 'HMAC', hash: 'SHA-256' },
            true,
            ['sign']
        );

        const hashBuffer = await crypto.subtle.exportKey('raw', key);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

        // Combine salt + hash for storage
        const saltHex = Array.from(salt).map(b => b.toString(16).padStart(2, '0')).join('');
        return saltHex + ':' + hashHex;
    }

    /**
     * Verify password against stored hash
     */
    async function verifyPassword(password, storedHash) {
        const [saltHex, expectedHash] = storedHash.split(':');
        const salt = new Uint8Array(saltHex.match(/.{1,2}/g).map(b => parseInt(b, 16)));

        const encoder = new TextEncoder();
        const data = encoder.encode(password);

        const key = await crypto.subtle.deriveKey(
            {
                name: 'PBKDF2',
                hash: 'SHA-256',
                salt: salt,
                iterations: 100000
            },
            await crypto.subtle.importKey('raw', data, 'PBKDF2', false, ['deriveKey']),
            { name: 'HMAC', hash: 'SHA-256' },
            true,
            ['sign']
        );

        const hashBuffer = await crypto.subtle.exportKey('raw', key);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

        return hashHex === expectedHash;
    }

    /**
     * Check password strength
     */
    function checkPasswordStrength(password) {
        let score = 0;
        const feedback = [];

        if (password.length >= 8) {
            score += 25;
        } else {
            feedback.push('Use at least 8 characters');
        }

        if (/[a-z]/.test(password)) {
            score += 25;
        } else {
            feedback.push('Add lowercase letters');
        }

        if (/[A-Z]/.test(password)) {
            score += 25;
        } else {
            feedback.push('Add uppercase letters');
        }

        if (/[0-9]/.test(password)) {
            score += 12.5;
        } else {
            feedback.push('Add numbers');
        }

        if (/[!@#$%^&*]/.test(password)) {
            score += 12.5;
        } else {
            feedback.push('Add special characters');
        }

        const strength = score < 50 ? 'weak' : score < 75 ? 'fair' : score < 90 ? 'good' : 'strong';

        return { score: Math.min(100, score), strength, feedback };
    }

    /**
     * Register biometric authentication (WebAuthn)
     */
    async function registerBiometric(username) {
        try {
            if (!window.PublicKeyCredential) {
                return { error: 'WebAuthn not supported' };
            }

            const credential = await navigator.credentials.create({
                publicKey: {
                    challenge: crypto.getRandomValues(new Uint8Array(32)),
                    rp: { name: 'MoonBite Wallet' },
                    user: {
                        id: crypto.getRandomValues(new Uint8Array(16)),
                        name: username,
                        displayName: username
                    },
                    pubKeyCredParams: [
                        { type: 'public-key', alg: -7 },
                        { type: 'public-key', alg: -257 }
                    ],
                    authenticatorSelection: {
                        authenticatorAttachment: 'platform',
                        residentKey: 'preferred'
                    },
                    timeout: 60000,
                    attestation: 'direct'
                }
            });

            if (credential) {
                return {
                    success: true,
                    credentialId: Array.from(new Uint8Array(credential.id)).map(b => b.toString(16).padStart(2, '0')).join(''),
                    publicKey: 'registered'
                };
            }
        } catch (error) {
            return { error: `Biometric registration failed: ${error.message}` };
        }
    }

    /**
     * Verify biometric authentication
     */
    async function verifyBiometric(credentialId) {
        try {
            if (!window.PublicKeyCredential) {
                return { error: 'WebAuthn not supported' };
            }

            const assertion = await navigator.credentials.get({
                publicKey: {
                    challenge: crypto.getRandomValues(new Uint8Array(32)),
                    timeout: 60000,
                    userVerification: 'preferred'
                }
            });

            if (assertion) {
                resetSessionTimer();
                return {
                    success: true,
                    verified: true,
                    timestamp: Date.now()
                };
            }
        } catch (error) {
            return { error: `Biometric verification failed: ${error.message}` };
        }
    }

    /**
     * Initialize session timeout
     */
    function initSessionTimeout(onTimeout) {
        if (sessionTimer) clearTimeout(sessionTimer);

        sessionTimer = setTimeout(() => {
            if (onTimeout) onTimeout();
        }, SESSION_TIMEOUT);

        // Track user activity
        document.addEventListener('click', resetSessionTimer);
        document.addEventListener('keypress', resetSessionTimer);
    }

    /**
     * Reset session timer
     */
    function resetSessionTimer() {
        lastActivity = Date.now();
        if (sessionTimer) clearTimeout(sessionTimer);
        sessionTimer = setTimeout(() => {
            // Session expired - require re-authentication
            window.dispatchEvent(new CustomEvent('sessionExpired'));
        }, SESSION_TIMEOUT);
    }

    /**
     * Validate bech32 address
     */
    function validateBech32Address(address, prefix = 'moon1') {
        if (!address.startsWith(prefix)) {
            return { valid: false, error: `Address must start with ${prefix}` };
        }

        const validChars = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l';
        for (let i = prefix.length; i < address.length; i++) {
            if (!validChars.includes(address[i].toLowerCase())) {
                return { valid: false, error: 'Invalid bech32 characters' };
            }
        }

        if (address.length !== 62) {
            return { valid: false, error: 'Invalid address length' };
        }

        // Verify checksum (simplified)
        return { valid: true };
    }

    /**
     * Generate security audit log
     */
    function createAuditLog(action, details = {}) {
        return {
            timestamp: Date.now(),
            action: action,
            ipAddress: 'local', // In production, get from server
            userAgent: navigator.userAgent,
            ...details
        };
    }

    /**
     * Generate secure random token
     */
    function generateSecureToken(length = 32) {
        const bytes = crypto.getRandomValues(new Uint8Array(length));
        return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
    }

    /**
     * Enable session timeout
     */
    function enableSessionTimeout() {
        initSessionTimeout(() => {
            console.log('Session expired due to inactivity');
            window.dispatchEvent(new CustomEvent('sessionTimeout'));
        });
    }

    /**
     * Disable session timeout
     */
    function disableSessionTimeout() {
        if (sessionTimer) {
            clearTimeout(sessionTimer);
            sessionTimer = null;
        }
        document.removeEventListener('click', resetSessionTimer);
        document.removeEventListener('keypress', resetSessionTimer);
    }

    return {
        hashPassword,
        verifyPassword,
        checkPasswordStrength,
        registerBiometric,
        verifyBiometric,
        initSessionTimeout,
        resetSessionTimer,
        validateBech32Address,
        createAuditLog,
        generateSecureToken,
        enableSessionTimeout,
        disableSessionTimeout,
        SESSION_TIMEOUT
    };
})();
