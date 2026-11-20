"""Verbose local-source logging (NFO and artwork discovery)."""

from __future__ import annotations

import xbmc

from lib.jsonrpc import log
from lib.settings import UpdatarrSettings


def verbose_log(settings: UpdatarrSettings, message: str) -> None:
    if settings.verbose_log:
        log(f"[verbose] {message}", xbmc.LOGINFO)
