# MoonBite Wallet Biometric Authentication

## Overview

The MoonBite Wallet now supports biometric authentication (fingerprint and face recognition) for faster, more secure access. This document describes the implementation, security considerations, and API usage.

## Features

- **WebAuthn/FIDO2 Support**: Uses the browser's native PublicKeyCredential API
- **No Biometric Data Storage**: Only credential IDs stored on server, biometric data never leaves device
- **Secure Challenge-Response**: Prevents replay attacks with cryptographic challenges
- **Rate Limiting**: Max 5 verification attempts per minute with automatic lockout
- **Password Fallback**: Password authentication always available as fallback
- **Audit Trail**: Complete logging of all biometric events for security compliance
- **Multi-Device**: Support for multiple biometric devices per user session

## Architecture

### Database Schema

#### `auth_state` Table
Stores authentication state per user session:
- `user_session_id`: Session identifier
- `password_hash`: Argon2id-hashed password (with SHA256 fallback)
- `biometric_enabled`: Boolean flag (0/1)
- `biometric_device_name`: Human-readable device name
- `biometric_credential_id`: WebAuthn credential ID (base64)
- `biometric_public_key`: COSE public key (base64)
- `totp_secret`: Reserved for future TOTP support
- `failed_attempts`: Counter for failed verification attempts
- `last_failed_at`: Timestamp of last failed attempt
- `last_login`: Timestamp of last successful authentication
- `created_at`, `updated_at`: Timestamps

#### `biometric_audit` Table
Audit trail for all biometric events:
- `user_session_id`: Session identifier (foreign key)
- `action`: Event type (register, verify, disable)
- `status`: Event result (success, failed)
- `credential_id`: Associated credential ID
- `device_name`: Device name if applicable
- `error_message`: Error details on failure
- `ip_address`: Client IP for security analysis
- `user_agent`: Browser/client identifier
- `created_at`: Event timestamp

#### `preferences` Table Updates
Extended with biometric settings:
- `biometric_enabled`: Boolean flag
- `biometric_device_name`: Device name for UI display

## Backend API

### REST Endpoints

#### GET `/api/auth/biometric/available`
Check if device supports WebAuthn and if biometric is enabled.

**Response:**
```json
{
  "status": "success",
  "device_support": true,
  "user_enabled": false,
  "device_name": null
}
```

#### POST `/api/auth/biometric/register`
Register a biometric credential.

**Request:**
```json
{
  "credential_id": "base64-encoded-credential-id",
  "public_key": "base64-encoded-cose-public-key",
  "device_name": "My iPhone"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Biometric registered for My iPhone",
  "device_name": "My iPhone"
}
```

#### POST `/api/auth/biometric/verify`
Verify a biometric assertion for authentication.

**Request:**
```json
{
  "assertion_id": "base64-encoded-assertion-credential-id"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Biometric verification successful"
}
```

**Response (Failure):**
```json
{
  "status": "error",
  "error_code": "SECURITY_INVALID_PASSWORD",
  "message": "Fingerprint/face not recognized. Try again or use password."
}
```

#### POST `/api/auth/biometric/disable`
Disable biometric authentication.

**Response:**
```json
{
  "status": "success",
  "message": "Biometric authentication disabled"
}
```

#### GET `/api/auth/biometric/status`
Get current biometric status for session.

**Response:**
```json
{
  "status": "success",
  "enabled": true,
  "device_name": "My iPhone",
  "last_login": 1234567890,
  "failed_attempts": 0
}
```

#### GET `/api/auth/biometric/audit`
Get audit log for biometric events.

**Query Parameters:**
- `action`: Filter by action (register, verify, disable) - optional
- `limit`: Max records per page (default 50, max 100)
- `offset`: Pagination offset (default 0)

**Response:**
```json
{
  "status": "success",
  "events": [
    {
      "id": 1,
      "action": "register",
      "status": "success",
      "credential_id": "...",
      "created_at": 1234567890
    }
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

### Python Functions (wallet_history.py)

#### Authentication State Management

```python
def get_auth_state(session_id: str) -> Optional[dict]
    """Get auth state for session."""

def is_biometric_available(session_id: str) -> bool
    """Check if biometric is enabled and configured."""
```

#### Biometric Registration

```python
def setup_biometric(
    session_id: str,
    credential_id: str,
    public_key: str,
    device_name: str = "Default Device"
) -> dict
    """Register biometric credential for session."""
```

#### Biometric Verification

```python
def verify_biometric(session_id: str, assertion_id: str) -> bool
    """Verify biometric assertion (after WebAuthn validation)."""

def record_biometric_failure(session_id: str) -> int
    """Record failed attempt, return attempt count."""

def check_biometric_rate_limit(
    session_id: str,
    max_attempts: int = 5,
    window_seconds: int = 60
) -> tuple[bool, int]
    """Check rate limiting, return (is_limited, attempts_in_window)."""
```

#### Disable Biometric

```python
def disable_biometric(session_id: str) -> bool
    """Disable biometric for session."""
