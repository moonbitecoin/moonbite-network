/**
 * iOS PWA Initialization & Management
 * Handles service worker, manifest, gestures, and iOS-specific features
 */

class iOSPWAManager {
  constructor() {
    this.swRegistration = null;
    this.isStandalone = this.detectStandalone();
    this.isIOS = this.detectiOS();
    this.init();
  }

  /**
   * Detect if running as iOS standalone app
   */
  detectStandalone() {
    return (
      window.navigator.standalone === true ||
      window.matchMedia('(display-mode: standalone)').matches ||
      window.matchMedia('(display-mode: fullscreen)').matches
    );
  }

  /**
   * Detect iOS device
   */
  detectiOS() {
    return /iPhone|iPad|iPod/.test(navigator.userAgent);
  }

  /**
   * Initialize PWA features
   */
  async init() {
    console.log('[iOS PWA] Initializing...');

    // Apply iOS classes
    if (this.isIOS) {
      document.documentElement.classList.add('ios-device');
    }
    if (this.isStandalone) {
      document.documentElement.classList.add('ios-standalone');
    }

    // Register service worker
    await this.registerServiceWorker();

    // Setup viewport fixes
    this.setupViewportFixes();

    // Setup gesture handlers
    this.setupGestureHandlers();

    // Setup safe area observers
    this.setupSafeAreaObserver();

    // Setup app lifecycle handlers
    this.setupAppLifecycle();

    // Check for app updates
    this.setupUpdateChecker();

    console.log('[iOS PWA] Initialization complete');
  }

  /**
   * Register service worker with iOS support
   */
  async registerServiceWorker() {
    if (!('serviceWorker' in navigator)) {
      console.warn('[iOS PWA] Service Worker not supported');
      return;
    }

    try {
      // Register with updateViaCache disabled for iOS compatibility
      this.swRegistration = await navigator.serviceWorker.register(
        '/static/service-worker.js',
        {
          scope: '/',
          updateViaCache: 'none'
        }
      );

      console.log('[iOS PWA] Service Worker registered:', this.swRegistration.scope);

      // Handle controller change
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        console.log('[iOS PWA] Service Worker controller changed');
        this.notifyUpdateAvailable();
      });

      // Listen for messages from service worker
      navigator.serviceWorker.addEventListener('message', (event) => {
        this.handleServiceWorkerMessage(event.data);
      });

