"""Paginated VideoLibrary queries."""

from __future__ import annotations

import xbmc
import xbmcgui

from lib.kodi_fields import SEASON_GET_PROPERTIES, SEASON_LIST_PROPERTIES, TVSHOW_GET_PROPERTIES
from lib.jsonrpc import jsonrpc, log
from lib.models import LibraryItem
from lib.settings import UpdatarrSettings
from lib.verbose_log import verbose_log


class ScanCanceled(Exception):
    """Raised when the user cancels a library scan via DialogProgress."""


def _check_cancel(
    progress: xbmcgui.DialogProgress | None,
    monitor: xbmc.Monitor | None = None,
) -> None:
    if (progress and progress.iscanceled()) or (monitor and monitor.abortRequested()):
        raise ScanCanceled()


def _update_scan_progress(
    progress: xbmcgui.DialogProgress | None,
    message: str,
    *,
    percent: int = 0,
) -> None:
    if progress:
        progress.update(percent, message)

MOVIE_PROPERTIES = ["art", "plot", "title", "file", "rating", "cast", "uniqueid", "imdbnumber"]
TVSHOW_PROPERTIES = TVSHOW_GET_PROPERTIES
EPISODE_PROPERTIES = [
    "art",
    "plot",
    "title",
    "file",
    "season",
    "episode",
    "showtitle",
    "rating",
    "cast",
]
SEASON_PROPERTIES = SEASON_GET_PROPERTIES


def _movie_from_payload(payload: dict) -> LibraryItem:
    return LibraryItem(
        item_type="movie",
        item_id=int(payload.get("movieid", 0)),
        title=str(payload.get("title") or ""),
        file_path=str(payload.get("file") or ""),
        plot=str(payload.get("plot") or ""),
        art=dict(payload.get("art") or {}),
        extra={
            "rating": payload.get("rating"),
            "cast": payload.get("cast"),
            "uniqueid": payload.get("uniqueid"),
            "imdbnumber": payload.get("imdbnumber"),
        },
    )


def _tvshow_from_payload(payload: dict) -> LibraryItem:
    return LibraryItem(
        item_type="tvshow",
        item_id=int(payload.get("tvshowid", 0)),
        title=str(payload.get("title") or ""),
        file_path=str(payload.get("file") or ""),
        plot=str(payload.get("plot") or ""),
        art=dict(payload.get("art") or {}),
        extra={
            "rating": payload.get("rating"),
            "cast": payload.get("cast"),
            "uniqueid": payload.get("uniqueid"),
        },
    )


def _episode_from_payload(payload: dict, tvshowid: int = 0) -> LibraryItem:
    return LibraryItem(
        item_type="episode",
        item_id=int(payload.get("episodeid", 0)),
        title=str(payload.get("title") or ""),
        file_path=str(payload.get("file") or ""),
        plot=str(payload.get("plot") or ""),
        art=dict(payload.get("art") or {}),
        season=int(payload.get("season") or 0),
        episode=int(payload.get("episode") or 0),
        showtitle=str(payload.get("showtitle") or ""),
        tvshowid=tvshowid or int(payload.get("tvshowid") or 0),
        extra={
            "rating": payload.get("rating"),
            "cast": payload.get("cast"),
        },
    )


def _paginated_get(
    method: str,
    result_key: str,
    properties: list[str],
    settings: UpdatarrSettings,
    extra_params: dict | None = None,
    *,
    progress: xbmcgui.DialogProgress | None = None,
    monitor: xbmc.Monitor | None = None,
    progress_label: str = "",
) -> list[dict]:
    items: list[dict] = []
    start = 0
    batch = settings.batch_size

    while True:
        _check_cancel(progress, monitor)

        params = {
            "properties": properties,
            "limits": {"start": start, "end": start + batch},
            "sort": {"order": "ascending", "method": "title", "ignorearticle": True},
        }
        if extra_params:
            params.update(extra_params)

        result = jsonrpc(method, params, debug=settings.debug_log)
        batch_items = result.get(result_key, [])
        if not batch_items:
            break

        items.extend(batch_items)
        if progress_label:
            _update_scan_progress(
                progress,
                f"{progress_label} ({len(items)})",
                percent=0,
            )

        if len(batch_items) < batch:
            break
        start += batch

    return items


def fetch_movies(
    settings: UpdatarrSettings,
    *,
    progress: xbmcgui.DialogProgress | None = None,
    monitor: xbmc.Monitor | None = None,
) -> list[LibraryItem]:
    _update_scan_progress(progress, "Scanning movies…")
    payloads = _paginated_get(
        "VideoLibrary.GetMovies",
        "movies",
        MOVIE_PROPERTIES,
        settings,
        progress=progress,
        monitor=monitor,
        progress_label="Scanning movies",
    )
    return [_movie_from_payload(p) for p in payloads if p.get("movieid")]


