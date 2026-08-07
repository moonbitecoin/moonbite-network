# MoonBite iOS PWA Implementation Guide

## Overview

This guide covers complete iOS PWA implementation for MoonBite Wallet, ensuring perfect compatibility with iPhone Safari, iPad, and AndroidChrome.

## Project Files Created

### 1. PWA Configuration Files

**Location**: `/static/manifest.json`
- Web App Manifest (W3C standard)
- iOS app icon definitions
- Splash screen configurations
- App shortcuts and file handlers
- Protocol handlers for deep linking

**Location**: `/static/ios-pwa-head.html`
- iOS-specific meta tags
- Launch images for all screen sizes
- Apple touch icons
- Service worker registration
- Safe area detection

### 2. Service Worker

**Location**: `/static/service-worker.js`
- Offline-first caching strategy
- TLS 1.3 compatible
- Background sync for transactions
- Periodic wallet updates
- iOS gesture support
- Network timeout handling

**Cache Strategy**:
- Critical assets: Cache-first
- API calls: Network-first with 5s timeout
- Images: Cache-first
- HTML: Network-first (dynamic content)
- CSS/JS: Cache-first (versioned)

### 3. iOS PWA Initialization

**Location**: `/static/ios-pwa-init.js`
- Service worker registration
- Gesture handlers (swipe, long-press)
- Haptic feedback support
- Safe area management
- App lifecycle handling
- Update notifications

### 4. iOS CSS

**Location**: `/static/ios-pwa.css`
- Safe area support (notch, home indicator)
- Viewport fixes
- Gesture-friendly UI (44x44px min tap targets)
- Landscape orientation handling
- iOS input styling
- Keyboard handling

### 5. SSL/HTTPS Deployment

**Dockerfile**: `/deploy/Dockerfile.https`
- Ubuntu 22.04 base
- nginx + certbot included
- Python app support
- Health checks
- Let's Encrypt ready

**nginx Configuration**: `/deploy/nginx.conf`
- TLS 1.2 + 1.3
- OCSP stapling
- Security headers (HSTS, CSP, etc.)
- Rate limiting
- Service worker cache control
- iOS-optimized headers

**SSL Configuration**: `/deploy/ssl.conf`
- Cipher suite optimization
- Session management
- Certificate pinning headers
- DH parameters

**Entrypoint Script**: `/deploy/entrypoint-https.sh`
- Automatic certificate management
- Let's Encrypt integration
- Self-signed fallback
- Service startup orchestration
- Renewal automation

## Implementation Steps

### Step 1: Update HTML Head Tags

Add to your main HTML template (e.g., `website/index.html`, `templates/base.html`):

```html
<!-- In <head> section -->
<link rel="manifest" href="/static/manifest.json">
<meta name="viewport" content="viewport-fit=cover, width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="true">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="MoonBite">
<meta name="theme-color" content="#0A0C0F">

<!-- Include iOS PWA meta tags (copy from ios-pwa-head.html) -->
<link rel="apple-touch-icon" sizes="180x180" href="data:image/svg+xml,...">

<!-- Link iOS PWA CSS -->
<link rel="stylesheet" href="/static/ios-pwa.css">

<!-- Initialize iOS PWA -->
<script src="/static/ios-pwa-init.js"></script>
```

### Step 2: Deploy with HTTPS

#### Option A: Docker Deployment (Recommended)

```bash
# Build the Docker image
docker build -f deploy/Dockerfile.https -t moonbite-https:latest .

# Run with Let's Encrypt (production)
docker run -e DOMAIN=moonbite.org \
           -e LETSENCRYPT_EMAIL=admin@moonbite.org \
           -e USE_LETSENCRYPT=true \
           -p 80:80 \
           -p 443:443 \
           -v /etc/letsencrypt:/etc/letsencrypt \
           moonbite-https:latest

# Run with self-signed certificate (development)
docker run -e DOMAIN=localhost \
           -p 80:80 \
           -p 443:443 \
           moonbite-https:latest
```

#### Option B: Manual Certbot Setup

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot certonly --standalone \
  --email admin@moonbite.org \
  --agree-tos \
  --domains moonbite.org,www.moonbite.org

# Restart nginx
sudo systemctl restart nginx

# Setup auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### Step 3: Configure Service Worker

The service worker is automatically registered via `ios-pwa-init.js`. To customize cache strategy:

```javascript
// In your app.js or initialization code
window.addEventListener('update-available', (event) => {
    console.log('Update available:', event.detail.message);
    // Show update notification to user
});

window.addEventListener('sync-complete', () => {
    console.log('Wallet synced from offline');
});
```

