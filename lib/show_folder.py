"""Resolve the on-disk TV show folder when Kodi's file path is wrong."""

from __future__ import annotations

import os
import re

import xbmc
import xbmcvfs

from lib.jsonrpc import log
from lib.models import LibraryItem
from lib.scanner import fetch_episodes_for_show, fetch_item_details
from lib.settings import UpdatarrSettings
from lib.verbose_log import verbose_log
from lib.vfs import vfs_isdir, vfs_listdir

_SHOW_FOLDER_CACHE: dict[int, str] = {}


def clear_show_folder_cache() -> None:
    _SHOW_FOLDER_CACHE.clear()
_TVSHOW_NFO_NAME = "tvshow.nfo"
_FLAT_SEASON_NFO_RE = re.compile(r"^season\d+\.nfo$", re.IGNORECASE)
_MAX_PARENT_WALK = 6


def _kodi_path(path: str) -> str:
    return path.replace("\\", "/")


def _join_path(base: str, name: str) -> str:
    return _kodi_path(os.path.join(base, name.rstrip("/\\")))


def _normalize_show_path(file_path: str) -> str:
    if not file_path or file_path.startswith("videodb://"):
        return ""
    path = file_path.rstrip("/\\")
    if os.path.splitext(path)[1]:
        return os.path.dirname(path)
    return path


def _tvshow_nfo_path(folder: str) -> str:
    return _join_path(folder, _TVSHOW_NFO_NAME)


def _has_tvshow_nfo(folder: str) -> bool:
    return bool(folder) and xbmcvfs.exists(_tvshow_nfo_path(folder))


def _has_season_nfo(folder: str) -> bool:
    if not folder or not vfs_isdir(folder):
        return False
    if xbmcvfs.exists(_join_path(folder, "season.nfo")):
        return True
    for name, is_dir in vfs_listdir(folder):
        if not is_dir and _FLAT_SEASON_NFO_RE.match(name):
            return True
    return False


def _parent_dir(path: str) -> str:
    parent = os.path.dirname(path.rstrip("/\\"))
    if not parent or _kodi_path(parent) == _kodi_path(path):
        return ""
    return parent


def _walk_up_for_show_folder(start_dir: str, settings: UpdatarrSettings) -> str:
    """Walk parents from an episode folder, looking for tvshow.nfo and season.nfo markers."""
    current = start_dir
    for depth in range(_MAX_PARENT_WALK):
        if not current:
            break

        has_tvshow = _has_tvshow_nfo(current)
        has_season = _has_season_nfo(current)
        verbose_log(
            settings,
            f"Show folder walk depth {depth} at {_kodi_path(current)}: "
            f"tvshow.nfo={'yes' if has_tvshow else 'no'} season.nfo={'yes' if has_season else 'no'}",
        )

        if has_tvshow:
            return current

        if has_season:
            parent = _parent_dir(current)
            if parent and _has_tvshow_nfo(parent):
                verbose_log(
                    settings,
                    f"Show folder from parent of season folder: {_kodi_path(parent)}",
                )
                return parent

        current = _parent_dir(current)

    return ""


def _folder_from_episodes(tvshowid: int, settings: UpdatarrSettings) -> str:
    episodes = fetch_episodes_for_show(tvshowid, settings)
    for episode in episodes:
        if not episode.file_path or episode.file_path.startswith("videodb://"):
            continue
        episode_dir = os.path.dirname(episode.file_path)
        found = _walk_up_for_show_folder(episode_dir, settings)
        if found:
            return found
    return ""


def _folder_from_title_subdir(base: str, title: str) -> str:
    if not base or not title:
        return ""
    candidate = _join_path(base, title)
    if _has_tvshow_nfo(candidate):
        return candidate
    return ""


