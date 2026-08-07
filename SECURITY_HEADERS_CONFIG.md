# MoonBite Wallet - Security Headers Configuration

**Purpose**: Comprehensive HTTP security headers to protect against MITM, XSS, clickjacking, and other web attacks.

## Implementation Methods

### 1. Flask/Python Backend (app.py)

```python
# Add security headers to all responses
from flask import Flask, after_this_request

app = Flask(__name__)

@app.after_request
def set_security_headers(response):
    """Apply comprehensive security headers to all responses."""

    # Content Security Policy - Prevent XSS, code injection
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'wasm-unsafe-eval' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: https:; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "connect-src 'self' https://moonbite.org wss:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "upgrade-insecure-requests"
    )

    # HTTP Strict Transport Security - Force HTTPS
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'

    # Clickjacking protection
    response.headers['X-Frame-Options'] = 'DENY'

    # XSS protection
    response.headers['X-XSS-Protection'] = '1; mode=block'

    # Referrer policy - Don't leak URL to external sites
    response.headers['Referrer-Policy'] = 'no-referrer'

    # Feature policy / Permissions policy
    response.headers['Permissions-Policy'] = (
        'geolocation=(), '
        'microphone=(), '
        'camera=(), '
        'payment=(), '
        'usb=(), '
        'accelerometer=(), '
        'gyroscope=(), '
        'magnetometer=()'
    )

    # Remove server header to avoid fingerprinting
    response.headers.pop('Server', None)

    # Prevent caching of sensitive data
    if 'wallet' in request.path or 'api' in request.path:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

    # Additional security headers
    response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'
    response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'

    return response

@app.route('/security.txt', methods=['GET'])
def security_txt():
    """Provide security contact information."""
    return """Contact: security@moonbite.org
Expires: 2026-12-31T23:59:59.000Z
Preferred-Languages: en
""", 200, {'Content-Type': 'text/plain'}

@app.route('/.well-known/security.json', methods=['GET'])
def security_json():
    """Provide security policy in JSON format."""
    return {
        "security_contact": "security@moonbite.org",
        "security_policy_url": "https://moonbite.org/security",
        "preferred_languages": ["en"],
        "encryption_support": {
            "key_algorithm": "RSA-4096",
            "key_id": "moonbite-2026-001",
            "key_url": "https://moonbite.org/.well-known/pgp-key.pub"
        },
        "bug_bounty": {
            "enabled": True,
            "contact": "security@moonbite.org",
            "scope": "https://moonbite.org/wallet"
        }
    }, 200, {'Content-Type': 'application/json'}
```

### 2. Nginx Configuration

```nginx
# /etc/nginx/includes/security-headers.conf

# Content Security Policy
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'wasm-unsafe-eval' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: https:; font-src 'self' data: https://fonts.gstatic.com; connect-src 'self' https://moonbite.org wss:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests;" always;

# HSTS - Force HTTPS for 1 year, including subdomains
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

# Prevent MIME type sniffing
add_header X-Content-Type-Options "nosniff" always;

# Clickjacking protection
add_header X-Frame-Options "DENY" always;

# XSS protection (legacy)
add_header X-XSS-Protection "1; mode=block" always;

# Referrer policy
add_header Referrer-Policy "no-referrer" always;

# Feature/Permissions policy
add_header Permissions-Policy "geolocation=(), microphone=(), camera=(), payment=(), usb=(), accelerometer=(), gyroscope=(), magnetometer=()" always;

# Remove server header
server_tokens off;

# Don't allow embedding
add_header X-Permitted-Cross-Domain-Policies "none" always;

# Cross-Origin policies
add_header Cross-Origin-Embedder-Policy "require-corp" always;
add_header Cross-Origin-Opener-Policy "same-origin" always;
add_header Cross-Origin-Resource-Policy "same-origin" always;

# Disable cache for sensitive endpoints
location ~ /(wallet|api)/ {
    add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0" always;
    add_header Pragma "no-cache" always;
    add_header Expires "0" always;
}

# CORS configuration for API
location /api/ {
    add_header Access-Control-Allow-Origin "https://moonbite.org" always;
    add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;
    add_header Access-Control-Max-Age "3600" always;

    if ($request_method = 'OPTIONS') {
        return 204;
    }
}

# Security.txt
location /.well-known/security.txt {
    alias /usr/share/nginx/html/.well-known/security.txt;
    add_header Content-Type "text/plain" always;
}
```

### 3. HTML Meta Tags

Add to `wallet-pwa.html` `<head>`:

