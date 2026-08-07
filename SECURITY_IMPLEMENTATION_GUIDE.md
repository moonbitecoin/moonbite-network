# Security Implementation Integration Guide

**Status**: Ready for Production Deployment
**Date**: 2026-08-06
**Target**: MoonBite Wallet PWA

---

## Quick Start Integration

### Step 1: Include Security Module

Add to `templates/wallet-pwa.html` before closing `</body>`:

```html
<!-- Security module must load FIRST before wallet script -->
<script src="/static/wallet-security.js"></script>
<script>
  // Initialize security systems
  initializeWalletSecurity();
</script>

<!-- Main wallet app (loaded after security) -->
<script src="/static/wallet-app.js"></script>
```

### Step 2: Update Flask App

```python
# app.py - Add security headers middleware

from flask import Flask
from flask_talisman import Talisman

app = Flask(__name__)

# Enable Talisman for security headers
Talisman(app,
    force_https=True,
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,
    content_security_policy={
        'default-src': "'self'",
        'script-src': ["'self'", "'wasm-unsafe-eval'"],
        'style-src': ["'self'", "'unsafe-inline'"],
        'img-src': ["'self'", "data:", "https:"],
        'connect-src': ["'self'", "https://moonbite.org"],
    }
)

# Add session management
from flask_session import Session
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
```

### Step 3: Enable Session Management in Wallet

```javascript
// In wallet-pwa.html script section, after unlock:

document.getElementById('unlockBtn')?.addEventListener('click', async () => {
  // ... existing unlock code ...

  // IMPORTANT: Start session management after successful unlock
  initSessionManagement();

  // ... rest of unlock logic ...
});

function initSessionManagement() {
  if (!sessionManager) {
    sessionManager = new SessionManager(15, 10); // 15 min timeout, 10 min warning

    sessionManager.on('logout', (data) => {
      auditLog.record({
        type: 'SESSION_LOGOUT',
        severity: 'info',
        sessionId: data.sessionId,
        reason: 'inactivity_timeout'
      });
    });
  }
}
```

### Step 4: Add Security Styles

Add to `templates/wallet-pwa.html` before closing `</head>`:

```html
<style>
/* Session Warning */
.session-warning {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(4px);
  z-index: 1000;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.3s;
}

.session-warning.active {
  display: flex;
}

.warning-content {
  background: var(--bg-card);
  border: 2px solid var(--warning);
  border-radius: 16px;
  padding: 32px;
  max-width: 400px;
  text-align: center;
  gap: 16px;
  display: flex;
  flex-direction: column;
}

.warning-content h3 {
  font-size: 20px;
  color: var(--warning);
}

.warning-content p {
  font-size: 14px;
  color: var(--text-secondary);
}

/* Screen Blur */
.screen-blur {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 20, 25, 0.95);
  backdrop-filter: blur(20px);
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.3s;
}

.blur-content {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.blur-icon {
  font-size: 64px;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.blur-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--primary);
}

.blur-subtext {
  font-size: 12px;
  color: var(--text-secondary);
}

/* Secure PIN Entry */
.secure-pin-entry {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px;
}

.pin-display {
  display: flex;
  justify-content: center;
  gap: 16px;
  padding: 24px;
  background: rgba(0, 212, 255, 0.05);
  border-radius: 12px;
  border: 1px solid rgba(0, 212, 255, 0.2);
}

.pin-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--border);
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  background: transparent;
}

.pin-dot.filled {
  background: var(--primary);
  border-color: var(--primary);
  box-shadow: 0 0 8px var(--primary);
}

.pin-keypad {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.pin-key {
  padding: 16px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 600;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  touch-action: manipulation;
  user-select: none;
}

.pin-key:active {
  background: var(--primary);
  border-color: var(--primary);
  color: #000;
  transform: scale(0.95);
}

.pin-key.delete-key {
  grid-column: 3;
}

.pin-key.clear-key {
  grid-column: 1 / 4;
  background: rgba(255, 51, 51, 0.1);
  border-color: var(--danger);
  color: var(--danger);
}

.pin-key.clear-key:active {
  background: var(--danger);
  color: white;
}

/* Security Warning Modal */
.security-warning-modal .modal-content {
  border-left: 4px solid var(--danger);
}
</style>
```

