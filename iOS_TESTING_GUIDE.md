# MoonBite iOS PWA Testing Guide

## Overview

Complete testing procedures for iOS Safari PWA compatibility, offline functionality, and native app-like experience.

## Pre-Testing Setup

### Environment Preparation

```bash
# 1. Ensure HTTPS is working
curl -I https://moonbite.org
# Should return 200 OK with Strict-Transport-Security header

# 2. Test on local machine first
npm run dev  # or python3 web_app.py

# 3. For testing on real device, use ngrok or similar
ngrok http 5000
# Get URL like https://abc123.ngrok.io

# 4. Test on different network (WiFi & cellular)
```

### Device Preparation (Physical iPhone/iPad)

1. Update to latest iOS version (Settings > General > Software Update)
2. Close all apps (clear from memory)
3. Clear Safari cache:
   - Settings > Safari > Clear History and Website Data
4. Reset network settings (if having connection issues):
   - Settings > General > Reset > Reset Network Settings

## Test Case 1: Installation & Home Screen

### Add to Home Screen

**Procedure**:
1. Open Safari
2. Navigate to https://moonbite.org
3. Tap Share button (square with arrow)
4. Select "Add to Home Screen"
5. Verify app name: "MoonBite"
6. Tap "Add"

**Expected Results**:
- [ ] App appears on home screen
- [ ] Custom icon visible (moon emoji on gold)
- [ ] App name is "MoonBite"
- [ ] No "Clip" or bookmark label

**Verification**:
```javascript
// In console, check standalone mode
console.log(window.navigator.standalone); // Should be true
console.log(window.matchMedia('(display-mode: standalone)').matches); // true
```

### Launch Behavior

**Procedure**:
1. Close Safari completely
2. Tap MoonBite app on home screen
3. Observe launch sequence

**Expected Results**:
- [ ] Splash screen appears (MoonBite logo on dark background)
- [ ] App launches in 2-3 seconds
- [ ] No Safari chrome (address bar, buttons)
- [ ] Status bar color is black (translucent)
- [ ] App takes full screen

**Verification**:
```javascript
console.log(document.documentElement.classList.contains('ios-standalone')); // true
```

## Test Case 2: Safe Area & Notch Support

### Portrait Mode (Notched iPhone)

**Devices**: iPhone 12/13/14/Pro, iPhone X/Xs
**Procedure**:
1. Launch app in portrait
2. Observe content in notch area
3. Check top and bottom spacing

**Expected Results**:
- [ ] No content under notch
- [ ] Top navigation visible below notch
- [ ] Status bar properly colored
- [ ] No content cut off on sides

**Verification**:
```javascript
// Check safe area values
const style = getComputedStyle(document.documentElement);
const top = style.getPropertyValue('--safe-area-inset-top');
const bottom = style.getPropertyValue('--safe-area-inset-bottom');
console.log('Safe area top:', top, 'bottom:', bottom);
```

### Landscape Mode (Home Indicator)

**Procedure**:
1. Rotate device to landscape
2. Observe bottom spacing
3. Check left/right edges for notch

**Expected Results**:
- [ ] Content respects bottom safe area (home indicator)
- [ ] No content under home indicator
- [ ] Navigation properly positioned
- [ ] Proper spacing on notched sides

### iPad (Landscape & Portrait)

**Devices**: iPad Pro 12.9", iPad Air
**Procedure**:
1. Launch on iPad
2. Test portrait orientation
3. Rotate to landscape
4. Check all edges

**Expected Results**:
- [ ] Content scales properly
- [ ] Touch targets remain 44x44px minimum
- [ ] No horizontal scroll
- [ ] Proper landscape navigation layout

## Test Case 3: Offline Functionality

### Service Worker Installation

**Procedure**:
1. Launch app (online)
2. Open DevTools: Tap Settings > Developer > Web Inspector
3. Check Service Worker status

**Expected Results**:
- [ ] Service Worker shows "activated"
- [ ] Caches listed in Sources tab
- [ ] No errors in Console

**Verification**:
```javascript
navigator.serviceWorker.getRegistrations().then(regs => {
    regs.forEach(reg => console.log('SW:', reg.scope, reg.active ? 'active' : 'inactive'));
});
```

### Offline Access Test

**Procedure**:
1. App open and working (online)
2. Settings > Airplane Mode: ON
3. Return to app
4. Try to navigate

**Expected Results**:
- [ ] Page remains visible
- [ ] Previous data still displayed
- [ ] Network requests show "offline" in cache
- [ ] No page crashes
- [ ] "Offline" indicator appears (if implemented)

### Offline Data Caching

