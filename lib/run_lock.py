"""Cross-invocation run lock to prevent overlapping Library Updatarr runs."""

from __future__ import annotations

import threading
import time

import xbmcgui

_LOCK_PROPERTY = "service.library.updatarr.lock"
_HOME_WINDOW_ID = 10000
_THREAD_LOCK = threading.Lock()
_IN_PROCESS_HELD = False


def _home_window() -> xbmcgui.Window | None:
    try:
        return xbmcgui.Window(_HOME_WINDOW_ID)
    except (AttributeError, RuntimeError, TypeError):
        return None


def acquire_run_lock(scope: str) -> bool:
    """Acquire the run lock; returns False if another run is active."""
    global _IN_PROCESS_HELD
    with _THREAD_LOCK:
        if _IN_PROCESS_HELD:
            return False
        window = _home_window()
        if window is not None and window.getProperty(_LOCK_PROPERTY):
            return False
        _IN_PROCESS_HELD = True
        if window is not None:
            window.setProperty(_LOCK_PROPERTY, f"{scope}:{int(time.time())}")
        return True


def release_run_lock() -> None:
    """Release the run lock."""
    global _IN_PROCESS_HELD
    with _THREAD_LOCK:
        _IN_PROCESS_HELD = False
        window = _home_window()
        if window is not None:
            window.clearProperty(_LOCK_PROPERTY)
