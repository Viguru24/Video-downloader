import sqlite3
import os
import time
from typing import List, Dict, Optional, Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "downloads.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS downloads (
        id TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        title TEXT NOT NULL,
        platform TEXT,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        filesize INTEGER DEFAULT 0,
        duration INTEGER DEFAULT 0,
        thumbnail TEXT,
        format TEXT,
        quality TEXT,
        status TEXT DEFAULT 'completed',
        created_at REAL NOT NULL
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON downloads(created_at DESC)")
    conn.commit()
    conn.close()

def add_download(record: Dict[str, Any]) -> Dict[str, Any]:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO downloads 
    (id, url, title, platform, filename, filepath, filesize, duration, thumbnail, format, quality, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.get("id"),
        record.get("url"),
        record.get("title", "Untitled Video"),
        record.get("platform", "generic"),
        record.get("filename", ""),
        record.get("filepath", ""),
        record.get("filesize", 0),
        record.get("duration", 0),
        record.get("thumbnail", ""),
        record.get("format", "mp4"),
        record.get("quality", "best"),
        record.get("status", "completed"),
        record.get("created_at", time.time())
    ))
    conn.commit()
    conn.close()
    return record

def update_download(download_id: str, updates: Dict[str, Any]):
    if not updates:
        return
    conn = get_connection()
    cursor = conn.cursor()
    keys = list(updates.keys())
    values = [updates[k] for k in keys]
    set_clause = ", ".join([f"{k} = ?" for k in keys])
    values.append(download_id)
    cursor.execute(f"UPDATE downloads SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()

def get_downloads(limit: int = 100, search: Optional[str] = None) -> List[Dict[str, Any]]:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    if search:
        cursor.execute("""
        SELECT * FROM downloads 
        WHERE title LIKE ? OR url LIKE ? OR platform LIKE ?
        ORDER BY created_at DESC LIMIT ?
        """, (f"%{search}%", f"%{search}%", f"%{search}%", limit))
    else:
        cursor.execute("SELECT * FROM downloads ORDER BY created_at DESC LIMIT ?", (limit,))
    
    rows = cursor.fetchall()
    results = [dict(row) for row in rows]
    conn.close()

    # Validate if files still exist on disk
    for item in results:
        fpath = item.get("filepath")
        if fpath and os.path.exists(fpath):
            item["file_exists"] = True
            try:
                item["filesize"] = os.path.getsize(fpath)
            except Exception:
                pass
        else:
            item["file_exists"] = False
    return results

def get_download(download_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM downloads WHERE id = ?", (download_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    item = dict(row)
    fpath = item.get("filepath")
    item["file_exists"] = bool(fpath and os.path.exists(fpath))
    return item

def delete_download(download_id: str, delete_file: bool = True) -> bool:
    item = get_download(download_id)
    if not item:
        return False
    if delete_file and item.get("filepath") and os.path.exists(item["filepath"]):
        try:
            os.remove(item["filepath"])
        except Exception:
            pass
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM downloads WHERE id = ?", (download_id,))
    conn.commit()
    conn.close()
    return True

def get_downloads_stats() -> Dict[str, Any]:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(filesize), 0) FROM downloads")
    row = cursor.fetchone()
    total_count = row[0] if row else 0
    total_bytes = row[1] if row else 0
    conn.close()
    return {
        "total_downloads": total_count,
        "total_bytes": total_bytes,
        "total_size_mb": round(total_bytes / (1024 * 1024), 2)
    }
