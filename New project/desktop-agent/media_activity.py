"""
Detect whether media is actively playing in the foreground Windows app.

The implementation uses Windows System Media Transport Controls and fails
safe on unsupported platforms or when the optional integrations are absent.
"""
import asyncio
import sys


_MEDIA_APP_ALIASES = {
    "chrome": {"chrome", "googlechrome"},
    "msedge": {"msedge", "microsoftedge"},
    "firefox": {"firefox", "mozilla firefox"},
    "vlc": {"vlc", "videolan"},
    "wmplayer": {"wmplayer", "windows media player"},
    "spotify": {"spotify"},
}


def is_foreground_media_playing():
    if sys.platform != "win32":
        return False
    try:
        return asyncio.run(_windows_foreground_media_playing())
    except Exception:
        return False


async def _windows_foreground_media_playing():
    import psutil
    import win32gui
    import win32process
    from winsdk.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as MediaManager,
    )

    manager = await MediaManager.request_async()
    session = manager.get_current_session()
    if session is None:
        return False

    playback_info = session.get_playback_info()
    if playback_info is None or playback_info.playback_status != 4:
        return False

    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return False
    _, foreground_pid = win32process.GetWindowThreadProcessId(hwnd)
    if not foreground_pid:
        return False

    try:
        foreground_exe = psutil.Process(foreground_pid).name().lower()
    except Exception:
        return False

    app_id = (session.source_app_user_model_id or "").lower()
    return _media_app_matches_foreground_process(foreground_exe, app_id)


def _media_app_matches_foreground_process(foreground_exe, app_id):
    executable = foreground_exe.lower().removesuffix(".exe").replace(" ", "")
    media_identity = app_id.lower().replace(" ", "")
    if not executable or not media_identity:
        return False
    if executable in media_identity or media_identity in executable:
        return True
    return any(
        executable == known_name.replace(" ", "")
        and any(alias.replace(" ", "") in media_identity for alias in aliases)
        for known_name, aliases in _MEDIA_APP_ALIASES.items()
    )