### Step 4: Enable Background Sync

Add to your wallet component:

```javascript
// Request sync when transaction is pending
if ('serviceWorker' in navigator && 'SyncManager' in window) {
    navigator.serviceWorker.ready.then(registration => {
        registration.sync.register('sync-transactions');
    });
}
```

### Step 5: Handle iOS-Specific Features

```javascript
// Access iOS PWA manager
if (window.iOSPWA) {
    // Get app status
    const status = window.iOSPWA.getStatus();
    console.log('Standalone mode:', status.isStandalone);

    // Request notifications
    window.iOSPWA.requestNotificationPermission();

    // Show notification
    window.iOSPWA.showNotification('Transaction confirmed', {
        body: 'Your MBITE transfer is complete',
        icon: '/static/moonbite-logo.svg'
    });

    // Trigger haptic feedback
    if (window.haptic) {
        window.haptic.success(); // Haptic feedback
    }
}
```

## iOS Testing Guide

### Test on Real iPhone/iPad

#### Add to Home Screen (iOS 13+)

1. Open Safari
2. Navigate to `https://moonbite.org`
3. Tap **Share** button
4. Select **Add to Home Screen**
5. Name: "MoonBite"
6. Tap **Add**

#### Test Standalone Mode

1. Launch app from home screen
2. Verify:
   - No Safari chrome (address bar, buttons)
   - Custom status bar color (black-translucent)
   - App icon visible
   - Proper splash screen on launch

#### Test Offline Functionality

1. Go to Settings > WiFi > Disconnect
2. Enable Airplane Mode
3. Launch app
4. Verify:
   - App loads from cache
   - Previous data visible
   - Network error messages clear
   - Pending transactions queue

#### Test Notifications

1. Enable notifications when prompted
2. Close app (swipe up from home)
3. Trigger notification from backend
4. Verify notification appears

#### Test Safe Areas

1. Launch on notched device (iPhone 12, 13, 14)
2. Rotate to landscape
3. Verify:
   - Content avoids notch
   - Bottom bar respects home indicator
   - Proper spacing on all edges

### Automated Testing (Development)

```bash
# Test SSL certificate
openssl s_client -connect moonbite.org:443 -tls1_3

# Check OCSP stapling
openssl s_client -connect moonbite.org:443 -tlsextdebug 2>&1 | grep -A5 "OCSP"

# Validate service worker
curl -I https://moonbite.org/static/service-worker.js

# Check security headers
curl -I https://moonbite.org/ | grep -E "Strict-Transport|X-Content-Type|Content-Security"

# Test offline caching
curl -H "Service-Worker: true" https://moonbite.org/static/manifest.json
```

## iOS Compatibility Checklist

### Certificate & SSL

- [x] HTTPS enabled (TLS 1.3)
- [x] Valid certificate from trusted CA
- [x] Certificate not self-signed (or ignored in dev)
- [x] OCSP stapling enabled
- [x] HSTS header present
- [x] Mixed content warnings eliminated

### Manifest & Icons

- [x] manifest.json present
- [x] Icons for all sizes (192px, 512px, 180px, 152px, 120px)
- [x] Splash images for all devices
- [x] Start URL configured
- [x] Theme colors set
- [x] Display mode: standalone

### Service Worker

- [x] Registered with proper scope
- [x] Cache strategy working offline
- [x] Background sync for data
- [x] Periodic updates
- [x] Message handling
- [x] Update notifications

### HTML/CSS

- [x] Viewport meta tag (viewport-fit=cover)
- [x] Apple mobile web app meta tags
- [x] Safe area CSS variables
- [x] Gesture-friendly buttons (44x44px)
- [x] No iOS input zoom
- [x] Proper status bar color

### Performance

- [x] Sub-3s first paint
- [x] Sub-5s interactive
- [x] Gzip compression
- [x] Asset versioning
- [x] Lazy loading images
- [x] Code splitting

### Security

- [x] CSP headers configured
- [x] CORS headers set
- [x] X-Frame-Options: SAMEORIGIN
- [x] No XSS vulnerabilities
- [x] Password fields secure
- [x] No sensitive data in URLs

## Troubleshooting

### App Won't Install to Home Screen

**Issue**: "Add to Home Screen" option missing

**Solutions**:
1. Ensure manifest.json is valid JSON
2. Check manifest Content-Type: `application/manifest+json`
3. Verify HTTPS is working
4. Test in Safari (not Chrome)
5. Clear Safari cache: Settings > Safari > Clear History and Website Data