def fetch_tvshows(
    settings: UpdatarrSettings,
    *,
    progress: xbmcgui.DialogProgress | None = None,
    monitor: xbmc.Monitor | None = None,
) -> list[LibraryItem]:
    _update_scan_progress(progress, "Scanning TV shows…")
    payloads = _paginated_get(
        "VideoLibrary.GetTVShows",
        "tvshows",
        TVSHOW_PROPERTIES,
        settings,
        progress=progress,
        monitor=monitor,
        progress_label="Scanning TV shows",
    )
    return [_tvshow_from_payload(p) for p in payloads if p.get("tvshowid")]


def fetch_episodes_for_show(
    tvshowid: int,
    settings: UpdatarrSettings,
    *,
    progress: xbmcgui.DialogProgress | None = None,
    monitor: xbmc.Monitor | None = None,
) -> list[LibraryItem]:
    payloads = _paginated_get(
        "VideoLibrary.GetEpisodes",
        "episodes",
        EPISODE_PROPERTIES,
        settings,
        extra_params={"tvshowid": tvshowid},
        progress=progress,
        monitor=monitor,
    )
    return [_episode_from_payload(p, tvshowid) for p in payloads if p.get("episodeid")]


def fetch_all_episodes(
    settings: UpdatarrSettings,
    *,
    progress: xbmcgui.DialogProgress | None = None,
    monitor: xbmc.Monitor | None = None,
    shows: list[LibraryItem] | None = None,
) -> list[LibraryItem]:
    episodes: list[LibraryItem] = []
    show_list = shows if shows is not None else fetch_tvshows(settings, progress=progress, monitor=monitor)
    total = len(show_list)

    for index, show in enumerate(show_list):
        _check_cancel(progress, monitor)
        if total:
            percent = int((index / total) * 100)
            label = show.title or f"Show {show.item_id}"
            _update_scan_progress(
                progress,
                f"Scanning episodes ({index + 1}/{total}): {label}",
                percent=percent,
            )
        episodes.extend(fetch_episodes_for_show(show.item_id, settings, progress=progress, monitor=monitor))

    return episodes


def _season_from_payload(payload: dict, tvshowid: int = 0) -> LibraryItem:
    return LibraryItem(
        item_type="season",
        item_id=int(payload.get("seasonid") or 0),
        title=str(payload.get("title") or f"Season {payload.get('season', 0)}"),
        file_path="",
        plot=str(payload.get("plot") or ""),
        art=dict(payload.get("art") or {}),
        season=int(payload.get("season") or 0),
        tvshowid=int(payload.get("tvshowid") or tvshowid),
    )


def fetch_item_details(item: LibraryItem, settings: UpdatarrSettings) -> LibraryItem | None:
    method_map = {
        "movie": ("VideoLibrary.GetMovieDetails", "moviedetails", MOVIE_PROPERTIES),
        "tvshow": ("VideoLibrary.GetTVShowDetails", "tvshowdetails", TVSHOW_PROPERTIES),
        "season": ("VideoLibrary.GetSeasonDetails", "seasondetails", SEASON_PROPERTIES),
        "episode": ("VideoLibrary.GetEpisodeDetails", "episodedetails", EPISODE_PROPERTIES),
    }
    mapping = method_map.get(item.item_type)
    if not mapping:
        return None

    method, result_key, properties = mapping
    id_key = item.item_dict()
    if not id_key:
        return None

    result = jsonrpc(
        method,
        {list(id_key.keys())[0]: list(id_key.values())[0], "properties": properties},
        debug=settings.debug_log,
    )
    payload = result.get(result_key)
    if not payload:
        return None

    if item.item_type == "movie":
        return _movie_from_payload(payload)
    if item.item_type == "tvshow":
        return _tvshow_from_payload(payload)
    if item.item_type == "season":
        return _season_from_payload(payload, item.tvshowid)
    if item.item_type == "episode":
        return _episode_from_payload(payload, item.tvshowid)
    return None


def fetch_season_by_id(seasonid: int, tvshowid: int, settings: UpdatarrSettings) -> LibraryItem | None:
    if seasonid <= 0:
        return None
    result = jsonrpc(
        "VideoLibrary.GetSeasonDetails",
        {
            "seasonid": seasonid,
            "properties": SEASON_PROPERTIES,
        },
        debug=settings.debug_log,
    )
    payload = result.get("seasondetails")
    if not payload:
        return None

    return _season_from_payload(payload, tvshowid)


