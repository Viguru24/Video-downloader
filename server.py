import os
import sys
import socket

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import uvicorn

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def print_banner(port: int):
    local_ip = get_local_ip()
    print("=" * 64)
    print("  * OmniDownloader - Universal Video PWA")
    print("  * Premium Glassmorphic Progressive Web App")
    print("=" * 64)
    print(f"  -> Local PWA Access:   http://localhost:{port}")
    print(f"  -> Network / Mobile:   http://{local_ip}:{port}")
    print(f"  -> Downloads Folder:   {os.path.abspath('downloads')}")
    print("=" * 64)
    print("  Tip: In Chrome/Edge, click the 'Install App' icon in the URL bar")
    print("  or on the page to install as a standalone desktop app!")
    print("=" * 64)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8484))
    print_banner(port)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
