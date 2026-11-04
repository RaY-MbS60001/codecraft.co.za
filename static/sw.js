/* CodeCraft Co service worker.
   Strategy: cache-first for our own static assets (CSS/JS/fonts/images —
   versioned by CACHE_NAME, so a deploy just needs that bumped), network-first
   for everything else (HTML pages, API-ish routes) with a tiny offline
   fallback page so a flaky mobile connection doesn't show the browser's
   blank error screen. Never caches POSTs, auth/session-bearing redirects,
   or anything outside our own origin. */
const CACHE_NAME = "cc-static-v24";
const OFFLINE_URL = "/static/offline.html";
const PRECACHE = [
  "/static/v2/app.css",
  "/static/vendor/bootstrap/bootstrap.min.css",
  "/static/css/custom-loading.css",
  "/static/images/logos/icon-192.png",
  OFFLINE_URL,
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

function isStaticAsset(url) {
  return url.pathname.startsWith("/static/") &&
    /\.(css|js|png|jpg|jpeg|webp|svg|woff2?|ico)$/.test(url.pathname);
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (isStaticAsset(url)) {
    event.respondWith(
      caches.match(req).then((cached) => cached || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => cached))
    );
    return;
  }

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match(OFFLINE_URL))
    );
  }
});

/* Tapping a bulk-send progress/completion notification focuses an already
   open CodeCraft tab if there is one, otherwise opens My Applications. */
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          return client.focus();
        }
      }
      return self.clients.openWindow("/user/applications");
    })
  );
});
