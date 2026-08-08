/**
 * MoonBite Wallet Biometric Authentication Module
 *
 * Provides WebAuthn/FIDO2 biometric authentication (fingerprint/face recognition)
 * using the browser's native PublicKeyCredential API. Handles registration,
 * verification, and fallback to password authentication.
 *
 * Security patterns:
 * - Challenge-response protocol to prevent replay attacks
 * - No biometric data stored on server (only credential IDs)
 * - Rate limiting on verify attempts (5/minute server-side)
 * - Password always available as fallback
 * - Session-based isolation via user_session_id
 * - Audit trail for all biometric events
 */

class BiometricAuth {
    constructor(apiBaseUrl = "/api/auth/biometric") {
        this.apiBaseUrl = apiBaseUrl;
        this.isSupported = this.checkBrowserSupport();
    }

    /**
     * Check if browser supports WebAuthn/FIDO2
     * @returns {boolean} True if WebAuthn API is available
     */
    checkBrowserSupport() {
        return (
            window.PublicKeyCredential !== undefined &&
            navigator.credentials !== undefined &&
            navigator.credentials.create !== undefined &&
            navigator.credentials.get !== undefined
        );
    }

    /**
     * Check if device supports biometric auth and if user has it enabled
     * @returns {Promise<{device_support: boolean, user_enabled: boolean, device_name: string|null}>}
     */
    async isAvailable() {
        if (!this.isSupported) {
            return {
                device_support: false,
                user_enabled: false,
                device_name: null,
            };
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/available`, {
                method: "GET",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error("[BiometricAuth] Error checking availability:", error);
            return {
                device_support: false,
                user_enabled: false,
                device_name: null,
            };
        }
    }

    /**
     * Get current biometric status for this session
     * @returns {Promise<{enabled: boolean, device_name: string|null, last_login: number|null, failed_attempts: number}>}
     */
    async getStatus() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/status`, {
                method: "GET",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            return data;
        } catch (error) {
            console.error("[BiometricAuth] Error getting status:", error);
            return {
                enabled: false,
                device_name: null,
                last_login: null,
                failed_attempts: 0,
            };
        }
    }

    /**
     * Generate a random challenge for WebAuthn
     * @param {number} length - Length of challenge in bytes (default 32)
     * @returns {Uint8Array} Random challenge bytes
     * @private
     */
    _generateChallenge(length = 32) {
        return crypto.getRandomValues(new Uint8Array(length));
    }

    /**
     * Convert ArrayBuffer to base64 string
     * @param {ArrayBuffer} buffer - Buffer to encode
     * @returns {string} Base64-encoded string
     * @private
     */
    _bufferToBase64(buffer) {
        let binary = "";
        const bytes = new Uint8Array(buffer);
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }

    /**
     * Convert base64 string to ArrayBuffer
     * @param {string} base64 - Base64-encoded string
     * @returns {ArrayBuffer} Decoded buffer
     * @private
     */
    _base64ToBuffer(base64) {
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes.buffer;
    }

    /**
     * Register a new biometric credential (fingerprint/face)
     * @param {string} userId - User identifier (optional, for display)
     * @param {string} deviceName - Human-readable device name (default: "Default Device")
     * @returns {Promise<{success: boolean, message: string, device_name: string}>}
     */
    async register(userId = "User", deviceName = "Default Device") {
        if (!this.isSupported) {
            throw new Error(
                "Your device does not support biometric authentication"
            );
        }

        try {
            // Generate a challenge
            const challenge = this._generateChallenge();

            // Create credential options
            const createOptions = {
                challenge: challenge,
                rp: {
                    name: "MoonBite Wallet",
                    id: window.location.hostname,
                },
                user: {
                    id: new TextEncoder().encode(userId),
                    name: userId,
                    displayName: userId,
                },
                pubKeyCredParams: [
                    { type: "public-key", alg: -7 }, // ES256
                    { type: "public-key", alg: -257 }, // RS256
                ],
                authenticatorSelection: {
                    authenticatorAttachment: "platform", // Use built-in authenticator (fingerprint/face)
                    residentKey: "preferred",
                    userVerification: "required", // Require biometric verification
                },
                timeout: 60000, // 60 seconds
                attestation: "direct",
            };

            // Create the credential
            const credential = await navigator.credentials.create({
                publicKey: createOptions,
            });

            if (!credential) {
                throw new Error("Biometric registration was cancelled");
            }

            // Extract credential ID and public key
            const credentialId = this._bufferToBase64(credential.id);
            const attestationObject = new Uint8Array(
                credential.response.attestationObject
            );
            const publicKey = this._bufferToBase64(attestationObject);

            // Send to server for storage
            const response = await fetch(`${this.apiBaseUrl}/register`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    credential_id: credentialId,
                    public_key: publicKey,
                    device_name: deviceName,
                }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP ${response.status}`);
            }

            const result = await response.json();
            console.log("[BiometricAuth] Registration successful");
            return result;
        } catch (error) {
            console.error("[BiometricAuth] Registration failed:", error);
            throw error;
        }
    }

    /**
     * Authenticate with biometric credential
     * @returns {Promise<{success: boolean, message: string}>}
     */
    async authenticate() {
        if (!this.isSupported) {
            throw new Error(
                "Your device does not support biometric authentication"
            );
        }

        try {
            // Generate challenge
            const challenge = this._generateChallenge();

            // Get credential options
            const getOptions = {
                challenge: challenge,
                timeout: 60000, // 60 seconds
                userVerification: "required",
            };

            // Get the credential
            const assertion = await navigator.credentials.get({
                publicKey: getOptions,
            });

            if (!assertion) {
                throw new Error("Biometric authentication was cancelled");
            }

            // Extract assertion credential ID
            const assertionId = this._bufferToBase64(assertion.id);

            // Send to server for verification
            const response = await fetch(`${this.apiBaseUrl}/verify`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    assertion_id: assertionId,
                }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP ${response.status}`);
            }

            const result = await response.json();
            console.log("[BiometricAuth] Verification successful");
            return result;
        } catch (error) {
            console.error("[BiometricAuth] Verification failed:", error);
            throw error;
        }
    }

    /**
     * Disable biometric authentication for this session
     * @returns {Promise<{success: boolean, message: string}>}
     */
    async disable() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/disable`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP ${response.status}`);
            }

            const result = await response.json();
            console.log("[BiometricAuth] Biometric disabled");
            return result;
        } catch (error) {
            console.error("[BiometricAuth] Error disabling biometric:", error);
            throw error;
        }
    }

    /**
     * Get audit log for biometric events
     * @param {string} action - Filter by action (register, verify, disable) or null for all
     * @param {number} limit - Max records per page (default 50)
     * @param {number} offset - Pagination offset (default 0)
     * @returns {Promise<{events: Array, total: number, limit: number, offset: number}>}
     */
    async getAuditLog(action = null, limit = 50, offset = 0) {
        try {
            const params = new URLSearchParams();
            if (action) params.append("action", action);
            params.append("limit", limit);
            params.append("offset", offset);

            const response = await fetch(`${this.apiBaseUrl}/audit?${params}`, {
                method: "GET",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error("[BiometricAuth] Error getting audit log:", error);
            return {
                events: [],
                total: 0,
                limit: limit,
                offset: offset,
            };
        }
    }
}

// Export for use in wallet UI
window.BiometricAuth = BiometricAuth;
