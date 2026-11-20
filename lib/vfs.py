"""Kodi VFS helpers (xbmcvfs has no isdir/isfile)."""

from __future__ import annotations

import os
import stat

import xbmcvfs


def _entry_name(entry) -> str:
    if isinstance(entry, (list, tuple)):
        return ""
    if isinstance(entry, bytes):
        entry = entry.decode("utf-8", errors="replace")
    return str(entry).rstrip("/\\")


def vfs_listdir(path: str) -> list[tuple[str, bool]]:
    """List directory entries as (name, is_dir) pairs.

    Kodi returns (dirs, files) tuples from xbmcvfs.listdir, not a flat list.
    """
    try:
        raw = xbmcvfs.listdir(path)
    except (OSError, RuntimeError, ValueError):
        return []
    if not raw:
        return []

    entries: list[tuple[str, bool]] = []
    if isinstance(raw, tuple) and len(raw) == 2:
        dirs, files = raw
        for name in dirs or []:
            clean = _entry_name(name)
            if clean and clean not in (".", ".."):
                entries.append((clean, True))
        for name in files or []:
            clean = _entry_name(name)
            if clean and clean not in (".", ".."):
                entries.append((clean, False))
        return entries

    iterable = raw if isinstance(raw, (list, tuple)) else [raw]
    for entry in iterable:
        clean = _entry_name(entry)
        if not clean or clean in (".", ".."):
            continue
        full = os.path.join(path, clean).replace("\\", "/")
        entries.append((clean, vfs_isdir(full)))
    return entries


def vfs_isdir(path: str) -> bool:
    if not path:
        return False
    if not xbmcvfs.exists(path):
        return False
    try:
        st = xbmcvfs.Stat(path)
        mode = st.st_mode()
        if callable(mode):
            mode = mode()
        return bool(stat.S_ISDIR(mode))
    except (OSError, RuntimeError, ValueError, AttributeError, TypeError):
        return False
    return False
