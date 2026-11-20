# -*- coding: utf-8 -*-
"""Context menu entry for scoped library updates."""

from __future__ import annotations

import xbmc
import xbmcgui

from lib.addon_guard import ADDON_ID, is_addon_available
from lib.context_item import get_context_item, get_context_label
from lib.runner import run
from lib.settings import addon_name, localized


def main() -> None:
    if not is_addon_available():
        xbmc.log(f"[{ADDON_ID}] context ignored: add-on not installed", xbmc.LOGINFO)
        return

    item_type, item_id = get_context_item()
    if not item_type or not item_id:
        xbmcgui.Dialog().notification(
            addon_name(),
            localized(32075, "Could not determine library item."),
            xbmcgui.NOTIFICATION_ERROR,
            4000,
        )
        return

    label = get_context_label() or item_type
    if not xbmcgui.Dialog().yesno(
        addon_name(),
        localized(32061, "Fix missing metadata/artwork for:\n%s?") % label,
    ):
        return

    progress = xbmcgui.DialogProgress()
    progress.create(addon_name(), localized(32062, "Processing %s…") % label)

    try:
        result = run(
            scope="context",
            item_type=item_type,
            item_id=item_id,
            progress=progress,
        )
    finally:
        progress.close()

    if result.scan_canceled or result.canceled:
        return

    xbmcgui.Dialog().ok(addon_name(), result.summary_text())


if __name__ == "__main__":
    xbmc.log(f"[{ADDON_ID}] context menu triggered", xbmc.LOGINFO)
    try:
        if is_addon_available():
            main()
    except RuntimeError:
        xbmc.log(f"[{ADDON_ID}] context ignored: add-on unavailable", xbmc.LOGINFO)
    except Exception as exc:
        xbmc.log(f"[{ADDON_ID}] context error: {exc}", xbmc.LOGERROR)
        try:
            xbmcgui.Dialog().ok(addon_name(), localized(32068, "Error:\n%s") % exc)
        except RuntimeError:
            pass
