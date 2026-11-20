"""Addon settings reader."""

from __future__ import annotations

from dataclasses import dataclass

import xbmcaddon

ADDON_ID = "service.library.updatarr"


@dataclass
class UpdatarrSettings:
    process_movies: bool = True
    process_tvshows: bool = True
    process_episodes: bool = True
    check_poster: bool = True
    check_fanart: bool = True
    check_thumb: bool = True
    check_plot: bool = True
    check_title: bool = False
    check_rating: bool = False
    check_cast: bool = False
    enable_local_artwork: bool = True
    enable_local_nfo: bool = True
    enable_scraper_pass: bool = True
    ignore_nfo: bool = False
    refresh_show_episodes: bool = False
    context_refresh_episodes: bool = True
    delay_ms: int = 3000
    batch_size: int = 100
    debug_log: bool = False
    verbose_log: bool = False
    enable_schedule: bool = False
    schedule_interval_hours: int = 24
    run_while_idle: bool = True
    notify_on_schedule: bool = True


def _addon() -> xbmcaddon.Addon:
    return xbmcaddon.Addon(id=ADDON_ID)


def _read_int(addon: xbmcaddon.Addon, setting_id: str, default: int, minimum: int) -> int:
    raw = addon.getSettingInt(setting_id)
    value = default if raw is None else int(raw)
    return max(minimum, value)


def read_settings() -> UpdatarrSettings:
    addon = _addon()
    return UpdatarrSettings(
        process_movies=addon.getSettingBool("process_movies"),
        process_tvshows=addon.getSettingBool("process_tvshows"),
        process_episodes=addon.getSettingBool("process_episodes"),
        check_poster=addon.getSettingBool("check_poster"),
        check_fanart=addon.getSettingBool("check_fanart"),
        check_thumb=addon.getSettingBool("check_thumb"),
        check_plot=addon.getSettingBool("check_plot"),
        check_title=addon.getSettingBool("check_title"),
        check_rating=addon.getSettingBool("check_rating"),
        check_cast=addon.getSettingBool("check_cast"),
        enable_local_artwork=addon.getSettingBool("enable_local_artwork"),
        enable_local_nfo=addon.getSettingBool("enable_local_nfo"),
        enable_scraper_pass=addon.getSettingBool("enable_scraper_pass"),
        ignore_nfo=addon.getSettingBool("ignore_nfo"),
        refresh_show_episodes=addon.getSettingBool("refresh_show_episodes"),
        context_refresh_episodes=addon.getSettingBool("context_refresh_episodes"),
        delay_ms=_read_int(addon, "delay_ms", 3000, 0),
        batch_size=_read_int(addon, "batch_size", 100, 10),
        debug_log=addon.getSettingBool("debug_log"),
        verbose_log=addon.getSettingBool("verbose_log"),
        enable_schedule=addon.getSettingBool("enable_schedule"),
        schedule_interval_hours=_read_int(addon, "schedule_interval_hours", 24, 1),
        run_while_idle=addon.getSettingBool("run_while_idle"),
        notify_on_schedule=addon.getSettingBool("notify_on_schedule"),
    )


def get_last_run_epoch() -> int:
    try:
        return int(_addon().getSettingString("last_run_epoch") or "0")
    except (TypeError, ValueError):
        return 0


def set_last_run_epoch(epoch: int) -> None:
    _addon().setSettingString("last_run_epoch", str(int(epoch)))


def addon_name() -> str:
    return _addon().getAddonInfo("name")


def addon_icon() -> str:
    return _addon().getAddonInfo("icon")


def localized(string_id: int, fallback: str = "") -> str:
    try:
        text = _addon().getLocalizedString(string_id)
        return text or fallback
    except (RuntimeError, AttributeError):
        return fallback
