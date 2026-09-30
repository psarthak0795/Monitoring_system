"""
Cross-platform (Windows / macOS / Ubuntu) desktop tracking agent.

Flow:
  1. Employee logs in once (email/password against the backend API).
  2. Click "Start Tracking" in the system tray icon -> opens a time entry on
     the server and starts a background loop that takes a screenshot every
     SCREENSHOT_INTERVAL_SECONDS and uploads it (with the machine's public IP).
  3. Click "Stop Tracking" -> closes the time entry and stops the loop.

Notes for packaging on each OS:
  - Windows: works as-is. Package with PyInstaller (`pyinstaller --onefile --noconsole agent.py`).
  - macOS: the OS will prompt for "Screen Recording" permission the first time
    a screenshot is taken (System Settings > Privacy & Security > Screen Recording).
    Grant it to Terminal/Python (or to the packaged .app) or captures will be black.
  - Ubuntu/Linux: on Wayland, mss/screenshot tools may be restricted; X11 works
    out of the box. If needed, run the session under X11 or use `grim` as a fallback.
"""
import io
import json
import os
import socket
import statistics
import sys
import threading
import time
import traceback
from collections import deque
from datetime import datetime, timezone
from getpass import getpass
from pynput import keyboard, mouse
import ctypes

import mss
import requests
from PIL import Image
import pystray
from pystray import MenuItem as Item

from activity_detection import get_foreground_activity_details
from media_activity import is_foreground_media_playing
from mouse_pattern_detector import MousePatternDetector
from synthetic_input_detector import SyntheticInputDetector
from system_state import (
    get_system_uptime_milliseconds,
    is_workstation_locked,
)

from config import (
    BACKEND_URL,
    AUTO_START_TRACKING,
    DATA_DIR,
    SCREENSHOT_INTERVAL_SECONDS,
    IDLE_TIMEOUT_SECONDS,
    LONG_RUNNING_ACTIVITY_DETECTION_ENABLED,
    MEDIA_ACTIVITY_DETECTION_ENABLED,
    MEDIA_CHECK_INTERVAL_SECONDS,
    SCREENSHOT_NOTIFICATIONS_ENABLED,
    SILENT_MODE,
    SYSTEM_STATE_DETECTION_ENABLED,
    TOKEN_FILE,
)


_INSTANCE_MUTEX = None


def _acquire_single_instance():
    """Allow only one agent process per Windows user session."""
    global _INSTANCE_MUTEX
    if sys.platform != "win32":
        return True

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.GetLastError.restype = ctypes.c_ulong
        _INSTANCE_MUTEX = kernel32.CreateMutexW(
            None, False, "Local\\OrgTrackerDesktopAgent"
        )
        if not _INSTANCE_MUTEX:
            return True
        return ctypes.get_last_error() != 183
    except Exception:
        return True


