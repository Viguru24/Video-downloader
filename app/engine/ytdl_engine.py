import os
import re
import time
import uuid
import threading
from typing import Dict, Any, Optional, List
import requests
import yt_dlp
from yt_dlp.extractor.beeg import BeegIE

from .storage import add_download, update_download
from .generic_scraper import scrape_webpage_media

# Global task state tracker
DOWNLOAD_TASKS: Dict[str, Dict[str, Any]] = {}
CANCEL_FLAGS: Dict[str, bool] = {}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def patch_beeg_extractor():
    """
    Monkey-patches yt-dlp's BeegIE extractor to fix:
    1. HTTP 400 Bad Request caused by leading zeroes in video IDs (e.g. 0474481513382690).
    2. Missing 'hls_resources' in facts/file/{id} JSON metadata by querying the live
       stream path endpoint at https://store.externulls.com/video/play_url/{id}.
    """
    def custom_real_extract(self, url):
        raw_id = self._match_id(url)
        # Strip leading zeros so store.externulls.com API doesn't 400 Bad Request
        video_id = str(int(raw_id)) if raw_id.isdigit() else raw_id
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'Referer': 'https://beeg.com/',
            'Accept': '*/*'
        }
        
        # 1. Fetch metadata
        title = 'Video'
        duration = 0
        tags = []
        try:
            meta_res = requests.get(f'https://store.externulls.com/facts/file/{video_id}', headers=headers, timeout=10).json()
            file_obj = meta_res.get('file', {})
            data_list = file_obj.get('data', [])
            if data_list and isinstance(data_list, list):
                title = data_list[0].get('cd_value', title)
            duration = file_obj.get('fl_duration', 0)
            tags = [t.get('tg_name') for t in meta_res.get('tags', []) if isinstance(t, dict) and t.get('tg_name')]
        except Exception:
            pass

        # 2. Fetch live play_url
        play_res = requests.get(f'https://store.externulls.com/video/play_url/{video_id}', headers=headers, timeout=10)
        if play_res.status_code != 200:
            raise Exception(f'Failed to get stream url from beeg (HTTP {play_res.status_code})')
        
        play_path = play_res.text.strip()
        m3u8_url = f'https://video.beeg.com/{play_path}'
        
        formats = self._extract_m3u8_formats(m3u8_url, video_id, ext='mp4', m3u8_id='hls')
        
        return {
            'id': video_id,
            'title': title,
            'duration': duration,
            'tags': tags,
            'formats': formats,
        }

    BeegIE._real_extract = custom_real_extract

# Apply patch at startup
try:
    patch_beeg_extractor()
except Exception as e:
    print(f"Warning: Beeg extractor patch failed: {e}")

def normalize_url(url: str) -> str:
    url = url.strip()
    # Normalize Beeg URL leading zeroes: e.g. /0474481513382690 -> /474481513382690
    if "beeg.com" in url.lower():
        url = re.sub(r'(beeg\.com(?:/video)?/-?)0+(\d+)', r'\g<1>\2', url)
    return url

def format_bytes(size: Optional[int]) -> str:
    if not size or size <= 0:
        return "Unknown size"
    power = 2**10
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size > power and n < 4:
        size /= power
        n += 1
    return f"{size:.1f} {power_labels[n]}"

def format_seconds(seconds: Optional[int]) -> str:
    if not seconds:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def detect_platform(url: str) -> str:
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "YouTube"
    if "tiktok.com" in u:
        return "TikTok"
    if "twitter.com" in u or "x.com" in u:
        return "X (Twitter)"
    if "instagram.com" in u:
        return "Instagram"
    if "reddit.com" in u:
        return "Reddit"
    if "facebook.com" in u or "fb.watch" in u:
        return "Facebook"
    if "vimeo.com" in u:
        return "Vimeo"
    if "twitch.tv" in u:
        return "Twitch"
    if "beeg.com" in u:
        return "Beeg"
    if "dailymotion.com" in u:
        return "Dailymotion"
    if "bilibili.com" in u:
        return "Bilibili"
    if "rumble.com" in u:
        return "Rumble"
    return "Web Media"