**Procedure**:
1. Load wallet page (online)
2. View balance
3. Enable Airplane Mode
4. Navigate to different page
5. Return to wallet

**Expected Results**:
- [ ] Balance still visible
- [ ] Transaction history cached
- [ ] Last known state restored
- [ ] "Last synced" timestamp shown

### Cache Size

**Procedure**:
1. Open browser console
2. Check storage usage

**Expected Results**:
```javascript
navigator.storage.estimate().then(estimate => {
    console.log(`Used: ${estimate.usage} bytes`);
    console.log(`Quota: ${estimate.quota} bytes`);
    console.log(`Usage %: ${(estimate.usage/estimate.quota*100).toFixed(2)}%`);
});
// Should be < 50MB for web app
```

## Test Case 4: Network Conditions

### Slow 3G Simulation

**Procedure**:
1. Connect to mobile network (or throttle with DevTools)
2. Load app
3. Measure load time

**Expected Results**:
- [ ] First paint < 3 seconds
- [ ] Interactive < 5 seconds
- [ ] No hung requests
- [ ] Responsive to user input

### Network Reconnection

**Procedure**:
1. Load app (online)
2. Disable WiFi + cellular
3. Observe offline state
4. Re-enable network
5. Check if data syncs

**Expected Results**:
- [ ] App detects network loss
- [ ] User informed of offline state
- [ ] Pending data queued
- [ ] Data syncs when reconnected
- [ ] No duplicate submissions

### Connection Interruption

**Procedure**:
1. Start transaction
2. Interrupt network mid-request
3. Re-establish connection

**Expected Results**:
- [ ] Request either completes or fails gracefully
- [ ] Error message clear
- [ ] Can retry manually
- [ ] No corrupted state

## Test Case 5: Gestures & Interactions

### Back Swipe Gesture

**Procedure**:
1. Navigate to wallet page
2. Perform swipe from left edge toward right
3. Verify back navigation

**Expected Results**:
- [ ] Back gesture recognized
- [ ] Previous page loads
- [ ] Smooth animation
- [ ] History maintained

**Note**: iOS controls swipe-back natively, but verify app doesn't interfere.

### Long Press Menu

**Procedure**:
1. Long press on transaction
2. Hold for 0.5+ seconds

**Expected Results**:
- [ ] Context menu appears (if implemented)
- [ ] Options visible (copy, share, etc.)
- [ ] No page selection
- [ ] Menu dismisses on tap away

### Double Tap Zoom (Disabled)

**Procedure**:
1. Double-tap on content
2. Attempt to zoom

**Expected Results**:
- [ ] No zoom occurs
- [ ] Double-tap doesn't trigger back
- [ ] User expects normal behavior

### Pinch Zoom

**Procedure**:
1. Pinch gesture (zoom out)
2. Pinch gesture (zoom in)

**Expected Results**:
- [ ] No zoom occurs (viewport-fit=cover prevents)
- [ ] Content stays same size
- [ ] Smooth interaction (no lag)

## Test Case 6: Touch Input & Keyboards

### Button Touch Targets

**Procedure**:
1. Identify all interactive elements
2. Test touch accuracy

**Expected Results**:
- [ ] All buttons minimum 44x44px
- [ ] Adequate spacing between targets
- [ ] No accidental taps on adjacent elements
- [ ] Consistent tap response

### Form Input - No Zoom

**Procedure**:
1. Tap on text input
2. Keyboard appears
3. Observe zoom level

**Expected Results**:
- [ ] Page does NOT zoom to input
- [ ] Input remains centered
- [ ] Keyboard doesn't cover critical buttons
- [ ] Can dismiss keyboard with return key

### Form Input - Proper Keyboard

**Procedure**:
1. Test different input types:
   - type="email" → Email keyboard
   - type="tel" → Phone keyboard
   - type="number" → Number pad
   - type="password" → Obscured keyboard

**Expected Results**:
- [ ] Correct keyboard type appears
- [ ] Autofill suggestions work
- [ ] Password autocomplete available
- [ ] No unwanted suggestions

### Textarea Scrolling

**Procedure**:
1. Focus textarea with long content
2. Scroll content
3. Type additional text

**Expected Results**:
- [ ] Content scrolls smoothly (-webkit-overflow-scrolling)
- [ ] No lag or jank
- [ ] New text appears at bottom

## Test Case 7: App Notifications

### Request Permission

**Procedure**:
1. Launch app
2. Grant notification permission when prompted

**Expected Results**:
- [ ] Permission dialog appears
- [ ] Clearly asks for permission
- [ ] Can grant or deny
- [ ] Settings show app has permission

### Send Notification

**Procedure**:
1. Trigger transaction
2. Notification should appear

