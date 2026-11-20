"""Shared helpers for Kodi context menu entries."""

from __future__ import annotations

import xbmc


def get_context_item() -> tuple[str | None, int | None]:
    media_type = xbmc.getInfoLabel("ListItem.DBTYPE")
    dbid = xbmc.getInfoLabel("ListItem.DBID")
    if not media_type or not dbid:
        return None, None
    try:
        return media_type.strip().lower(), int(dbid)
    except (TypeError, ValueError):
        return None, None


def get_context_label() -> str:
    return xbmc.getInfoLabel("ListItem.Label") or ""
