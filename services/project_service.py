from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from models.project import Project
from models.chapter import Chapter
from models.character import Character
from models.environment import Environment
from models.scene import Scene

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
PROJECTS_DIR = PROJECT_ROOT / "Projects"


def get_project_dir(project_name: str) -> Path:
    return PROJECTS_DIR / project_name


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def create_project(title: str, art_style: str, source_file_path: str = None) -> tuple[Project, Path]:
    clean_title = title.replace('\u0000', '').replace('\x00', '').strip()
    safe_name = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in clean_title).strip()
    if not safe_name:
        safe_name = "Untitled"

    project_dir = PROJECTS_DIR / safe_name
    counter = 1
    base = project_dir
    while project_dir.exists():
        project_dir = base.parent / f"{base.name}_{counter}"
        counter += 1

    _ensure_dir(project_dir / "images" / "characters")
    _ensure_dir(project_dir / "images" / "environments")
    _ensure_dir(project_dir / "images" / "scenes")
    _ensure_dir(project_dir / "source")

    project = Project(title=clean_title, art_style=art_style)

    if source_file_path:
        src = Path(source_file_path)
        if src.is_file():
            dest = project_dir / "source" / src.name
            shutil.copy2(src, dest)
            project.source_filename = src.name

    save_project(project, project_dir)

    return project, project_dir


def save_project(project: Project, project_dir: Path) -> None:
    _ensure_dir(project_dir)
    data = _project_to_dict(project)
    json_path = project_dir / "project.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_project(project_dir: Path) -> Project:
    json_path = project_dir / "project.json"
    if not json_path.exists():
        raise FileNotFoundError(f"No project.json found in {project_dir}")

    raw = json.loads(json_path.read_text(encoding="utf-8"))
    return _dict_to_project(raw)


def delete_asset_image(image_path: str | None) -> None:
    if not image_path:
        return
    p = Path(image_path)
    if p.is_file():
        p.unlink()


def delete_project(project_dir: Path) -> None:
    if project_dir.exists():
        shutil.rmtree(project_dir)


def list_projects() -> list[dict]:
    if not PROJECTS_DIR.exists():
        return []

    results = []
    for folder in sorted(PROJECTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        json_path = folder / "project.json"
        if not json_path.is_file():
            continue
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            import datetime
            mtime = datetime.datetime.fromtimestamp(json_path.stat().st_mtime)
            results.append({
                "id": folder.name,
                "title": raw.get("title", folder.name),
                "date": mtime.strftime("%B %d, %Y"),
                "dir_path": str(folder),
                "bg_color": "#2a2a2a",
            })
        except Exception:
            continue

    return results


def _dict_to_chapter(d: dict) -> Chapter:
    scenes_list = []
    scenes_data = d.get("scenes", [])
    if scenes_data:
        from models.scene import Scene
        from dataclasses import fields
        valid_fields = {f.name for f in fields(Scene)}

        scenes_list = []
        for item in scenes_data:
            clean_item = {k: v for k, v in item.items() if k in valid_fields}
            scenes_list.append(Scene(**clean_item))

    return Chapter(
        order_index=d.get("order_index", 0),
        title=d.get("title", ""),
        raw_text=d.get("raw_text", ""),
        scenes=scenes_list
    )


def _chapter_to_dict(ch: Chapter) -> dict:
    return {
        "order_index": ch.order_index,
        "title": ch.title,
        "raw_text": ch.raw_text,
        "scenes": [asdict(s) for s in ch.scenes],
    }


def _project_to_dict(project: Project) -> dict:
    return {
        "title": project.title,
        "art_style": project.art_style,
        "source_filename": project.source_filename,
        "view_models": project.view_models,
        "chapters": [asdict(ch) for ch in project.chapters],
        "characters": [asdict(c) for c in project.characters],
        "environments": [asdict(e) for e in project.environments],
    }


def _dict_to_project(d: dict) -> Project:
    chapters_data = d.get("chapters", [])
    chapters = []

    from models.scene import Scene
    from dataclasses import fields
    scene_valid_keys = {f.name for f in fields(Scene)}

    for cd in chapters_data:
        scenes_list = []
        for sd in cd.get("scenes", []):
             clean_sd = {k: v for k, v in sd.items() if k in scene_valid_keys}
             scenes_list.append(Scene(**clean_sd))

        chapters.append(Chapter(
            order_index=cd.get("order_index", 0),
            title=cd.get("title", ""),
            raw_text=cd.get("raw_text", ""),
            scenes=scenes_list
        ))

    characters_data = d.get("characters", [])
    characters = []
    if characters_data:
        from models.character import Character
        from dataclasses import fields
        char_valid_keys = {f.name for f in fields(Character)}
        for cd in characters_data:
            clean_cd = {k: v for k, v in cd.items() if k in char_valid_keys}
            characters.append(Character(**clean_cd))

    environments_data = d.get("environments", [])
    environments = []
    if environments_data:
        from models.environment import Environment
        from dataclasses import fields
        env_valid_keys = {f.name for f in fields(Environment)}
        for ed in environments_data:
            clean_ed = {k: v for k, v in ed.items() if k in env_valid_keys}
            environments.append(Environment(**clean_ed))

    return Project(
        title=d.get("title", "Untitled"),
        art_style=d.get("art_style", ""),
        source_filename=d.get("source_filename"),
        view_models=d.get("view_models", {}),
        chapters=chapters,
        characters=characters,
        environments=environments,
    )


def save_project_as(project: Project, new_project_dir: Path) -> None:
    _ensure_dir(new_project_dir)
    chars_dir = new_project_dir / "images" / "characters"
    envs_dir = new_project_dir / "images" / "environments"
    scenes_dir = new_project_dir / "images" / "scenes"
    _ensure_dir(chars_dir)
    _ensure_dir(envs_dir)
    _ensure_dir(scenes_dir)

    def _copy_asset(src_path: str | None, dst_dir: Path) -> str | None:
        if not src_path:
            return None
        src = Path(src_path)
        if not src.is_file():
            # If the path is relative to an existing project, try resolving
            # relative to PROJECTS_DIR (best-effort). Otherwise skip.
            alt = PROJECTS_DIR / src_path
            if alt.is_file():
                src = alt
            else:
                return None

        dst = dst_dir / src.name
        if dst.exists():
            try:
                if dst.stat().st_size == src.stat().st_size:
                    return str(dst)
            except Exception:
                pass

        shutil.copy2(src, dst)
        return str(dst)

    for c in project.characters:
        c.image_path = _copy_asset(c.image_path, chars_dir)

    for e in project.environments:
        e.image_path = _copy_asset(e.image_path, envs_dir)

    for ch in project.chapters:
        for s in ch.scenes:
            s.image_path = _copy_asset(s.image_path, scenes_dir)

    save_project(project, new_project_dir)