---

## Feature Integration Checklist

### Session Management
- [ ] Imported `SessionManager` class
- [ ] Called `initSessionManagement()` after unlock
- [ ] Added session warning styles
- [ ] Tested 15-minute timeout
- [ ] Verified audit logging on logout

### Rate Limiting
- [ ] Imported `RateLimiter` class (auto-initialized)
- [ ] Added to unlock button handler:
```javascript
const identifier = 'wallet_unlock';
const delay = rateLimiter.getDelayMs(identifier);
if (delay > 0) {
  await new Promise(resolve => setTimeout(resolve, delay));
}
// ... rest of unlock logic ...
```
- [ ] Tested 5 failed attempts lockout
- [ ] Verified 5-minute lockout period

### Memory Security
- [ ] Called `MemorySecure.setupAutoClearing()`
- [ ] Verified password inputs clear after 30s
- [ ] Tested memory zeroization
- [ ] Verified no sensitive data in logs

### Biometric Authentication
- [ ] Called `BiometricAuth.isAvailable()` after unlock screen loads
- [ ] Added biometric button to unlock if available
- [ ] Tested on iOS (Face ID) and Android (Fingerprint)
- [ ] Fallback to password works

### 2FA/TOTP
- [ ] Imported `TOTPManager` class
- [ ] Added 2FA setup after wallet creation
- [ ] Display QR code using qrcode.js library
- [ ] Tested TOTP code verification
- [ ] Backup codes generated and stored
- [ ] Verified 2FA during login

### Screen Blur
- [ ] Imported `ScreenBlur` class (auto-initialized)
- [ ] Tested app backgrounding
- [ ] Verified sensitive elements blur
- [ ] Tested screen restoration on foreground

### Device Security Checks
- [ ] Called `DeviceSecurityCheck.performCheck()`
- [ ] Display warnings for high severity issues
- [ ] Tested on emulator/jailbroken device
- [ ] Verified audit logging

### Audit Logging
- [ ] Initialized `auditLog` globally
- [ ] Recorded all security events
- [ ] Verified logs in localStorage
- [ ] Tested log export
- [ ] Set up periodic upload to server (optional)

### Clipboard Security
- [ ] Replaced `navigator.clipboard.writeText()` with `copyToClipboardSecure()`
- [ ] Tested clipboard auto-clear after 30s
- [ ] Verified no sensitive data remains in clipboard

### Security Headers
- [ ] Updated Flask app with Talisman
- [ ] Configured CSP headers
- [ ] Enabled HSTS
- [ ] Set X-Frame-Options to DENY
- [ ] Verified headers with securityheaders.com

---

## API Endpoint Updates

### Add audit log endpoint to backend:

```python
# app.py

@app.route('/api/audit-log', methods=['POST'])
@app.route('/api/audit-log', methods=['GET'])
def audit_log():
    """Central audit logging endpoint."""
    if request.method == 'POST':
        data = request.get_json()

        # Log to file/database
        with open('audit.log', 'a') as f:
            f.write(json.dumps({
                'timestamp': datetime.utcnow().isoformat(),
                'ip': request.remote_addr,
                'user_agent': request.headers.get('User-Agent'),
                'event': data
            }) + '\n')

        return {'status': 'logged'}, 200

    # GET - retrieve recent logs (requires auth)
    if not is_authenticated():
        return {'error': 'Unauthorized'}, 401

    # Return last 100 logs
    logs = []
    try:
        with open('audit.log', 'r') as f:
            logs = [json.loads(line) for line in f.readlines()[-100:]]
    except:
        pass

    return {'logs': logs}, 200
```

