"""Remove video library entries from Kodi without deleting media files."""

from __future__ import annotations

import xbmc

from lib.jsonrpc import jsonrpc, log


_SUPPORTED_TYPES = frozenset({"movie", "tvshow", "season", "episode", "musicvideo"})


def remove_from_library(item_type: str, item_id: int, *, debug: bool = False) -> tuple[bool, str]:
    """
    Remove a library entry from Kodi's database only (deletefile=False).

    Returns (ok, detail).
    """
    item_type = (item_type or "").strip().lower()
    if item_type not in _SUPPORTED_TYPES:
        return False, f"unsupported item type: {item_type or 'unknown'}"

    if item_id <= 0:
        return False, "invalid library id"

    params: dict = {"deletefile": False}

    if item_type == "movie":
        method = "VideoLibrary.RemoveMovie"
        params["movieid"] = item_id
    elif item_type == "tvshow":
        method = "VideoLibrary.RemoveTVShow"
        params["tvshowid"] = item_id
    elif item_type == "season":
        method = "VideoLibrary.RemoveSeason"
        params["seasonid"] = item_id
    elif item_type == "musicvideo":
        method = "VideoLibrary.RemoveMusicVideo"
        params["musicvideoid"] = item_id
    else:
        method = "VideoLibrary.RemoveEpisode"
        params["episodeid"] = item_id

    result = jsonrpc(method, params, debug=debug)
    if result.get("_error"):
        return False, f"{method} failed"

    log(f"Removed from library ({item_type} id={item_id}, files kept on disk)")
    return True, item_type
