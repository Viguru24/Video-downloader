// OmniDownloader PWA Service Worker
const CACHE_NAME = "omnidownloader-v3.2";

// Install immediately
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

// Activate: clean up ALL older caches immediately and claim clients
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

// Fetch event listener: Network-First with guaranteed valid Response
self.addEventListener("fetch", (event) => {
  // Only intercept GET requests
  if (event.request.method !== "GET") {
    return;
  }

  // Only handle HTTP/HTTPS schemes (ignore chrome-extension://, etc.)
  if (!event.request.url.startsWith("http")) {
    return;
  }

  const url = new URL(event.request.url);

  // Bypass cache completely for API calls, SSE streams, and media streaming
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/stream") ||
    event.request.headers.get("accept")?.includes("text/event-stream")
  ) {
    return;
  }

  // Network-First with guaranteed Response fallback
  event.respondWith(
    (async () => {
      try {
        const networkResponse = await fetch(event.request);
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === "basic") {
          const copy = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)).catch(() => {});
        }
        return networkResponse;
      } catch (err) {
        // Network failed (offline)
        const cached = await caches.match(event.request);
        if (cached) {
          return cached;
        }

        // For navigation requests, fallback to cached index if present
        if (event.request.mode === "navigate") {
          const rootCached = await caches.match("/");
          if (rootCached) return rootCached;
        }

        // Guaranteed Response object (prevents TypeError: Failed to convert value to 'Response')
        return new Response("OmniDownloader offline fallback", {
          status: 503,
          statusText: "Offline",
          headers: new Headers({ "Content-Type": "text/plain; charset=utf-8" })
        });
      }
    })()
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