def _has_display():
    """Whether a login dialog can actually be shown. On Windows/macOS a
    display is always assumed present; on Linux, tray apps require an X11/
    Wayland session (there's no DISPLAY on a headless server, for example)."""
    if sys.platform in ("win32", "darwin"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def prompt_login_gui(error_message=None):
    """Shows a small login window and returns (email, password), or None if
    the user closed it. Used instead of a console prompt because a packaged,
    auto-starting tray app has no terminal to type into."""
    import tkinter as tk

    result = {}

    root = tk.Tk()
    root.title("Org Tracker — Log in")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    frame = tk.Frame(root, padx=24, pady=20)
    frame.pack()

    tk.Label(frame, text="Org Tracker", font=("Segoe UI", 14, "bold")).grid(
        row=0, column=0, columnspan=2, pady=(0, 12)
    )

    if error_message:
        tk.Label(frame, text=error_message, fg="#c0392b", wraplength=260).grid(
            row=1, column=0, columnspan=2, pady=(0, 8)
        )

    tk.Label(frame, text="Email").grid(row=2, column=0, sticky="w")
    email_var = tk.StringVar()
    email_entry = tk.Entry(frame, textvariable=email_var, width=30)
    email_entry.grid(row=3, column=0, columnspan=2, pady=(0, 8))
    email_entry.focus_set()

    tk.Label(frame, text="Password").grid(row=4, column=0, sticky="w")
    password_var = tk.StringVar()
    password_entry = tk.Entry(frame, textvariable=password_var, width=30, show="*")
    password_entry.grid(row=5, column=0, columnspan=2, pady=(0, 14))

    def submit(event=None):
        result["email"] = email_var.get().strip()
        result["password"] = password_var.get()
        root.destroy()

    password_entry.bind("<Return>", submit)
    tk.Button(frame, text="Log in", command=submit, width=12).grid(row=6, column=0, columnspan=2)

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.eval("tk::PlaceWindow . center")
    root.mainloop()

    if not result.get("email"):
        return None
    return result["email"], result["password"]


class ActivityMonitor:
    """Track mouse and keyboard activity through one monitor per input type."""

    def __init__(
        self,
        on_idle_change,
        timeout_seconds=IDLE_TIMEOUT_SECONDS,
        on_pattern_change=None,
        on_synthetic_input=None,
    ):
        self._on_idle_change = on_idle_change
        self._on_pattern_change = on_pattern_change
        self._on_synthetic_input = on_synthetic_input
    def __init__(self, on_idle_change, on_signal=None, timeout_seconds=IDLE_TIMEOUT_SECONDS):
        self._on_idle_change = on_idle_change
        self._on_signal = on_signal or (lambda *_args, **_kwargs: None)
        self._timeout_seconds = timeout_seconds
        self._last_activity = time.monotonic()
        self._last_media_check = 0.0
        self._last_system_uptime = get_system_uptime_milliseconds()
        self._system_blocked = False
        self._idle = False
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._thread = None
        self._mouse_listener = None
        self._keyboard_listener = None
        self._pattern_detector = MousePatternDetector()
        self._pattern_detected = False
        self._synthetic_input_detector = SyntheticInputDetector(
            on_real_input=self._on_real_input,
            on_synthetic_input=self._on_synthetic_input_event,
        )
        self._synthetic_streak = 0
        self._real_streak = 0
        self._synthetic_detected = False
        self._mouse_events = deque(maxlen=60)
        self._keyboard_events = deque(maxlen=60)
        self._last_jiggler_signal = 0.0

        self._last_system_input = self._get_system_input_time()

    @staticmethod
    def _get_system_input_time():
        if sys.platform != "win32":
            return None

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        try:
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
                return info.dwTime
        except Exception:
            pass
        return None

    def set_timeout(self, timeout_seconds):
        with self._state_lock:
            self._timeout_seconds = timeout_seconds

    def start(self):
        with self._state_lock:
            if self._thread and self._thread.is_alive():
                return
            self._last_activity = time.monotonic()
            self._last_media_check = 0.0
            self._last_system_uptime = get_system_uptime_milliseconds()
            self._system_blocked = False
            self._last_system_input = self._get_system_input_time()
            self._idle = False
            self._pattern_detector.reset()
            self._pattern_detected = False
            self._synthetic_streak = 0
            self._real_streak = 0
            self._synthetic_detected = False
            self._stop_event.clear()
            self._mouse_listener = mouse.Listener(
                on_move=self._on_mouse_move,
                on_click=self._on_other_input,
                on_scroll=self._on_other_input,
            )
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_other_input
            )
            self._mouse_listener.start()
            self._keyboard_listener.start()
            self._synthetic_input_detector.start()
            self._thread = threading.Thread(
                target=self._run,
                daemon=True
            )
                on_move=self._mouse_activity,
                on_click=self._activity,
                on_scroll=self._activity,
            )
            self._keyboard_listener = keyboard.Listener(on_press=self._keyboard_activity)
            self._mouse_listener.start()
            self._keyboard_listener.start()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._synthetic_input_detector.stop()
        for listener in (
            self._mouse_listener,
            self._keyboard_listener
        ):
        for listener in (self._mouse_listener, self._keyboard_listener):
            if listener:
                listener.stop()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
        self._mouse_listener = None
        self._keyboard_listener = None
        self._thread = None

    def _activity(self, *args):
        became_active = False
        with self._state_lock:
            if self._system_blocked:
                return
            self._last_activity = time.monotonic()
            if self._idle:
                self._idle = False
                became_active = True

        if became_active:
            self._on_idle_change(False)

    def _on_mouse_move(self, *args):
        self._pattern_detector.record_mouse_move()
        self._activity()

    def _on_other_input(self, *args):
        self._pattern_detector.record_other_input()
        self._activity()

    def _on_real_input(self):
        self._real_streak += 1
        self._synthetic_streak = max(0, self._synthetic_streak - 2)
        if self._synthetic_detected and self._synthetic_streak == 0:
            self._synthetic_detected = False
            if self._on_synthetic_input:
                self._on_synthetic_input(False)

    def _on_synthetic_input_event(self):
        self._synthetic_streak += 1
        self._real_streak = 0
        if self._synthetic_streak >= 5 and not self._synthetic_detected:
            self._synthetic_detected = True
            if self._on_synthetic_input:
                self._on_synthetic_input(True)
    def _mouse_activity(self, *args):
        self._mouse_events.append(time.monotonic())
        self._activity(*args)

    def _keyboard_activity(self, *args):
        self._keyboard_events.append(time.monotonic())
        self._activity(*args)

    def _check_mouse_jiggler(self, now):
        if len(self._mouse_events) < 8 or now - self._last_jiggler_signal < 300:
            return
        events = list(self._mouse_events)
        recent = [event for event in events if now - event <= 60]
        if len(recent) < 8:
            return
        intervals = [right - left for left, right in zip(events[-8:], events[-7:])]
        mean_interval = statistics.mean(intervals)
        deviation = statistics.pstdev(intervals)
        has_no_keyboard = not self._keyboard_events or now - self._keyboard_events[-1] > 60
        if has_no_keyboard and 1.0 <= mean_interval <= 15.0 and deviation <= 0.2:
            self._last_jiggler_signal = now
            self._on_signal(
                "possible_input_simulator",
                "Pointer input has an unusually regular pattern without keyboard activity.",
                {"events_last_60_seconds": len(recent), "mean_interval_seconds": round(mean_interval, 3), "interval_deviation": round(deviation, 3)},
            )

    def _check_windows_input(self):
        """
        Check whether Windows has registered new user input.
        This is especially useful for Precision Touchpad gestures.
        """
        current_input = self._get_system_input_time()

        if current_input is None:
            return

        with self._state_lock:
            previous_input = self._last_system_input
            if self._system_blocked:
                self._last_system_input = current_input
                return
            if (
                previous_input is not None
                and current_input != previous_input
            ):
                self._last_activity = time.monotonic()
                if self._idle:
                    self._idle = False
                    became_active = True
                else:
                    became_active = False
            else:
                became_active = False
            self._last_system_input = current_input
        if became_active:
            self._on_idle_change(False)

    def _check_system_state(self):
        if not SYSTEM_STATE_DETECTION_ENABLED:
            return False

        current_uptime = get_system_uptime_milliseconds()
        resumed_from_sleep = (
            current_uptime is not None
            and self._last_system_uptime is not None
            and current_uptime - self._last_system_uptime >= 5000
        )
        self._last_system_uptime = current_uptime
        blocked = is_workstation_locked() or resumed_from_sleep

        if blocked:
            became_idle = False
            with self._state_lock:
                self._system_blocked = True
                if not self._idle:
                    self._idle = True
                    became_idle = True
            if became_idle:
                self._on_idle_change(True)
            return True

        with self._state_lock:
            self._system_blocked = False
        return False

    def _run(self):
        while not self._stop_event.wait(1):
            now = time.monotonic()

            if self._check_system_state():
                continue

            self._check_windows_input()
            self._check_mouse_jiggler(now)

            if (
                (
                    MEDIA_ACTIVITY_DETECTION_ENABLED
                    or LONG_RUNNING_ACTIVITY_DETECTION_ENABLED
                )
                and now - self._last_media_check >= MEDIA_CHECK_INTERVAL_SECONDS
            ):
                self._last_media_check = now
                activity_details = None
                if (
                    (
                        MEDIA_ACTIVITY_DETECTION_ENABLED
                        and is_foreground_media_playing()
                    )
                    or (
                        LONG_RUNNING_ACTIVITY_DETECTION_ENABLED
                        and (activity_details := get_foreground_activity_details()) is not None
                    )
                ):
                    if activity_details:
                        self._on_signal(
                            "suspicious_automated_activity",
                            "A script, download, or remote-session process was detected in the foreground.",
                            activity_details,
                        )
                    self._activity()
                    continue
            pattern_detected = self._pattern_detector.is_automated_pattern()
            if pattern_detected != self._pattern_detected:
                self._pattern_detected = pattern_detected
                if self._on_pattern_change:
                    self._on_pattern_change(pattern_detected)
            became_idle = False
            with self._state_lock:
                timeout = self._timeout_seconds
                if not self._idle and time.monotonic() - self._last_activity >= timeout:
                    self._idle = True
                    became_idle = True
            if became_idle:
                self._on_idle_change(True)


