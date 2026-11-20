"""Detect missing artwork and metadata fields."""

from __future__ import annotations

from lib.models import LibraryItem
from lib.settings import UpdatarrSettings


def is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def is_missing_rating(value) -> bool:
    if is_missing(value):
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value <= 0
    return False


def art_types_to_check(settings: UpdatarrSettings) -> list[str]:
    types: list[str] = []
    if settings.check_poster:
        types.append("poster")
    if settings.check_fanart:
        types.append("fanart")
    if settings.check_thumb:
        types.append("thumb")
    return types


def missing_art_types(item: LibraryItem, settings: UpdatarrSettings) -> list[str]:
    art = item.art or {}
    return [art_type for art_type in art_types_to_check(settings) if is_missing(art.get(art_type))]


def missing_metadata_fields(item: LibraryItem, settings: UpdatarrSettings) -> list[str]:
    missing: list[str] = []
    # Kodi v22 GetSeasonDetails/SetSeasonDetails only expose title/art/userrating for seasons.
    is_season = item.item_type == "season"
    if settings.check_plot and not is_season and is_missing(item.plot):
        missing.append("plot")
    if settings.check_title and is_missing(item.title):
        missing.append("title")
    if settings.check_rating and not is_season and is_missing_rating(item.extra.get("rating")):
        missing.append("rating")
    if settings.check_cast and not is_season and is_missing(item.extra.get("cast")):
        missing.append("cast")
    return missing


def has_missing_data(item: LibraryItem, settings: UpdatarrSettings) -> bool:
    return bool(missing_art_types(item, settings) or missing_metadata_fields(item, settings))


def summarize_missing(items: list[LibraryItem], settings: UpdatarrSettings) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for art_type in missing_art_types(item, settings):
            key = f"art:{art_type}"
            counts[key] = counts.get(key, 0) + 1
        for field in missing_metadata_fields(item, settings):
            key = f"meta:{field}"
            counts[key] = counts.get(key, 0) + 1
    return counts