def _folder_from_subdir_scan(base: str, settings: UpdatarrSettings) -> str:
    if not base or not vfs_isdir(base):
        return ""

    for name, is_dir in vfs_listdir(base):
        if not is_dir:
            continue
        candidate = _join_path(base, name)
        if _has_tvshow_nfo(candidate):
            verbose_log(settings, f"Show folder resolved via subdir scan: {_kodi_path(candidate)}")
            return candidate
    return ""


def is_suspect_tvshow_source_path(kodi_path: str, resolved_path: str) -> bool:
    """True when Kodi's stored path looks like a TV source root, not the show folder."""
    if not kodi_path or not resolved_path:
        return False
    kodi_norm = _kodi_path(kodi_path).rstrip("/")
    resolved_norm = _kodi_path(resolved_path).rstrip("/")
    if kodi_norm == resolved_norm:
        return False
    return not _has_tvshow_nfo(kodi_norm) and _has_tvshow_nfo(resolved_norm)


def tvshow_path_warning(show: LibraryItem, settings: UpdatarrSettings) -> str | None:
    """Return a warning when Kodi's tvshow.path likely breaks scraper refresh."""
    if show.item_type != "tvshow":
        return None
    kodi_path = _normalize_show_path(show.file_path)
    if not kodi_path:
        return None
    resolved = resolve_show_media_dir(show, settings)
    if not is_suspect_tvshow_source_path(kodi_path, resolved):
        return None
    return (
        f"Kodi tvshow.path is {_kodi_path(kodi_path)} but media is under {_kodi_path(resolved)}; "
        "scraper refresh may not read local season/show NFOs — use Kodi Information → Refresh, "
        "or remove and re-add the show so the stored path is corrected"
    )


def log_tvshow_path_warning(
    show: LibraryItem,
    settings: UpdatarrSettings,
    *,
    context: str = "",
) -> None:
    message = tvshow_path_warning(show, settings)
    if not message:
        return
    prefix = f"{context}: " if context else ""
    log(f"{prefix}{message}", xbmc.LOGWARNING)
    verbose_log(settings, f"[path] {prefix}{message}")


def _show_record_for_item(item: LibraryItem, settings: UpdatarrSettings) -> LibraryItem | None:
    if item.item_type == "tvshow":
        return item
    if item.tvshowid:
        return fetch_item_details(LibraryItem("tvshow", item.tvshowid), settings)
    return None


def resolve_show_media_dir(item: LibraryItem, settings: UpdatarrSettings) -> str:
    """Return the folder containing tvshow.nfo for a show/season, when possible."""
    show = _show_record_for_item(item, settings)
    if not show:
        return _normalize_show_path(item.file_path)

    tvshowid = show.item_id
    if tvshowid in _SHOW_FOLDER_CACHE:
        return _SHOW_FOLDER_CACHE[tvshowid]

    base = _normalize_show_path(show.file_path)
    resolved = ""

    if base and _has_tvshow_nfo(base):
        resolved = base
        verbose_log(settings, f"Show folder from Kodi file path: {_kodi_path(resolved)}")

    if not resolved and tvshowid:
        resolved = _folder_from_episodes(tvshowid, settings)
        if resolved:
            verbose_log(settings, f"Show folder resolved via episode paths: {_kodi_path(resolved)}")

    if not resolved and base and show.title:
        resolved = _folder_from_title_subdir(base, show.title)
        if resolved:
            verbose_log(
                settings,
                f"Show folder resolved via title subfolder '{show.title}': {_kodi_path(resolved)}",
            )

    if not resolved and base:
        resolved = _folder_from_subdir_scan(base, settings)

    if not resolved:
        resolved = base
        if base:
            verbose_log(
                settings,
                f"Show folder fallback to Kodi path (no tvshow.nfo found): {_kodi_path(base)}",
            )

    if tvshowid and resolved:
        _SHOW_FOLDER_CACHE[tvshowid] = resolved

    if show.item_type == "tvshow" and is_suspect_tvshow_source_path(base, resolved):
        log_tvshow_path_warning(show, settings, context="show folder resolve")

    return resolved
