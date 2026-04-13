from __future__ import annotations
from dataclasses import dataclass, field
import uuid


@dataclass
class Character:
    name: str
    merged_description: str = ""
    descriptions_by_chapter: list[str] = field(default_factory=list)
    image_path: str | None = None
    seed: int | None = None
    seed_locked: bool = False
    refinement_history: list[str] = field(default_factory=list)
    image_path_history: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
