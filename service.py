# -*- coding: utf-8 -*-
"""Background service for scheduled library updates."""

from __future__ import annotations

import time

import xbmc
import xbmcgui

from lib.job_store import has_resumable_job, load_job
from lib.jsonrpc import is_library_scanning, log
from lib.runner import run
from lib.settings import (
    addon_icon,
    addon_name,
    get_last_run_epoch,
    read_settings,
    set_last_run_epoch,
)

ADDON_ID = "service.library.updatarr"
CHECK_INTERVAL_SEC = 60


class UpdatarrMonitor(xbmc.Monitor):
    def onScreensaverActivated(self) -> None:
        self._maybe_run_scheduled()

    def run(self) -> None:
        log("Service started")
        while not self.waitForAbort(CHECK_INTERVAL_SEC):
            if self.abortRequested():
                break
            self._maybe_run_scheduled()
        log("Service stopped (add-on unload or Kodi shutdown)")

    def _playback_idle(self, settings) -> bool:
        if not settings.run_while_idle:
            return True
        try:
            return not xbmc.Player().isPlayingVideo()
        except RuntimeError:
            return True

    def _maybe_run_scheduled(self) -> None:
        settings = read_settings()
        if not settings.enable_schedule:
            return

        if is_library_scanning():
            log("Scheduled run deferred: library scan active")
            return

        if not self._playback_idle(settings):
            log("Scheduled run deferred: video playing")
            return

        resume_job = load_job() if has_resumable_job() else None
        if resume_job:
            log("Resuming saved update job from scheduled service")
        else:
            now = int(time.time())
            last_run = get_last_run_epoch()
            interval_sec = settings.schedule_interval_hours * 3600
            if last_run and (now - last_run) < interval_sec:
                return
            log("Starting scheduled library update")

        result = run(notify=False, settings=settings, resume_job=resume_job, monitor=self)
        if result.already_running:
            return
        if not result.canceled:
            set_last_run_epoch(int(time.time()))

        if settings.notify_on_schedule:
            xbmcgui.Dialog().notification(
                addon_name(),
                result.summary_text().replace("\n", " | "),
                addon_icon(),
                8000,
            )


if __name__ == "__main__":
    UpdatarrMonitor().run()
