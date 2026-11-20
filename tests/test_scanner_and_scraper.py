"""Tests for scanner scope isolation, season list optimization, and scraper error handling."""

from __future__ import annotations

from lib import scanner, scraper
from lib.models import LibraryItem
from lib.settings import UpdatarrSettings


def test_context_scope_unsupported_type_does_not_fall_through(monkeypatch):
    called_methods: list[str] = []

    def fake_jsonrpc(method, params=None, *, debug=False):
        called_methods.append(method)
        return {}

    monkeypatch.setattr(scanner, "jsonrpc", fake_jsonrpc)
    settings = UpdatarrSettings(process_movies=True, process_tvshows=True, process_episodes=True)

    items = scanner.fetch_items_for_scope(settings, scope="context", item_type="musicvideo", item_id=42)
    assert items == []
    assert called_methods == []


def test_fetch_seasons_for_show_avoids_n_plus_one_details(monkeypatch):
    called_methods: list[str] = []

    def fake_jsonrpc(method, params=None, *, debug=False):
        called_methods.append(method)
        if method == "VideoLibrary.GetSeasons":
            return {
                "seasons": [
                    {"seasonid": 101, "season": 1, "title": "Season 1", "art": {"poster": "p1.jpg"}},
                    {"seasonid": 102, "season": 2, "title": "Season 2", "art": {}},
                ]
            }
        raise AssertionError(f"Unexpected JSON-RPC call: {method}")

    monkeypatch.setattr(scanner, "jsonrpc", fake_jsonrpc)
    seasons = scanner.fetch_seasons_for_show(7, UpdatarrSettings())

    assert len(seasons) == 2
    assert seasons[0].item_id == 101
    assert seasons[0].tvshowid == 7
    assert seasons[1].art == {}
    assert called_methods == ["VideoLibrary.GetSeasons"]


def test_refresh_item_returns_false_on_jsonrpc_error(monkeypatch):
    monkeypatch.setattr(scraper, "jsonrpc", lambda method, params=None, *, debug=False: {"_error": True})
    movie = LibraryItem("movie", 5, title="Broken Movie")
    assert scraper.refresh_item(movie, UpdatarrSettings(enable_scraper_pass=True)) is False