**Expected Results**:
- [ ] Notification appears in Notification Center
- [ ] Shows custom icon
- [ ] Shows relevant message
- [ ] Tap opens app
- [ ] Badge updates on home screen (if applicable)

### Notification Sounds

**Procedure**:
1. Send notification while app in background
2. Listen for sound

**Expected Results**:
- [ ] Subtle notification sound (if enabled)
- [ ] Respects device sound settings
- [ ] Haptic feedback (if enabled)

## Test Case 8: Performance

### Startup Time

**Procedure**:
1. Force quit app
2. Tap to launch
3. Measure to interactive

**Expected Results**:
- [ ] First paint: < 1 second
- [ ] Interactive: < 3 seconds
- [ ] No blank screen
- [ ] Smooth animations

**Measurement** (DevTools):
```javascript
// Performance timing
console.log('Navigation Timing:');
performance.getEntriesByType('navigation').forEach(entry => {
    console.log(`Load: ${entry.loadEventEnd}ms`);
    console.log(`DOM: ${entry.domContentLoadedEventEnd}ms`);
});
```

### Memory Usage

**Procedure**:
1. Open app
2. Navigate multiple pages
3. Monitor memory

**Expected Results**:
- [ ] Initial load < 30MB
- [ ] Grows to < 50MB with usage
- [ ] Stays consistent
- [ ] No memory leaks

### Battery Impact

**Procedure**:
1. Use app for 1 hour
2. Check battery usage in Settings

**Expected Results**:
- [ ] No excessive battery drain
- [ ] Comparable to Safari usage
- [ ] No continuous background activity
- [ ] No unusual CPU usage

## Test Case 9: Security

### HTTPS Verification

**Procedure**:
1. Open app
2. Safari > Share > "More" > Check address bar

**Expected Results**:
- [ ] Shows "Secure" or lock icon
- [ ] No SSL certificate warnings
- [ ] Secure connection indicator present
- [ ] No mixed content warnings

### Content Security Policy

**Procedure**:
1. Open DevTools
2. Check network requests

**Expected Results**:
- [ ] All requests over HTTPS
- [ ] No external script execution
- [ ] No inline eval
- [ ] CSP violations logged (none should appear)

### Sensitive Data Handling

**Procedure**:
1. Enter sensitive data (private keys, passwords)
2. Close app
3. Open again

**Expected Results**:
- [ ] Data not logged in console
- [ ] Not visible in URL
- [ ] Not stored in localStorage (IndexedDB only)
- [ ] Cleared on logout

### XSS Protection

**Procedure**:
1. Try injecting HTML in forms:
   ```html
   <img src=x onerror="alert('XSS')">
   ```

**Expected Results**:
- [ ] No alert appears
- [ ] Content escaped safely
- [ ] HTML rendered as text
- [ ] CSP blocks inline scripts

## Test Case 10: Orientation Changes

### Portrait to Landscape

**Procedure**:
1. App in portrait
2. Rotate device to landscape
3. Observe layout change

**Expected Results**:
- [ ] Layout adjusts for landscape
- [ ] No content cut off
- [ ] Navigation accessible
- [ ] Safe areas respected

### Landscape to Portrait

**Procedure**:
1. App in landscape
2. Rotate device to portrait
3. Observe layout change

**Expected Results**:
- [ ] Layout returns to portrait
- [ ] Scroll position maintained
- [ ] No data loss
- [ ] Smooth transition

### Rapid Rotation

**Procedure**:
1. Rapidly rotate device multiple times
2. Perform action mid-rotation

**Expected Results**:
- [ ] No crashes
- [ ] Layout updates correctly
- [ ] No stuck elements
- [ ] Responsive to input

## Test Case 11: Updates

### Check for Updates

**Procedure**:
1. Leave app open for 1+ hour
2. Observe update notification (if available)

**Expected Results**:
- [ ] Service Worker checks for updates
- [ ] Notification appears (if update found)
- [ ] Can manually check for updates
- [ ] No forced reloads

### Install Update

**Procedure**:
1. Update available
2. Tap "Update" in notification
3. App reloads

**Expected Results**:
- [ ] App reloads with new version
- [ ] No data loss
- [ ] Seamless update
- [ ] Clear user feedback

## Test Case 12: Browser Compatibility

### Safari (Latest)

**iOS Versions to Test**:
- [ ] iOS 15
- [ ] iOS 16
- [ ] iOS 17
- [ ] iOS 18 (beta)

### Other Browsers (for comparison)

**Chrome for iOS**:
- [ ] Installs correctly
- [ ] Works offline
- [ ] Same features as Safari

**Firefox for iOS**:
- [ ] Basic functionality
- [ ] Performance acceptable

## Automated Testing Script

