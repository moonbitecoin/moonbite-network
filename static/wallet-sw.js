/* Bump on every wallet release: activate() deletes caches whose name does not
   match, so changing this string is what flushes stale assets from installed
   PWAs. */
const CACHE_VERSION = 'moonbite-wallet-v2';
const CACHE_URLS = [
  '/wallet',
  '/static/wallet-pwa.html',
  '/wallet-manifest.json',
  'https://moonbite.org/api/blockchain/info',
];

// Install event - cache essential files
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then(cache => {
      return cache.addAll(CACHE_URLS).catch(err => {
        console.log('Cache add failed:', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_VERSION) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // For API calls, try network first, fallback to cache
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Cache successful API responses
          if (response.ok) {
            const cache = caches.open(CACHE_VERSION);
            cache.then(c => c.put(request, response.clone()));
          }
          return response;
        })
        .catch(() => {
          // Return cached API response if network fails
          return caches.match(request).then(cached => {
            return cached || new Response(
              JSON.stringify({ error: 'offline' }),
              { headers: { 'Content-Type': 'application/json' }, status: 503 }
            );
          });
        })
    );
    return;
  }

  // Navigations and HTML: NETWORK FIRST.
  //
  // Cache-first here meant an installed wallet kept serving the first HTML it
  // ever cached, so no deploy - including a security fix - could ever reach
  // an existing user. Always try the network for the document and fall back to
  // cache only when genuinely offline, which keeps the PWA usable on a plane
  // without freezing its code forever.
  const wantsHTML = request.mode === 'navigate' ||
    (request.headers.get('accept') || '').includes('text/html');
  if (wantsHTML) {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_VERSION).then(cache => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => caches.match(request).then(
          cached => cached || caches.match('/wallet')
        ))
    );
    return;
  }

  // For static assets, use cache-first strategy
  event.respondWith(
    caches.match(request).then(cached => {
      return cached || fetch(request).then(response => {
        if (response.ok) {
          caches.open(CACHE_VERSION).then(cache => {
            cache.put(request, response.clone());
          });
        }
        return response;
      });
    })
  );
});

// Background sync for pending transactions
self.addEventListener('sync', event => {
  if (event.tag === 'sync-wallet') {
    event.waitUntil(syncWallet());
  }
});

async function syncWallet() {
  try {
    const pending = await getPendingTransactions();
    for (const tx of pending) {
      await submitTransaction(tx);
    }
  } catch (err) {
    console.error('Sync failed:', err);
  }
}

async function getPendingTransactions() {
  const db = await openDB();
  // Implementation would depend on IndexedDB setup
  return [];
}

async function submitTransaction(tx) {
  // Implementation for submitting pending transactions
  return true;
}

async function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('MoonBiteWallet', 1);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

// Message handler for client communication
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  if (event.data && event.data.type === 'GET_CACHE_STATUS') {
    caches.keys().then(cacheNames => {
      event.ports[0].postMessage({
        type: 'CACHE_STATUS',
        caches: cacheNames
      });
    });
  }
});

// Periodic background sync for wallet updates (if supported)
self.addEventListener('periodicsync', event => {
  if (event.tag === 'update-wallet') {
    event.waitUntil(updateWalletData());
  }
});

async function updateWalletData() {
  try {
    const response = await fetch('/api/blockchain/info');
    if (response.ok) {
      const clients = await self.clients.matchAll();
      clients.forEach(client => {
        client.postMessage({
          type: 'WALLET_UPDATE',
          data: response
        });
      });
    }
  } catch (err) {
    console.error('Wallet update failed:', err);
  }
}