### Add rate limiting to API:

```python
# app.py

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/api/wallet/unlock', methods=['POST'])
@limiter.limit("5 per 5 minutes")
def wallet_unlock():
    """Unlock wallet - rate limited."""
    # Unlock logic
    pass

@app.route('/api/wallet/send', methods=['POST'])
@limiter.limit("10 per hour")
def send_transaction():
    """Send transaction - rate limited."""
    # Send logic
    pass
```

---

## Mobile App Integration (Cordova/Capacitor)

### Install plugins:

```bash
# Screen blur on background
cordova plugin add cordova-plugin-secure-screen

# Biometric auth
cordova plugin add cordova-plugin-fingerprint-aio

# Secure storage
cordova plugin add cordova-plugin-secure-storage

# Device info
cordova plugin add cordova-plugin-device
```

### JavaScript integration:

```javascript
// Check device security on app start
document.addEventListener('deviceready', async () => {
  // Check for root/jailbreak
  const issues = await DeviceSecurityCheck.performCheck();
  DeviceSecurityCheck.displaySecurityWarnings(issues);

  // Enable screen blur on pause
  document.addEventListener('pause', () => {
    screenBlur.blur();
  });

  document.addEventListener('resume', () => {
    screenBlur.unblur();
  });

  // Enable secure screen flag
  if (window.cordova?.plugins?.SecureScreen) {
    window.cordova.plugins.SecureScreen.enable();
  }

  // Store sensitive data securely
  if (window.SecureStorage) {
    const storage = new window.SecureStorage(
      () => console.log('SecureStorage ready'),
      (error) => console.error('SecureStorage error:', error)
    );

    // Store encrypted wallet
    storage.set('wallet_key', encryptedWallet,
      () => console.log('Wallet stored securely'),
      (error) => console.error('Storage error:', error)
    );
  }
});
```

---

## Testing Checklist

### Unit Tests

```javascript
// tests/security.test.js

describe('SessionManager', () => {
  test('should logout after timeout', (done) => {
    const manager = new SessionManager(0.1, 0.05); // 6s timeout, 3s warning

    setTimeout(() => {
      expect(manager.isBlurred).toBe(true);
      done();
    }, 4000);
  });
});

describe('RateLimiter', () => {
  test('should lock after 5 attempts', () => {
    const limiter = new RateLimiter(5, 5);

    for (let i = 0; i < 4; i++) {
      limiter.recordAttempt('test');
    }

    expect(() => limiter.recordAttempt('test')).toThrow();
  });
});

describe('MemorySecure', () => {
  test('should clear sensitive variable', () => {
    window.testVar = 'sensitive_data';
    MemorySecure.clearVariable('testVar');
    expect(window.testVar).toBeUndefined();
  });
});

describe('TOTPManager', () => {
  test('should verify valid TOTP code', async () => {
    const secret = TOTPManager.generateSecret();
    const code = await TOTPManager.generateTOTP(secret);
    expect(await TOTPManager.verifyTOTP(secret, code)).toBe(true);
  });
});
```

### Security Testing

1. **Penetration Testing**
   ```bash
   # OWASP ZAP scan
   zaproxy -cmd -quickurl https://moonbite.org/wallet -quickout report.html
   ```

2. **SSL/TLS Testing**
   ```bash
   # testssl.sh
   ./testssl.sh --full https://moonbite.org
   ```

3. **CSP Validation**
   ```bash
   # Check CSP compliance
   curl -I https://moonbite.org/wallet | grep Content-Security-Policy
   ```

4. **XSS Testing**
   - Input: `<script>alert('XSS')</script>` in all forms
   - Should be escaped or blocked by CSP

5. **CSRF Testing**
   - Verify CSRF tokens on state-changing requests
   - Test cross-origin requests blocked

6. **Memory Leak Testing**
   - Use Chrome DevTools Memory Profiler
   - Verify no accumulation of sensitive data

---

## Deployment Checklist

