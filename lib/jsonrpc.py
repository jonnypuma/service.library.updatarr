"""JSON-RPC helpers for Kodi VideoLibrary calls."""

from __future__ import annotations

import json

import xbmc

LOG_PREFIX = "[service.library.updatarr]"


def log(message: str, level=xbmc.LOGINFO) -> None:
    xbmc.log(f"{LOG_PREFIX} {message}", level)


def jsonrpc(method: str, params: dict | None = None, *, debug: bool = False) -> dict:
    command = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}
    try:
        raw = xbmc.executeJSONRPC(json.dumps(command))
        response = json.loads(raw)
    except (RuntimeError, TypeError, ValueError) as exc:
        log(f"JSON-RPC transport error for {method}: {exc}", xbmc.LOGERROR)
        return {}

    if debug:
        log(f"{method} response: {raw}", xbmc.LOGDEBUG)

    if "error" in response:
        log(f"JSON-RPC error for {method}: {response['error']}", xbmc.LOGERROR)
        return {"_error": True}

    result = response.get("result")
    if isinstance(result, dict):
        return result
    if result is not None:
        return {"_ok": True, "_value": result}
    return {"_ok": True}


def is_library_scanning() -> bool:
    """True when Kodi is scanning/updating the video library (Kodi v22+ compatible)."""
    try:
        if xbmc.getCondVisibility("Library.IsScanningVideo"):
            return True
        if xbmc.getCondVisibility("Library.IsScanning"):
            return True
    except (RuntimeError, AttributeError, TypeError):
        pass
    return False
