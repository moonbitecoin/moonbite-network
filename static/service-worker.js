/**
 * MoonBite Service Worker
 * iOS & Android PWA Support with offline-first strategy
 * TLS 1.3 compliant, secure headers support
 */

const CACHE_VERSION = 'moonbite-v4-bulletproof-wallet';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const DYNAMIC_CACHE = `${CACHE_VERSION}-dynamic`;
const API_CACHE = `${CACHE_VERSION}-api`;
const IMAGE_CACHE = `${CACHE_VERSION}-images`;

// Critical static assets to cache on install
const CRITICAL_ASSETS = [
  '/',
  '/wallet',
  '/index.html',
  '/wallet.html',
  '/static/manifest.json',
  '/static/style.css',
  '/static/site.css',
  '/static/wallet-security.js',
  '/static/moonbite-logo.svg'
];

// Install Event - Precache critical assets
self.addEventListener('install', event => {
  console.log('[SW] Installing service worker v' + CACHE_VERSION);

  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        console.log('[SW] Caching critical assets');
        return cache.addAll(CRITICAL_ASSETS).catch(err => {
          console.warn('[SW] Some critical assets failed to cache:', err);
          // Don't fail install if some assets unavailable
        });
      })
      .then(() => self.skipWaiting())
  );
});

// Activate Event - Clean up old caches
self.addEventListener('activate', event => {
  console.log('[SW] Activating service worker');

  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => !name.startsWith(CACHE_VERSION))
          .map(name => {
            console.log('[SW] Deleting old cache:', name);
            return caches.delete(name);
          })
      );
    })
      .then(() => self.clients.claim())
  );
});

// Fetch Event - Smart caching strategy
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip cross-origin requests and non-GET requests
  if (!url.origin.includes(self.location.origin) || request.method !== 'GET') {
    return;
  }

  // API requests: Network-first with fallback to cache
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstStrategy(request, API_CACHE));
    return;
  }

  // Images: Cache-first with network fallback
  if (request.destination === 'image') {
    event.respondWith(cacheFirstStrategy(request, IMAGE_CACHE));
    return;
  }

  // HTML: Network-first for dynamic content
  if (request.destination === 'document') {
    event.respondWith(networkFirstStrategy(request, DYNAMIC_CACHE, 5000));
    return;
  }

  // CSS, JS, fonts: Cache-first (versioned)
  if (['style', 'script', 'font'].includes(request.destination)) {
    event.respondWith(cacheFirstStrategy(request, STATIC_CACHE));
    return;
  }

  // Default: Stale-while-revalidate
  event.respondWith(staleWhileRevalidateStrategy(request, DYNAMIC_CACHE));
});

/**
 * Cache-first strategy: Use cache, fallback to network
 */
function cacheFirstStrategy(request, cacheName) {
  return caches.match(request)
    .then(cached => {
      if (cached) {
        return cached;
      }

      return fetch(request)
        .then(response => {
          // Only cache successful responses
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(cacheName).then(cache => {
              cache.put(request, clone);
            });
          }
          return response;
        })
        .catch(() => {
          // Return offline response for specific content types
          if (request.destination === 'image') {
            return caches.match('/static/offline-image.svg');
          }
          return new Response('Offline - resource unavailable', {
            status: 503,
            statusText: 'Service Unavailable',
            headers: new Headers({ 'Content-Type': 'text/plain' })
          });
        });
    });
}

/**
 * Network-first strategy: Try network, fallback to cache
 */
function networkFirstStrategy(request, cacheName, timeout = 5000) {
  return new Promise((resolve, reject) => {
    let timeoutId;

    // Set timeout for network request
    timeoutId = setTimeout(() => {
      console.log('[SW] Network timeout, trying cache for:', request.url);
      caches.match(request)
        .then(cached => {
          if (cached) {
            resolve(cached);
          } else {
            resolve(new Response(
              JSON.stringify({ error: 'Offline and no cached response' }),
              {
                status: 503,
                statusText: 'Service Unavailable',
                headers: new Headers({ 'Content-Type': 'application/json' })
              }
            ));
          }
        })
        .catch(reject);
    }, timeout);

    // Try network first
    fetch(request)
      .then(response => {
        clearTimeout(timeoutId);

        // Cache successful responses
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(cacheName).then(cache => {
            cache.put(request, clone);
          });
        }

        resolve(response);
      })
      .catch(() => {
        clearTimeout(timeoutId);
        // Network failed, try cache
        caches.match(request)
          .then(cached => {
            if (cached) {
              resolve(cached);
            } else {
              resolve(new Response(
                JSON.stringify({ error: 'Network error and no cached response' }),
                {
                  status: 503,
                  statusText: 'Service Unavailable',
                  headers: new Headers({ 'Content-Type': 'application/json' })
                }
              ));
            }
          })
          .catch(reject);
      });
  });
}

