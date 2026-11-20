"""Tests for launcher dialog mapping and addon.xml context visibility."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import launcher
from lib.job_store import UpdateJob


def test_prompt_existing_job_button_mapping(monkeypatch):
    calls: list[tuple] = []

    class _FakeDialog:
        def __init__(self, return_value: int):
            self._rv = return_value

        def yesnocustom(self, heading, message, customlabel, nolabel, yeslabel):
            calls.append((customlabel, nolabel, yeslabel))
            return self._rv

    job = UpdateJob(pending_items=[{"item_type": "movie", "item_id": 1}], next_index=0)
    monkeypatch.setattr(launcher, "load_job", lambda: job)

    monkeypatch.setattr(launcher.xbmcgui, "Dialog", lambda: _FakeDialog(1))
    assert launcher._prompt_existing_job() == launcher.JOB_RESUME

    monkeypatch.setattr(launcher.xbmcgui, "Dialog", lambda: _FakeDialog(0))
    assert launcher._prompt_existing_job() == launcher.JOB_START_FRESH

    monkeypatch.setattr(launcher.xbmcgui, "Dialog", lambda: _FakeDialog(2))
    assert launcher._prompt_existing_job() == launcher.JOB_CANCEL

    monkeypatch.setattr(launcher.xbmcgui, "Dialog", lambda: _FakeDialog(-1))
    assert launcher._prompt_existing_job() == launcher.JOB_CANCEL

    # customlabel=Cancel (32056), nolabel=Start Fresh (32055), yeslabel=Resume Job (32054)
    assert calls[0] == ("STR_32056", "STR_32055", "STR_32054")


def test_addon_xml_context_visibility_restricts_dbtype():
    addon_xml = Path(__file__).resolve().parent.parent / "addon.xml"
    root = ET.fromstring(addon_xml.read_text(encoding="utf-8"))
    items = root.findall(".//extension[@point='kodi.context.item']//item")
    by_lib = {item.attrib["library"]: item.findtext("visible", "") for item in items}

    ctx_vis = by_lib["context.py"]
    for media_type in ("movie", "tvshow", "season", "episode"):
        assert f"String.IsEqual(ListItem.DBType,{media_type})" in ctx_vis
    assert "musicvideo" not in ctx_vis
