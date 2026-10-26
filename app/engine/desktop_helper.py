"""
Standalone helper executed directly on the interactive user desktop (WinSta0\\Default).
Handles opening File Explorer windows, selecting files, and showing topmost native
folder selection dialogs even when the parent web server runs inside a background
or sandboxed desktop (such as exebox).
"""
import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import sys
import time


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
user32.AllowSetForegroundWindow.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL

HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
SW_RESTORE = 9
SW_SHOW = 5


def get_cabinet_windows():
    """Returns list of (hwnd, title) for all visible File Explorer windows on this desktop."""
    results = []

    @WNDENUMPROC
    def enum_cb(hwnd, lparam):
        if hwnd and user32.IsWindowVisible(hwnd):
            cls_buf = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, cls_buf, 128)
            if cls_buf.value == "CabinetWClass":
                title_buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, title_buf, 512)
                results.append((int(hwnd), title_buf.value))
        return True

    user32.EnumWindows(enum_cb, 0)
    return results


def bring_hwnd_to_front(hwnd: int):
    """Lifts a window cleanly above the browser and gives it focus without synthetic keypresses."""
    if not hwnd:
        return
    try:
        h = wintypes.HWND(hwnd)
        if user32.IsIconic(h):
            user32.ShowWindow(h, SW_RESTORE)
        else:
            user32.ShowWindow(h, SW_SHOW)

        fg_hwnd = user32.GetForegroundWindow()
        fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
        cur_tid = kernel32.GetCurrentThreadId()

        attached = False
        if fg_tid and fg_tid != cur_tid:
            attached = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))

        try:
            user32.SetWindowPos(
                h,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )
            user32.SetWindowPos(
                h,
                HWND_NOTOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )
            user32.SetForegroundWindow(h)
            user32.BringWindowToTop(h)
        finally:
            if attached:
                user32.AttachThreadInput(cur_tid, fg_tid, False)
    except Exception:
        pass


def match_existing_cabinet(target: str, cabinets):
    """Finds an already-open Explorer window matching target path or folder name."""
    norm = os.path.normpath(target).lower()
    base = os.path.basename(norm.rstrip("\\")).lower()
    for hwnd, title in cabinets:
        tl = title.lower()
        if norm in tl or (base and base in tl):
            return hwnd
    return None


def do_open_folder(target: str):
    target = os.path.normpath(os.path.abspath(target))
    drive, tail = os.path.splitdrive(target)
    if tail not in ("", "\\") and not os.path.exists(target):
        os.makedirs(target, exist_ok=True)

    before_hwnds = {h for h, _ in get_cabinet_windows()}

    user32.AllowSetForegroundWindow(0xFFFFFFFF)
    try:
        os.startfile(target)
    except Exception:
        subprocess.Popen(["explorer.exe", target])

    chosen_hwnd = None
    for i in range(34):
        time.sleep(0.06)
        cabinets = get_cabinet_windows()
        new_hwnds = [h for h, _ in cabinets if h not in before_hwnds]
        if new_hwnds:
            chosen_hwnd = new_hwnds[-1]
            break
        if i >= 5:
            matched = match_existing_cabinet(target, cabinets)
            if matched:
                chosen_hwnd = matched
                break

    if not chosen_hwnd:
        subprocess.Popen(["explorer.exe", target])
        for _ in range(25):
            time.sleep(0.06)
            cabinets = get_cabinet_windows()
            new_hwnds = [h for h, _ in cabinets if h not in before_hwnds]
            if new_hwnds:
                chosen_hwnd = new_hwnds[-1]
                break
            matched = match_existing_cabinet(target, cabinets)
            if matched:
                chosen_hwnd = matched
                break

    if chosen_hwnd:
        bring_hwnd_to_front(chosen_hwnd)
        return {"success": True, "folder_path": target, "hwnd": chosen_hwnd}

    cabinets = get_cabinet_windows()
    if cabinets:
        bring_hwnd_to_front(cabinets[0][0])
        return {"success": True, "folder_path": target, "hwnd": cabinets[0][0]}

    return {"success": False, "folder_path": target, "error": "Explorer window did not appear on desktop"}


def do_select_file(filepath: str):
    filepath = os.path.normpath(os.path.abspath(filepath))
    before_hwnds = {h for h, _ in get_cabinet_windows()}

    user32.AllowSetForegroundWindow(0xFFFFFFFF)
    subprocess.Popen(["explorer.exe", f"/select,{filepath}"])

    parent_dir = os.path.dirname(filepath)
    chosen_hwnd = None
    for i in range(34):
        time.sleep(0.06)
        cabinets = get_cabinet_windows()
        new_hwnds = [h for h, _ in cabinets if h not in before_hwnds]
        if new_hwnds:
            chosen_hwnd = new_hwnds[-1]
            break
        if i >= 5:
            matched = match_existing_cabinet(parent_dir, cabinets)
            if matched:
                chosen_hwnd = matched
                break

    if chosen_hwnd:
        bring_hwnd_to_front(chosen_hwnd)
        return {"success": True, "filepath": filepath, "hwnd": chosen_hwnd}

    cabinets = get_cabinet_windows()
    if cabinets:
        bring_hwnd_to_front(cabinets[0][0])
        return {"success": True, "filepath": filepath, "hwnd": cabinets[0][0]}

    return {"success": False, "filepath": filepath, "error": "Explorer window did not appear"}


def do_pick_folder(initial_dir: str):
    if not initial_dir or not os.path.exists(initial_dir):
        initial_dir = os.path.expanduser("~")
    initial_dir = os.path.normpath(os.path.abspath(initial_dir))

    user32.AllowSetForegroundWindow(0xFFFFFFFF)
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"1x1+{sw // 2}+{sh // 2}")
    root.wm_attributes("-alpha", 0.0)
    root.wm_attributes("-topmost", True)
    root.deiconify()
    root.update()
    try:
        frame_hwnd = int(root.wm_frame(), 16)
    except Exception:
        frame_hwnd = root.winfo_id()
    bring_hwnd_to_front(frame_hwnd)
    root.focus_force()

    selected = filedialog.askdirectory(
        parent=root,
        initialdir=initial_dir,
        title="Select OmniDownloader Default Save Folder",
        mustexist=True,
    )
    root.destroy()

    if selected:
        norm = os.path.normpath(selected)
        return {"success": True, "selected_path": norm}
    return {"success": False, "cancelled": True}


def main():
    if len(sys.argv) < 2:
        sys.exit(1)
    req_path = sys.argv[1]
    with open(req_path, "r", encoding="utf-8") as f:
        req = json.load(f)

    resp_path = req.get("resp_path")
    action = req.get("action")

    try:
        if action == "open_folder":
            result = do_open_folder(req.get("path", ""))
        elif action == "select_file":
            result = do_select_file(req.get("path", ""))
        elif action == "pick_folder":
            result = do_pick_folder(req.get("initial_dir", ""))
        else:
            result = {"success": False, "error": f"Unknown action: {action}"}
    except Exception as e:
        result = {"success": False, "error": str(e)}

    if resp_path:
        with open(resp_path, "w", encoding="utf-8") as f:
            json.dump(result, f)


if __name__ == "__main__":
    main()
