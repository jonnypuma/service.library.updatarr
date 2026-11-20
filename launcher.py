# -*- coding: utf-8 -*-
"""Manual entry point and settings actions."""

from __future__ import annotations

import sys
import time

import xbmc
import xbmcaddon
import xbmcgui

from lib.job_store import UpdateJob, clear_job, has_resumable_job, load_job
from lib.runner import (
    RunResult,
    dry_run_follow_up_message,
    dry_run_summary_text,
    run,
)
from lib.settings import addon_name, localized, read_settings

ADDON_ID = "service.library.updatarr"
_ADDON = xbmcaddon.Addon()

JOB_RESUME = 0
JOB_START_FRESH = 1
JOB_CANCEL = 2


def _confirm_run(dry_run: bool) -> bool:
    settings = read_settings()
    scope_parts = []
    if settings.process_movies:
        scope_parts.append("movies")
    if settings.process_tvshows:
        scope_parts.append("TV shows")
    if settings.process_episodes:
        scope_parts.append("episodes")

    action = localized(32065, "Dry run (scan only)") if dry_run else localized(32066, "Update missing data")
    scope = ", ".join(scope_parts) if scope_parts else "nothing enabled"
    message = (
        f"{action}\n\n"
        f"Scope: {scope}\n"
        f"Local artwork: {'yes' if settings.enable_local_artwork else 'no'}\n"
        f"Local NFO: {'yes' if settings.enable_local_nfo else 'no'}\n"
        f"Scraper pass: {'yes' if settings.enable_scraper_pass else 'no'}\n\n"
        f"{localized(32067, 'Continue?')}"
    )
    return xbmcgui.Dialog().yesno(addon_name(), message)


def _prompt_existing_job() -> int:
    job = load_job()
    if job is None:
        return JOB_START_FRESH

    updated = time.strftime(
        "%Y-%m-%d %H:%M",
        time.localtime(job.updated_epoch or job.created_epoch),
    )
    message = f"{job.summary_line()}\nLast checkpoint: {updated}"
    choice = xbmcgui.Dialog().yesnocustom(
        _ADDON.getLocalizedString(32053),
        message,
        _ADDON.getLocalizedString(32056),
        _ADDON.getLocalizedString(32055),
        _ADDON.getLocalizedString(32054),
    )
    if choice == 1:
        return JOB_RESUME
    if choice == 0:
        return JOB_START_FRESH
    return JOB_CANCEL


def _resolve_resume_job() -> tuple[UpdateJob | None, bool]:
    """Return (resume_job, canceled). canceled=True when the user aborts."""
    if not has_resumable_job():
        return None, False

    job_choice = _prompt_existing_job()
    if job_choice == JOB_CANCEL:
        return None, True
    if job_choice == JOB_RESUME:
        resume_job = load_job()
        if resume_job is None:
            xbmcgui.Dialog().ok(addon_name(), _ADDON.getLocalizedString(32057))
            return None, True
        return resume_job, False

    clear_job()
    return None, False


def _run_with_progress(
    *,
    dry_run: bool,
    resume_job=None,
    from_dry_run: RunResult | None = None,
    progress_label: str,
) -> RunResult:
    progress = xbmcgui.DialogProgress()
    progress.create(addon_name(), progress_label)
    try:
        return run(
            dry_run=dry_run,
            progress=progress,
            resume_job=resume_job,
            from_dry_run=from_dry_run,
        )
    finally:
        progress.close()


def _handle_dry_run_result(dry_result: RunResult) -> None:
    if dry_result.scan_canceled or dry_result.canceled:
        return

    if dry_result.need_updates <= 0:
        xbmcgui.Dialog().ok(addon_name(), dry_run_summary_text(dry_result))
        return

    prompt = _ADDON.getLocalizedString(32052)
    if not xbmcgui.Dialog().yesno(
        addon_name(),
        dry_run_follow_up_message(dry_result, prompt),
    ):
        return

    resume_job, canceled = _resolve_resume_job()
    if canceled:
        return

    if resume_job is not None:
        update_result = _run_with_progress(
            dry_run=False,
            resume_job=resume_job,
            progress_label=_ADDON.getLocalizedString(32058),
        )
    else:
        update_result = _run_with_progress(
            dry_run=False,
            from_dry_run=dry_result,
            progress_label=_ADDON.getLocalizedString(32059),
        )

    if update_result.scan_canceled or update_result.canceled:
        return

    xbmcgui.Dialog().ok(addon_name(), update_result.summary_text())


def _execute(action: str) -> None:
    dry_run = action == "dry_run"
    full_run = action in ("", "run_now")

    if not dry_run and not full_run:
        xbmcgui.Dialog().ok(addon_name(), f"Unknown action: {action}")
        return

    resume_job = None
    if full_run:
        resume_job, canceled = _resolve_resume_job()
        if canceled:
            return

    if resume_job is None and not _confirm_run(dry_run):
        return

    if dry_run:
        dry_result = _run_with_progress(
            dry_run=True,
            progress_label=_ADDON.getLocalizedString(32060),
        )
        if dry_result.scan_canceled or dry_result.canceled:
            return
        _handle_dry_run_result(dry_result)
        return

    result = _run_with_progress(
        dry_run=False,
        resume_job=resume_job,
        progress_label=(
            _ADDON.getLocalizedString(32058)
            if resume_job
            else _ADDON.getLocalizedString(32060)
        ),
    )
    if result.scan_canceled or result.canceled:
        return
    xbmcgui.Dialog().ok(addon_name(), result.summary_text())


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    xbmc.log(f"[{ADDON_ID}] launcher action={action or 'default'}", xbmc.LOGINFO)
    try:
        _execute(action)
    except Exception as exc:
        xbmc.log(f"[{ADDON_ID}] launcher error: {exc}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok(addon_name(), localized(32068, "Error:\n%s") % exc)
