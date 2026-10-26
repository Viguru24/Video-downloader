"""
Launcher that bridges background/sandboxed Windows server processes (such as
exebox desktops) to the active interactive user desktop (WinSta0\\Default)
using Win32 CreateProcessW + STARTUPINFOW.lpDesktop.
"""
import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import sys
import tempfile
import uuid
from typing import Any, Dict


HELPER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "desktop_helper.py")


if sys.platform == "win32":
    kernel32 = ctypes.windll.kernel32

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(wintypes.BYTE)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]

    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL


CREATE_NO_WINDOW = 0x08000000
WAIT_TIMEOUT = 0x00000102


def invoke_on_user_desktop(payload: Dict[str, Any], timeout_ms: int = 10000) -> Dict[str, Any]:
    """
    Executes desktop_helper.py directly on WinSta0\\Default and returns its JSON result.
    """
    if sys.platform != "win32":
        return {"success": False, "error": "Windows desktop bridge only supported on win32"}

    token = uuid.uuid4().hex
    tmp_dir = tempfile.gettempdir()
    req_path = os.path.join(tmp_dir, f"omni_desk_req_{token}.json")
    resp_path = os.path.join(tmp_dir, f"omni_desk_resp_{token}.json")

    req_data = dict(payload)
    req_data["resp_path"] = resp_path

    try:
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(req_data, f)

        si = STARTUPINFOW()
        si.cb = ctypes.sizeof(STARTUPINFOW)
        si.lpDesktop = "WinSta0\\Default"
        pi = PROCESS_INFORMATION()

        cmd_str = subprocess.list2cmdline([sys.executable, HELPER_SCRIPT, req_path])
        cmd_buf = ctypes.create_unicode_buffer(cmd_str)

        ok = kernel32.CreateProcessW(
            None,
            cmd_buf,
            None,
            None,
            False,
            CREATE_NO_WINDOW,
            None,
            None,
            ctypes.byref(si),
            ctypes.byref(pi),
        )

        if not ok:
            err_code = ctypes.GetLastError()
            return {"success": False, "error": f"CreateProcessW failed (WinError {err_code})"}

        try:
            wait_res = kernel32.WaitForSingleObject(pi.hProcess, timeout_ms)
            if wait_res == WAIT_TIMEOUT:
                kernel32.TerminateProcess(pi.hProcess, 1)
                return {"success": False, "error": "Desktop action timed out"}
        finally:
            kernel32.CloseHandle(pi.hProcess)
            kernel32.CloseHandle(pi.hThread)

        if os.path.exists(resp_path):
            with open(resp_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return {"success": False, "error": "Desktop helper finished without response"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        for p in (req_path, resp_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
