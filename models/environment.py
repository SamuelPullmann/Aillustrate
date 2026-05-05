from __future__ import annotations
from dataclasses import dataclass, field
import uuid


@dataclass
class Environment:
    """Represents a location or setting extracted from the book.

    ``aspect_ratio`` controls the generated image orientation (e.g. ``"16:9"``, ``"9:16"``).
    ``image_path_history`` and ``refinement_history`` enable undo/rollback of image edits.
    """
    name: str
    merged_description: str = ""
    descriptions_by_chapter: list[str] = field(default_factory=list)
    image_path: str | None = None
    seed: int | None = None
    seed_locked: bool = False
    refinement_history: list[str] = field(default_factory=list)
    image_path_history: list[str] = field(default_factory=list)
    aspect_ratio: str = "16:9"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
