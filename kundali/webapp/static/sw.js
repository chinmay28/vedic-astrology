/* sw.js - app shell offline, API network-first with a stale fallback.
   Downloads (reports, exports) are never cached: they are large and
   always recomputed server-side. */
const SHELL = 'kundali-shell-v8';
const DATA = 'kundali-data-v2';
const ASSETS = ['/', '/app.css', '/app.js', '/icon.svg',
                '/manifest.webmanifest', '/dev-badge.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(ASSETS))
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((k) => k !== SHELL && k !== DATA).map((k) => caches.delete(k))
  )).then(() => self.clients.claim()));
});

/* Place search is live or not at all: a cached hit list for a query typed
   while offline would look like a working search and be a stale one. */
const NEVER_CACHE = /\/(report\.(pdf|html)|export\.json|positions\.csv|dasha\.csv)|\/api\/(export|import|geocode)/;

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin || NEVER_CACHE.test(url.pathname)) return;

  if (url.pathname.startsWith('/api/')) {
    e.respondWith(fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(DATA).then((c) => c.put(req, copy));
      return res;
    }).catch(() => caches.match(req).then((hit) => hit || new Response(
      JSON.stringify({ error: 'offline, and this view is not cached yet' }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }))));
    return;
  }

  e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
    const copy = res.clone();
    caches.open(SHELL).then((c) => c.put(req, copy));
    return res;
  })));
});
