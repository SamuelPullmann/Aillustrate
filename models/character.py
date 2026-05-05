from __future__ import annotations
from dataclasses import dataclass, field
import uuid


@dataclass
class Character:
    """Represents a character extracted from the book.

    ``image_path_history`` stores the sequence of image paths in the order
    [original, after_refine_1, after_refine_2, ...] to enable undo/rollback.
    ``refinement_history`` stores the corresponding user instructions.
    """
    name: str
    merged_description: str = ""
    descriptions_by_chapter: list[str] = field(default_factory=list)
    image_path: str | None = None
    seed: int | None = None
    seed_locked: bool = False
    refinement_history: list[str] = field(default_factory=list)
    image_path_history: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
