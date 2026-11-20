"""Shared data models for library items."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LibraryItem:
    item_type: str
    item_id: int
    title: str = ""
    file_path: str = ""
    plot: str = ""
    art: dict[str, str] = field(default_factory=dict)
    season: int = 0
    episode: int = 0
    showtitle: str = ""
    tvshowid: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def display_title(self) -> str:
        if self.item_type == "episode":
            return f"{self.showtitle or self.title} S{self.season:02d}E{self.episode:02d}"
        if self.item_type == "season":
            label = self.title or f"Season {self.season}"
            if self.tvshowid and not self.title:
                return f"Season {self.season:02d} (#{self.tvshowid})"
            return label
        return self.title or f"{self.item_type} #{self.item_id}"

    def item_dict(self) -> dict[str, int]:
        key = {
            "movie": "movieid",
            "tvshow": "tvshowid",
            "season": "seasonid",
            "episode": "episodeid",
        }.get(self.item_type)
        if not key:
            return {}
        return {key: self.item_id}
