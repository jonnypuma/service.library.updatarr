"""Tests for runner orchestration, job store, run lock, and service."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import service
from lib import job_store, run_lock, runner
from lib.models import LibraryItem
from lib.settings import UpdatarrSettings


def test_context_scope_ignores_global_type_toggles_and_preserves_job(monkeypatch, tmp_path):
    job_file = tmp_path / "update_job.json"
    job_file.write_text('{"version":1,"pending_items":[{"item_type":"movie","item_id":1}],"next_index":0}', encoding="utf-8")
    monkeypatch.setattr(job_store, "_job_path", lambda: str(job_file))

    ep = LibraryItem("episode", 55, title="Ep 1", season=1, episode=1, showtitle="Show", plot="")
    monkeypatch.setattr(runner, "fetch_items_for_scope", lambda *a, **kw: [ep])
    monkeypatch.setattr(runner, "fetch_item_details", lambda item, settings: item)
    monkeypatch.setattr(runner, "apply_local_fixes", lambda item, settings: (False, False))
    monkeypatch.setattr(runner, "refresh_item", lambda item, settings: True)

    settings = UpdatarrSettings(process_episodes=False, delay_ms=0, check_plot=True)
    result = runner.run(scope="context", item_type="episode", item_id=55, settings=settings)

    assert result.scanned == 1
    assert result.scraper_refreshed == 1
    assert job_file.exists()


def test_seasons_deduplicate_refresh_tvshow(monkeypatch):
    s1 = LibraryItem("season", 101, title="Season 1", season=1, tvshowid=7, art={})
    s2 = LibraryItem("season", 102, title="Season 2", season=2, tvshowid=7, art={})

    monkeypatch.setattr(runner, "fetch_items_for_scope", lambda *a, **kw: [s1, s2])
    monkeypatch.setattr(runner, "fetch_item_details", lambda item, settings: item)
    monkeypatch.setattr(runner, "apply_local_fixes", lambda item, settings: (False, False))
    monkeypatch.setattr(runner, "save_job", lambda job: None)
    monkeypatch.setattr(runner, "clear_job", lambda: None)

    refreshed_ids: list[int] = []
    monkeypatch.setattr(
        runner,
        "refresh_item",
        lambda item, settings: refreshed_ids.append(item.item_id) or True,
    )

    settings = UpdatarrSettings(check_poster=True, check_fanart=False, check_thumb=False, delay_ms=0)
    result = runner.run(scope="full", settings=settings)

    assert result.scraper_refreshed == 1
    assert refreshed_ids == [101]


def test_run_lock_blocks_overlapping_runs():
    assert run_lock.acquire_run_lock("full") is True
    try:
        res = runner.run(scope="full", settings=UpdatarrSettings())
        assert res.already_running is True
    finally:
        run_lock.release_run_lock()

    assert run_lock.acquire_run_lock("context") is True
    run_lock.release_run_lock()


def test_monitor_abort_stops_processing_and_saves_checkpoint(monkeypatch):
    m1 = LibraryItem("movie", 1, title="M1", plot="")
    m2 = LibraryItem("movie", 2, title="M2", plot="")

    monkeypatch.setattr(runner, "fetch_items_for_scope", lambda *a, **kw: [m1, m2])
    monkeypatch.setattr(runner, "fetch_item_details", lambda item, settings: item)
    monkeypatch.setattr(runner, "apply_local_fixes", lambda item, settings: (False, False))
    monkeypatch.setattr(runner, "refresh_item", lambda item, settings: True)

    saved_jobs: list[int] = []
    monkeypatch.setattr(runner, "save_job", lambda job: saved_jobs.append(job.next_index))
    monkeypatch.setattr(runner, "clear_job", lambda: None)

    class _AbortingMonitor:
        def abortRequested(self) -> bool:
            return False

        def waitForAbort(self, timeout: float) -> bool:
            return True

    settings = UpdatarrSettings(delay_ms=1000, check_plot=True)
    res = runner.run(scope="full", settings=settings, monitor=_AbortingMonitor())

    assert res.canceled is True
    assert res.scraper_refreshed == 1
    assert saved_jobs[-1] == 1


def test_atomic_save_job_writes_minimal_records(monkeypatch, tmp_path):
    job_path = tmp_path / "update_job.json"
    monkeypatch.setattr(job_store, "_job_path", lambda: str(job_path))

    class _LocalFile:
        def __init__(self, path: str, mode: str = "r"):
            self._f = open(path, mode, encoding="utf-8")

        def write(self, data: str):
            self._f.write(data)

        def read(self):
            return self._f.read()

        def close(self):
            self._f.close()

    monkeypatch.setattr(job_store.xbmcvfs, "File", _LocalFile)
    monkeypatch.setattr(job_store.xbmcvfs, "exists", lambda p: Path(p).exists())
    monkeypatch.setattr(job_store.xbmcvfs, "delete", lambda p: Path(p).unlink(missing_ok=True) or True)
    monkeypatch.setattr(job_store.xbmcvfs, "rename", lambda src, dst: Path(src).replace(dst) or True)

    item = LibraryItem("movie", 7, title="Big Movie", plot="Long plot", art={"poster": "p.jpg"}, extra={"cast": ["A"]})
    job = job_store.create_job(
        scope="full",
        item_type=None,
        item_id=None,
        scanned=1,
        skipped_complete=0,
        missing_summary={"meta:plot": 1},
        pending_items=[item],
    )
    job_store.save_job(job)

    data = json.loads(job_path.read_text(encoding="utf-8"))
    record = data["pending_items"][0]
    assert record["item_id"] == 7
    assert "plot" not in record
    assert "extra" not in record
    assert not (tmp_path / "update_job.json.tmp").exists()


def test_service_sends_single_notification(monkeypatch):
    notifications: list = []

    class _FakeDialog:
        def notification(self, *args, **kwargs):
            notifications.append(args)

    monkeypatch.setattr(service.xbmcgui, "Dialog", lambda: _FakeDialog())
    monkeypatch.setattr(service, "is_library_scanning", lambda: False)
    monkeypatch.setattr(service, "has_resumable_job", lambda: False)
    monkeypatch.setattr(service, "get_last_run_epoch", lambda: 0)
    monkeypatch.setattr(service, "set_last_run_epoch", MagicMock())
    monkeypatch.setattr(
        service,
        "read_settings",
        lambda: UpdatarrSettings(enable_schedule=True, notify_on_schedule=True, run_while_idle=False),
    )

    run_kwargs: list[dict] = []

    def fake_run(**kwargs):
        run_kwargs.append(kwargs)
        return runner.RunResult(scanned=2, scraper_refreshed=1)

    monkeypatch.setattr(service, "run", fake_run)

    mon = service.UpdatarrMonitor()
    mon._maybe_run_scheduled()

    assert run_kwargs[0]["notify"] is False
    assert len(notifications) == 1
