from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from models.project import Project


@dataclass
class ProjectStore:
    """Holds the currently open project and its folder path."""
    current_project: Project | None = None
    project_dir: Path | None = None


@dataclass
class UIStore:
    """Tracks transient UI state shared across views (active tab, selections, etc.)."""
    current_screen: str = "start"
    active_tab: str = "Characters"
    is_analyzing_book: bool = False
    global_error_message: str = ""
    selected_character_id: str | None = None
    selected_environment_id: str | None = None
    selected_scene_id: str | None = None
    scene_env_map: dict[str, str] = field(default_factory=dict)