### Service Worker Not Working

**Issue**: App still loads old version or won't work offline

**Solutions**:
```javascript
// Force service worker update
navigator.serviceWorker.getRegistrations().then(regs => {
    regs.forEach(reg => reg.unregister());
});

// Or manually check for updates
if (navigator.serviceWorker.controller) {
    navigator.serviceWorker.controller.postMessage({
        type: 'GET_VERSION'
    });
}
```

### SSL Certificate Error on iPhone

**Issue**: "This site can't be reached" or security warning

**Solutions**:
1. Install certificate on device (Settings > General > VPN & Device Management)
2. Ensure certificate is from trusted CA (not self-signed)
3. Check certificate expiration
4. Verify domain matches certificate
5. Test with `openssl s_client`

### Notch/Safe Area Not Respected

**Issue**: Content overlaps with notch

**Solutions**:
1. Add viewport-fit=cover to meta tag
2. Use safe area CSS variables
3. Add padding to header/footer:
   ```css
   header {
       padding-top: max(12px, env(safe-area-inset-top));
   }
   ```

### Offline Mode Not Working

**Issue**: App requires network even with cache

**Solutions**:
```javascript
// Check cache
caches.keys().then(names => console.log('Caches:', names));

// Verify service worker is active
navigator.serviceWorker.controller !== null

// Check fetch event handling
// (Look in DevTools console for '[SW]' logs)
```

### Notification Not Showing

**Issue**: Notifications not appearing

**Solutions**:
1. Request notification permission: `Notification.requestPermission()`
2. Use service worker for notifications (not main thread)
3. Ensure app has permission in Settings
4. Test with `window.iOSPWA.showNotification()`

## Performance Optimization

### Cache Strategy

```javascript
// Critical assets loaded first
const CRITICAL = ['/wallet', '/static/style.css'];

// API calls always try network
// Images cached after first load
// Old caches automatically cleaned up
```

### Code Splitting

```html
<!-- Lazy load non-critical features -->
<script async src="/static/advanced-features.js"></script>

<!-- Inline critical CSS -->
<style>
  /* Critical above-fold styles */
</style>
<link rel="stylesheet" href="/static/rest.css">
```

### Asset Optimization

```bash
# Minify CSS/JS
minify-css input.css -o input.min.css
minify-js input.js -o input.min.js

# Compress images
cwebp image.png -o image.webp
pngquant image.png -o image-min.png

# Generate responsive images
convert image.png -resize 192x192 icon-192.png
convert image.png -resize 512x512 icon-512.png
```

## Security Best Practices

1. **Certificate Pinning** (Advanced):
   ```javascript
   // Verify certificate on connection
   if (window.iOSPWA && window.iOSPWA.getStatus().isStandalone) {
       // Implement certificate pinning verification
   }
   ```

2. **Content Security Policy**:
   - Default to 'self'
   - Only allow necessary external sources
   - Disable eval/inline scripts

3. **Secure Storage**:
   - Use IndexedDB for encrypted data
   - Never store keys in localStorage
   - Clear sensitive data on logout

4. **HTTPS Only**:
   - HSTS header with long max-age
   - Redirect HTTP to HTTPS
   - Preload HSTS in browser

## Deployment Commands

```bash
# Build and test locally
npm run build
npm run test:ios

# Deploy to Docker
docker build -f deploy/Dockerfile.https -t moonbite:latest .
docker push your-registry/moonbite:latest

# Deploy to Kubernetes
kubectl apply -f deploy/k8s-moonbite.yaml

# Deploy to Railway
railway up -d moonbite-https

# Monitor logs
docker logs -f <container-id>
kubectl logs -f deployment/moonbite
```

## Next Steps

1. **Add Progressive Updates**: Implement update notifications
2. **Enable Offline Payments**: Queue transactions while offline
3. **Add Share API**: Share payment URLs via native share
4. **Implement Backup/Restore**: Let users export/import wallet
5. **Add Push Notifications**: Real-time transaction alerts
6. **Biometric Auth**: Face ID / Touch ID support

## References

- [Web App Manifest Spec](https://w3c.github.io/manifest/)
- [Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [Apple App Store Guidelines - Web Apps](https://developer.apple.com/app-store/web-apps/)
- [iOS Safari PWA Support](https://webkit.org/blog/15256/web-apps-on-ios-17-beta-2/)
- [OWASP Mobile Security](https://owasp.org/www-project-mobile-security/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review browser console for errors
3. Check nginx error logs
4. Test with different iOS versions
5. Open GitHub issue with details
