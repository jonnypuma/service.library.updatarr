"""Batch orchestration for Library Updatarr."""

from __future__ import annotations

from dataclasses import dataclass, field

import xbmc
import xbmcgui

from lib.job_store import (
    UpdateJob,
    clear_job,
    create_job,
    load_job,
    record_to_item,
    save_job,
)
from lib.jsonrpc import is_library_scanning, log
from lib.local_fixer import apply_local_fixes, clear_season_nfo_index
from lib.missing import has_missing_data, summarize_missing
from lib.models import LibraryItem
from lib.run_lock import acquire_run_lock, release_run_lock
from lib.scanner import ScanCanceled, fetch_item_details, fetch_items_for_scope
from lib.scraper import refresh_item
from lib.settings import UpdatarrSettings, addon_icon, addon_name, localized, read_settings
from lib.show_folder import clear_show_folder_cache


@dataclass
class RunResult:
    scanned: int = 0
    skipped_complete: int = 0
    local_art_fixed: int = 0
    local_nfo_fixed: int = 0
    scraper_refreshed: int = 0
    errors: int = 0
    canceled: bool = False
    scan_canceled: bool = False
    resumed: bool = False
    already_running: bool = False
    missing_summary: dict[str, int] = field(default_factory=dict)
    pending_items: list[LibraryItem] = field(default_factory=list)

    @property
    def need_updates(self) -> int:
        return len(self.pending_items)

    def summary_text(self) -> str:
        if self.already_running:
            return localized(32063, "Another Library Updatarr run is already in progress.")
        if self.scan_canceled:
            return localized(32064, "Scan canceled.")
        lines = [
            f"Scanned: {self.scanned}",
            f"Already complete: {self.skipped_complete}",
            f"Local artwork applied: {self.local_art_fixed}",
            f"Local NFO applied: {self.local_nfo_fixed}",
            f"Scraper refreshes: {self.scraper_refreshed}",
            f"Errors: {self.errors}",
        ]
        if self.resumed:
            lines.append("Resumed from saved job.")
        if self.canceled:
            lines.append("Run stopped. Progress was saved and can be resumed.")
        return "\n".join(lines)


def _should_process_type(item_type: str, settings: UpdatarrSettings) -> bool:
    return {
        "movie": settings.process_movies,
        "tvshow": settings.process_tvshows,
        "episode": settings.process_episodes,
        "season": settings.process_tvshows,
    }.get(item_type, False)


def _sleep_throttle(
    settings: UpdatarrSettings,
    monitor: xbmc.Monitor | None = None,
) -> bool:
    """Sleep for delay_ms; returns True if aborted via monitor."""
    if settings.delay_ms <= 0:
        return False
    if monitor is not None:
        return bool(monitor.waitForAbort(settings.delay_ms / 1000.0))
    xbmc.sleep(settings.delay_ms)
    return False


def _items_from_job(job: UpdateJob) -> list[LibraryItem]:
    return [record_to_item(record) for record in job.pending_items]


def _filter_missing_items(
    candidates: list[LibraryItem],
    settings: UpdatarrSettings,
    progress: xbmcgui.DialogProgress | None,
    monitor: xbmc.Monitor | None = None,
) -> list[LibraryItem]:
    missing_items: list[LibraryItem] = []
    total = len(candidates)

    for index, item in enumerate(candidates):
        if (progress and progress.iscanceled()) or (monitor and monitor.abortRequested()):
            raise ScanCanceled()
        if total and index % 50 == 0:
            _update_scan_progress(
                progress,
                f"Checking missing fields ({index + 1}/{total})…",
                percent=int((index / total) * 100),
            )
        if has_missing_data(item, settings):
            missing_items.append(item)

    return missing_items


def _update_scan_progress(
    progress: xbmcgui.DialogProgress | None,
    message: str,
    *,
    percent: int = 0,
) -> None:
    if progress:
        progress.update(percent, message)


def _apply_stats_to_result(result: RunResult, job: UpdateJob) -> None:
    result.local_art_fixed = job.stats.local_art_fixed
    result.local_nfo_fixed = job.stats.local_nfo_fixed
    result.scraper_refreshed = job.stats.scraper_refreshed
    result.errors = job.stats.errors


