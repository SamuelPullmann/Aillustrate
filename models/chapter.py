from __future__ import annotations
from dataclasses import dataclass, field
from models.scene import Scene


@dataclass
class Chapter:
    """Represents a single chapter of the source book.

    ``start_page`` and ``end_page`` are 1-based PDF page numbers used during
    PDF export to locate where to insert scene illustrations.
    """
    order_index: int
    title: str
    raw_text: str
    scenes: list[Scene] = field(default_factory=list)
    start_page: int | None = None
    end_page: int | None = None