```bash
#!/bin/bash
# test-ios-pwa.sh

DOMAIN="https://moonbite.org"
USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"

echo "=== MoonBite iOS PWA Test Suite ==="

# 1. HTTPS Check
echo "[1] Checking HTTPS..."
curl -s -I $DOMAIN | grep -E "HTTP/|Strict-Transport"

# 2. Manifest Check
echo "[2] Checking manifest.json..."
curl -s $DOMAIN/static/manifest.json | jq '.name, .display, .start_url'

# 3. Service Worker Check
echo "[3] Checking service worker..."
curl -s -I $DOMAIN/static/service-worker.js | grep "Cache-Control"

# 4. Security Headers
echo "[4] Checking security headers..."
curl -s -I $DOMAIN | grep -E "X-Content-Type-Options|X-Frame-Options|CSP"

# 5. Performance
echo "[5] Checking performance..."
curl -s -w "\nTotal Time: %{time_total}s\nLoad Time: %{time_starttransfer}s\n" -o /dev/null $DOMAIN

# 6. Mobile Viewport
echo "[6] Checking viewport meta tag..."
curl -s $DOMAIN | grep 'viewport-fit=cover'

# 7. Apple Tags
echo "[7] Checking iOS meta tags..."
curl -s $DOMAIN | grep 'apple-mobile-web-app'

echo "=== Test Complete ==="
```

## Test Checklist

### Installation
- [ ] Add to Home Screen works
- [ ] Custom icon displays
- [ ] App name correct
- [ ] Splash screen appears

### Display
- [ ] Full screen mode (no Safari chrome)
- [ ] Status bar correct color
- [ ] Safe areas respected
- [ ] Notch handled properly
- [ ] Home indicator clear

### Offline
- [ ] Loads from cache
- [ ] Previous data visible
- [ ] Can navigate offline
- [ ] Syncs when reconnected

### Performance
- [ ] Startup < 3 seconds
- [ ] Smooth scrolling
- [ ] No jank or lag
- [ ] Responsive to touch

### Security
- [ ] HTTPS enforced
- [ ] No SSL warnings
- [ ] CSP headers present
- [ ] No XSS vulnerabilities

### Functionality
- [ ] All buttons work
- [ ] Forms responsive
- [ ] Network requests succeed
- [ ] Notifications work

### Devices Tested
- [ ] iPhone SE
- [ ] iPhone 11/12/13/14/15
- [ ] iPhone Pro Max
- [ ] iPad

## Known Issues & Limitations

### iOS Safari Limitations

1. **Fullscreen API**: Not supported
2. **WebRTC**: Limited support
3. **Background Sync**: Limited availability
4. **Push Notifications**: Only in standalone mode
5. **IndexedDB**: ~50MB limit

### Workarounds

```javascript
// Detect iOS limitations
const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent);
const isStandalone = window.navigator.standalone === true;

if (isIOS && !isStandalone) {
    console.warn('Some features limited in Safari browser mode');
    console.log('Add to home screen for full PWA experience');
}
```

## Test Results Template

```markdown
# iOS PWA Test Results
**Date**: 2024-XX-XX
**Tester**: [Name]
**Device**: iPhone/iPad [Model] [iOS Version]

## Installation
- [ ] Pass: Add to home screen
- [ ] Pass: Custom icon
- [ ] Pass: Splash screen

## Offline
- [ ] Pass: Loads offline
- [ ] Pass: Cache working

## Performance
- [ ] Pass: Startup time < 3s
- [ ] Pass: Smooth scrolling

## Issues Found
1. [Issue description]
   - Steps to reproduce
   - Expected vs actual
   - Severity: [Low/Medium/High]

## Recommendations
1. [Recommendation]
```

## Continuous Testing

```bash
# Setup GitHub Actions for automated testing
# .github/workflows/ios-test.yml

name: iOS PWA Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Test HTTPS
        run: curl -I https://moonbite.org
      - name: Test Manifest
        run: curl https://moonbite.org/static/manifest.json | jq .
      - name: Test Service Worker
        run: curl -I https://moonbite.org/static/service-worker.js
      - name: Test Security Headers
        run: |
          curl -I https://moonbite.org | grep "Strict-Transport-Security"
          curl -I https://moonbite.org | grep "X-Content-Type-Options"
```

## Resources

- [Apple PWA Documentation](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariWebContent/ConfiguringWebApplications/ConfiguringWebApplications.html)
- [MDN Web App Manifest](https://developer.mozilla.org/en-US/docs/Web/Manifest)
- [iOS Testing Guide](https://developer.apple.com/documentation/safari-release-notes)
- [WebKit Blog](https://webkit.org/blog/)