def _process_items(
    missing_items: list[LibraryItem],
    *,
    settings: UpdatarrSettings,
    result: RunResult,
    progress: xbmcgui.DialogProgress | None,
    job: UpdateJob | None,
    start_index: int = 0,
    monitor: xbmc.Monitor | None = None,
) -> None:
    total = len(missing_items)
    refreshed_tvshows: set[int] = set()

    for index in range(start_index, total):
        item = missing_items[index]

        if monitor and monitor.abortRequested():
            result.canceled = True
            if job is not None:
                job.next_index = index
                save_job(job)
            return

        if progress:
            if progress.iscanceled():
                result.canceled = True
                if job is not None:
                    job.next_index = index
                    save_job(job)
                return
            percent = int((index / max(total, 1)) * 100)
            progress.update(percent, f"{item.display_title} — checking local sources…")

        if is_library_scanning():
            log("Library scan started mid-run; stopping gracefully", xbmc.LOGWARNING)
            result.canceled = True
            if job is not None:
                job.next_index = index
                save_job(job)
            return

        try:
            current = fetch_item_details(item, settings) or item
            if not has_missing_data(current, settings):
                if job is not None:
                    job.next_index = index + 1
                    save_job(job)
                continue

            art_applied, nfo_applied = apply_local_fixes(current, settings)
            if art_applied:
                result.local_art_fixed += 1
                if job is not None:
                    job.stats.local_art_fixed = result.local_art_fixed
            if nfo_applied:
                result.local_nfo_fixed += 1
                if job is not None:
                    job.stats.local_nfo_fixed = result.local_nfo_fixed

            updated = fetch_item_details(current, settings) or current
            if not has_missing_data(updated, settings):
                if job is not None:
                    job.next_index = index + 1
                    save_job(job)
                continue

            if progress:
                progress.update(
                    int((index / max(total, 1)) * 100),
                    f"{updated.display_title} — refreshing via scrapers…",
                )

            if updated.item_type == "season" and updated.tvshowid in refreshed_tvshows:
                log(
                    f"Skipping duplicate RefreshTVShow for {updated.display_title} "
                    f"(tvshowid={updated.tvshowid} already refreshed this run)"
                )
            elif refresh_item(updated, settings):
                result.scraper_refreshed += 1
                if updated.item_type == "tvshow":
                    refreshed_tvshows.add(updated.item_id)
                elif updated.item_type == "season" and updated.tvshowid:
                    refreshed_tvshows.add(updated.tvshowid)
                if job is not None:
                    job.stats.scraper_refreshed = result.scraper_refreshed
                if _sleep_throttle(settings, monitor):
                    result.canceled = True
                    if job is not None:
                        job.next_index = index + 1
                        save_job(job)
                    return
            elif art_applied or nfo_applied:
                if _sleep_throttle(settings, monitor):
                    result.canceled = True
                    if job is not None:
                        job.next_index = index + 1
                        save_job(job)
                    return
        except Exception as exc:
            log(f"Error processing {item.display_title}: {exc}", xbmc.LOGERROR)
            result.errors += 1
            if job is not None:
                job.stats.errors = result.errors

        if job is not None:
            job.next_index = index + 1
            save_job(job)

    if progress:
        progress.update(100, "Complete")


def run(
    *,
    dry_run: bool = False,
    scope: str = "full",
    item_type: str | None = None,
    item_id: int | None = None,
    progress: xbmcgui.DialogProgress | None = None,
    notify: bool = False,
    settings: UpdatarrSettings | None = None,
    resume_job: UpdateJob | None = None,
    from_dry_run: RunResult | None = None,
    monitor: xbmc.Monitor | None = None,
) -> RunResult:
    settings = settings or read_settings()
    result = RunResult()

    if not acquire_run_lock(scope):
        log(f"Run skipped (scope={scope}): another Library Updatarr run is already in progress", xbmc.LOGWARNING)
        result.already_running = True
        return result

    try:
        return _run_locked(
            dry_run=dry_run,
            scope=scope,
            item_type=item_type,
            item_id=item_id,
            progress=progress,
            notify=notify,
            settings=settings,
            resume_job=resume_job,
            from_dry_run=from_dry_run,
            monitor=monitor,
            result=result,
        )
    finally:
        release_run_lock()


