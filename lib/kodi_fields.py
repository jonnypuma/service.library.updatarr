"""Kodi v22 VideoLibrary JSON-RPC field allowlists."""

from __future__ import annotations

TVSHOW_GET_PROPERTIES = ["art", "plot", "title", "file", "rating", "cast", "uniqueid"]
SEASON_GET_PROPERTIES = ["art", "title", "season", "tvshowid"]
SEASON_LIST_PROPERTIES = ["season", "title", "art"]

TVSHOW_SET_FIELDS = frozenset(
    {
        "title",
        "playcount",
        "studio",
        "plot",
        "genre",
        "rating",
        "mpaa",
        "imdbnumber",
        "premiered",
        "votes",
        "lastplayed",
        "originaltitle",
        "sorttitle",
        "episodeguide",
        "thumbnail",
        "fanart",
        "tag",
        "art",
        "userrating",
        "ratings",
        "dateadded",
        "runtime",
        "status",
        "uniqueid",
    }
)

SEASON_SET_FIELDS = frozenset({"art", "userrating", "title"})

_SET_DETAILS_METHODS: dict[str, tuple[str, str]] = {
    "movie": ("VideoLibrary.SetMovieDetails", "movieid"),
    "tvshow": ("VideoLibrary.SetTVShowDetails", "tvshowid"),
    "season": ("VideoLibrary.SetSeasonDetails", "seasonid"),
    "episode": ("VideoLibrary.SetEpisodeDetails", "episodeid"),
}


def build_set_arts_params(item_type: str, item_id: int, art_map: dict[str, str]) -> tuple[str, dict] | None:
    """Build Set*Details request for artwork (VideoLibrary.SetArt was removed in Kodi v22)."""
    if not art_map:
        return None
    entry = _SET_DETAILS_METHODS.get(item_type)
    if not entry:
        return None
    method, id_key = entry
    return method, {id_key: item_id, "art": dict(art_map)}


def build_set_art_params(item_type: str, item_id: int, art_type: str, art_value: str) -> tuple[str, dict] | None:
    """Build Set*Details request for one art type."""
    return build_set_arts_params(item_type, item_id, {art_type: art_value})


def sanitize_set_details(item_type: str, details: dict) -> dict:
    """Keep only fields Kodi accepts for Set*Details on this item type."""
    if item_type == "tvshow":
        payload: dict = {}
        for key, value in details.items():
            if key not in TVSHOW_SET_FIELDS or key == "uniqueid":
                continue
            payload[key] = value

        uniqueids = details.get("uniqueid")
        if isinstance(uniqueids, dict):
            imdb = uniqueids.get("imdb")
            if imdb and "imdbnumber" not in payload:
                payload["imdbnumber"] = imdb
            for provider in ("tvdb", "imdb", "tmdb"):
                value = uniqueids.get(provider)
                if value:
                    payload["uniqueid"] = {provider: value}
                    break
        return payload

    if item_type == "season":
        return {key: value for key, value in details.items() if key in SEASON_SET_FIELDS}

    return dict(details)