class TrackerAgent:
    def __init__(self):
        self.token = None
        self.active_entry_id = None
        self.tracking = False
        self._stop_event = threading.Event()
        self._worker_thread = None
        self._command_thread = None
        self._start_lock = threading.Lock()
        self._activity_monitor = None
        self._idle = False
        self._resume_after_idle = False
        self._stopped_due_to_pattern = False
        self._stopped_due_to_synthetic_input = False
        self._settings_thread = None
        self.icon = None
        self.screenshot_interval_seconds = SCREENSHOT_INTERVAL_SECONDS
        self.idle_timeout_seconds = IDLE_TIMEOUT_SECONDS

    def _log(self, message):
        print(message)
        try:
            with open(os.path.join(DATA_DIR, "agent.log"), "a", encoding="utf-8") as log:
                log.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")
        except OSError:
            pass

    # ---------- Notifications ----------

    def notify(self, message, title="Org Tracker"):
        """Shows a small OS-native popup (Windows toast / macOS notification
        center / Linux libnotify, depending on platform support). This is the
        ONLY thing an employee sees once the agent is packaged with
        --noconsole for real deployment — print() statements go nowhere
        visible at that point, so every important status change needs to
        also call this."""
        if SILENT_MODE:
            return
        print(f"[{title}] {message}")
        if not self.icon:
            return
        try:
            if getattr(self.icon, "HAS_NOTIFICATION", True):
                self.icon.notify(message, title)
        except Exception as e:
            print(f"Notification failed (non-fatal): {e}")

    # ---------- Auth ----------

    def load_token(self):
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                self.token = json.load(f).get("token")

    def save_token(self, token):
        self.token = token
        with open(TOKEN_FILE, "w") as f:
            json.dump({"token": token}, f)

    def delete_token(self):
        self.token = None
        if os.path.exists(TOKEN_FILE):
            try:
                os.remove(TOKEN_FILE)
            except OSError:
                pass

    def _prompt_credentials(self, error_message=None):
        if SILENT_MODE and self.token:
            raise SystemExit("Silent mode requires a valid saved login token.")
        if _has_display():
            try:
                creds = prompt_login_gui(error_message)
            except Exception as e:
                print(f"Login window failed ({e}), falling back to console login.")
                creds = None
            if creds is not None:
                return creds
            if _has_display():
                # user closed the window deliberately — don't fall through to console
                raise SystemExit("Login cancelled.")

        print("=== Org Tracker Agent: Login ===")
        if error_message:
            print(error_message)
        email = input("Email: ").strip()
        password = getpass("Password: ")
        return email, password

    def login(self):
        error_message = None
        while True:
            email, password = self._prompt_credentials(error_message)
            resp = requests.post(
                f"{BACKEND_URL}/auth/login",
                data={"username": email, "password": password},
                timeout=10,
            )
            if resp.status_code == 401:
                error_message = "Incorrect email or password. Please try again."
                continue
            resp.raise_for_status()
            token = resp.json()["access_token"]
            self.save_token(token)
            print("Logged in successfully.")
            return

    def validate_token(self):
        if not self.token:
            return False
        try:
            resp = requests.get(
                f"{BACKEND_URL}/users/me",
                headers=self.auth_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in (401, 403):
                print("Stored token is invalid or expired. Please log in again.")
                self.delete_token()
                return False
            raise
        except Exception as exc:
            print(f"Token validation failed: {exc}")
            return False

    def auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def fetch_settings(self):
        if not self.token:
            return
        try:
            resp = requests.get(
                f"{BACKEND_URL}/settings",
                headers=self.auth_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            new_interval = data.get("screenshot_interval_seconds")
            if isinstance(new_interval, int) and new_interval > 0:
                if new_interval != self.screenshot_interval_seconds:
                    self._log(f"Screenshot interval updated: {self.screenshot_interval_seconds}s -> {new_interval}s")
                self.screenshot_interval_seconds = new_interval

            new_idle_timeout = data.get("idle_timeout_seconds")
            if isinstance(new_idle_timeout, int) and new_idle_timeout > 0:
                if new_idle_timeout != self.idle_timeout_seconds:
                    print(f"Idle timeout updated: {self.idle_timeout_seconds}s -> {new_idle_timeout}s")
                self.idle_timeout_seconds = new_idle_timeout
                if self._activity_monitor:
                    self._activity_monitor.set_timeout(new_idle_timeout)
        except requests.exceptions.RequestException as e:
            self._log(f"Could not refresh settings ({e.__class__.__name__}); keeping current interval.")
        except Exception as e:
            self._log(f"Unexpected error refreshing settings: {e}")

    def _settings_loop(self):
        while True:
            self.fetch_settings()
            # Pick up administrator changes quickly without restarting the agent.
            time.sleep(10)

    def _get_error_detail(self, response):
        try:
            return response.json().get("detail")
        except Exception:
            return response.text

    def _handle_unauthorized(self):
        was_tracking = self.tracking
        self.delete_token()
        self.tracking = False
        self.active_entry_id = None
        self._stop_event.set()
        if self.icon:
            self._update_menu()
        if was_tracking:
            self.notify("Session expired — tracking stopped. Please log in again.")
        else:
            self.notify("Session expired. Please log in again.")

    def sync_active_entry(self):
        try:
            resp = requests.get(
                f"{BACKEND_URL}/time-entries/active",
                headers=self.auth_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            entry = resp.json()
            if entry:
                self.active_entry_id = entry["id"]
                self.tracking = True
                self._idle = bool(entry.get("is_idle", False))
                try:
                    self._send_heartbeat()
                except Exception as e:
                    print(f"Active-session heartbeat failed: {e}")
                self._start_worker()
            else:
                self.active_entry_id = None
                self.tracking = False
            if self.icon:
                self._update_menu()
        except Exception as e:
            print(f"Could not refresh active tracking state: {e}")
            self.active_entry_id = None
            self.tracking = False

    # ---------- Helpers ----------

    @staticmethod
    def get_system_ip():
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "unknown"

    @staticmethod
    def capture_screenshot_bytes():
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # full virtual screen, all monitors combined
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70)
            return buf.getvalue()

    # ---------- Tracking control ----------

    def _start_worker(self):
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self._worker_thread.start()

    def _start_activity_monitor(self):
        if not self._activity_monitor:
            self._activity_monitor = ActivityMonitor(
                self._handle_idle_change,
                self.idle_timeout_seconds,
                self._handle_pattern_change,
                self._handle_synthetic_input_change,
                self._submit_alert,
                self.idle_timeout_seconds,
            )
        else:
            self._activity_monitor.set_timeout(self.idle_timeout_seconds)
        self._activity_monitor.start()

    def _submit_alert(self, alert_type, message, evidence=None):
        if not self.token:
            return
        try:
            response = requests.post(
                f"{BACKEND_URL}/alerts/telemetry",
                json={
                    "alert_type": alert_type,
                    "message": message,
                    "evidence": evidence or {},
                },
                headers=self.auth_headers(),
                timeout=10,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            print(f"Could not submit security alert: {exc}")

    def _handle_idle_change(self, is_idle):
        self._idle = is_idle
        if is_idle:
            if self.tracking:
                entry_id = self.active_entry_id
                self.notify(
                    f"Tracking stopped after {self.idle_timeout_seconds} seconds of inactivity "
                    f"(session #{entry_id})."
                )
                self._stop_tracking(notify_user=False, preserve_for_idle=True)
        elif (
            self._resume_after_idle
            and not self._stopped_due_to_pattern
            and not self._stopped_due_to_synthetic_input
        ):
            self._resume_after_idle = False
            self.start_tracking()
            self.notify("Activity detected. Tracking resumed.")

    def _handle_pattern_change(self, detected):
        if detected:
            if self.tracking and not self._stopped_due_to_pattern:
                self._stopped_due_to_pattern = True
                entry_id = self.active_entry_id
                self._stop_tracking(notify_user=False, preserve_for_idle=True)
                self.notify(
                    f"Tracking paused because automated mouse movement was detected "
                    f"(session #{entry_id})."
                )
            return

        if self._stopped_due_to_pattern:
            self._stopped_due_to_pattern = False
            if (
                self._resume_after_idle
                and not self.tracking
                and not self._stopped_due_to_synthetic_input
            ):
                self._resume_after_idle = False
                self.start_tracking()
                self.notify("Automated mouse movement ended. Tracking resumed.")

    def _handle_synthetic_input_change(self, detected):
        if detected:
            if not self._stopped_due_to_synthetic_input:
                self._stopped_due_to_synthetic_input = True
                if self.tracking:
                    entry_id = self.active_entry_id
                    self._stop_tracking(notify_user=False, preserve_for_idle=True)
                    self.notify(
                        f"Tracking paused because synthetic input was detected "
                        f"(session #{entry_id})."
                    )
            return

        if self._stopped_due_to_synthetic_input:
            self._stopped_due_to_synthetic_input = False
            if (
                self._resume_after_idle
                and not self.tracking
                and not self._stopped_due_to_pattern
            ):
                self._resume_after_idle = False
                self.start_tracking()
                self.notify("Synthetic input ended. Tracking resumed.")

    def start_tracking(self, icon=None, item=None):
        if not self._start_lock.acquire(blocking=False):
            return
        try:
            self._start_tracking()
        finally:
            self._start_lock.release()

    def _start_tracking(self):
        if (
            self.tracking
            or self._stopped_due_to_pattern
            or self._stopped_due_to_synthetic_input
        ):
            return

        try:
            if not self.token or not self.validate_token():
                self.login()

            ip_address = self.get_system_ip()
            resp = requests.post(
                f"{BACKEND_URL}/time-entries/start",
                json={"ip_address": ip_address},
                
                headers=self.auth_headers(),
                timeout=10,
            )
            try:
                resp.raise_for_status()
            except requests.exceptions.HTTPError:
                detail = self._get_error_detail(resp)
                if resp.status_code == 400 and "already active" in str(detail).lower():
                    print("Tracking session already active on the backend. Syncing local state.")
                    self.sync_active_entry()
                    return
                if resp.status_code == 401:
                    print("Start Tracking auth failed. Please log in again.")
                    self.delete_token()
                    self.login()
                    resp = requests.post(
                        f"{BACKEND_URL}/time-entries/start",
                        json={"ip_address": ip_address},
                        headers=self.auth_headers(),
                        timeout=10,
                    )
                    resp.raise_for_status()
                else:
                    raise
        except requests.exceptions.RequestException as e:
            self.notify(f"Could not reach the server — tracking not started. ({e.__class__.__name__})")
            return
        except SystemExit:
            return
        except Exception as e:
            self.notify(f"Could not start tracking: {e}")
            return

        self.active_entry_id = resp.json()["id"]
        self.tracking = True
        self._idle = False
        try:
            self._send_heartbeat()
        except Exception as e:
            print(f"Initial heartbeat failed: {e}")
        self._start_worker()
        self._update_menu()
        self.notify(f"Tracking started (IP {ip_address})")

    def stop_tracking(self, icon=None, item=None):
        self._stop_tracking()

    def _stop_tracking(self, notify_user=True, preserve_for_idle=False):
        if not self.tracking:
            if not preserve_for_idle:
                self._resume_after_idle = False
                self._stopped_due_to_pattern = False
                self._stopped_due_to_synthetic_input = False
            return
        if not preserve_for_idle:
            self._stopped_due_to_pattern = False
            self._stopped_due_to_synthetic_input = False
        self._resume_after_idle = preserve_for_idle
        self.tracking = False
        self._stop_event.set()
        if self._worker_thread:
            self._worker_thread.join(timeout=5)

        entry_id = self.active_entry_id
        try:
            resp = requests.post(
                f"{BACKEND_URL}/time-entries/{entry_id}/stop",
                headers=self.auth_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            if notify_user:
                if preserve_for_idle:
                    self.notify(f"Tracking paused (session #{entry_id})")
                else:
                    self.notify(f"Tracking stopped (session #{entry_id})")
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 401:
                self._handle_unauthorized()
            else:
                if notify_user:
                    self.notify(f"Tracking stopped locally, but the server didn't confirm it "
                                f"(HTTP {exc.response.status_code if exc.response else '?'}).")
        except requests.exceptions.RequestException as e:
            if notify_user:
                self.notify(f"Tracking stopped locally, but couldn't reach the server to confirm it "
                            f"({e.__class__.__name__}). It may still show as active on the dashboard.")

        self.active_entry_id = None
        self._update_menu()

    def _tracking_loop(self):
        elapsed = 0
        heartbeat_elapsed = 0
        while not self._stop_event.is_set():
            # sleep in 1s ticks so Stop reacts quickly instead of waiting a full interval
            if self._stop_event.wait(timeout=1):
                break
            elapsed += 1
            heartbeat_elapsed += 1
            if heartbeat_elapsed >= 10:
                heartbeat_elapsed = 0
                try:
                    self._send_heartbeat()
                except Exception as e:
                    print(f"Heartbeat failed: {e}")
            if heartbeat_elapsed >= 10 and self.active_entry_id:
                heartbeat_elapsed = 0
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/time-entries/{self.active_entry_id}/heartbeat",
                        json={"is_idle": False},
                        headers=self.auth_headers(),
                        timeout=10,
                    )
                    response.raise_for_status()
                except requests.exceptions.RequestException as exc:
                    self._log(f"Heartbeat failed: {exc}")
            if elapsed >= self.screenshot_interval_seconds:
                elapsed = 0
                try:
                    self._capture_and_upload()
                except Exception as e:
                    self._log(f"Screenshot failed: {type(e).__name__}: {e}")
                    self.notify(f"Screenshot failed: {e}")

    def _send_heartbeat(self):
        resp = requests.post(
            f"{BACKEND_URL}/time-entries/{self.active_entry_id}/heartbeat",
            json={"is_idle": self._idle},
            headers=self.auth_headers(),
            timeout=10,
        )
        if resp.status_code == 401:
            self._handle_unauthorized()
            return
        resp.raise_for_status()

    def _command_loop(self):
        request_file = os.path.join(DATA_DIR, "start_tracking.request")
        while True:
            if os.path.exists(request_file):
                try:
                    os.remove(request_file)
                except OSError:
                    pass
                if not self.tracking:
                    self.start_tracking()
            time.sleep(1)

    def _capture_and_upload(self):
        image_bytes = self.capture_screenshot_bytes()
        if not image_bytes:
            raise RuntimeError("Screen capture returned no image data")
        ip_address = self.get_system_ip()
        self._drain_pending_uploads()
        files = {"file": (f"shot_{int(time.time())}.jpg", image_bytes, "image/jpeg")}
        data = {"time_entry_id": self.active_entry_id, "ip_address": ip_address}
        try:
            resp = requests.post(
                f"{BACKEND_URL}/screenshots", data=data, files=files,
                headers=self.auth_headers(), timeout=30,
            )
        except requests.exceptions.RequestException:
            self._queue_upload(image_bytes, data)
            raise
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError:
            if resp.status_code == 401:
                self._handle_unauthorized()
            raise
        captured_at = datetime.now(timezone.utc).astimezone().strftime("%I:%M %p")
        if SCREENSHOT_NOTIFICATIONS_ENABLED:
            self.notify(f"Screenshot captured at {captured_at} (IP {ip_address})")

    def _pending_upload_dir(self):
        path = os.path.join(DATA_DIR, "pending_screenshots")
        os.makedirs(path, exist_ok=True)
        return path

    def _queue_upload(self, image_bytes, data):
        filename = f"{int(time.time() * 1000)}.jpg"
        path = os.path.join(self._pending_upload_dir(), filename)
        with open(path, "wb") as output:
            output.write(image_bytes)
        with open(f"{path}.json", "w", encoding="utf-8") as metadata:
            json.dump(data, metadata)

    def _drain_pending_uploads(self):
        pending_dir = self._pending_upload_dir()
        for path in sorted(
            os.path.join(pending_dir, name)
            for name in os.listdir(pending_dir)
            if name.endswith(".jpg")
        )[:10]:
            metadata_path = f"{path}.json"
            if not os.path.exists(metadata_path):
                continue
            try:
                with open(metadata_path, encoding="utf-8") as metadata:
                    data = json.load(metadata)
                with open(path, "rb") as image:
                    response = requests.post(
                        f"{BACKEND_URL}/screenshots", data=data,
                        files={"file": (os.path.basename(path), image, "image/jpeg")},
                        headers=self.auth_headers(), timeout=30,
                    )
                response.raise_for_status()
                os.remove(path)
                os.remove(metadata_path)
            except (OSError, requests.exceptions.RequestException):
                break

    # ---------- Tray icon ----------

    def _make_icon_image(self, color):
        img = Image.new("RGB", (64, 64), color)
        return img

    def _update_menu(self):
        if self.icon:
            self.icon.icon = self._make_icon_image("green" if self.tracking else "gray")
            self.icon.menu = self._build_menu()

    def _build_menu(self):
        return pystray.Menu(
            Item("Start Tracking", self.start_tracking, enabled=not self.tracking),
            Item("Stop Tracking", self.stop_tracking, enabled=self.tracking),
            Item("Quit", self.quit),
        )

    def quit(self, icon=None, item=None):
        if self.tracking:
            self.stop_tracking()
        if self.icon:
            self.icon.stop()

    def run(self):
        if not _acquire_single_instance():
            print("Org Tracker is already running.")
            return
        self.load_token()
        if self.token and not self.validate_token():
            # Expired tokens must fall back to the login window even when the
            # agent normally runs without a console.
            self.delete_token()
        if not self.token:
            self.login()

        if not SILENT_MODE:
            self.icon = pystray.Icon(
                "org-tracker",
                self._make_icon_image("gray"),
                "Org Tracker (stopped)",
                menu=self._build_menu(),
            )
        self._start_activity_monitor()
        self.fetch_settings()
        self.sync_active_entry()
        if AUTO_START_TRACKING and not self.tracking:
            self.start_tracking()
        self._command_thread = threading.Thread(target=self._command_loop, daemon=True)
        self._command_thread.start()
        self._settings_thread = threading.Thread(target=self._settings_loop, daemon=True)
        self._settings_thread.start()
        if SILENT_MODE:
            threading.Event().wait()
        else:
            print("Agent started. Look for the tray icon in the notification area.")
            self.icon.run()


if __name__ == "__main__":
    try:
        TrackerAgent().run()
    except Exception:
        # Running via pythonw.exe means there's no console for a crash to
        # print to — without this, a startup failure looks like "nothing
        # happened" with zero clues why. Always leave a trail on disk.
        log_path = os.path.join(DATA_DIR, "agent_error.log")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n--- crash at {datetime.now(timezone.utc).isoformat()} ---\n")
                f.write(traceback.format_exc())
        except Exception:
            pass
        raise
 