def _run_locked(
    *,
    dry_run: bool,
    scope: str,
    item_type: str | None,
    item_id: int | None,
    progress: xbmcgui.DialogProgress | None,
    notify: bool,
    settings: UpdatarrSettings,
    resume_job: UpdateJob | None,
    from_dry_run: RunResult | None,
    monitor: xbmc.Monitor | None,
    result: RunResult,
) -> RunResult:
    clear_show_folder_cache()
    clear_season_nfo_index()

    if is_library_scanning():
        log("Library scan in progress; aborting run", xbmc.LOGWARNING)
        result.errors += 1
        return result

    job: UpdateJob | None = None
    missing_items: list[LibraryItem] = []
    start_index = 0

    if resume_job is not None:
        job = resume_job
        missing_items = _items_from_job(job)
        start_index = job.next_index
        result.scanned = job.scanned
        result.skipped_complete = job.skipped_complete
        result.missing_summary = dict(job.missing_summary)
        result.resumed = True
        _apply_stats_to_result(result, job)
        log(f"Resuming job at item {start_index + 1}/{len(missing_items)}")
    elif from_dry_run is not None:
        missing_items = list(from_dry_run.pending_items)
        result.scanned = from_dry_run.scanned
        result.skipped_complete = from_dry_run.skipped_complete
        result.missing_summary = dict(from_dry_run.missing_summary)
        log(f"Starting update from dry run ({len(missing_items)} item(s))")
        if missing_items:
            job = create_job(
                scope=scope,
                item_type=item_type,
                item_id=item_id,
                scanned=result.scanned,
                skipped_complete=result.skipped_complete,
                missing_summary=result.missing_summary,
                pending_items=missing_items,
            )
            save_job(job)
    else:
        try:
            all_items = fetch_items_for_scope(
                settings,
                scope=scope,
                item_type=item_type,
                item_id=item_id,
                progress=progress,
                monitor=monitor,
            )
        except ScanCanceled:
            result.canceled = True
            result.scan_canceled = True
            log("Library scan canceled by user")
            return result
        except Exception as exc:
            log(f"Failed to fetch library items: {exc}", xbmc.LOGERROR)
            result.errors += 1
            return result

        if scope == "context":
            candidates = list(all_items)
        else:
            candidates = [item for item in all_items if _should_process_type(item.item_type, settings)]
        try:
            missing_items = _filter_missing_items(candidates, settings, progress, monitor)
        except ScanCanceled:
            result.canceled = True
            result.scan_canceled = True
            log("Library scan canceled by user")
            return result
        result.scanned = len(candidates)
        result.skipped_complete = len(candidates) - len(missing_items)
        result.missing_summary = summarize_missing(missing_items, settings)

        if dry_run:
            result.pending_items = missing_items
            log(f"Dry run: {len(missing_items)} item(s) need updates")
            return result

        if missing_items and scope != "context":
            job = create_job(
                scope=scope,
                item_type=item_type,
                item_id=item_id,
                scanned=result.scanned,
                skipped_complete=result.skipped_complete,
                missing_summary=result.missing_summary,
                pending_items=missing_items,
            )
            save_job(job)

    if not missing_items:
        if scope != "context" and resume_job is None:
            clear_job()
        return result

    _process_items(
        missing_items,
        settings=settings,
        result=result,
        progress=progress,
        job=job,
        start_index=start_index,
        monitor=monitor,
    )

    if result.canceled:
        return result

    if scope != "context":
        clear_job()

    if notify:
        xbmcgui.Dialog().notification(
            addon_name(),
            f"Updated {result.scraper_refreshed + result.local_art_fixed + result.local_nfo_fixed} item(s)",
            addon_icon(),
            5000,
        )

    log(result.summary_text())
    return result


def dry_run_summary_text(result: RunResult) -> str:
    if result.scanned == 0:
        return "No library items found for the selected scope."

    lines = [
        f"Items scanned: {result.scanned}",
        f"Already complete: {result.skipped_complete}",
        f"Need updates: {result.need_updates}",
    ]
    if result.missing_summary:
        lines.append("")
        lines.append("Missing field breakdown:")
        for key, count in sorted(result.missing_summary.items()):
            lines.append(f"  {key}: {count}")
    return "\n".join(lines)


def dry_run_follow_up_message(result: RunResult, prompt: str) -> str:
    """Combine dry-run summary with the run-now confirmation prompt."""
    return f"{dry_run_summary_text(result)}\n\n{prompt}"
