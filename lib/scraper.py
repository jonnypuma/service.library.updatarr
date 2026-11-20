"""Online scraper refresh via Kodi JSON-RPC."""

from __future__ import annotations

import xbmc

from lib.jsonrpc import jsonrpc, log
from lib.models import LibraryItem
from lib.scanner import fetch_item_details
from lib.settings import UpdatarrSettings
from lib.show_folder import log_tvshow_path_warning


def _warn_suspect_tvshow_path(item: LibraryItem, settings: UpdatarrSettings) -> None:
    show = item
    if item.item_type == "season" and item.tvshowid:
        show = fetch_item_details(LibraryItem("tvshow", item.tvshowid), settings) or show
    elif item.item_type != "tvshow":
        return
    if show and show.item_type == "tvshow":
        log_tvshow_path_warning(show, settings, context="before scraper refresh")


def refresh_item(item: LibraryItem, settings: UpdatarrSettings) -> bool:
    if not settings.enable_scraper_pass:
        return False

    if item.item_type in ("tvshow", "season"):
        _warn_suspect_tvshow_path(item, settings)

    item_dict = item.item_dict()
    if not item_dict:
        log(f"No refresh method for item type {item.item_type}", xbmc.LOGWARNING)
        return False

    if item.item_type == "movie":
        result = jsonrpc(
            "VideoLibrary.RefreshMovie",
            {
                "movieid": item.item_id,
                "ignorenfo": settings.ignore_nfo,
            },
            debug=settings.debug_log,
        )
    elif item.item_type == "tvshow":
        result = jsonrpc(
            "VideoLibrary.RefreshTVShow",
            {
                "tvshowid": item.item_id,
                "ignorenfo": settings.ignore_nfo,
                "refreshepisodes": settings.refresh_show_episodes,
            },
            debug=settings.debug_log,
        )
    elif item.item_type == "episode":
        result = jsonrpc(
            "VideoLibrary.RefreshEpisode",
            {
                "episodeid": item.item_id,
                "ignorenfo": settings.ignore_nfo,
            },
            debug=settings.debug_log,
        )
    elif item.item_type == "season" and item.tvshowid:
        result = jsonrpc(
            "VideoLibrary.RefreshTVShow",
            {
                "tvshowid": item.tvshowid,
                "ignorenfo": settings.ignore_nfo,
                "refreshepisodes": False,
            },
            debug=settings.debug_log,
        )
    else:
        return False

    if not result or result.get("_error"):
        log(f"Scraper refresh failed for {item.display_title}", xbmc.LOGWARNING)
        return False

    log(f"Triggered scraper refresh for {item.display_title}")
    return True
