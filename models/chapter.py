from __future__ import annotations
from dataclasses import dataclass, field
from models.scene import Scene


@dataclass
class Chapter:
    order_index: int
    title: str
    raw_text: str
    scenes: list[Scene] = field(default_factory=list)
    start_page: int | None = None
    end_page: int | None = None
