"""Apply local artwork and NFO metadata."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

import xbmc
import xbmcvfs

from lib.jsonrpc import jsonrpc, log
from lib.kodi_fields import build_set_arts_params, sanitize_set_details
from lib.missing import missing_art_types, missing_metadata_fields
from lib.models import LibraryItem
from lib.settings import UpdatarrSettings
from lib.show_folder import resolve_show_media_dir
from lib.verbose_log import verbose_log
from lib.vfs import vfs_isdir, vfs_listdir

_ID_TAG_MAP = {
    "tvdbid": "tvdb",
    "imdbid": "imdb",
    "tmdbid": "tmdb",
    "tvmazeid": "tvmaze",
}

# Show root = depth 0; Season folders = 1; allow one more level for odd layouts.
SEASON_WALK_MAX_DEPTH = 3

_SEASON_NFO_INDEX: dict[str, list[tuple[str, int | None]]] = {}


def clear_season_nfo_index() -> None:
    _SEASON_NFO_INDEX.clear()


_ART_EXTENSIONS = (".jpg", ".png", ".jpeg")

_FLAT_SEASON_NFO_RE = re.compile(r"^season(\d+)\.nfo$", re.IGNORECASE)

_SEASON_ART_FILES = (
    ("poster", "poster.jpg"),
    ("fanart", "fanart.jpg"),
    ("thumb", "thumb.jpg"),
    ("banner", "banner.jpg"),
    ("landscape", "landscape.jpg"),
)

_SEASON_FLAT_ART_PARTS = (
    ("banner", "banner"),
    ("poster", "poster"),
    ("fanart", "fanart"),
    ("landscape", "landscape"),
    ("thumb", "thumb"),
)

# NFO <thumb aspect="..."> labels often differ from Kodi SetArt types (e.g. poster vs thumb).
_ART_URL_FALLBACKS: dict[str, tuple[str, ...]] = {
    "thumb": ("thumb", "poster", "characterart"),
    "fanart": ("fanart", "landscape", "banner", "poster"),
    "poster": ("poster", "thumb"),
    "banner": ("banner", "landscape", "poster"),
    "landscape": ("landscape", "banner", "fanart"),
}


def _show_folder_for_item(item: LibraryItem, settings: UpdatarrSettings) -> str:
    if item.item_type in ("tvshow", "season"):
        return resolve_show_media_dir(item, settings)

    if item.file_path and not item.file_path.startswith("videodb://"):
        if item.item_type in ("movie", "episode"):
            return os.path.dirname(item.file_path)
        return item.file_path

    return ""


def _kodi_path(path: str) -> str:
    return path.replace("\\", "/")


def _join_path(base: str, name: str) -> str:
    return _kodi_path(os.path.join(base, name.rstrip("/\\")))


def _path_depth_under(root: str, path: str) -> int:
    root_norm = _kodi_path(root).rstrip("/")
    path_norm = _kodi_path(path)
    if not path_norm.startswith(root_norm):
        return 999
    remainder = path_norm[len(root_norm) :].strip("/")
    if not remainder:
        return 0
    return remainder.count("/") + 1


def _file_stat_line(path: str) -> str:
    local = _kodi_path(path)
    try:
        if not xbmcvfs.exists(path):
            return f"{local} (missing)"
        stat = xbmcvfs.Stat(path)
        return f"{local} (size={stat.st_size()}, mtime={stat.st_mtime()})"
    except (OSError, RuntimeError, ValueError):
        return f"{local} (stat unavailable)"


def _walk_files(root: str, max_depth: int = SEASON_WALK_MAX_DEPTH) -> list[str]:
    """Return file paths under root up to max_depth levels below root."""
    if not root or not xbmcvfs.exists(root) or not vfs_isdir(root):
        return []

    files: list[str] = []

    def walk(current: str, depth: int) -> None:
        if depth > max_depth:
            return

        for name, is_dir in vfs_listdir(current):
            full = _join_path(current, name)
            if is_dir:
                walk(full, depth + 1)
            else:
                files.append(full)

    walk(root, 0)
    return files


def _parse_nfo(path: str) -> dict:
    if not xbmcvfs.exists(path):
        return {}

    try:
        handle = xbmcvfs.File(path)
        raw = handle.read()
        handle.close()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        root = ET.fromstring(raw)
    except (ET.ParseError, OSError, ValueError) as exc:
        log(f"Failed to parse NFO {path}: {exc}", xbmc.LOGWARNING)
        return {}

    data: dict = {}

    def text(tag: str) -> str | None:
        node = root.find(f"./{tag}")
        if node is not None and node.text and node.text.strip():
            return node.text.strip()
        return None

    for tag in ("title", "plot", "tagline", "mpaa", "studio", "premiered", "status"):
        value = text(tag)
        if value:
            data[tag] = value

    seasonplots: dict[int, str] = {}
    for node in root.findall("./seasonplot"):
        number = (node.attrib.get("number") or "").strip()
        if number.isdigit() and node.text and node.text.strip():
            seasonplots[int(number)] = node.text.strip()
    if seasonplots:
        data["seasonplots"] = seasonplots

    seasonnumber = text("seasonnumber")
    if seasonnumber and seasonnumber.isdigit():
        data["seasonnumber"] = int(seasonnumber)

    year = text("year")
    if year and year.isdigit():
        data["year"] = int(year)

    rating_node = root.find("./rating")
    if rating_node is not None:
        value_node = rating_node.find("./value") or rating_node.find("./rating")
        rating_text = (
            value_node.text.strip()
            if value_node is not None and value_node.text
            else (rating_node.text.strip() if rating_node.text else "")
        )
        if rating_text:
            try:
                data["rating"] = float(rating_text)
            except ValueError:
                pass

    if "rating" not in data:
        ratings_parent = root.find("./ratings")
        if ratings_parent is not None:
            chosen: ET.Element | None = None
            for rating_el in ratings_parent.findall("./rating"):
                if rating_el.attrib.get("default", "").lower() == "true":
                    chosen = rating_el
                    break
            if chosen is None:
                ratings = ratings_parent.findall("./rating")
                chosen = ratings[0] if ratings else None
            if chosen is not None:
                value_node = chosen.find("./value")
                if value_node is not None and value_node.text:
                    try:
                        data["rating"] = float(value_node.text.strip())
                    except ValueError:
                        pass

    genres = [g.text.strip() for g in root.findall("./genre") if g.text and g.text.strip()]
    if genres:
        data["genre"] = genres

    uniqueids: dict[str, str] = {}
    for node in root.findall("./uniqueid"):
        type_attr = node.attrib.get("type", "unknown")
        if node.text and node.text.strip():
            uniqueids[type_attr] = node.text.strip()
    for tag, uid_type in _ID_TAG_MAP.items():
        value = text(tag)
        if value:
            uniqueids.setdefault(uid_type, value)
    imdb = text("imdb")
    if imdb:
        uniqueids.setdefault("imdb", imdb)
    if uniqueids:
        data["uniqueid"] = uniqueids

    thumb_urls: dict[str, str] = {}
    season_thumb_urls: dict[tuple[int, str], str] = {}
    for node in root.findall("./thumb"):
        if not node.text or not node.text.strip():
            continue
        url = node.text.strip()
        if not url.lower().startswith(("http://", "https://")):
            continue
        aspect = (node.attrib.get("aspect") or "thumb").strip().lower()
        season_attr = (node.attrib.get("season") or "").strip()
        if season_attr.isdigit():
            season_thumb_urls[(int(season_attr), aspect)] = url
            continue
        thumb_urls[aspect] = url
    if thumb_urls:
        data["thumb_urls"] = thumb_urls
    if season_thumb_urls:
        data["season_thumb_urls"] = season_thumb_urls

    fanart_url = text("fanart")
    if fanart_url and fanart_url.lower().startswith(("http://", "https://")):
        thumb_urls.setdefault("fanart", fanart_url)
        data["thumb_urls"] = thumb_urls

    return data


def _season_number_for_nfo(path: str, nfo_data: dict) -> int | None:
    seasonnumber = nfo_data.get("seasonnumber")
    if isinstance(seasonnumber, int) and seasonnumber > 0:
        return seasonnumber

    base = os.path.basename(path)
    match = _FLAT_SEASON_NFO_RE.match(base)
    if match:
        return int(match.group(1))
    return None


def _index_season_nfos(show_dir: str, settings: UpdatarrSettings) -> list[tuple[str, int | None]]:
    if show_dir in _SEASON_NFO_INDEX:
        return _SEASON_NFO_INDEX[show_dir]

    indexed: list[tuple[str, int | None]] = []
    for file_path in _walk_files(show_dir):
        base = os.path.basename(file_path)
        base_lower = base.lower()
        if base_lower == "season.nfo" or _FLAT_SEASON_NFO_RE.match(base):
            nfo_data = _parse_nfo(file_path)
            season_num = _season_number_for_nfo(file_path, nfo_data)
            indexed.append((file_path, season_num))
            verbose_log(
                settings,
                f"Season NFO discovered under {show_dir}: {_file_stat_line(file_path)}"
                + (f" seasonnumber={season_num}" if season_num is not None else " seasonnumber=unknown"),
            )

    _SEASON_NFO_INDEX[show_dir] = indexed
    return indexed


def _pick_season_nfo(
    show_dir: str,
    season: int,
    settings: UpdatarrSettings,
) -> tuple[str | None, list[tuple[str, int | None]]]:
    indexed = _index_season_nfos(show_dir, settings)
    matches = [(path, num) for path, num in indexed if num == season]
    if not matches:
        return None, indexed

    matches.sort(key=lambda entry: _path_depth_under(show_dir, entry[0]))
    chosen = matches[0][0]
    if len(matches) > 1:
        verbose_log(
            settings,
            f"Season {season}: multiple season.nfo matches; using shallowest {_kodi_path(chosen)}",
        )
    return chosen, indexed


def _season_nfo_search_summary(
    show_dir: str,
    season: int,
    indexed: list[tuple[str, int | None]],
) -> str:
    if not show_dir:
        return "(no show folder)"
    lines = [f"walked {_kodi_path(show_dir)} depth<={SEASON_WALK_MAX_DEPTH}"]
    if not indexed:
        lines.append("no season.nfo or seasonNN.nfo files found")
    else:
        for path, num in indexed:
            marker = " *" if num == season else ""
            lines.append(
                f"  {_kodi_path(path)} seasonnumber={num if num is not None else 'unknown'}{marker}",
            )
    return "; ".join(lines)


def _tvshow_nfo_path(show_dir: str) -> str | None:
    if not show_dir:
        return None
    path = os.path.join(show_dir, "tvshow.nfo")
    return path if xbmcvfs.exists(path) else None


def _season_plot_from_tvshow_nfo(item: LibraryItem, settings: UpdatarrSettings) -> tuple[str | None, dict]:
    show_dir = _show_folder_for_item(item, settings)
    tvshow_path = _tvshow_nfo_path(show_dir)
    if not tvshow_path:
        return None, {}
    nfo_data = _parse_nfo(tvshow_path)
    seasonplots = nfo_data.get("seasonplots") or {}
    plot = seasonplots.get(item.season) if isinstance(seasonplots, dict) else None
    if plot:
        return tvshow_path, {"plot": plot, **{k: v for k, v in nfo_data.items() if k != "seasonplots"}}
    return None, {}


def _nfo_candidates_for_item(item: LibraryItem, settings: UpdatarrSettings) -> list[str]:
    if item.item_type == "movie":
        if not item.file_path:
            return []
        base, _ = os.path.splitext(item.file_path)
        media_dir = os.path.dirname(item.file_path)
        candidates = [f"{base}.nfo"]
        if media_dir:
            candidates.append(os.path.join(media_dir, "movie.nfo"))
        return candidates

    if item.item_type == "tvshow":
        media_dir = _show_folder_for_item(item, settings)
        return [os.path.join(media_dir, "tvshow.nfo")] if media_dir else []

    if item.item_type == "season":
        show_dir = _show_folder_for_item(item, settings)
        if not show_dir or item.season <= 0:
            return []
        _, indexed = _pick_season_nfo(show_dir, item.season, settings)
        return [path for path, _ in indexed]

    if item.item_type == "episode":
        if not item.file_path:
            return []
        base, _ = os.path.splitext(item.file_path)
        return [f"{base}.nfo"]

    return []


def _resolve_nfo_path(item: LibraryItem, settings: UpdatarrSettings) -> tuple[str | None, list[str]]:
    if item.item_type == "season":
        show_dir = _show_folder_for_item(item, settings)
        if not show_dir or item.season <= 0:
            return None, []
        matched, indexed = _pick_season_nfo(show_dir, item.season, settings)
        candidates = [path for path, _ in indexed]
        if matched:
            return matched, candidates
        tvshow_path, _ = _season_plot_from_tvshow_nfo(item, settings)
        if tvshow_path:
            verbose_log(
                settings,
                f"NFO seasonplot fallback for {item.display_title} from {_kodi_path(tvshow_path)}",
            )
            return tvshow_path, candidates + [tvshow_path]
        verbose_log(
            settings,
            f"NFO search for {item.display_title}: {_season_nfo_search_summary(show_dir, item.season, indexed)}",
        )
        return None, candidates

    candidates = _nfo_candidates_for_item(item, settings)
    for candidate in candidates:
        if xbmcvfs.exists(candidate):
            return candidate, candidates
    return None, candidates


def _season_nfo_folder(item: LibraryItem, settings: UpdatarrSettings) -> str | None:
    show_dir = _show_folder_for_item(item, settings)
    if not show_dir or item.season <= 0:
        return None
    matched, _ = _pick_season_nfo(show_dir, item.season, settings)
    if not matched:
        return None
    # Flat seasonNN.nfo at show root uses seasonNN-poster.jpg naming, not show-level poster.jpg.
    if _FLAT_SEASON_NFO_RE.match(os.path.basename(matched)):
        return None
    return os.path.dirname(matched)


def _append_art_variants(
    candidates: list[tuple[str, str]],
    art_type: str,
    prefix_path: str,
) -> None:
    for ext in _ART_EXTENSIONS:
        candidates.append((art_type, f"{prefix_path}{ext}"))


def _artwork_candidates(
    item: LibraryItem,
    settings: UpdatarrSettings,
) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    if item.item_type == "movie":
        if not item.file_path:
            return []
        base, _ = os.path.splitext(item.file_path)
        media_dir = os.path.dirname(item.file_path)
        for art_type in ("poster", "fanart", "thumb"):
            _append_art_variants(candidates, art_type, f"{base}-{art_type}")
            _append_art_variants(candidates, art_type, os.path.join(media_dir, art_type))
    elif item.item_type == "episode":
        if not item.file_path:
            return []
        base, _ = os.path.splitext(item.file_path)
        _append_art_variants(candidates, "thumb", f"{base}-thumb")
        candidates.append(("thumb", f"{base}.tbn"))
        _append_art_variants(candidates, "poster", f"{base}-thumb")
    elif item.item_type == "tvshow":
        media_dir = _show_folder_for_item(item, settings)
        if media_dir:
            for art_type in ("poster", "fanart", "thumb"):
                _append_art_variants(candidates, art_type, os.path.join(media_dir, art_type))
            _append_art_variants(candidates, "thumb", os.path.join(media_dir, "poster"))
    elif item.item_type == "season":
        season_num = f"{item.season:02d}"
        show_dir = _show_folder_for_item(item, settings)
        if not show_dir:
            return []

        season_folder = _season_nfo_folder(item, settings)
        if season_folder:
            for art_type, filename in _SEASON_ART_FILES:
                stem, _ = os.path.splitext(filename)
                _append_art_variants(candidates, art_type, os.path.join(season_folder, stem))
            verbose_log(
                settings,
                f"Artwork season folder for {item.display_title}: {_kodi_path(season_folder)}",
            )
        else:
            verbose_log(
                settings,
                f"Artwork season folder for {item.display_title}: none (no matching season.nfo)",
            )

        for art_type, part in _SEASON_FLAT_ART_PARTS:
            _append_art_variants(candidates, art_type, os.path.join(show_dir, f"season{season_num}-{part}"))

        if season_folder:
            _append_art_variants(candidates, "thumb", os.path.join(season_folder, "poster"))
        _append_art_variants(candidates, "fanart", os.path.join(show_dir, "fanart"))

    return candidates


def _nfo_url_aspects(nfo_data: dict, season: int = 0) -> list[str]:
    aspects: list[str] = []
    thumb_urls = nfo_data.get("thumb_urls") or {}
    if isinstance(thumb_urls, dict):
        aspects.extend(sorted(thumb_urls.keys()))
    season_thumb_urls = nfo_data.get("season_thumb_urls") or {}
    if season > 0 and isinstance(season_thumb_urls, dict):
        for (s, aspect) in sorted(season_thumb_urls.keys()):
            if s == season:
                aspects.append(f"season{s}:{aspect}")
    return aspects


def _thumb_url_for_art_type(nfo_data: dict, art_type: str, season: int = 0) -> str | None:
    aspects = _ART_URL_FALLBACKS.get(art_type, (art_type,))

    season_thumb_urls = nfo_data.get("season_thumb_urls") or {}
    if season > 0 and isinstance(season_thumb_urls, dict):
        for aspect in aspects:
            url = season_thumb_urls.get((season, aspect))
            if url:
                return url

    thumb_urls = nfo_data.get("thumb_urls") or {}
    if isinstance(thumb_urls, dict):
        for aspect in aspects:
            url = thumb_urls.get(aspect)
            if url:
                return url
    return None


def _apply_item_arts(
    item: LibraryItem,
    art_map: dict[str, str],
    settings: UpdatarrSettings,
) -> tuple[bool, str]:
    """Set multiple art types via one Set*Details call. Returns (success, method name)."""
    request = build_set_arts_params(item.item_type, item.item_id, art_map)
    if not request:
        return False, ""
    method, params = request
    result = jsonrpc(method, params, debug=settings.debug_log)
    return not result.get("_error"), method


def _build_details_payload(
    item: LibraryItem,
    nfo_data: dict,
    settings: UpdatarrSettings,
    *,
    nfo_path: str = "",
) -> dict:
    missing_fields = set(missing_metadata_fields(item, settings))
    payload: dict = {}

    seasonplot_only = (
        item.item_type == "season"
        and nfo_path
        and os.path.basename(nfo_path).lower() == "tvshow.nfo"
    )
    if seasonplot_only:
        if "plot" in missing_fields:
            seasonplots = nfo_data.get("seasonplots") or {}
            if isinstance(seasonplots, dict) and seasonplots.get(item.season):
                payload["plot"] = seasonplots[item.season]
        return payload

    if "plot" in missing_fields:
        if item.item_type == "season":
            seasonplots = nfo_data.get("seasonplots") or {}
            if isinstance(seasonplots, dict) and seasonplots.get(item.season):
                payload["plot"] = seasonplots[item.season]
        elif nfo_data.get("plot"):
            payload["plot"] = nfo_data["plot"]
    if "title" in missing_fields and nfo_data.get("title"):
        payload["title"] = nfo_data["title"]
    if "rating" in missing_fields and nfo_data.get("rating") is not None:
        payload["rating"] = nfo_data["rating"]
    if item.item_type == "tvshow":
        if nfo_data.get("premiered"):
            payload["premiered"] = nfo_data["premiered"]
        elif nfo_data.get("year") is not None:
            payload["premiered"] = f"{nfo_data['year']}-01-01"
    elif nfo_data.get("year") is not None:
        payload["year"] = nfo_data["year"]
    if nfo_data.get("mpaa"):
        payload["mpaa"] = nfo_data["mpaa"]
    if nfo_data.get("genre"):
        payload["genre"] = nfo_data["genre"]
    if nfo_data.get("uniqueid"):
        payload["uniqueid"] = nfo_data["uniqueid"]

    return payload


def apply_local_artwork(item: LibraryItem, settings: UpdatarrSettings) -> bool:
    if not settings.enable_local_artwork:
        verbose_log(settings, f"Artwork skip {item.display_title}: disabled")
        return False

    needed = set(missing_art_types(item, settings))
    if not needed:
        verbose_log(settings, f"Artwork skip {item.display_title}: no missing art types in settings check")
        return False

    item_dict = item.item_dict()
    if not item_dict:
        verbose_log(settings, f"Artwork skip {item.display_title}: no JSON-RPC item id")
        return False

    show_dir = _show_folder_for_item(item, settings)
    verbose_log(
        settings,
        f"Artwork scan {item.display_title}: needed={sorted(needed)} show_dir={show_dir or '(unknown)'}",
    )

    nfo_data: dict = {}
    nfo_path, _ = _resolve_nfo_path(item, settings)
    if nfo_path:
        nfo_data = _parse_nfo(nfo_path)
    if item.item_type == "season":
        show_dir = _show_folder_for_item(item, settings)
        tvshow_path = _tvshow_nfo_path(show_dir)
        if tvshow_path and tvshow_path != nfo_path:
            tvshow_data = _parse_nfo(tvshow_path)
            nfo_data = {**tvshow_data, **nfo_data}

    paths_by_type: dict[str, list[str]] = {}
    for art_type, art_path in _artwork_candidates(item, settings):
        paths_by_type.setdefault(art_type, []).append(art_path)

    art_to_set: dict[str, str] = {}
    sources_for_log: dict[str, str] = {}
    season_num = item.season if item.item_type == "season" else 0

    for art_type in sorted(needed):
        found_local = False
        for art_path in paths_by_type.get(art_type, []):
            if not xbmcvfs.exists(art_path):
                continue
            art_to_set[art_type] = _kodi_path(art_path)
            sources_for_log[art_type] = _file_stat_line(art_path)
            found_local = True
            break

        if found_local:
            continue

        remote_url = _thumb_url_for_art_type(nfo_data, art_type, season=season_num)
        if remote_url:
            art_to_set[art_type] = remote_url
            sources_for_log[art_type] = f"remote URL from NFO ({remote_url})"
            continue

        paths = paths_by_type.get(art_type, [])
        sample = _file_stat_line(paths[0]) if paths else "(no local paths)"
        aspects = _nfo_url_aspects(nfo_data, season_num)
        verbose_log(
            settings,
            f"Artwork missing {item.display_title} {art_type}: no file at {sample}"
            + (f"; NFO URL aspects available: {aspects}" if aspects else " and no NFO thumb URLs"),
        )

    if not art_to_set:
        return False

    ok, method = _apply_item_arts(item, art_to_set, settings)
    if ok:
        log(f"Set local artwork {sorted(art_to_set.keys())} for {item.display_title}")
        for art_type, source_desc in sources_for_log.items():
            verbose_log(
                settings,
                f"Artwork applied {item.display_title} {art_type} via {method}: {source_desc}",
            )
        return True

    verbose_log(
        settings,
        f"Artwork failed {item.display_title}: {method or 'Set*Details'} error for {sorted(art_to_set.keys())}",
    )
    return False


def apply_local_nfo(item: LibraryItem, settings: UpdatarrSettings) -> bool:
    if not settings.enable_local_nfo:
        verbose_log(settings, f"NFO skip {item.display_title}: local NFO disabled in settings")
        return False

    missing_fields = set(missing_metadata_fields(item, settings))
    if not missing_fields:
        verbose_log(settings, f"NFO skip {item.display_title}: no missing metadata fields")
        return False

    nfo_path, candidates = _resolve_nfo_path(item, settings)
    if not nfo_path:
        if item.item_type == "season":
            show_dir = _show_folder_for_item(item, settings)
            if show_dir:
                _, indexed = _pick_season_nfo(show_dir, item.season, settings)
                summary = _season_nfo_search_summary(show_dir, item.season, indexed)
            else:
                summary = "(no show folder)"
            verbose_log(settings, f"NFO not found for {item.display_title}; {summary}")
        else:
            searched = "; ".join(_file_stat_line(path) for path in candidates) if candidates else "(no paths)"
            verbose_log(settings, f"NFO not found for {item.display_title}; searched: {searched}")
        return False

    verbose_log(settings, f"NFO found for {item.display_title}: {_file_stat_line(nfo_path)}")

    nfo_data = _parse_nfo(nfo_path)
    if not nfo_data:
        verbose_log(settings, f"NFO empty/unparseable for {item.display_title}: {nfo_path}")
        return False

    missing_fields = set(missing_metadata_fields(item, settings))
    raw_details = _build_details_payload(item, nfo_data, settings, nfo_path=nfo_path or "")
    details = sanitize_set_details(item.item_type, raw_details)

    if item.item_type == "season" and "plot" in raw_details and "plot" not in details:
        verbose_log(
            settings,
            f"NFO season plot for {item.display_title} is not writable via SetSeasonDetails on Kodi v22",
        )

    dropped = sorted(set(raw_details.keys()) - set(details.keys()))
    if dropped:
        verbose_log(settings, f"NFO fields dropped for {item.display_title} (unsupported by Set API): {dropped}")

    if not details:
        verbose_log(
            settings,
            f"NFO no applicable fields for {item.display_title}: "
            f"missing_in_library={sorted(missing_fields)} parsed={sorted(nfo_data.keys())}",
        )
        return False

    method_map = {
        "movie": "VideoLibrary.SetMovieDetails",
        "tvshow": "VideoLibrary.SetTVShowDetails",
        "season": "VideoLibrary.SetSeasonDetails",
        "episode": "VideoLibrary.SetEpisodeDetails",
    }
    method = method_map.get(item.item_type)
    if not method:
        verbose_log(settings, f"NFO skip {item.display_title}: unsupported type {item.item_type}")
        return False

    id_key = list(item.item_dict().keys())[0]
    params = {id_key: item.item_id, **details}
    verbose_log(
        settings,
        f"NFO applying {item.display_title} via {method}: fields={sorted(details.keys())} from {nfo_path}",
    )
    result = jsonrpc(method, params, debug=settings.debug_log)
    if result.get("_error"):
        verbose_log(settings, f"NFO apply failed for {item.display_title}: {method} returned error")
        return False
    log(f"Applied local NFO fields to {item.display_title}: {list(details.keys())}")
    return True


def apply_local_fixes(item: LibraryItem, settings: UpdatarrSettings) -> tuple[bool, bool]:
    art_applied = apply_local_artwork(item, settings)
    nfo_applied = apply_local_nfo(item, settings)
    return art_applied, nfo_applied
