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
    "trigger_browser_download": False,
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
    Forces Windows File Explorer to open the folder window directly on the
    active interactive user desktop (WinSta0\\Default) and brings it to front.
    """
    target = (folder_path or "").strip() or get_download_dir()
    target = os.path.normpath(os.path.abspath(target))
    drive, tail = os.path.splitdrive(target)
    if tail not in ("", "\\") and not os.path.exists(target):
        try:
            os.makedirs(target, exist_ok=True)
        except Exception:
            pass

    try:
        if sys.platform == "win32":
            from app.engine.win_desktop import invoke_on_user_desktop
            res = invoke_on_user_desktop({"action": "open_folder", "path": target}, timeout_ms=8000)
            if res.get("success"):
                return True
            # Fallback if desktop bridge unavailable
            os.startfile(target)
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


def select_file_in_explorer(filepath: str) -> Dict[str, Any]:
    """
    Opens File Explorer on the interactive user desktop (WinSta0\\Default)
    with the target file highlighted and brings the window to front.
    """
    filepath = os.path.normpath(os.path.abspath(filepath))
    folder_path = os.path.dirname(filepath)
    try:
        if sys.platform == "win32":
            from app.engine.win_desktop import invoke_on_user_desktop
            res = invoke_on_user_desktop({"action": "select_file", "path": filepath}, timeout_ms=8000)
            if res.get("success"):
                return {"success": True, "filepath": filepath, "folder_path": folder_path}
            subprocess.Popen(f'explorer.exe /select,"{filepath}"')
            return {"success": True, "filepath": filepath, "folder_path": folder_path}
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", filepath])
            return {"success": True, "filepath": filepath, "folder_path": folder_path}
        else:
            subprocess.Popen(["xdg-open", folder_path])
            return {"success": True, "filepath": filepath, "folder_path": folder_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


def pick_folder_gui() -> Dict[str, Any]:
    """
    Launches a topmost native folder picker dialog directly on the active
    interactive user desktop (WinSta0\\Default).
    """
    initial = get_download_dir()
    if not os.path.exists(initial):
        initial = os.path.expanduser("~")

    if sys.platform == "win32":
        from app.engine.win_desktop import invoke_on_user_desktop
        res = invoke_on_user_desktop(
            {"action": "pick_folder", "initial_dir": initial},
            timeout_ms=180000,
        )
        if res.get("success") and res.get("selected_path"):
            selected = res["selected_path"]
            if os.path.exists(selected):
                new_cfg = save_config({"download_dir": selected})
                return {"success": True, "selected_path": selected, "config": new_cfg}
        if res.get("cancelled"):
            return {"success": False, "cancelled": True}
        return {"success": False, "error": res.get("error", "Folder picker failed")}

    return {"success": False, "error": "Native GUI picker only supported on Windows"}

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
