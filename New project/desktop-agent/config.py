import os
import sys
from dotenv import load_dotenv


def get_app_dir():
    """Folder the running program lives in.
    When packaged with PyInstaller (--onefile), __file__ points inside a
    temporary extraction folder that's wiped after the process exits, so we
    use the real .exe's location instead — this is where IT drops the
    per-organization .env file (e.g. BACKEND_URL) next to the executable."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir():
    """A stable, per-user, per-OS folder that survives across app restarts
    and reboots — used for anything that must persist (the saved login
    token), since the app folder itself may be read-only or temporary."""
    if sys.platform == "win32":
        base = os.getenv("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    path = os.path.join(base, "OrgTracker")
    os.makedirs(path, exist_ok=True)
    return path


APP_DIR = get_app_dir()
DATA_DIR = get_data_dir()

load_dotenv(os.path.join(APP_DIR, ".env"))

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
SCREENSHOT_INTERVAL_SECONDS = int(os.getenv("SCREENSHOT_INTERVAL_SECONDS", "300"))
IDLE_TIMEOUT_SECONDS = int(os.getenv("IDLE_TIMEOUT_SECONDS", "30"))
MEDIA_ACTIVITY_DETECTION_ENABLED = os.getenv(
    "MEDIA_ACTIVITY_DETECTION_ENABLED", "true"
).lower() in ("1", "true", "yes", "on")
MEDIA_CHECK_INTERVAL_SECONDS = int(os.getenv("MEDIA_CHECK_INTERVAL_SECONDS", "5"))
LONG_RUNNING_ACTIVITY_DETECTION_ENABLED = os.getenv(
    "LONG_RUNNING_ACTIVITY_DETECTION_ENABLED", "true"
).lower() in ("1", "true", "yes", "on")
SYSTEM_STATE_DETECTION_ENABLED = os.getenv(
    "SYSTEM_STATE_DETECTION_ENABLED", "true"
).lower() in ("1", "true", "yes", "on")
SCREENSHOT_NOTIFICATIONS_ENABLED = os.getenv(
    "SCREENSHOT_NOTIFICATIONS_ENABLED", "true"
).lower() in ("1", "true", "yes", "on")
AUTO_START_TRACKING = os.getenv("AUTO_START_TRACKING", "false").lower() in (
    "1", "true", "yes", "on"
)
SILENT_MODE = os.getenv("SILENT_MODE", "false").lower() in (
    "1", "true", "yes", "on"
)
TOKEN_FILE = os.path.join(DATA_DIR, "auth_token.json")
