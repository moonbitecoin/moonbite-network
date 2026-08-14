// MoonBite Wallet Service Worker
const CACHE_NAME = 'moonbite-wallet-v1';
const OFFLINE_URL = '/wallet-app';

const STATIC_ASSETS = [
  '/wallet-app',
  '/wallet-manifest.json',
  '/static/site.css',
  '/static/site.js'
];

// Install event - cache essential assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch(() => {
        console.log('Some assets failed to cache during install');
      });
    })
  );
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  // Only handle GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // Skip chrome extensions and other schemes
  if (event.request.url.includes('chrome-extension://')) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((response) => {
      // Return cached response if available
      if (response) {
        return response;
      }

      // Try to fetch from network
      return fetch(event.request).then((response) => {
        // Don't cache non-successful responses
        if (!response || response.status !== 200 || response.type === 'error') {
          return response;
        }

        // Cache successful responses
        const responseToCache = response.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseToCache).catch(() => {});
        });

        return response;
      }).catch(() => {
        // Offline fallback - return cached main page
        return caches.match(OFFLINE_URL).then((response) => {
          return response || new Response('Offline - App not available', {
            status: 503,
            statusText: 'Service Unavailable',
            headers: new Headers({
              'Content-Type': 'text/plain'
            })
          });
        });
      });
    })
  );
});

// Handle messages from clients
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

// Background sync for transactions (when network returns)
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-transactions') {
    event.waitUntil(
      // This would sync pending transactions when network is available
      Promise.resolve()
    );
  }
});

// Push notifications for MBITE alerts
self.addEventListener('push', (event) => {
  const options = {
    body: event.data ? event.data.text() : 'MoonBite Notification',
    icon: '/moonbite-icon-192x192.svg',
    badge: '/moonbite-badge-72x72.svg',
    tag: 'moonbite-notification',
    requireInteraction: false
  };

  event.waitUntil(
    self.registration.showNotification('MoonBite Wallet', options)
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Check if wallet app is already open
      for (const client of clientList) {
        if (client.url === '/wallet-app' && 'focus' in client) {
          return client.focus();
        }
      }
      // If not open, open new window
      if (clients.openWindow) {
        return clients.openWindow('/wallet-app');
      }
    })
  );
});
