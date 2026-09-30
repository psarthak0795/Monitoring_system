"""Windows workstation lock and suspend-state detection."""
import sys


_LOCKED_DESKTOP_NAMES = {"winlogon", "secure"}
_LOCKED_PROCESS_NAMES = {"logonui.exe", "lockapp.exe"}


def is_workstation_locked():
    if sys.platform != "win32":
        return False
    try:
        import psutil
        import win32gui
        import win32process

        foreground_window = win32gui.GetForegroundWindow()
        if foreground_window:
            _, process_id = win32process.GetWindowThreadProcessId(foreground_window)
            process_name = psutil.Process(process_id).name().lower()
            if process_name in _LOCKED_PROCESS_NAMES:
                return True

        user32 = __import__("ctypes").windll.user32
        desktop = user32.OpenInputDesktop(0, False, 0x0100)
        if not desktop:
            return True
        user32.CloseDesktop(desktop)
        return False
    except Exception:
        return False


def get_system_uptime_milliseconds():
    if sys.platform != "win32":
        return None
    try:
        return __import__("ctypes").windll.kernel32.GetTickCount64()
    except Exception:
        return None


def is_locked_process(process_name):
    return (process_name or "").lower() in _LOCKED_PROCESS_NAMES


def is_locked_desktop(desktop_name):
    return (desktop_name or "").lower() in _LOCKED_DESKTOP_NAMES