```html
<!-- Content Security Policy -->
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  script-src 'self' 'wasm-unsafe-eval' https://cdnjs.cloudflare.com;
  style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
  img-src 'self' data: https:;
  font-src 'self' data: https://fonts.gstatic.com;
  connect-src 'self' https://moonbite.org wss:;
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
  upgrade-insecure-requests
">

<!-- IE Compatibility -->
<meta http-equiv="X-UA-Compatible" content="IE=edge">

<!-- MIME type prevention -->
<meta http-equiv="X-Content-Type-Options" content="nosniff">

<!-- Referrer policy -->
<meta http-equiv="Referrer-Policy" content="no-referrer">

<!-- Color scheme preference -->
<meta name="color-scheme" content="dark">

<!-- Google Site Verification (if needed) -->
<meta name="google-site-verification" content="YOUR_VERIFICATION_CODE">

<!-- Security DNS settings -->
<link rel="dns-prefetch" href="https://moonbite.org">
<link rel="preconnect" href="https://moonbite.org">
```

## Subresource Integrity (SRI)

For any external scripts or stylesheets:

```html
<!-- Example: jQuery with SRI -->
<script
  src="https://code.jquery.com/jquery-3.6.0.min.js"
  integrity="sha384-KyZXEAg3QhqLMpG8r+Knujsl5+backend/..."
  crossorigin="anonymous">
</script>

<!-- Generate SRI hashes -->
<!-- Use: openssl dgst -sha384 -binary file.js | openssl base64 -A -->
```

## HTTPS/TLS Configuration

### Certbot Setup (Let's Encrypt)

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate
sudo certbot certonly --nginx -d moonbite.org -d www.moonbite.org

# Auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Test renewal
sudo certbot renew --dry-run
```

### TLS Configuration (Nginx)

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers HIGH:!aNULL:!MD5;
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
ssl_session_tickets off;

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name moonbite.org www.moonbite.org;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name moonbite.org www.moonbite.org;

    ssl_certificate /etc/letsencrypt/live/moonbite.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/moonbite.org/privkey.pem;

    # Include security headers
    include /etc/nginx/includes/security-headers.conf;
}
```

## Certificate Pinning

For mobile applications:

```javascript
// JavaScript (Web): Subresource Integrity
// Android: Network Security Configuration
// iOS: Certificate Pinning via NSAppDelegate

// Verify certificate during API calls
async function fetchWithCertPinning(url, options = {}) {
    const response = await fetch(url, options);

    // Verify certificate chain
    const certificate = await response.headers.get('x-ssl-certificate');
    if (!certificate || !verifyPinnedCertificate(certificate)) {
        throw new Error('Certificate pinning validation failed');
    }

    return response;
}

function verifyPinnedCertificate(cert) {
    const pinnedCerts = [
        'sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
        // Add your cert hashes
    ];

    return pinnedCerts.includes(cert);
}
```

## Security Testing Endpoints

### SSL Labs Test
https://www.ssllabs.com/ssltest/analyze.html?d=moonbite.org

### Security Headers Test
https://securityheaders.com/?q=moonbite.org

### Mozilla Observatory
https://observatory.mozilla.org/analyze/moonbite.org

## Implementation Checklist

- [ ] CSP headers configured
- [ ] HSTS enabled (min 1 year)
- [ ] X-Frame-Options set to DENY
- [ ] X-Content-Type-Options set to nosniff
- [ ] HTTPS enforced (redirect HTTP)
- [ ] TLS 1.2+ only
- [ ] Strong ciphers configured
- [ ] Security.txt published
- [ ] SRI hashes for external resources
- [ ] CORS headers restrictive
- [ ] Remove server identification headers
- [ ] Cache headers for sensitive pages
- [ ] Permissions-Policy configured
- [ ] Referrer-Policy set
- [ ] DNSSEC enabled (if applicable)
- [ ] Certificate pinning (mobile apps)
- [ ] Regular SSL/TLS audits
- [ ] Documented security policy
- [ ] Bug bounty program (optional)

## Monitoring & Alerts

### Python monitoring script:

```python
import requests
from datetime import datetime

def check_security_headers():
    """Verify security headers are present."""
    url = 'https://moonbite.org/wallet'
    headers_required = [
        'Strict-Transport-Security',
        'Content-Security-Policy',
        'X-Content-Type-Options',
        'X-Frame-Options',
        'Referrer-Policy'
    ]

    try:
        response = requests.head(url, timeout=5)
        missing = []

        for header in headers_required:
            if header not in response.headers:
                missing.append(header)

        if missing:
            print(f"[ALERT] Missing security headers: {', '.join(missing)}")
            # Send alert to security team
        else:
            print(f"[OK] All security headers present at {datetime.now()}")

    except requests.RequestException as e:
        print(f"[ERROR] Could not verify headers: {e}")

# Run as cron job
# 0 */6 * * * python3 /opt/security-headers-check.py
```

---

**Maintained by**: MoonBite Security Team
**Last Updated**: 2026-08-06
**Version**: 1.0