def inspect_media(url: str) -> Dict[str, Any]:
    """
    Inspects media URL using yt-dlp first; falls back to generic HTML5 scraping
    if yt-dlp does not support the URL.
    """
    url = normalize_url(url)
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
        'noplaylist': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as ydl_err:
        # Fallback to generic HTML5 scraper
        fallback = scrape_webpage_media(url)
        if "error" not in fallback and fallback.get("sources"):
            return {
                "success": True,
                "engine": "generic",
                "platform": fallback.get("platform", "Generic Web"),
                "title": fallback.get("title", "Discovered Video Stream"),
                "thumbnail": fallback.get("thumbnail", ""),
                "duration": 0,
                "duration_str": "Direct Stream",
                "author": fallback.get("author", "Webpage Media"),
                "url": url,
                "qualities": [
                    {"id": "best", "label": "Original Quality (MP4)", "height": 1080, "ext": "mp4", "filesize_str": "Source"}
                ],
                "audio_qualities": [
                    {"id": "bestaudio", "label": "Extract Audio (MP3 320kbps)", "ext": "mp3"}
                ],
                "raw_sources": fallback.get("sources", []),
                "is_generic": True
            }
        return {
            "success": False,
            "error": f"Could not extract video stream: {str(ydl_err)}"
        }

    if not info:
        return {"success": False, "error": "No media found at this URL."}

    # Handle playlist preview if multi-entry
    if "entries" in info and info["entries"]:
        first = info["entries"][0]
        entries_count = len(list(info["entries"]))
        return {
            "success": True,
            "is_playlist": True,
            "playlist_count": entries_count,
            "title": info.get("title", "Video Playlist"),
            "platform": detect_platform(url),
            "thumbnail": first.get("thumbnail") or info.get("thumbnail", ""),
            "duration": 0,
            "duration_str": f"{entries_count} videos",
            "author": info.get("uploader", "Various"),
            "url": url,
            "qualities": [
                {"id": "best", "label": "Best Available (All)", "height": 1080, "ext": "mp4"},
                {"id": "720", "label": "720p HD", "height": 720, "ext": "mp4"},
                {"id": "480", "label": "480p SD", "height": 480, "ext": "mp4"}
            ],
            "audio_qualities": [
                {"id": "mp3", "label": "Extract All to MP3 (320kbps)", "ext": "mp3"}
            ]
        }

    title = info.get("title", "Video")
    duration = info.get("duration", 0)
    thumbnail = info.get("thumbnail", "")
    author = info.get("uploader") or info.get("channel") or info.get("creator", "Unknown")
    platform = detect_platform(url)

    # Process formats
    formats = info.get("formats", [])
    qualities_list = []

    # Priority resolutions
    preset_heights = [2160, 1440, 1080, 720, 480, 360]
    height_labels = {
        2160: "4K Ultra HD (2160p)",
        1440: "2K Quad HD (1440p)",
        1080: "Full HD (1080p 60fps)",
        720: "HD (720p)",
        480: "Standard (480p)",
        360: "Mobile (360p)"
    }

    found_heights = set()
    for f in formats:
        h = f.get("height")
        if h and f.get("vcodec") != "none":
            found_heights.add(h)

    # Add best available
    qualities_list.append({
        "id": "best",
        "label": "Best Available (Maximum Quality)",
        "height": max(found_heights) if found_heights else 1080,
        "ext": "mp4",
        "badge": "Recommended",
        "filesize_str": format_bytes(info.get("filesize") or info.get("filesize_approx"))
    })

    for ph in preset_heights:
        # Check if video supports this or greater height
        matches = [h for h in found_heights if h >= ph - 40 and h <= ph + 40]
        if matches:
            qualities_list.append({
                "id": f"res_{ph}",
                "label": height_labels.get(ph, f"{ph}p"),
                "height": ph,
                "ext": "mp4",
                "format_selector": f"bestvideo[height<={ph}]+bestaudio/best[height<={ph}]"
            })

    audio_qualities = [
        {"id": "mp3_320", "label": "MP3 Audio (320 kbps Studio)", "ext": "mp3", "bitrate": "320"},
        {"id": "mp3_192", "label": "MP3 Audio (192 kbps High)", "ext": "mp3", "bitrate": "192"},
        {"id": "m4a", "label": "M4A AAC (High Definition)", "ext": "m4a"},
        {"id": "flac", "label": "FLAC (Lossless Master)", "ext": "flac"},
        {"id": "wav", "label": "WAV (Uncompressed)", "ext": "wav"}
    ]

    return {
        "success": True,
        "title": title,
        "url": url,
        "platform": platform,
        "thumbnail": thumbnail,
        "duration": duration,
        "duration_str": format_seconds(duration),
        "author": author,
        "views": info.get("view_count", 0),
        "qualities": qualities_list,
        "audio_qualities": audio_qualities,
        "is_playlist": False,
        "is_generic": False
    }

def get_progress_hook(task_id: str):
    def hook(d):
        if CANCEL_FLAGS.get(task_id):
            raise Exception("Download cancelled by user")

        status = d.get("status")
        task = DOWNLOAD_TASKS.get(task_id, {})

        if status == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            percent = (downloaded / total * 100) if total > 0 else 0
            speed = d.get("speed", 0)
            eta = d.get("eta", 0)

            speed_str = f"{format_bytes(speed)}/s" if speed else "Calculating..."
            eta_str = f"{eta}s remaining" if eta else ""

            task.update({
                "status": "downloading",
                "percent": round(percent, 1),
                "downloaded_bytes": downloaded,
                "total_bytes": total,
                "speed_str": speed_str,
                "eta_str": eta_str,
                "stage": "Downloading video stream..."
            })
        elif status == "finished":
            task.update({
                "status": "processing",
                "percent": 99.0,
                "stage": "Muxing and finalising media with FFmpeg..."
            })
        DOWNLOAD_TASKS[task_id] = task

    return hook

