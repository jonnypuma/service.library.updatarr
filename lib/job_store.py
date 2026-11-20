"""Persist in-progress update jobs for crash/resume support."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import xbmc
import xbmcaddon
import xbmcvfs

from lib.jsonrpc import log
from lib.models import LibraryItem
from lib.settings import ADDON_ID

JOB_VERSION = 1
JOB_FILENAME = "update_job.json"


@dataclass
class JobStats:
    local_art_fixed: int = 0
    local_nfo_fixed: int = 0
    scraper_refreshed: int = 0
    errors: int = 0


@dataclass
class UpdateJob:
    version: int = JOB_VERSION
    created_epoch: int = 0
    updated_epoch: int = 0
    scope: str = "full"
    item_type: str | None = None
    item_id: int | None = None
    dry_run: bool = False
    scanned: int = 0
    skipped_complete: int = 0
    missing_summary: dict[str, int] = field(default_factory=dict)
    pending_items: list[dict[str, Any]] = field(default_factory=list)
    next_index: int = 0
    stats: JobStats = field(default_factory=JobStats)

    @property
    def total_pending(self) -> int:
        return len(self.pending_items)

    @property
    def remaining(self) -> int:
        return max(0, self.total_pending - self.next_index)

    def summary_line(self) -> str:
        return f"{self.remaining} of {self.total_pending} item(s) remaining"


def _job_path() -> str:
    profile = xbmcaddon.Addon(id=ADDON_ID).getAddonInfo("profile")
    return xbmcvfs.translatePath(f"{profile}{JOB_FILENAME}")


def item_to_record(item: LibraryItem) -> dict[str, Any]:
    return {
        "item_type": item.item_type,
        "item_id": item.item_id,
        "title": item.title,
        "season": item.season,
        "episode": item.episode,
        "showtitle": item.showtitle,
        "tvshowid": item.tvshowid,
    }


def record_to_item(record: dict[str, Any]) -> LibraryItem:
    return LibraryItem(
        item_type=str(record.get("item_type") or ""),
        item_id=int(record.get("item_id") or 0),
        title=str(record.get("title") or ""),
        file_path=str(record.get("file_path") or ""),
        plot=str(record.get("plot") or ""),
        art=dict(record.get("art") or {}),
        season=int(record.get("season") or 0),
        episode=int(record.get("episode") or 0),
        showtitle=str(record.get("showtitle") or ""),
        tvshowid=int(record.get("tvshowid") or 0),
        extra=dict(record.get("extra") or {}),
    )


def _serialize_job(job: UpdateJob) -> str:
    payload = asdict(job)
    payload["stats"] = asdict(job.stats)
    return json.dumps(payload, indent=2)


def _deserialize_job(payload: dict[str, Any]) -> UpdateJob | None:
    try:
        stats_raw = payload.get("stats") or {}
        stats = JobStats(
            local_art_fixed=int(stats_raw.get("local_art_fixed") or 0),
            local_nfo_fixed=int(stats_raw.get("local_nfo_fixed") or 0),
            scraper_refreshed=int(stats_raw.get("scraper_refreshed") or 0),
            errors=int(stats_raw.get("errors") or 0),
        )
        return UpdateJob(
            version=int(payload.get("version") or JOB_VERSION),
            created_epoch=int(payload.get("created_epoch") or 0),
            updated_epoch=int(payload.get("updated_epoch") or 0),
            scope=str(payload.get("scope") or "full"),
            item_type=payload.get("item_type"),
            item_id=int(payload["item_id"]) if payload.get("item_id") is not None else None,
            dry_run=bool(payload.get("dry_run")),
            scanned=int(payload.get("scanned") or 0),
            skipped_complete=int(payload.get("skipped_complete") or 0),
            missing_summary=dict(payload.get("missing_summary") or {}),
            pending_items=list(payload.get("pending_items") or []),
            next_index=int(payload.get("next_index") or 0),
            stats=stats,
        )
    except (TypeError, ValueError, KeyError) as exc:
        log(f"Invalid job file: {exc}", xbmc.LOGWARNING)
        return None


def has_resumable_job() -> bool:
    job = load_job()
    return job is not None and job.remaining > 0 and not job.dry_run


def load_job() -> UpdateJob | None:
    path = _job_path()
    if not xbmcvfs.exists(path):
        return None

    try:
        handle = xbmcvfs.File(path)
        raw = handle.read()
        handle.close()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        payload = json.loads(raw)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        log(f"Failed to read job file: {exc}", xbmc.LOGWARNING)
        return None

    if not isinstance(payload, dict):
        return None

    job = _deserialize_job(payload)
    if job is None:
        return None
    if job.version != JOB_VERSION:
        log("Job file version mismatch; ignoring", xbmc.LOGWARNING)
        return None
    if job.dry_run or job.remaining <= 0:
        return None
    return job


def save_job(job: UpdateJob) -> None:
    job.updated_epoch = int(time.time())
    path = _job_path()
    tmp_path = f"{path}.tmp"
    serialized = _serialize_job(job)
    try:
        handle = xbmcvfs.File(tmp_path, "w")
        handle.write(serialized)
        handle.close()
        if hasattr(xbmcvfs, "rename"):
            if not xbmcvfs.rename(tmp_path, path):
                if xbmcvfs.exists(path):
                    xbmcvfs.delete(path)
                if not xbmcvfs.rename(tmp_path, path):
                    handle = xbmcvfs.File(path, "w")
                    handle.write(serialized)
                    handle.close()
                    xbmcvfs.delete(tmp_path)
        else:
            handle = xbmcvfs.File(path, "w")
            handle.write(serialized)
            handle.close()
        log(f"Saved job checkpoint ({job.next_index}/{job.total_pending})")
    except OSError as exc:
        log(f"Failed to save job file: {exc}", xbmc.LOGERROR)


def clear_job() -> None:
    path = _job_path()
    if xbmcvfs.exists(path):
        try:
            xbmcvfs.delete(path)
            log("Cleared update job file")
        except OSError as exc:
            log(f"Failed to delete job file: {exc}", xbmc.LOGWARNING)


def create_job(
    *,
    scope: str,
    item_type: str | None,
    item_id: int | None,
    scanned: int,
    skipped_complete: int,
    missing_summary: dict[str, int],
    pending_items: list[LibraryItem],
) -> UpdateJob:
    now = int(time.time())
    return UpdateJob(
        created_epoch=now,
        updated_epoch=now,
        scope=scope,
        item_type=item_type,
        item_id=item_id,
        scanned=scanned,
        skipped_complete=skipped_complete,
        missing_summary=missing_summary,
        pending_items=[item_to_record(item) for item in pending_items],
        next_index=0,
    )