/**
 * Stale-while-revalidate: Serve cache immediately, update in background
 */
function staleWhileRevalidateStrategy(request, cacheName) {
  return caches.match(request)
    .then(cached => {
      const fetchPromise = fetch(request)
        .then(response => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(cacheName).then(cache => {
              cache.put(request, clone);
            });
          }
          return response;
        })
        .catch(() => {
          // Network failed, return cached or error
          if (cached) {
            return cached;
          }
          return new Response('Offline and no cached response', {
            status: 503,
            statusText: 'Service Unavailable'
          });
        });

      return cached || fetchPromise;
    });
}

// Background Sync for pending transactions
self.addEventListener('sync', event => {
  console.log('[SW] Background sync triggered:', event.tag);

  if (event.tag === 'sync-transactions') {
    event.waitUntil(syncPendingTransactions());
  }

  if (event.tag === 'sync-wallet') {
    event.waitUntil(syncWalletData());
  }
});

async function syncPendingTransactions() {
  try {
    const db = await openDB();
    const pending = await getPendingTransactions(db);

    console.log('[SW] Syncing ' + pending.length + ' pending transactions');

    for (const tx of pending) {
      try {
        const response = await fetch('/api/wallet/submit-tx', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(tx)
        });

        if (response.ok) {
          await markTransactionSynced(db, tx.id);
          notifyClients({
            type: 'TRANSACTION_SYNCED',
            txId: tx.id,
            status: 'success'
          });
        }
      } catch (err) {
        console.error('[SW] Failed to sync transaction:', tx.id, err);
      }
    }
  } catch (err) {
    console.error('[SW] Sync error:', err);
    throw err;
  }
}

async function syncWalletData() {
  try {
    const response = await fetch('/api/wallet/info');

    if (response.ok) {
      const data = await response.json();

      // Store in cache for offline access
      const cache = await caches.open(API_CACHE);
      cache.put('/api/wallet/info', response.clone());

      // Notify clients of update
      notifyClients({
        type: 'WALLET_SYNCED',
        data: data,
        timestamp: Date.now()
      });
    }
  } catch (err) {
    console.error('[SW] Wallet sync failed:', err);
  }
}

// Periodic Background Sync (if supported)
self.addEventListener('periodicsync', event => {
  console.log('[SW] Periodic sync triggered:', event.tag);

  if (event.tag === 'update-wallet') {
    event.waitUntil(syncWalletData());
  }
});

// Message handling from clients
self.addEventListener('message', event => {
  console.log('[SW] Message received:', event.data);

  const { type, payload } = event.data;

  switch (type) {
    case 'SKIP_WAITING':
      self.skipWaiting();
      break;

    case 'GET_VERSION':
      event.ports[0].postMessage({
        type: 'VERSION',
        version: CACHE_VERSION
      });
      break;

    case 'CACHE_STATUS':
      caches.keys().then(cacheNames => {
        event.ports[0].postMessage({
          type: 'CACHE_STATUS',
          caches: cacheNames,
          timestamp: Date.now()
        });
      });
      break;

    case 'CLEAR_CACHE':
      caches.delete(payload.cacheName).then(() => {
        event.ports[0].postMessage({
          type: 'CACHE_CLEARED',
          cacheName: payload.cacheName
        });
      });
      break;

    case 'SYNC_WALLET':
      event.waitUntil(
        syncWalletData().then(() => {
          event.ports[0].postMessage({
            type: 'SYNC_COMPLETE',
            success: true
          });
        })
      );
      break;
  }
});

// Utility: Notify all clients
function notifyClients(message) {
  self.clients.matchAll().then(clients => {
    clients.forEach(client => {
      client.postMessage(message);
    });
  });
}

// IndexedDB helpers
function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('MoonBiteWallet', 1);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = event => {
      const db = event.target.result;

      if (!db.objectStoreNames.contains('transactions')) {
        const txStore = db.createObjectStore('transactions', { keyPath: 'id' });
        txStore.createIndex('status', 'status', { unique: false });
        txStore.createIndex('timestamp', 'timestamp', { unique: false });
      }
    };
  });
}

async function getPendingTransactions(db) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('transactions', 'readonly');
    const store = transaction.objectStore('transactions');
    const index = store.index('status');
    const range = IDBKeyRange.only('pending');
    const request = index.getAll(range);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

async function markTransactionSynced(db, txId) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('transactions', 'readwrite');
    const store = transaction.objectStore('transactions');
    const request = store.get(txId);

    request.onsuccess = () => {
      const tx = request.result;
      if (tx) {
        tx.status = 'synced';
        const updateRequest = store.put(tx);
        updateRequest.onerror = () => reject(updateRequest.error);
        updateRequest.onsuccess = () => resolve();
      }
    };

    request.onerror = () => reject(request.error);
  });
}

// Log service worker state
console.log('[SW] Service Worker loaded and ready');
