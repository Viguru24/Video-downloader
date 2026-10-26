const CACHE_NAME = "omnidownloader-v2.6";

// Install immediately
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

// Activate: delete ALL older caches immediately
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log("Removing old cache:", key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Network-First strategy for everything so updates are INSTANT
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Bypass cache completely for API calls, SSE streams, and media streaming
  if (url.pathname.startsWith("/api/") || event.request.headers.get("accept")?.includes("text/event-stream")) {
    return;
  }

  // Network First: Always try network to get freshest code, fallback to cache if offline
  event.respondWith(
    fetch(event.request).then((networkResponse) => {
      if (networkResponse && networkResponse.status === 200) {
        const copy = networkResponse.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
      }
      return networkResponse;
    }).catch(() => {
      return caches.match(event.request);
    })
  );
});

// Notifications
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      if (clientList.length > 0) {
        let client = clientList[0];
        for (let i = 0; i < clientList.length; i++) {
          if (clientList[i].focused) {
            client = clientList[i];
            break;
          }
        }
        return client.focus();
      }
      return clients.openWindow("/");
    })
  );
});
