# -*- coding: utf-8 -*-
"""Context menu: remove library entry without deleting media files."""

from __future__ import annotations

import xbmc
import xbmcaddon
import xbmcgui

from lib.addon_guard import ADDON_ID, is_addon_available
from lib.context_item import get_context_item, get_context_label
from lib.library_remove import remove_from_library
from lib.settings import addon_name, read_settings

_ADDON = xbmcaddon.Addon()


def main() -> None:
    if not is_addon_available():
        xbmc.log(f"[{ADDON_ID}] context remove ignored: add-on not installed", xbmc.LOGINFO)
        return

    item_type, item_id = get_context_item()
    if not item_type or not item_id:
        xbmcgui.Dialog().notification(
            addon_name(),
            _ADDON.getLocalizedString(32075),
            xbmcgui.NOTIFICATION_ERROR,
            4000,
        )
        return

    label = get_context_label() or f"{item_type} #{item_id}"
    if not xbmcgui.Dialog().yesno(
        _ADDON.getLocalizedString(32070),
        _ADDON.getLocalizedString(32071) % label,
    ):
        return

    settings = read_settings()
    ok, detail = remove_from_library(item_type, item_id, debug=settings.debug_log)
    if ok:
        xbmcgui.Dialog().notification(
            addon_name(),
            _ADDON.getLocalizedString(32072) % label,
            xbmcgui.NOTIFICATION_INFO,
            5000,
        )
        return

    xbmcgui.Dialog().ok(
        addon_name(),
        _ADDON.getLocalizedString(32073) % (label, detail),
    )


if __name__ == "__main__":
    xbmc.log(f"[{ADDON_ID}] context remove triggered", xbmc.LOGINFO)
    try:
        if is_addon_available():
            main()
    except RuntimeError:
        xbmc.log(f"[{ADDON_ID}] context remove ignored: add-on unavailable", xbmc.LOGINFO)
    except Exception as exc:
        xbmc.log(f"[{ADDON_ID}] context remove error: {exc}", xbmc.LOGERROR)
        try:
            xbmcgui.Dialog().ok(addon_name(), _ADDON.getLocalizedString(32073) % ("", exc))
        except RuntimeError:
            pass
