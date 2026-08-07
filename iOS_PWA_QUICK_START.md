# MoonBite iOS PWA Quick Start (5-Minute Setup)

## TL;DR

```bash
# 1. Add to HTML head
<link rel="manifest" href="/static/manifest.json">
<link rel="stylesheet" href="/static/ios-pwa.css">
<script src="/static/ios-pwa-init.js"></script>

# 2. Deploy with HTTPS (Docker)
docker build -f deploy/Dockerfile.https -t moonbite-https:latest .
docker run -e DOMAIN=moonbite.org \
           -e LETSENCRYPT_EMAIL=admin@moonbite.org \
           -e USE_LETSENCRYPT=true \
           -p 80:80 -p 443:443 \
           moonbite-https:latest

# 3. Test on iPhone
# Settings > Safari > Clear History and Website Data
# Navigate to https://moonbite.org
# Tap Share > Add to Home Screen
```

## Files Created

| File | Purpose |
|------|---------|
| `/static/manifest.json` | PWA metadata & icons |
| `/static/service-worker.js` | Offline caching & sync |
| `/static/ios-pwa-init.js` | iOS feature initialization |
| `/static/ios-pwa.css` | Safe area & notch support |
| `/static/ios-pwa-head.html` | Copy iOS meta tags from this |
| `/deploy/Dockerfile.https` | Docker with SSL/nginx |
| `/deploy/nginx.conf` | nginx HTTPS config |
| `/deploy/ssl.conf` | SSL/TLS settings |
| `/deploy/entrypoint-https.sh` | Container entrypoint |

## Add to Your HTML (Right Now)

### Copy iOS Meta Tags

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="viewport-fit=cover, width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">

  <!-- PWA Manifest -->
  <link rel="manifest" href="/static/manifest.json">

  <!-- iOS Web App Meta Tags -->
  <meta name="apple-mobile-web-app-capable" content="true">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="MoonBite">
  <meta name="theme-color" content="#0A0C0F">

  <!-- Apple Touch Icons -->
  <link rel="apple-touch-icon" sizes="180x180" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 180 180'%3E%3Crect fill='%230A0C0F' width='180' height='180' rx='40'/%3E%3Ccircle cx='90' cy='90' r='70' fill='%23C9A24B'/%3E%3Ctext x='90' y='110' font-size='100' fill='%230A0C0F' text-anchor='middle' dominant-baseline='central' font-weight='bold'%3E%F0%9F%8C%99%3C/text%3E%3C/svg%3E">

  <!-- iOS PWA Styles -->
  <link rel="stylesheet" href="/static/ios-pwa.css">

  <title>MoonBite</title>
</head>
<body>
  <!-- Your content -->

  <!-- iOS PWA Initialization -->
  <script src="/static/ios-pwa-init.js"></script>
</body>
</html>
```

## Deploy in 3 Steps

### Step 1: Build Docker Image
```bash
docker build -f deploy/Dockerfile.https -t moonbite-https:latest .
```

### Step 2: Run Container
```bash
# Production (with Let's Encrypt)
docker run -d --name moonbite-web \
  -e DOMAIN=moonbite.org \
  -e LETSENCRYPT_EMAIL=admin@moonbite.org \
  -e USE_LETSENCRYPT=true \
  -p 80:80 -p 443:443 \
  -v moonbite-certs:/etc/letsencrypt \
  -v moonbite-logs:/app/logs \
  moonbite-https:latest

# Development (self-signed)
docker run -d --name moonbite-web \
  -e DOMAIN=localhost \
  -p 80:80 -p 443:443 \
  moonbite-https:latest
```

### Step 3: Check Logs
```bash
docker logs -f moonbite-web
# Wait for: "MoonBite HTTPS Ready"
```

## Test on iPhone (90 seconds)

1. **Clear Safari Cache**:
   - Settings > Safari > Clear History and Website Data
   - Tap "Clear History and Data"

2. **Open Safari**:
   - Navigate to `https://moonbite.org`
   - Should show green lock (HTTPS)

3. **Add to Home Screen**:
   - Tap Share button (square arrow icon)
   - Scroll down
   - Tap "Add to Home Screen"
   - Verify name is "MoonBite"
   - Tap "Add"

4. **Launch App**:
   - Go to home screen
   - Tap MoonBite icon
   - Should launch full-screen (no Safari chrome)

## Verify It Works

### In Browser Console
```javascript
// Check standalone mode
window.navigator.standalone // Should be true

// Check service worker
navigator.serviceWorker.controller !== null // Should be true

// Check manifest
fetch('/static/manifest.json').then(r => r.json()).then(m => console.log(m.name))

// Check offline
navigator.onLine // true when online, false when offline
```

### Test Offline
1. Enable Airplane Mode: Settings > Airplane Mode
2. Return to app
3. Page should still load from cache
4. Disable Airplane Mode to sync

## Common Issues & Fixes

### "Add to Home Screen" Missing
```
Fix: Clear Safari cache
Settings > Safari > Clear History and Website Data
```

