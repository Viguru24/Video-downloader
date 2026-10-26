# 🌌 OmniDownloader — Universal Video & Audio Studio PWA

> **A high-performance, glassmorphic Progressive Web App (PWA) designed to download any video from any website in ultra-high resolution (4K, 1080p 60fps, MP3 320kbps) with real-time FFmpeg processing, background sync, and offline playback.**

---

## ✨ Features & Architecture

### 1. 🌐 Truly Universal Video Extraction
- **Platform Extractors**: Built on `yt-dlp` supporting 1,000+ top platforms:
  - **YouTube**: 4K UHD, 1080p 60fps, Playlists, Shorts, Live VODs
  - **TikTok**: HD watermark-free downloads
  - **X / Twitter**: Full resolution video extraction & animated GIFs
  - **Instagram**: Reels, Stories, Posts, and IGTV
  - **Reddit**: Merged HD video and audio tracks
  - **Facebook, Vimeo, Twitch, Rumble, Dailymotion, Bilibili**, and more.
- **Deep HTML5 Sniffer & Stream Fallback**:
  - Automatically inspects custom websites, news portals, and blogs for `<video>`, `<source>`, OpenGraph tags, `.m3u8` HLS manifests, and direct MP4/WebM files.

### 2. ⚡ Real-Time Streaming & FFmpeg Muxing
- **Server-Sent Events (SSE)**: Live download speeds (MB/s), remaining ETA, downloaded bytes, and progress percentages streamed directly to the browser UI.
- **FFmpeg Muxing Engine**: Automatically downloads separate high-res video (VP9/AV1/H.264) and audio (Opus/AAC) tracks and packages them into crisp MP4 or audio-only MP3/FLAC/M4A.

### 3. 📱 Progressive Web App (PWA) Standard
- **Installable**: Full Web App Manifest with desktop and mobile standalone display modes.
- **Offline Shell**: Service Worker caches UI assets, icons, and fonts for immediate launch.
- **Native Share Target**: When browsing on mobile, tap "Share" from YouTube, Twitter, or browser, and select **OmniDownloader** to auto-fill the URL!
- **1-Click Magic Bookmarklet**: Drag the bookmarklet into your browser's bookmarks bar to download the video on any page you're watching with a single click.

### 4. 🎨 Cyber-Luxe Glassmorphic Interface
- Obsidian and deep sapphire backdrop with ambient animated radial light beams.
- Frosted acrylic blur cards (`backdrop-filter: blur(24px)`).
- Synthesized Web Audio API tactile acoustic clicks and completion chimes.
- In-app custom media player modal with Picture-in-Picture (PiP) and speed controls.
- Searchable local library with Windows Explorer integration (`📂 Folder`).
- Batch queue processor for multiple URLs or playlists.

---

## 🚀 Quick Start (Local-First)

### Prerequisites
- **Python 3.10+** (Python 3.12 verified)
- **FFmpeg** (installed and in PATH)

### 1. Launch with PowerShell
```powershell
.\start.ps1
```

### 2. Or Launch with Python
```powershell
python server.py
```

Open your browser to:
```
http://localhost:8484
```

Click **"Install App"** in the top bar or browser URL bar to install OmniDownloader directly to your Windows desktop or mobile home screen!

---

## 📂 Project Structure

```
├── app/
│   ├── engine/
│   │   ├── generic_scraper.py   # Fallback HTML5, m3u8, and OpenGraph scraper
│   │   ├── storage.py           # SQLite database tracking downloads & library
│   │   └── ytdl_engine.py       # yt-dlp & FFmpeg processing with live progress hooks
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css        # Glassmorphic cyber-luxe styling & animations
│   │   ├── icons/
│   │   │   ├── icon-192.png     # PWA icon
│   │   │   ├── icon-512.png     # PWA icon (maskable)
│   │   │   ├── icon.svg         # Crisp vector brand icon
│   │   │   └── favicon.svg      # Favicon
│   │   ├── js/
│   │   │   └── app.js           # Client controller, SSE, clipboard, PWA logic
│   │   ├── index.html           # Dynamic PWA Shell
│   │   ├── manifest.json        # Web App Manifest
│   │   └── sw.js                # Service Worker
│   └── main.py                  # FastAPI REST & SSE API application
├── downloads/                   # Downloaded media storage folder
├── requirements.txt             # Dependencies
├── server.py                    # Root entrypoint
├── start.ps1                    # One-click Windows launch script
└── README.md
```

---

## 🔒 Privacy & Local-First Philosophy
- All files are downloaded and processed entirely locally on your machine.
- No third-party data tracking, advertising networks, or external telemetry.
- Direct downloads can be triggered to your browser's default `Downloads` folder or saved to the server's local media library.
