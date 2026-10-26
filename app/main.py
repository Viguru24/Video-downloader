import os
import sys
import json
import asyncio
import subprocess
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

from .engine.storage import (
    init_db,
    get_downloads,
    get_download,
    delete_download,
    get_downloads_stats,
    DB_PATH
)
from .engine.config import (
    load_config,
    save_config,
    get_download_dir,
    get_presets,
    open_folder_in_explorer,
    pick_folder_gui,
    list_directory
)
from .engine.ytdl_engine import (
    inspect_media,
    start_download_async,
    get_task_status,
    cancel_task,
    DOWNLOADS_DIR,
    format_bytes
)

# Initialize database
init_db()

app = FastAPI(
    title="OmniDownloader - Universal Video PWA",
    description="Universal Web Media & Video Downloader Progressive Web App",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Mount static folder
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Models
class InspectRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    quality_id: Optional[str] = "best"
    audio_only: Optional[bool] = False
    audio_format: Optional[str] = "mp3"
    embed_thumbnail: Optional[bool] = True

# Service Worker & Manifest routes at root
@app.get("/manifest.json")
async def get_manifest():
    manifest_path = os.path.join(STATIC_DIR, "manifest.json")
    return FileResponse(manifest_path, media_type="application/manifest+json")

@app.get("/sw.js")
async def get_sw():
    sw_path = os.path.join(STATIC_DIR, "sw.js")
    response = FileResponse(sw_path, media_type="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response

@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        resp = HTMLResponse(content=f.read())
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

@app.post("/api/inspect")
async def api_inspect(payload: InspectRequest):
    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Please enter a valid URL")
    
    # Run inspection in threadpool so it doesn't block async loop
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, inspect_media, url)
    return info

@app.post("/api/download")
async def api_download(payload: DownloadRequest):
    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    options = {
        "quality_id": payload.quality_id or "best",
        "audio_only": bool(payload.audio_only),
        "audio_format": payload.audio_format or "mp3",
        "embed_thumbnail": bool(payload.embed_thumbnail)
    }

    task_id = start_download_async(url, options)
    return {"success": True, "task_id": task_id}

@app.get("/api/tasks/{task_id}")
async def api_task_status(task_id: str):
    task = get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/api/tasks/{task_id}/cancel")
async def api_cancel_task(task_id: str):
    res = cancel_task(task_id)
    return {"success": res}

@app.get("/api/tasks/{task_id}/stream")
async def api_task_stream(task_id: str):
    """
    Server-Sent Events (SSE) endpoint to provide real-time updates for downloads.
    """
    async def event_generator():
        while True:
            task = get_task_status(task_id)
            if not task:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                break
            
            yield f"data: {json.dumps(task)}\n\n"

            if task.get("status") in ["completed", "error", "cancelled"]:
                break
            
            await asyncio.sleep(0.4)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/file/{task_id}")
async def api_download_file(task_id: str):
    task = get_task_status(task_id)
    if not task or task.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Download not completed yet or not found")
    
    filepath = task.get("filepath")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File missing from disk")

    filename = task.get("filename") or os.path.basename(filepath)
    return FileResponse(
        filepath,
        filename=filename,
        media_type="application/octet-stream"
    )

@app.get("/api/stream-file/{download_id}")
async def api_stream_file(download_id: str):
    """
    Plays or streams downloaded media in browser with Range support.
    """
    item = get_download(download_id)
    if not item or not item.get("filepath") or not os.path.exists(item["filepath"]):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    filepath = item["filepath"]
    ext = os.path.splitext(filepath)[1].lower()
    media_type = "video/mp4"
    if ext == ".mp3":
        media_type = "audio/mpeg"
    elif ext == ".m4a":
        media_type = "audio/mp4"
    elif ext == ".webm":
        media_type = "video/webm"
    elif ext == ".mkv":
        media_type = "video/x-matroska"
    elif ext == ".wav":
        media_type = "audio/wav"
    elif ext == ".flac":
        media_type = "audio/flac"

    return FileResponse(
        filepath,
        media_type=media_type,
        filename=item.get("filename", os.path.basename(filepath))
    )

@app.get("/api/library")
async def api_get_library(search: Optional[str] = None):
    downloads = get_downloads(limit=100, search=search)
    return {"downloads": downloads, "count": len(downloads)}

@app.delete("/api/library/{download_id}")
async def api_delete_download(download_id: str, delete_file: bool = True):
    success = delete_download(download_id, delete_file=delete_file)
    return {"success": success}

@app.post("/api/library/{download_id}/open-folder")
async def api_open_folder(download_id: str):
    """
    Opens the file in Windows File Explorer locally and highlights it.
    """
    item = get_download(download_id)
    if not item or not item.get("filepath") or not os.path.exists(item["filepath"]):
        raise HTTPException(status_code=404, detail="File not found on system")
    
    filepath = os.path.normpath(os.path.abspath(item["filepath"]))
    try:
        if sys.platform == "win32":
            subprocess.Popen(f'explorer.exe /select,"{filepath}"', shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", filepath])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(filepath)])
        return {"success": True, "filepath": filepath}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/stats")
async def api_stats():
    stats = get_downloads_stats()
    stats["downloads_directory"] = get_download_dir()
    return stats

@app.get("/api/config")
async def api_get_config():
    return {
        "config": load_config(),
        "presets": get_presets()
    }

@app.post("/api/config")
async def api_update_config(request: Request):
    payload = await request.json()
    try:
        updated = save_config(payload)
        return {"success": True, "config": updated}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/config/pick-folder")
async def api_pick_folder():
    """
    Triggers the native Windows folder picker GUI dialog.
    """
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, pick_folder_gui)
    return res

@app.post("/api/config/open-folder")
async def api_open_configured_folder(request: Request):
    """
    Opens the default or specified folder in Windows Explorer.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    folder_path = body.get("folder_path") or get_download_dir()
    success = open_folder_in_explorer(folder_path)
    return {"success": success, "folder_path": folder_path}

@app.get("/api/fs/list")
async def api_fs_list(path: Optional[str] = Query(None)):
    """
    Lists directories for the in-app visual folder browser.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, list_directory, path)

@app.get("/api/proxy-stream")
async def api_proxy_stream(url: str = Query(...)):
    """
    Proxies external video stream chunks if CORS prevents direct browser download.
    """
    try:
        r = requests.get(url, stream=True, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        return StreamingResponse(
            r.iter_content(chunk_size=1024 * 64),
            media_type=r.headers.get("content-type", "application/octet-stream")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
