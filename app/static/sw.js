// OmniDownloader PWA Service Worker
const CACHE_NAME = "omnidownloader-v3.3";

const SHELL_ASSETS = [
  "/",
  "/manifest.json",
  "/static/css/style.css",
  "/static/js/app.js",
  "/static/icons/favicon.svg",
  "/static/icons/icon.svg"
];

// Install: pre-cache shell assets for offline resilience
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(SHELL_ASSETS).catch((err) => {
        console.warn("Pre-cache non-fatal error:", err);
      });
    }).then(() => self.skipWaiting())
  );
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

// Offline Fallback HTML (Zinc/Obsidian + Emerald palette - strictly no purple/indigo)
const OFFLINE_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OmniDownloader - Connecting...</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #09090b;
      color: #f4f4f5;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 24px;
    }
    .card {
      background: #121215;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 16px;
      padding: 36px 32px;
      max-width: 480px;
      width: 100%;
      text-align: center;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
    }
    .pulse-icon {
      width: 56px;
      height: 56px;
      margin: 0 auto 20px;
      border-radius: 50%;
      background: rgba(16, 185, 129, 0.12);
      border: 2px solid #34d399;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 26px;
      animation: pulse 2s infinite ease-in-out;
    }
    @keyframes pulse {
      0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.4); }
      50% { transform: scale(1.05); box-shadow: 0 0 0 14px rgba(52, 211, 153, 0); }
    }
    h1 { font-size: 1.35rem; font-weight: 700; color: #f4f4f5; margin-bottom: 10px; }
    p { font-size: 0.9rem; color: #a1a1aa; line-height: 1.5; margin-bottom: 18px; }
    .status-box {
      background: #18181b;
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 8px;
      padding: 12px 14px;
      font-size: 0.82rem;
      color: #a1a1aa;
      font-family: monospace;
      margin-bottom: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #f59e0b;
      animation: blink 1s infinite alternate;
    }
    @keyframes blink { from { opacity: 0.3; } to { opacity: 1; } }
    .btn {
      background: #10b981;
      color: #09090b;
      font-weight: 600;
      font-size: 0.92rem;
      border: none;
      border-radius: 8px;
      padding: 12px 24px;
      cursor: pointer;
      transition: background 0.15s ease, transform 0.1s ease;
      width: 100%;
    }
    .btn:hover { background: #34d399; transform: translateY(-1px); }
    .btn:active { transform: translateY(0); }
    .hint { margin-top: 16px; font-size: 0.78rem; color: #71717a; }
    .hint code { background: #27272a; padding: 2px 6px; border-radius: 4px; color: #e4e4e7; font-family: monospace; }
  </style>
</head>
<body>
  <div class="card">
    <div class="pulse-icon">⚡</div>
    <h1>OmniDownloader Starting...</h1>
    <p>Waiting for the OmniDownloader local server to respond. This window will auto-reload the moment the server is ready.</p>
    <div class="status-box">
      <span class="dot"></span>
      <span id="stat">Connecting to http://localhost:8484...</span>
    </div>
    <button class="btn" onclick="retryNow()">Retry Now</button>
    <p class="hint">Ensure <code>start.bat</code> is running in the project folder.</p>
  </div>
  <script>
    async function checkServer() {
      try {
        const r = await fetch('/manifest.json', { cache: 'no-store' });
        if (r.ok) {
          window.location.reload();
        }
      } catch (e) {
        const stat = document.getElementById('stat');
        if (stat) stat.textContent = 'Server starting... auto-reconnecting';
      }
    }
    function retryNow() {
      const stat = document.getElementById('stat');
      if (stat) stat.textContent = 'Checking server connection...';
      fetch('/manifest.json', { cache: 'no-store' })
        .then(r => { if (r.ok) window.location.reload(); else throw new Error(); })
        .catch(() => { if (stat) stat.textContent = 'Server not responding yet. Ensure start.bat is running.'; });
    }
    setInterval(checkServer, 1500);
  </script>
</body>
</html>`;

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
    url.pathname.includes("/api/") ||
    url.pathname.includes("/stream") ||
    url.pathname.includes("/file/") ||
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
        // Network failed (server starting or offline)
        const cached = await caches.match(event.request);
        if (cached) {
          return cached;
        }

        // For navigation requests, fallback to cached index if present
        if (event.request.mode === "navigate") {
          const rootCached = await caches.match("/");
          if (rootCached) return rootCached;

          return new Response(OFFLINE_HTML, {
            status: 200,
            headers: new Headers({ "Content-Type": "text/html; charset=utf-8" })
          });
        }

        // Fallback for static assets
        return new Response("Offline", {
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
