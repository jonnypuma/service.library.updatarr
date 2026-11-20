"""Tests for missing field detection and settings parsing."""

from __future__ import annotations

from lib.missing import has_missing_data, missing_metadata_fields
from lib.models import LibraryItem
from lib.settings import UpdatarrSettings, read_settings


class _FakeAddon:
    def __init__(self, ints: dict[str, int] | None = None, bools: dict[str, bool] | None = None):
        self._ints = ints or {}
        self._bools = bools or {}

    def getSettingBool(self, key: str) -> bool:
        return self._bools.get(key, False)

    def getSettingInt(self, key: str) -> int:
        return self._ints.get(key, 0)


def test_delay_ms_zero_is_preserved(monkeypatch):
    fake = _FakeAddon(ints={"delay_ms": 0, "batch_size": 100, "schedule_interval_hours": 12})
    monkeypatch.setattr("lib.settings._addon", lambda: fake)
    settings = read_settings()
    assert settings.delay_ms == 0
    assert settings.batch_size == 100
    assert settings.schedule_interval_hours == 12


def test_rating_zero_is_detected_as_missing():
    settings = UpdatarrSettings(
        check_poster=False,
        check_fanart=False,
        check_thumb=False,
        check_plot=False,
        check_rating=True,
    )
    unrated = LibraryItem("movie", 1, title="Test", extra={"rating": 0.0})
    rated = LibraryItem("movie", 2, title="Test", extra={"rating": 7.2})

    assert missing_metadata_fields(unrated, settings) == ["rating"]
    assert has_missing_data(unrated, settings) is True
    assert missing_metadata_fields(rated, settings) == []
    assert has_missing_data(rated, settings) is False


def test_season_skips_non_season_metadata_fields():
    settings = UpdatarrSettings(
        check_poster=False,
        check_fanart=False,
        check_thumb=False,
        check_plot=True,
        check_title=True,
        check_rating=True,
        check_cast=True,
    )
    season = LibraryItem("season", 10, title="Season 1", season=1, tvshowid=5, plot="")
    assert missing_metadata_fields(season, settings) == []
    assert has_missing_data(season, settings) is False

    untitled_season = LibraryItem("season", 11, title="", season=2, tvshowid=5, plot="")
    assert missing_metadata_fields(untitled_season, settings) == ["title"]