def fetch_seasons_for_show(
    tvshowid: int,
    settings: UpdatarrSettings,
    *,
    progress: xbmcgui.DialogProgress | None = None,
    monitor: xbmc.Monitor | None = None,
) -> list[LibraryItem]:
    """Return all season library items for a TV show."""
    _check_cancel(progress, monitor)
    result = jsonrpc(
        "VideoLibrary.GetSeasons",
        {
            "tvshowid": tvshowid,
            "properties": SEASON_LIST_PROPERTIES,
        },
        debug=settings.debug_log,
    )
    seasons: list[LibraryItem] = []
    for payload in result.get("seasons", []):
        _check_cancel(progress, monitor)
        season_num = int(payload.get("season") or 0)
        seasonid = int(payload.get("seasonid") or 0)
        if season_num <= 0 or seasonid <= 0:
            verbose_log(
                settings,
                f"Skip season entry for show {tvshowid}: season={season_num} seasonid={seasonid}",
            )
            continue
        seasons.append(_season_from_payload(payload, tvshowid))
    return seasons


def _episodes_for_season(
    tvshowid: int,
    season_num: int,
    settings: UpdatarrSettings,
    *,
    progress: xbmcgui.DialogProgress | None = None,
) -> list[LibraryItem]:
    return [
        ep
        for ep in fetch_episodes_for_show(tvshowid, settings, progress=progress)
        if ep.season == season_num
    ]


def _context_tvshow_items(
    tvshowid: int,
    show: LibraryItem,
    settings: UpdatarrSettings,
    *,
    progress: xbmcgui.DialogProgress | None = None,
) -> list[LibraryItem]:
    """Show, then seasons, then episodes when child refresh is enabled."""
    items = [show]
    if not settings.context_refresh_episodes:
        return items
    seasons = fetch_seasons_for_show(tvshowid, settings, progress=progress)
    episodes = fetch_episodes_for_show(tvshowid, settings, progress=progress)
    verbose_log(
        settings,
        f"Context TV show {show.title}: 1 show, {len(seasons)} season(s), {len(episodes)} episode(s)",
    )
    items.extend(seasons)
    items.extend(episodes)
    return items


def _context_season_items(
    season_item: LibraryItem,
    settings: UpdatarrSettings,
    *,
    progress: xbmcgui.DialogProgress | None = None,
) -> list[LibraryItem]:
    """Season and episodes in that season only."""
    items = [season_item]
    if season_item.tvshowid and season_item.season > 0:
        items.extend(
            _episodes_for_season(
                season_item.tvshowid,
                season_item.season,
                settings,
                progress=progress,
            )
        )
    return items


def fetch_items_for_scope(
    settings: UpdatarrSettings,
    *,
    scope: str = "full",
    item_type: str | None = None,
    item_id: int | None = None,
    progress: xbmcgui.DialogProgress | None = None,
    monitor: xbmc.Monitor | None = None,
) -> list[LibraryItem]:
    items: list[LibraryItem] = []

    if scope == "context":
        _check_cancel(progress, monitor)
        if not item_type or not item_id:
            return []
        if item_type == "movie":
            details = fetch_item_details(LibraryItem("movie", item_id), settings)
            return [details] if details else []
        if item_type == "tvshow":
            details = fetch_item_details(LibraryItem("tvshow", item_id), settings)
            if not details:
                return []
            return _context_tvshow_items(item_id, details, settings, progress=progress)
        if item_type == "episode":
            details = fetch_item_details(LibraryItem("episode", item_id), settings)
            return [details] if details else []
        if item_type == "season":
            details = fetch_item_details(LibraryItem("season", item_id), settings)
            if not details:
                return []
            return _context_season_items(details, settings, progress=progress)
        log(f"Context scope ignored: unsupported item_type={item_type}")
        return []

    if settings.process_movies:
        items.extend(fetch_movies(settings, progress=progress, monitor=monitor))
    if settings.process_tvshows:
        shows = fetch_tvshows(settings, progress=progress, monitor=monitor)
        items.extend(shows)
        for show in shows:
            items.extend(fetch_seasons_for_show(show.item_id, settings, progress=progress, monitor=monitor))
    if settings.process_episodes:
        shows = (
            [item for item in items if item.item_type == "tvshow"]
            if settings.process_tvshows
            else fetch_tvshows(settings, progress=progress, monitor=monitor)
        )
        items.extend(fetch_all_episodes(settings, progress=progress, monitor=monitor, shows=shows))

    log(f"Fetched {len(items)} library item(s) for scope={scope}")
    return items
