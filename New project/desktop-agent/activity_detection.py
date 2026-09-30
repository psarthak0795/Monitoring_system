"""Windows foreground activity that can continue without new input events."""
import sys


_BROWSER_PROCESSES = {"chrome", "msedge", "firefox", "brave", "opera"}
_REMOTE_DESKTOP_PROCESSES = {
    "mstsc",
    "msrdc",
    "anydesk",
    "teamviewer",
    "rustdesk",
    "parsecd",
    "remoting_host",
}
_SCRIPT_PROCESSES = {
    "cmd",
    "cscript",
    "node",
    "powershell",
    "pwsh",
    "python",
    "pythonw",
    "wscript",
}
_DOWNLOAD_TITLE_TERMS = (
    "download",
    "downloading",
    "file transfer",
    "transferring",
    "uploading",
    "saving",
)


def is_foreground_long_running_activity():
    """Return whether the focused Windows app represents ongoing work."""
    if sys.platform != "win32":
        return False
    try:
        import psutil
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return False
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        executable = psutil.Process(process_id).name()
        title = win32gui.GetWindowText(hwnd)
        return _is_long_running_activity(executable, title)
    except Exception:
        return False


def get_foreground_activity_details():
    """Return a reviewable foreground-process signal, or None."""
    if sys.platform != "win32":
        return None
    try:
        import psutil
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        process = psutil.Process(process_id)
        executable = process.name()
        title = win32gui.GetWindowText(hwnd)
        if not _is_long_running_activity(executable, title):
            return None
        return {"process": executable, "window_title": title[:200], "pid": process_id}
    except Exception:
        return None


def _is_long_running_activity(executable, window_title):
    process_name = executable.lower().removesuffix(".exe").strip()
    title = (window_title or "").lower()

    if process_name in _REMOTE_DESKTOP_PROCESSES:
        return True
    if process_name in _SCRIPT_PROCESSES:
        return True
    return (
        process_name in _BROWSER_PROCESSES
        and any(term in title for term in _DOWNLOAD_TITLE_TERMS)
    )