import os
import sys
import json
import string
import subprocess
from typing import Dict, Any, Optional, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
DEFAULT_DOWNLOADS = os.path.join(BASE_DIR, "downloads")

# Common user directories
USER_HOME = os.path.expanduser("~")
USER_VIDEOS = os.path.join(USER_HOME, "Videos")
USER_DOWNLOADS = os.path.join(USER_HOME, "Downloads")
USER_DESKTOP_VIDEOS = os.path.join(USER_HOME, "Desktop", "Videos")

DEFAULT_CONFIG: Dict[str, Any] = {
    "download_dir": DEFAULT_DOWNLOADS,
    "trigger_browser_download": True,
    "audio_format": "mp3",
    "embed_thumbnail": True
}

def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = {**DEFAULT_CONFIG, **data}
                if not os.path.isabs(config.get("download_dir", "")):
                    config["download_dir"] = os.path.abspath(config["download_dir"])
                return config
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    current = load_config()
    current.update(updates)

    target_dir = current.get("download_dir", DEFAULT_DOWNLOADS)
    target_dir = os.path.expandvars(os.path.expanduser(target_dir))
    current["download_dir"] = os.path.abspath(target_dir)

    try:
        os.makedirs(current["download_dir"], exist_ok=True)
    except Exception as e:
        raise ValueError(f"Could not create folder '{current['download_dir']}': {str(e)}")

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)

    return current

def get_download_dir() -> str:
    cfg = load_config()
    d = cfg.get("download_dir", DEFAULT_DOWNLOADS)
    os.makedirs(d, exist_ok=True)
    return d

def get_presets() -> Dict[str, Any]:
    available_drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
    return {
        "project": DEFAULT_DOWNLOADS,
        "videos": USER_VIDEOS,
        "downloads": USER_DOWNLOADS,
        "desktop": USER_DESKTOP_VIDEOS,
        "drives": available_drives
    }

def open_folder_in_explorer(folder_path: str = None) -> bool:
    """
    Opens Windows File Explorer at the given directory using the native Windows Shell.
    """
    target = folder_path or get_download_dir()
    target = os.path.normpath(os.path.abspath(target))
    if not os.path.exists(target):
        try:
            os.makedirs(target, exist_ok=True)
        except Exception:
            pass

    try:
        if sys.platform == "win32":
            # Primary: native Windows os.startfile
            try:
                os.startfile(target)
                return True
            except Exception:
                # Fallback: explorer.exe
                subprocess.Popen(["explorer.exe", target])
                return True
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
            return True
        else:
            subprocess.Popen(["xdg-open", target])
            return True
    except Exception as e:
        print(f"Failed to open explorer for '{target}': {e}")
        return False

def pick_folder_gui() -> Dict[str, Any]:
    """
    Launches an independent standalone Python child process with Tkinter
    to show the native Windows FolderBrowserDialog on the interactive desktop.
    """
    initial = get_download_dir()
    if not os.path.exists(initial):
        initial = os.path.expanduser("~")

    # Run in a separate Python process so Tkinter runs on its own main thread
    code = f'''
import sys, os
try:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    root.focus_force()
    path = filedialog.askdirectory(
        title="Select OmniDownloader Default Save Folder",
        initialdir=r"{initial}",
        parent=root
    )
    root.destroy()
    if path:
        print(path.strip())
except Exception as e:
    sys.stderr.write(str(e))
'''
    try:
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
        selected = res.stdout.strip()
        if selected and os.path.exists(selected):
            new_cfg = save_config({"download_dir": selected})
            return {"success": True, "selected_path": selected, "config": new_cfg}
        return {"success": False, "cancelled": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def list_directory(target_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Provides structured folder tree listing for in-app visual navigation.
    """
    if not target_path or target_path in ["", "root", "drives"]:
        drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
        common = [
            {"name": "🎬 My Videos", "path": USER_VIDEOS, "exists": os.path.exists(USER_VIDEOS)},
            {"name": "📥 Downloads", "path": USER_DOWNLOADS, "exists": os.path.exists(USER_DOWNLOADS)},
            {"name": "🖥️ Desktop", "path": USER_DESKTOP_VIDEOS, "exists": os.path.exists(USER_DESKTOP_VIDEOS)},
            {"name": "📦 App Folder", "path": DEFAULT_DOWNLOADS, "exists": os.path.exists(DEFAULT_DOWNLOADS)}
        ]
        return {
            "current_path": "",
            "is_root": True,
            "drives": drives,
            "common": common,
            "folders": []
        }

    target_path = os.path.abspath(target_path)
    if not os.path.exists(target_path):
        return {"error": f"Path '{target_path}' does not exist", "current_path": target_path, "folders": []}

    subfolders = []
    try:
        with os.scandir(target_path) as it:
            for entry in it:
                try:
                    if entry.is_dir() and not entry.name.startswith(('.', '$', 'System Volume Information')):
                        subfolders.append({
                            "name": entry.name,
                            "path": os.path.normpath(entry.path)
                        })
                except Exception:
                    continue
        subfolders.sort(key=lambda x: x["name"].lower())
    except PermissionError:
        return {"error": "Access denied to this folder", "current_path": target_path, "folders": []}
    except Exception as e:
        return {"error": str(e), "current_path": target_path, "folders": []}

    parent = os.path.dirname(target_path) if target_path != os.path.dirname(target_path) else None
    return {
        "current_path": target_path,
        "parent_path": parent,
        "is_root": False,
        "folders": subfolders[:250]
    }
