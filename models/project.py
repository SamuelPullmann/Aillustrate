from __future__ import annotations
from dataclasses import dataclass, field
from models.chapter import Chapter
from models.character import Character
from models.environment import Environment


@dataclass
class Project:
    """Root data model holding all project content.

    ``source_filename`` is the filename (not full path) of the original book file,
    stored relative to ``project_dir/source/``.
    ``view_models`` maps tab names (e.g. ``"Characters"``) to the selected image model ID.
    """
    title: str
    art_style: str
    chapters: list[Chapter] = field(default_factory=list)
    characters: list[Character] = field(default_factory=list)
    environments: list[Environment] = field(default_factory=list)
    source_filename: str | None = None
    view_models: dict = field(default_factory=dict)