### SSL Certificate Warning
```
Fix: Use Let's Encrypt (automatic)
or accept warning in dev (Settings > General > VPN & Device Management)
```

### App Still Shows Safari Chrome
```
Fix: Not in standalone mode
1. Close app
2. Settings > Safari > Clear History and Website Data
3. Add to home screen again
```

### Offline Mode Not Working
```
Fix: Check service worker registration
navigator.serviceWorker.getRegistrations().then(r => console.log(r))
```

### Notch Overlaps Content
```
Fix: Already handled in ios-pwa.css
But verify viewport meta tag has viewport-fit=cover
```

## Configuration

### Change App Name
```json
// In static/manifest.json
{
  "name": "Your App Name",
  "short_name": "Short Name",
  ...
}
```

### Change Colors
```json
// In static/manifest.json
{
  "background_color": "#0A0C0F",  // During load
  "theme_color": "#C9A24B"         // Status bar
}
```

### Change Icons
Replace SVG data URIs in `manifest.json` and `ios-pwa-head.html`

### Change Cache Strategy
Edit `/static/service-worker.js`:
```javascript
// Lines 88-110: Modify cache strategies
// Network-first, Cache-first, or Stale-while-revalidate
```

## Performance Checklist

- [x] HTTPS enabled
- [x] Manifest valid JSON
- [x] Service worker < 100KB
- [x] Icons embedded (no external images)
- [x] CSS minified
- [x] JavaScript optimized
- [x] Cache headers set
- [x] Compression (gzip) enabled

## Security Checklist

- [x] TLS 1.2 minimum
- [x] HSTS header
- [x] CSP headers
- [x] X-Frame-Options: SAMEORIGIN
- [x] X-Content-Type-Options: nosniff
- [x] No mixed content
- [x] No inline scripts (except minimal init)
- [x] Service worker scope limited

## Monitoring

### Check Certificate Expiration
```bash
# View in Docker
docker exec moonbite-web \
  openssl x509 -in /etc/letsencrypt/live/moonbite.org/fullchain.pem \
  -noout -enddate

# View locally
openssl x509 -in /etc/letsencrypt/live/moonbite.org/fullchain.pem -noout -enddate
```

### Monitor Service Worker Updates
```javascript
// In app.js
window.addEventListener('update-available', (event) => {
    console.log('Update available:', event.detail);
    // Show notification to user
});
```

### Check Offline Usage
```javascript
// In console
navigator.storage.estimate().then(est => {
    console.log(`${(est.usage/est.quota*100).toFixed(2)}% used`);
});
```

## Next Steps

1. **Test on Real Device**: iPhone 12+ recommended
2. **Add Custom Features**:
   ```javascript
   // Use window.iOSPWA for iOS features
   if (window.iOSPWA) {
       window.iOSPWA.showNotification('Hello!', {
           body: 'App is working!',
           icon: '/static/moonbite-logo.svg'
       });
   }
   ```

3. **Setup Monitoring**:
   - Certificate expiration alerts
   - Service worker update notifications
   - Performance metrics

4. **Add More Features**:
   - Background sync
   - Push notifications
   - Offline transaction queueing
   - Biometric authentication

## Full Documentation

- **iOS PWA Implementation**: `iOS_PWA_IMPLEMENTATION.md`
- **Certificate Setup**: `CERTIFICATE_SETUP.md`
- **Testing Guide**: `iOS_TESTING_GUIDE.md`

## Support Commands

```bash
# Test HTTPS
curl -I https://moonbite.org

# Test manifest
curl https://moonbite.org/static/manifest.json | jq .

# Test service worker
curl -I https://moonbite.org/static/service-worker.js

# Check headers
curl -I https://moonbite.org | grep -i security

# Check certificate
openssl s_client -connect moonbite.org:443 -showcerts

# Check OCSP stapling
openssl s_client -connect moonbite.org:443 -tlsextdebug 2>&1 | grep -i ocsp
```

## Troubleshooting Flowchart

```
Is app on home screen?
├─ No → Clear Safari cache, readd to home screen
└─ Yes ↓

Does it launch full-screen?
├─ No (shows Safari) → Settings reset or different Safari version
└─ Yes ↓

Works offline?
├─ No → Check service worker console logs
└─ Yes ↓

Safe areas respected (notch)?
├─ No → Check viewport-fit=cover in meta tag
└─ Yes ↓

✓ All working!
```

## One-Liner Deployment

```bash
# Clone, build, and run
git clone https://github.com/moonbitecoin/MoonBite-Coin.git && \
cd MoonBite-Coin && \
docker build -f deploy/Dockerfile.https -t moonbite . && \
docker run -d -e DOMAIN=moonbite.org -e LETSENCRYPT_EMAIL=admin@moonbite.org -e USE_LETSENCRYPT=true -p 80:80 -p 443:443 moonbite
```

---

**Status**: Production Ready
**Last Updated**: 2024-08-07
**iOS Support**: 12.2+ (PWA), 15.0+ (Standalone)
**Android Support**: Chrome 57+
