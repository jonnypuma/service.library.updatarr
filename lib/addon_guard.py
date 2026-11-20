"""Check whether this add-on is still installed and usable."""

from __future__ import annotations

import xbmcaddon

ADDON_ID = "service.library.updatarr"


def is_addon_available(addon_id: str = ADDON_ID) -> bool:
    try:
        xbmcaddon.Addon(addon_id)
        return True
    except RuntimeError:
        return False
