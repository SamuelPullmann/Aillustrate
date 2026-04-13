from __future__ import annotations
from dataclasses import dataclass, field
import uuid


@dataclass
class Scene:
    title: str
    description: str
    environment_id: str | None = None
    character_ids: list[str] = field(default_factory=list)
    image_path: str | None = None
    seed: int | None = None
    seed_locked: bool = False
    aspect_ratio: str = "9:16"
    refinement_history: list[str] = field(default_factory=list)
    image_path_history: list[str] = field(default_factory=list)
    anchor_text: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
