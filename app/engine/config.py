import os
import sys
import json
import subprocess
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
DEFAULT_DOWNLOADS = os.path.join(BASE_DIR, "downloads")

# User common paths
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
                # Ensure directory is valid
                if not os.path.isabs(config.get("download_dir", "")):
                    config["download_dir"] = os.path.abspath(config["download_dir"])
                return config
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    current = load_config()
    current.update(updates)

    # Validate and make sure download_dir exists
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
    import string
    available_drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
    return {
        "project": DEFAULT_DOWNLOADS,
        "videos": USER_VIDEOS,
        "downloads": USER_DOWNLOADS,
        "desktop": USER_DESKTOP_VIDEOS,
        "drives": available_drives
    }

def open_folder_in_explorer(folder_path: str = None) -> bool:
    target = folder_path or get_download_dir()
    target = os.path.normpath(target)
    if not os.path.exists(target):
        os.makedirs(target, exist_ok=True)
    try:
        if sys.platform == "win32":
            subprocess.Popen(f'explorer.exe "{target}"')
            return True
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
            return True
        else:
            subprocess.Popen(["xdg-open", target])
            return True
    except Exception:
        return False

def pick_folder_gui() -> Dict[str, Any]:
    """
    Opens the native folder selection dialog in the foreground on Windows.
    Uses tkinter.filedialog with -topmost first, with PowerShell -STA fallback.
    """
    selected = None
    initial_dir = get_download_dir()
    if not os.path.exists(initial_dir):
        initial_dir = os.path.expanduser("~")

    # Try Tkinter with topmost focus
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)
        root.focus_force()
        selected = filedialog.askdirectory(
            title="Select OmniDownloader Default Save Folder",
            initialdir=initial_dir,
            parent=root
        )
        root.destroy()
    except Exception as tk_err:
        # Fallback to PowerShell -STA
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$top = New-Object System.Windows.Forms.Form; "
            "$top.TopMost = $true; "
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$d.Description = 'Select OmniDownloader Default Save Folder'; "
            "$d.ShowNewFolderButton = $true; "
            "if ($d.ShowDialog($top) -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $d.SelectedPath }"
        )
        try:
            res = subprocess.run(
                ["powershell", "-STA", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=120
            )
            selected = res.stdout.strip()
        except Exception as ps_err:
            return {"success": False, "error": f"Folder picker error: {str(tk_err)} | {str(ps_err)}"}

    if selected and os.path.exists(selected):
        new_cfg = save_config({"download_dir": selected})
        return {"success": True, "selected_path": selected, "config": new_cfg}
    return {"success": False, "cancelled": True}
