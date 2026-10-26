import re
import urllib.parse
from typing import Dict, Any, List, Optional
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,video/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Mode": "navigate",
}

def scrape_webpage_media(url: str, timeout: int = 15) -> Dict[str, Any]:
    """
    Fallback generic scraper that deeply inspects any HTML page for direct
    video tags, source elements, OpenGraph metadata, and streaming manifests.
    """
    # If the URL is already a direct media file:
    parsed = urllib.parse.urlparse(url)
    clean_path = parsed.path.lower()
    if clean_path.endswith((".mp4", ".webm", ".mkv", ".mov", ".m3u8", ".mpd", ".flv", ".mp3", ".m4a")):
        filename = clean_path.split("/")[-1] or "media_stream"
        return {
            "title": filename,
            "url": url,
            "platform": "direct",
            "thumbnail": "",
            "duration": 0,
            "author": parsed.netloc,
            "sources": [{
                "url": url,
                "type": "video/mp4" if clean_path.endswith(".mp4") else "video/stream",
                "quality": "Direct Stream",
                "label": "Original Direct Link"
            }],
            "is_direct": True
        }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return {"error": f"Failed to fetch webpage: {str(e)}"}

    soup = BeautifulSoup(html, "html.parser")
    
    # Extract title
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
    if not title:
        title = parsed.netloc

    # Extract thumbnail / preview
    thumbnail = ""
    og_image = soup.find("meta", property="og:image") or soup.find("meta", property="twitter:image")
    if og_image and og_image.get("content"):
        thumbnail = urllib.parse.urljoin(url, og_image["content"])

    found_urls = set()
    sources: List[Dict[str, Any]] = []

    def add_source(src_url: str, mime: str = "video/mp4", label: str = "HTML5 Video"):
        abs_url = urllib.parse.urljoin(url, src_url.strip())
        if abs_url in found_urls:
            return
        # Basic sanity check
        if not abs_url.startswith(("http://", "https://")):
            return
        # Exclude common trackers or tiny icons
        if any(bad in abs_url.lower() for bad in ["doubleclick", "googleads", "analytics", "pixel"]):
            return
        found_urls.add(abs_url)
        sources.append({
            "url": abs_url,
            "type": mime,
            "label": label,
            "quality": "Extracted"
        })

    # 1. <video> tags
    for video in soup.find_all("video"):
        if video.get("src"):
            add_source(video["src"], "video/mp4", "HTML5 Video Tag")
        for source in video.find_all("source"):
            if source.get("src"):
                mime = source.get("type", "video/mp4")
                label = f"HTML5 Source ({mime.split('/')[-1]})"
                add_source(source["src"], mime, label)

    # 2. OpenGraph / Twitter meta video tags
    for prop in ["og:video", "og:video:url", "og:video:secure_url", "twitter:player:stream"]:
        meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if meta and meta.get("content"):
            add_source(meta["content"], "video/mp4", f"Meta {prop}")

    # 3. Regex scan for .m3u8, .mpd, .mp4 inside scripts and page text
    media_pattern = re.compile(r"""(?:href|src|source|url|file|stream)[\s:="']+([^"'\s<>]+\.(?:mp4|webm|m3u8|mpd)(?:\?[^"'\s<>]*)?)""", re.IGNORECASE)
    matches = media_pattern.findall(html)
    for m in matches[:15]:
        m_clean = m.replace('\\/', '/')
        label = "Stream Manifest (.m3u8)" if ".m3u8" in m_clean.lower() else "Embedded Media"
        mime = "application/x-mpegURL" if ".m3u8" in m_clean.lower() else "video/mp4"
        add_source(m_clean, mime, label)

    return {
        "title": title,
        "url": url,
        "platform": parsed.netloc,
        "thumbnail": thumbnail,
        "duration": 0,
        "author": parsed.netloc,
        "sources": sources,
        "is_direct": False,
        "found_count": len(sources)
    }