      // Check for updates periodically
      this.startUpdateCheck();
    } catch (err) {
      console.error('[iOS PWA] Service Worker registration failed:', err);
    }
  }

  /**
   * Handle messages from service worker
   */
  handleServiceWorkerMessage(data) {
    const { type, payload } = data;

    switch (type) {
      case 'WALLET_UPDATE':
        console.log('[iOS PWA] Wallet update received');
        this.dispatchEvent('wallet-update', payload);
        break;

      case 'TRANSACTION_SYNCED':
        console.log('[iOS PWA] Transaction synced:', payload.txId);
        this.dispatchEvent('transaction-synced', payload);
        break;

      case 'SYNC_COMPLETE':
        console.log('[iOS PWA] Sync complete');
        this.dispatchEvent('sync-complete', {});
        break;

      case 'UPDATE_AVAILABLE':
        console.log('[iOS PWA] Update available');
        this.notifyUpdateAvailable();
        break;
    }
  }

  /**
   * Start periodic update checks
   */
  startUpdateCheck() {
    if (!this.swRegistration) return;

    // Check every hour
    setInterval(() => {
      this.swRegistration.update().catch(err => {
        console.error('[iOS PWA] Update check failed:', err);
      });
    }, 3600000);

    // Also check on visibility change
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) {
        this.swRegistration.update();
      }
    });
  }

  /**
   * Setup viewport fixes for iOS
   */
  setupViewportFixes() {
    // Fix for iOS keyboard interaction
    const viewportMeta = document.querySelector('meta[name="viewport"]');
    if (viewportMeta) {
      viewportMeta.setAttribute(
        'content',
        'viewport-fit=cover, width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover'
      );
    }

    // Fix for iOS input zoom
    document.addEventListener('touchstart', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        // Allow zoom for form inputs
      }
    }, false);

    // Prevent zoom on double-tap
    let lastTouchEnd = 0;
    document.addEventListener('touchend', (e) => {
      const now = Date.now();
      if (now - lastTouchEnd <= 300) {
        e.preventDefault();
      }
      lastTouchEnd = now;
    }, false);
  }

  /**
   * Setup iOS gesture handlers
   */
  setupGestureHandlers() {
    // Swipe back gesture (iOS native behavior)
    this.setupSwipeBackGesture();

    // Long press handler
    this.setupLongPressHandler();

    // Haptic feedback (vibration)
    this.setupHapticFeedback();

    // Safe area adjustments on rotation
    this.setupOrientationHandler();
  }

  /**
   * Setup swipe back gesture detection
   */
  setupSwipeBackGesture() {
    let touchStartX = 0;
    let touchEndX = 0;

    document.addEventListener('touchstart', (e) => {
      touchStartX = e.changedTouches[0].screenX;
    }, false);

    document.addEventListener('touchend', (e) => {
      touchEndX = e.changedTouches[0].screenX;
      this.handleSwipe(touchStartX, touchEndX);
    }, false);
  }

  /**
   * Handle swipe gestures
   */
  handleSwipe(startX, endX) {
    const diff = endX - startX;
    const threshold = 50; // Minimum swipe distance

    // Swipe right (back gesture)
    if (diff > threshold && startX < 20) {
      console.log('[iOS PWA] Swipe back detected');
      this.dispatchEvent('gesture-back', {});
    }

    // Swipe left (forward gesture)
    if (diff < -threshold && startX > window.innerWidth - 20) {
      console.log('[iOS PWA] Swipe forward detected');
      this.dispatchEvent('gesture-forward', {});
    }
  }

  /**
   * Setup long press handler
   */
  setupLongPressHandler() {
    let longPressTimer;
    const longPressDuration = 500; // ms

    document.addEventListener('touchstart', (e) => {
      if (e.target.classList.contains('long-press-enabled')) {
        longPressTimer = setTimeout(() => {
          console.log('[iOS PWA] Long press detected');
          this.dispatchEvent('long-press', {
            target: e.target,
            x: e.touches[0].clientX,
            y: e.touches[0].clientY
          });
        }, longPressDuration);
      }
    }, false);

    document.addEventListener('touchend', () => {
      clearTimeout(longPressTimer);
    }, false);
  }

  /**
   * Setup haptic feedback (vibration)
   */
  setupHapticFeedback() {
    if (!('vibrate' in navigator)) {
      console.log('[iOS PWA] Haptic feedback not supported');
      return;
    }

    // Add haptic feedback to buttons
    document.addEventListener('click', (e) => {
      const button = e.target.closest('button, [role="button"]');
      if (button && button.classList.contains('haptic-enabled')) {
        // Light haptic feedback (20ms vibration)
        navigator.vibrate(20);
      }
    }, false);

    // Expose haptic methods
    window.haptic = {
      light: () => navigator.vibrate(20),
      medium: () => navigator.vibrate(40),
      heavy: () => navigator.vibrate(60),
      success: () => navigator.vibrate([30, 20, 30]),
      error: () => navigator.vibrate([100, 50, 100]),
      warning: () => navigator.vibrate([50, 50, 50])
    };
  }

  /**
   * Setup orientation change handler
   */
  setupOrientationHandler() {
    window.addEventListener('orientationchange', () => {
      console.log('[iOS PWA] Orientation changed:', screen.orientation.type);

      // Reapply safe area styling
      this.applySafeAreaStyling();

      // Dispatch custom event
      this.dispatchEvent('orientation-changed', {
        orientation: screen.orientation.type
      });
    });

    // Initial safe area styling
    this.applySafeAreaStyling();
  }

  /**
   * Apply safe area styling
   */
  applySafeAreaStyling() {
    const root = document.documentElement;

    // Update safe area CSS variables
    root.style.setProperty('--safe-area-inset-top', 'env(safe-area-inset-top)');
    root.style.setProperty('--safe-area-inset-right', 'env(safe-area-inset-right)');
    root.style.setProperty('--safe-area-inset-bottom', 'env(safe-area-inset-bottom)');
    root.style.setProperty('--safe-area-inset-left', 'env(safe-area-inset-left)');
  }

  /**
   * Setup safe area observer
   */
  setupSafeAreaObserver() {
    // Use ResizeObserver to detect safe area changes
    if ('ResizeObserver' in window) {
      const observer = new ResizeObserver(() => {
        this.applySafeAreaStyling();
      });

      observer.observe(document.documentElement);
    }
  }

  /**
   * Setup app lifecycle handlers
   */
  setupAppLifecycle() {
    // Handle app suspension (iOS goes background)
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        console.log('[iOS PWA] App suspended');
        this.dispatchEvent('app-suspend', {});
      } else {
        console.log('[iOS PWA] App resumed');
        this.dispatchEvent('app-resume', {});

        // Sync when app comes back to foreground
        this.syncWallet();
      }
    });

    // Handle page unload
    window.addEventListener('beforeunload', () => {
      console.log('[iOS PWA] Page unloading');
      this.dispatchEvent('app-unload', {});
    });
  }

  /**
   * Setup update checker
   */
  setupUpdateChecker() {
    // Check for updates when app becomes active
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && this.swRegistration) {
        this.swRegistration.update();
      }
    });
  }

  /**
   * Sync wallet data with service worker
   */
  async syncWallet() {
    if (!navigator.serviceWorker.controller) return;

    return new Promise((resolve) => {
      const channel = new MessageChannel();

      channel.port1.onmessage = (event) => {
        if (event.data.type === 'SYNC_COMPLETE') {
          console.log('[iOS PWA] Wallet sync complete');
          resolve();
        }
      };

      navigator.serviceWorker.controller.postMessage(
        { type: 'SYNC_WALLET' },
        [channel.port2]
      );
    });
  }

  /**
   * Check service worker version
   */
  async getServiceWorkerVersion() {
    if (!navigator.serviceWorker.controller) {
      return null;
    }

    return new Promise((resolve) => {
      const channel = new MessageChannel();

      channel.port1.onmessage = (event) => {
        if (event.data.type === 'VERSION') {
          resolve(event.data.version);
        }
      };

      navigator.serviceWorker.controller.postMessage(
        { type: 'GET_VERSION' },
        [channel.port2]
      );
    });
  }

  /**
   * Clear specific cache
   */
  async clearCache(cacheName) {
    if (!navigator.serviceWorker.controller) return;

    return new Promise((resolve) => {
      const channel = new MessageChannel();

      channel.port1.onmessage = (event) => {
        if (event.data.type === 'CACHE_CLEARED') {
          console.log('[iOS PWA] Cache cleared:', cacheName);
          resolve();
        }
      };

      navigator.serviceWorker.controller.postMessage(
        { type: 'CLEAR_CACHE', payload: { cacheName } },
        [channel.port2]
      );
    });
  }

  /**
   * Notify user of update availability
   */
  notifyUpdateAvailable() {
    console.log('[iOS PWA] Update available');

    // Dispatch event for app to handle
    this.dispatchEvent('update-available', {
      message: 'A new version is available. Reload to update.'
    });

    // Show native-like notification
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('MoonBite Updated', {
        body: 'A new version is available. Tap to reload.',
        tag: 'update-notification',
        requireInteraction: true
      });
    }
  }

  /**
   * Dispatch custom events
   */
  dispatchEvent(eventName, detail) {
    const event = new CustomEvent(eventName, { detail });
    window.dispatchEvent(event);
  }

  /**
   * Request notification permission
   */
  async requestNotificationPermission() {
    if (!('Notification' in window)) {
      console.log('[iOS PWA] Notifications not supported');
      return false;
    }

    if (Notification.permission === 'granted') {
      return true;
    }

    if (Notification.permission !== 'denied') {
      const permission = await Notification.requestPermission();
      return permission === 'granted';
    }

    return false;
  }

  /**
   * Show notification
   */
  async showNotification(title, options = {}) {
    if (!this.swRegistration) return;

    return this.swRegistration.showNotification(title, {
      icon: '/static/moonbite-logo.svg',
      badge: '/static/favicon.svg',
      ...options
    });
  }

  /**
   * Get app status
   */
  getStatus() {
    return {
      isStandalone: this.isStandalone,
      isIOS: this.isIOS,
      hasServiceWorker: !!this.swRegistration,
      displayMode: window.matchMedia('(display-mode: standalone)').matches ? 'standalone' : 'browser',
      userAgent: navigator.userAgent
    };
  }
}

// Initialize on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.iOSPWA = new iOSPWAManager();
  });
} else {
  window.iOSPWA = new iOSPWAManager();
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = iOSPWAManager;
}