def execute_download(task_id: str, url: str, options: Dict[str, Any], output_dir: str = DOWNLOADS_DIR) -> Dict[str, Any]:
    url = normalize_url(url)
    task = {
        "id": task_id,
        "url": url,
        "status": "starting",
        "percent": 0.0,
        "speed_str": "Starting...",
        "eta_str": "",
        "stage": "Preparing download pipeline...",
        "filepath": None,
        "filename": None,
        "error": None,
        "start_time": time.time()
    }
    DOWNLOAD_TASKS[task_id] = task
    CANCEL_FLAGS[task_id] = False

    quality_id = options.get("quality_id", "best")
    is_audio_only = options.get("audio_only", False)
    audio_format = options.get("audio_format", "mp3")
    embed_thumbnail = options.get("embed_thumbnail", True)

    out_template = os.path.join(output_dir, "%(title).200B [%(id)s].%(ext)s")

    ydl_opts: Dict[str, Any] = {
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [get_progress_hook(task_id)],
    }

    if is_audio_only:
        ydl_opts["format"] = "bestaudio/best"
        postprocessors = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_format,
            "preferredquality": "320" if audio_format == "mp3" else "0",
        }]
        if embed_thumbnail:
            ydl_opts["writethumbnail"] = True
            postprocessors.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
            postprocessors.append({"key": "EmbedThumbnail"})
        ydl_opts["postprocessors"] = postprocessors
    else:
        # Video + Audio
        if quality_id == "best":
            ydl_opts["format"] = "bestvideo+bestaudio/best"
        elif quality_id.startswith("res_"):
            height = quality_id.replace("res_", "")
            ydl_opts["format"] = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
        else:
            ydl_opts["format"] = "bestvideo+bestaudio/best"

        ydl_opts["merge_output_format"] = "mp4"
        postprocessors = []
        if embed_thumbnail:
            ydl_opts["writethumbnail"] = True
            postprocessors.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
            postprocessors.append({"key": "EmbedThumbnail"})
        ydl_opts["postprocessors"] = postprocessors

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            meta = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(meta)
            
            # Postprocessor changes extension
            if is_audio_only:
                base, _ = os.path.splitext(filename)
                final_path = f"{base}.{audio_format}"
            else:
                base, _ = os.path.splitext(filename)
                final_path = f"{base}.mp4"
                if not os.path.exists(final_path) and os.path.exists(filename):
                    final_path = filename

            final_filename = os.path.basename(final_path)
            filesize = os.path.getsize(final_path) if os.path.exists(final_path) else 0

            # Store in database
            db_record = {
                "id": task_id,
                "url": url,
                "title": meta.get("title", "Video"),
                "platform": detect_platform(url),
                "filename": final_filename,
                "filepath": final_path,
                "filesize": filesize,
                "duration": meta.get("duration", 0),
                "thumbnail": meta.get("thumbnail", ""),
                "format": audio_format if is_audio_only else "mp4",
                "quality": quality_id,
                "status": "completed",
                "created_at": time.time()
            }
            add_download(db_record)

            task.update({
                "status": "completed",
                "percent": 100.0,
                "stage": "Ready!",
                "speed_str": "",
                "eta_str": "",
                "filename": final_filename,
                "filepath": final_path,
                "filesize": filesize,
                "filesize_str": format_bytes(filesize),
                "title": meta.get("title", "Video"),
                "thumbnail": meta.get("thumbnail", ""),
                "duration": meta.get("duration", 0),
            })
            DOWNLOAD_TASKS[task_id] = task
            return task

    except Exception as e:
        err_msg = str(e)
        task.update({
            "status": "error",
            "error": err_msg,
            "stage": f"Error: {err_msg}"
        })
        DOWNLOAD_TASKS[task_id] = task
        return task

def start_download_async(url: str, options: Dict[str, Any]) -> str:
    task_id = str(uuid.uuid4())
    t = threading.Thread(target=execute_download, args=(task_id, url, options))
    t.daemon = True
    t.start()
    return task_id

def cancel_task(task_id: str) -> bool:
    if task_id in DOWNLOAD_TASKS:
        CANCEL_FLAGS[task_id] = True
        DOWNLOAD_TASKS[task_id]["status"] = "cancelled"
        DOWNLOAD_TASKS[task_id]["stage"] = "Cancelled by user"
        return True
    return False

def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    return DOWNLOAD_TASKS.get(task_id)