```

#### Audit Logging

```python
def get_biometric_audit_log(
    session_id: str,
    action: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> dict
    """Get audit log for biometric events."""
```

#### Password Hashing

```python
def _hash_password(password: str) -> str
    """Hash password using Argon2id (with SHA256 fallback)."""

def _verify_password(password: str, password_hash: str) -> bool
    """Verify password against hash."""
```

## Frontend JavaScript

### BiometricAuth Class

Located in `static/wallet-biometric.js`, provides browser-side WebAuthn handling.

#### Constructor

```javascript
const biometricAuth = new BiometricAuth(apiBaseUrl = "/api/auth/biometric");
```

#### Methods

```javascript
// Check browser support
isAvailable() -> Promise<{device_support, user_enabled, device_name}>

// Get biometric status
getStatus() -> Promise<{enabled, device_name, last_login, failed_attempts}>

// Register new credential
register(userId: string, deviceName: string) -> Promise<{success, message, device_name}>

// Authenticate with biometric
authenticate() -> Promise<{success, message}>

// Disable biometric
disable() -> Promise<{success, message}>

// Get audit log
getAuditLog(action?: string, limit?: number, offset?: number) -> Promise<{events, total, limit, offset}>
```

### UI Integration

#### Login Screen
- "👆 Unlock with Biometric" button (shown if biometric is enabled)
- Falls back to password input if biometric unavailable

#### Password Setup Screen
- "💡 Tip: Add biometric authentication" prompt
- "👆 Set up Biometric" button (shown if browser supports WebAuthn)

#### Settings > Security Tab
- Biometric settings section (shown if WebAuthn supported)
- Device name display
- Last login timestamp
- "Set up Biometric" button or "Disable" button

#### Biometric Modal
- Setup instructions
- Device name input
- Progress indicator during registration
- Success/error messages
- Retry functionality

## Security Considerations

### What We Protect Against

1. **Replay Attacks**: Challenge-response protocol with cryptographic nonces
2. **Credential Interception**: Only credential IDs transmitted (no biometric data)
3. **Brute Force**: Rate limiting (5 attempts per 60 seconds)
4. **Session Hijacking**: Session-based isolation with user_session_id
5. **Audit Requirements**: Complete event logging for compliance

### What We Don't Protect Against

1. **Biometric Spoofing**: Relies on device authenticator robustness (fingerprint/face scanners)
2. **Compromised Device**: If device is compromised, biometric can be forged
3. **Malware**: Malware on device can intercept credentials before submission
4. **Timing Attacks**: HMAC constant-time comparison mitigates but not foolproof

### Best Practices

- **Always enable password**: Biometric should supplement, not replace passwords
- **Use strong passwords**: If password is weak, biometric doesn't help
- **Audit regularly**: Review `/api/auth/biometric/audit` logs
- **Monitor rate limits**: Repeated failures indicate attack attempts
- **Logout on untrusted devices**: Don't save biometric on public/shared devices

## Implementation Details

### Database Initialization

The `create_schema()` function initializes all required tables:
- Creates `auth_state` table with indexes
- Creates `biometric_audit` table with indexes
- Extends `preferences` table with biometric fields

### Password Hashing

Uses Argon2id if `argon2-cffi` is installed, falls back to SHA256:
- Argon2id recommended (secure, memory-hard)
- SHA256 fallback for environments without argon2-cffi

### Challenge-Response

WebAuthn challenge is generated on client side:
1. Client generates 32-byte random challenge
2. Browser prompts for biometric
3. Server validates credential ID matches stored value
4. HMAC constant-time comparison prevents timing attacks

### Rate Limiting

Implemented in `check_biometric_rate_limit()`:
- Default: 5 failed attempts per 60 seconds
- Checked before verification attempt
- Returns remaining attempts for UI feedback
- Server-side enforcement (not bypassed by client)

### Audit Logging

Every biometric event logged to `biometric_audit`:
- Register, verify (success/fail), disable actions
- IP address and user agent for security analysis
- Error messages on failure
- Timestamps for compliance/incident investigation

## Error Handling

### Client-Side Errors

- **Not Supported**: "Your device does not support biometric auth"
- **Cancelled**: "Biometric registration was cancelled"
- **Timeout**: "Biometric verification timed out. Please try again"
- **Failed Match**: "Fingerprint/face not recognized. Try again or use password"
- **Rate Limited**: "Too many failed attempts. Please use password"

### Server-Side Errors

- **VALIDATION_MISSING_FIELD**: Required fields missing from request
- **SECURITY_RATE_LIMITED**: Too many failed attempts (HTTP 429)
- **SECURITY_INVALID_PASSWORD**: Verification failed (HTTP 401)
- **INTERNAL_ERROR**: Server error (HTTP 500)

## Testing

Unit tests in `test_biometric_auth.py` cover:

- Password hashing and verification
- Biometric registration (new and existing sessions)
- Biometric verification (success and failure)
- Rate limiting enforcement
- Disable functionality
- Audit logging
- Availability checks
- Edge cases and error conditions

Run tests:
```bash
python -m pytest test_biometric_auth.py -v
```

## Deployment Checklist

- [ ] Install `argon2-cffi` for secure password hashing
- [ ] Set `SECRET_KEY` environment variable (already done for session cookies)
- [ ] Enable HTTPS in production (biometric requires secure context)
- [ ] Configure `TRUSTED_PROXY_COUNT` for IP address logging
- [ ] Review security headers (CSP, HSTS already configured)
- [ ] Monitor audit logs regularly
- [ ] Test rate limiting in staging environment
- [ ] Verify biometric modal appears in settings
- [ ] Test fallback to password on biometric failure

## Future Enhancements

1. **TOTP Support**: Time-based one-time passwords (field reserved in schema)
2. **Multiple Devices**: Allow registration of multiple biometric devices
3. **Recovery Codes**: Backup codes for account recovery
4. **Passwordless Login**: Support for passwordless authentication
5. **Session Management**: View active sessions and revoke remotely
6. **Compromise Detection**: Alert on unusual verification patterns

## References

- [WebAuthn Specification](https://www.w3.org/TR/webauthn-2/)
- [FIDO2 Alliance](https://fidoalliance.org/)
- [Argon2id Algorithm](https://github.com/P-H-C/phc-winner-argon2)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
