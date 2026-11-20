"""Tests for local artwork batching, episode/movie conventions, and NFO parsing."""

from __future__ import annotations

from pathlib import Path

from lib import local_fixer
from lib.models import LibraryItem
from lib.settings import UpdatarrSettings


def test_apply_local_artwork_batches_into_single_jsonrpc_call(monkeypatch, tmp_path):
    media_dir = tmp_path / "Movie (2024)"
    media_dir.mkdir()
    video = media_dir / "Movie (2024).mkv"
    poster = media_dir / "Movie (2024)-poster.png"
    fanart = media_dir / "fanart.jpeg"
    poster.write_bytes(b"png")
    fanart.write_bytes(b"jpg")

    monkeypatch.setattr(local_fixer.xbmcvfs, "exists", lambda p: Path(p).exists())

    rpc_calls: list[tuple[str, dict]] = []

    def fake_jsonrpc(method, params=None, *, debug=False):
        rpc_calls.append((method, params or {}))
        return {"_ok": True}

    monkeypatch.setattr(local_fixer, "jsonrpc", fake_jsonrpc)

    movie = LibraryItem("movie", 12, title="Movie", file_path=str(video), art={})
    settings = UpdatarrSettings(check_poster=True, check_fanart=True, check_thumb=False)

    assert local_fixer.apply_local_artwork(movie, settings) is True
    assert len(rpc_calls) == 1
    method, params = rpc_calls[0]
    assert method == "VideoLibrary.SetMovieDetails"
    assert params["movieid"] == 12
    assert set(params["art"].keys()) == {"poster", "fanart"}
    assert params["art"]["poster"].endswith("Movie (2024)-poster.png")
    assert params["art"]["fanart"].endswith("fanart.jpeg")


def test_apply_local_artwork_supports_episodes(monkeypatch, tmp_path):
    ep_dir = tmp_path / "Show" / "Season 1"
    ep_dir.mkdir(parents=True)
    ep_video = ep_dir / "Show S01E01.mkv"
    ep_thumb = ep_dir / "Show S01E01-thumb.jpg"
    ep_thumb.write_bytes(b"jpg")

    monkeypatch.setattr(local_fixer.xbmcvfs, "exists", lambda p: Path(p).exists())

    rpc_calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        local_fixer,
        "jsonrpc",
        lambda method, params=None, *, debug=False: rpc_calls.append((method, params or {})) or {"_ok": True},
    )

    ep = LibraryItem(
        "episode",
        99,
        title="Pilot",
        file_path=str(ep_video),
        season=1,
        episode=1,
        showtitle="Show",
        art={},
    )
    settings = UpdatarrSettings(check_poster=False, check_fanart=False, check_thumb=True)

    assert local_fixer.apply_local_artwork(ep, settings) is True
    assert len(rpc_calls) == 1
    assert rpc_calls[0][0] == "VideoLibrary.SetEpisodeDetails"
    assert rpc_calls[0][1]["art"]["thumb"].endswith("Show S01E01-thumb.jpg")


def test_parse_nfo_legacy_rating_and_apply_skips_when_nothing_missing(monkeypatch, tmp_path):
    nfo = tmp_path / "movie.nfo"
    nfo.write_text("<movie><title>Test</title><rating>8.4</rating></movie>", encoding="utf-8")

    class _FakeFile:
        def __init__(self, path: str):
            self._text = Path(path).read_text(encoding="utf-8")

        def read(self):
            return self._text

        def close(self):
            pass

    monkeypatch.setattr(local_fixer.xbmcvfs, "exists", lambda p: Path(p).exists())
    monkeypatch.setattr(local_fixer.xbmcvfs, "File", _FakeFile)

    parsed = local_fixer._parse_nfo(str(nfo))
    assert parsed["rating"] == 8.4

    rpc_calls: list = []
    monkeypatch.setattr(local_fixer, "jsonrpc", lambda *a, **kw: rpc_calls.append(a) or {"_ok": True})

    # Plot and title are already present; only poster is missing.
    movie = LibraryItem(
        "movie",
        5,
        title="Test",
        plot="Existing plot",
        file_path=str(tmp_path / "SomeMovie.mkv"),
        art={},
    )
    settings = UpdatarrSettings(check_plot=True, check_title=False, check_rating=False, check_cast=False)
    assert local_fixer.apply_local_nfo(movie, settings) is False
    assert rpc_calls == []