### Pre-Production
- [ ] All security modules enabled
- [ ] CSP headers configured
- [ ] HTTPS enforced
- [ ] Database encryption enabled
- [ ] Backup system tested
- [ ] Recovery key mechanism working
- [ ] Audit logging operational
- [ ] Rate limiting tested
- [ ] Session timeout verified
- [ ] Biometric auth tested on devices

### Production Release
- [ ] Security audit completed
- [ ] Third-party dependencies audited
- [ ] SSL certificate installed
- [ ] Firewall rules configured
- [ ] Monitoring alerts set up
- [ ] Incident response plan ready
- [ ] Security headers verified
- [ ] Penetration test passed
- [ ] Load testing completed
- [ ] Documentation updated

### Post-Launch Monitoring
- [ ] Monitor security headers (daily)
- [ ] Check audit logs (hourly)
- [ ] Review failed authentications (daily)
- [ ] Monitor SSL certificate expiry (monthly)
- [ ] Test backup restoration (weekly)
- [ ] Security updates check (daily)
- [ ] Performance monitoring (continuous)

---

## Security Event Response

### Incident Types

| Type | Severity | Action | Timeline |
|------|----------|--------|----------|
| Unauthorized Access | Critical | Disable account, reset password | Immediate |
| Suspicious Activity | High | Alert user, require re-auth | 1 hour |
| Rate Limit Exceeded | Medium | Temporary lockout | Automatic |
| Device Compromised | Critical | Warn user, force wallet reset | Immediate |
| Backup Breach | High | Notify user, mark backup invalid | 24 hours |
| Session Hijacking | Critical | Force logout all sessions | Immediate |

### Automated Response

```python
# app.py - Incident response

def handle_security_incident(incident_type, user_id, details):
    """Automated incident response."""

    if incident_type == 'UNAUTHORIZED_ACCESS':
        # Disable all sessions
        disable_user_sessions(user_id)
        # Send alert email
        send_security_alert(user_id, 'Unauthorized access detected')
        # Log to security team
        log_security_incident('CRITICAL', incident_type, details)

    elif incident_type == 'SUSPICIOUS_ACTIVITY':
        # Request step-up authentication
        request_additional_verification(user_id)
        log_security_incident('HIGH', incident_type, details)

    elif incident_type == 'DEVICE_COMPROMISED':
        # Force password reset
        invalidate_device(user_id)
        send_recovery_instructions(user_id)
        log_security_incident('CRITICAL', incident_type, details)
```

---

## Documentation

### User-Facing Documentation

Create `/docs/SECURITY_GUIDE.md` for users:

```markdown
# MoonBite Wallet Security Guide

## Your Responsibilities

1. **Password**: Create a strong, unique password
2. **2FA**: Enable two-factor authentication
3. **Device**: Keep your device updated
4. **Backup**: Save your recovery key safely
5. **Phishing**: Never share your password

## What We Do

- Encrypt your wallet with AES-256-GCM
- Protect your session with timeouts
- Monitor suspicious activity
- Secure HTTPS connections
- Regular security audits

## Reporting Security Issues

Found a security vulnerability?
Email: security@moonbite.org
We offer a bug bounty for valid reports.
```

---

## Maintenance Schedule

| Task | Frequency | Owner |
|------|-----------|-------|
| Security header audit | Weekly | DevOps |
| Dependency updates | Monthly | Development |
| Penetration testing | Quarterly | Security |
| Incident log review | Daily | Security |
| Backup verification | Weekly | Operations |
| SSL certificate renewal | 60 days before expiry | DevOps |

---

## References

- [OWASP Mobile Top 10](https://owasp.org/www-project-mobile-top-10/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CWE/SANS Top 25](https://cwe.mitre.org/top25/)
- [Bitcoin Security Best Practices](https://bitcoin.org/en/secure-your-wallet)

---

**Document Version**: 1.0
**Last Updated**: 2026-08-06
**Maintained By**: MoonBite Security Team
