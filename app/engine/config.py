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

def get_presets() -> Dict[str, str]:
    return {
        "project": DEFAULT_DOWNLOADS,
        "videos": USER_VIDEOS,
        "downloads": USER_DOWNLOADS,
        "desktop": USER_DESKTOP_VIDEOS
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
    Opens the native Windows FolderBrowserDialog to allow the user
    to click and select any folder visually on their computer.
    """
    if sys.platform != "win32":
        return {"success": False, "error": "GUI picker only supported on Windows"}

    ps_script = (
        "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
        "$dialog = New-Object Windows.Forms.FolderBrowserDialog;"
        "$dialog.Description = 'Select OmniDownloader Default Save Folder';"
        "$dialog.ShowNewFolderButton = $true;"
        "if ($dialog.ShowDialog() -eq [Windows.Forms.DialogResult]::OK) {"
        "  Write-Output $dialog.SelectedPath"
        "}"
    )

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=120
        )
        selected = res.stdout.strip()
        if selected and os.path.exists(selected):
            # Save it to config
            new_cfg = save_config({"download_dir": selected})
            return {"success": True, "selected_path": selected, "config": new_cfg}
        return {"success": False, "cancelled": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
