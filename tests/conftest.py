"""Pytest fixtures and Kodi module stubs for Library Updatarr tests."""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_kodi_stubs() -> None:
    if "xbmc" not in sys.modules:
        xbmc = types.ModuleType("xbmc")
        xbmc.LOGDEBUG = 0
        xbmc.LOGINFO = 1
        xbmc.LOGWARNING = 2
        xbmc.LOGERROR = 3
        xbmc.LOGFATAL = 4
        xbmc.LOGNONE = 5
        xbmc.log = MagicMock()
        xbmc.executeJSONRPC = MagicMock(return_value='{"jsonrpc":"2.0","id":1,"result":{}}')
        xbmc.getCondVisibility = MagicMock(return_value=False)
        xbmc.getInfoLabel = MagicMock(return_value="")
        xbmc.sleep = MagicMock()

        class Monitor:
            def abortRequested(self) -> bool:
                return False

            def waitForAbort(self, timeout: float) -> bool:
                return False

            def onScreensaverActivated(self) -> None:
                pass

        class Player:
            def isPlayingVideo(self) -> bool:
                return False

        xbmc.Monitor = Monitor
        xbmc.Player = Player
        sys.modules["xbmc"] = xbmc

    if "xbmcaddon" not in sys.modules:
        xbmcaddon = types.ModuleType("xbmcaddon")

        class Addon:
            def __init__(self, id: str | None = None, addon_id: str | None = None) -> None:
                self.id = id or addon_id or "service.library.updatarr"

            def getAddonInfo(self, info: str) -> str:
                return {"name": "Library Updatarr", "icon": "icon.png", "profile": "/tmp/updatarr/"}.get(info, "")

            def getLocalizedString(self, string_id: int) -> str:
                return f"STR_{string_id}"

            def getSettingBool(self, key: str) -> bool:
                return False

            def getSettingInt(self, key: str) -> int:
                return 0

            def getSettingString(self, key: str) -> str:
                return ""

            def setSettingString(self, key: str, value: str) -> None:
                pass

        xbmcaddon.Addon = Addon
        sys.modules["xbmcaddon"] = xbmcaddon

    if "xbmcgui" not in sys.modules:
        xbmcgui = types.ModuleType("xbmcgui")
        xbmcgui.NOTIFICATION_ERROR = 2
        xbmcgui.NOTIFICATION_INFO = 0
        xbmcgui.NOTIFICATION_WARNING = 1

        class DialogProgress:
            def create(self, heading: str, line1: str = "", line2: str = "", line3: str = "") -> None:
                pass

            def update(self, percent: int, line1: str = "", line2: str = "", line3: str = "") -> None:
                pass

            def iscanceled(self) -> bool:
                return False

            def close(self) -> None:
                pass

        class Dialog:
            def yesno(self, *args, **kwargs) -> bool:
                return True

            def yesnocustom(self, *args, **kwargs) -> int:
                return 1

            def ok(self, *args, **kwargs) -> None:
                pass

            def notification(self, *args, **kwargs) -> None:
                pass

        class Window:
            _props: dict[str, str] = {}

            def __init__(self, window_id: int = 10000) -> None:
                self.window_id = window_id

            def getProperty(self, key: str) -> str:
                return self._props.get(key, "")

            def setProperty(self, key: str, value: str) -> None:
                self._props[key] = value

            def clearProperty(self, key: str) -> None:
                self._props.pop(key, None)

        xbmcgui.DialogProgress = DialogProgress
        xbmcgui.Dialog = Dialog
        xbmcgui.Window = Window
        sys.modules["xbmcgui"] = xbmcgui

    if "xbmcvfs" not in sys.modules:
        xbmcvfs = types.ModuleType("xbmcvfs")
        xbmcvfs.exists = MagicMock(return_value=False)
        xbmcvfs.listdir = MagicMock(return_value=([], []))
        xbmcvfs.translatePath = lambda p: p
        xbmcvfs.delete = MagicMock(return_value=True)
        xbmcvfs.rename = MagicMock(return_value=True)
        xbmcvfs.File = MagicMock()
        xbmcvfs.Stat = MagicMock()
        sys.modules["xbmcvfs"] = xbmcvfs


_install_kodi_stubs()


@pytest.fixture(autouse=True)
def _reset_kodi_state(monkeypatch):
    import xbmc
    import xbmcgui
    import xbmcvfs
    from lib import local_fixer, run_lock, show_folder

    xbmcgui.Window._props.clear()
    run_lock._IN_PROCESS_HELD = False
    show_folder.clear_show_folder_cache()
    local_fixer.clear_season_nfo_index()
    monkeypatch.setattr(xbmc, "log", MagicMock())
    monkeypatch.setattr(xbmc, "sleep", MagicMock())
    monkeypatch.setattr(xbmc, "getCondVisibility", MagicMock(return_value=False))
    monkeypatch.setattr(xbmc, "executeJSONRPC", MagicMock(return_value='{"jsonrpc":"2.0","id":1,"result":{}}'))
    monkeypatch.setattr(xbmcvfs, "exists", MagicMock(return_value=False))
    monkeypatch.setattr(xbmcvfs, "listdir", MagicMock(return_value=([], [])))
    yield
    run_lock._IN_PROCESS_HELD = False
    xbmcgui.Window._props.clear()
