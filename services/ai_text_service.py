from __future__ import annotations

import math
from pathlib import Path
import threading
import vertexai
from vertexai.preview.generative_models import GenerativeModel, Part

from config import VERTEX_PROJECT, VERTEX_LOCATION, TEXT_MODEL, VERTEX_API_KEY, MAX_SCENES_PER_CHAPTER
from models.chapter import Chapter
from models.character import Character
from models.environment import Environment
from models.scene import Scene
from services.response_parser import parse_chapter_analysis

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "Prompts"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


_client_initialized: bool = False
_init_lock = threading.Lock()


def _init_vertex() -> None:
    global _client_initialized
    if _client_initialized:
        return
    with _init_lock:
        if _client_initialized:
            return
        if VERTEX_API_KEY:
            vertexai.init(api_key=VERTEX_API_KEY)
        elif VERTEX_PROJECT and VERTEX_LOCATION:
            vertexai.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION)
        else:
            raise RuntimeError(
                "VERTEX_API_KEY (or VERTEX_PROJECT+LOCATION) is not set. "
                "Put your key in config_local.py or set the env-var."
            )
        _client_initialized = True


# ── Sanitize description for image generation ────────────────────────────

def sanitize_description(description: str) -> str:
    """
    Rewrite a description to be safe for image generation APIs.
    Preserves all visual/physical details while removing content-policy violations.
    """
    _init_vertex()
    template = _load_prompt("sanitize_description.txt")
    prompt = template.replace("{{description}}", description)
    model = GenerativeModel(TEXT_MODEL)
    response = model.generate_content(prompt)
    return response.text.strip()


# ── Merge descriptions via AI ────────────────────────────────────────────

def merge_descriptions(descriptions_by_chapter: list[str]) -> str:
    """
    Send all per-chapter descriptions to the AI and get back a single
    merged description. Returns the merged text string.
    """
    if not descriptions_by_chapter:
        return ""
    if len(descriptions_by_chapter) == 1:
        # Strip the [Chapter Title] prefix if present
        desc = descriptions_by_chapter[0]
        if desc.startswith("[") and "] " in desc:
            desc = desc.split("] ", 1)[1]
        return desc.strip()

    _init_vertex()
    template = _load_prompt("merge_descriptions.txt")
    all_descs = "\n\n".join(descriptions_by_chapter)
    prompt = template.replace("{{descriptions}}", all_descs)

    model = GenerativeModel(TEXT_MODEL)
    response = model.generate_content(prompt)
    return response.text.strip()


# ── Single-chapter analysis ──────────────────────────────────────────────

def _analyze_entity(chapter_text: str, entity_type: str, extra_replacements: dict = None, template_replacements: dict = None) -> dict:
    _init_vertex()

    template = _load_prompt(f"{entity_type}_analysis.txt")
    instructions = _load_prompt(f"{entity_type}_extraction_instructions.txt")

    if extra_replacements:
        for placeholder, value in extra_replacements.items():
            instructions = instructions.replace(placeholder, str(value))

    placeholder = f"{{{{{entity_type}_extraction_instructions}}}}"

    prompt = template.replace("{{chapter}}", chapter_text)
    prompt = prompt.replace(placeholder, instructions)

    if template_replacements:
        for placeholder, value in template_replacements.items():
            prompt = prompt.replace(placeholder, str(value))

    model = GenerativeModel(TEXT_MODEL)
    response = model.generate_content(prompt)

    raw_text = response.text
    return parse_chapter_analysis(raw_text)


def analyze_chapter(chapter_text: str, existing_char_names: list[str] | None = None, existing_env_names: list[str] | None = None) -> dict:
    """Analyze a single chapter's text with AI and extract characters, environments and scenes.

    Passing already-known names via ``existing_char_names`` / ``existing_env_names``
    helps the AI reuse consistent naming instead of creating duplicates.
    Returns a dict with keys ``characters``, ``environments`` and ``scenes``.
    """
    from config import MAX_SCENES_PER_CHAPTER, ANALYZE_CHARACTERS, ANALYZE_SCENES, ANALYZE_ENVIRONMENTS

    char_context = ""
    if existing_char_names:
        names_list = "\n".join(f"- {n}" for n in existing_char_names)
        char_context = (
            "## ALREADY KNOWN CHARACTERS\n"
            "The following characters have already been identified in previous chapters. "
            "If you encounter any of these characters (even referred to by a shorter name, nickname, "
            "or title), use the EXACT name from this list rather than creating a new entry:\n"
            f"{names_list}"
        )

    env_context_for_scenes = ""
    context_parts = []
    if existing_env_names:
        envs_list = "\n".join(f"- {n}" for n in existing_env_names)
        context_parts.append(
            "## KNOWN ENVIRONMENTS\n"
            "The following environments/locations have already been identified. "
            "When filling the 'environment' field, use the EXACT name from this list if it matches the scene's location:\n"
            f"{envs_list}"
        )
    if existing_char_names:
        chars_list = "\n".join(f"- {n}" for n in existing_char_names)
        context_parts.append(
            "## KNOWN CHARACTERS\n"
            "The following characters have already been identified. "
            "When filling the 'characters' array, use the EXACT name from this list if the character appears in the scene "
            "(even if referred to by a shorter name or nickname in the text):\n"
            f"{chars_list}"
        )
    env_context_for_scenes = "\n\n".join(context_parts)

    scenes = []
    if ANALYZE_SCENES:
        max_scenes_val = str(MAX_SCENES_PER_CHAPTER) if MAX_SCENES_PER_CHAPTER > 0 else "ALL"
        scenes_data = _analyze_entity(
            chapter_text,
            "scene",
            extra_replacements={"{{MAX_SCENES}}": max_scenes_val},
            template_replacements={"{{existing_context}}": env_context_for_scenes},
        )
        scenes = scenes_data.get("scenes", [])

    scene_locations = set()
    if ANALYZE_SCENES:
        for s in scenes:
            env = s.get("environment")
            if env:
                scene_locations.add(env)

    scene_locations_str = "\n".join(f"- {loc}" for loc in scene_locations) if scene_locations else "No specific scenes found."

    #Analyze Environments using scene locations context
    environments = []
    if ANALYZE_ENVIRONMENTS and ANALYZE_SCENES:
        environments = _analyze_entity(
            chapter_text,
            "environment",
            extra_replacements={"{{SCENE_LOCATIONS}}": scene_locations_str}
        ).get("environments", [])

        # Safety net: if AI returned more environments than scene locations,
        # filter to keep only those whose name matches a scene location
        if scene_locations and len(environments) > len(scene_locations):
            scene_locs_lower = {loc.lower() for loc in scene_locations}
            filtered = []
            for env_data in environments:
                env_name = env_data.get("name", "").strip().lower()
                # Keep if exact match or if any scene location is a substring (or vice versa)
                if env_name in scene_locs_lower or any(
                    env_name in loc or loc in env_name for loc in scene_locs_lower
                ):
                    filtered.append(env_data)
            if filtered:
                environments = filtered

    characters = []
    if ANALYZE_CHARACTERS:
        characters = _analyze_entity(
            chapter_text,
            "character",
            template_replacements={"{{existing_characters_context}}": char_context},
        ).get("characters", [])

    return {
        "characters": characters,
        "environments": environments,
        "scenes": scenes,
    }


def _resolve_env_id(env_name: str, env_map: dict, analyze_environments: bool) -> str | None:
    if not env_name or not analyze_environments:
        return None
    env_key = env_name.lower()
    if env_key in env_map:
        return env_map[env_key].id
    for key, env in env_map.items():
        if env_key in key or key in env_key:
            return env.id
    return None


def analyze_all_chapters(
    chapters: list[Chapter],
    on_progress: callable = None,
    character_threshold: float = 0,
) -> tuple[list[Character], list[Environment]]:
    """Analyze all chapters and return de-duplicated lists of characters and environments.

    Runs chapter analysis sequentially, merges per-chapter descriptions with AI,
    then does a second pass to resolve any scene links that were missing on the first pass.
    Characters that appear in fewer chapters than the ``character_threshold`` percentage
    are removed, unless they are referenced in a scene.
    Calls ``on_progress(message)`` after each chapter if provided.
    """
    def _report(msg: str):
        if on_progress:
            on_progress(msg)

    from config import MAX_ANALYZE_CHAPTERS, MAX_SCENES_PER_CHAPTER, ANALYZE_CHARACTERS, ANALYZE_SCENES, ANALYZE_ENVIRONMENTS

    chapters_to_process = chapters
    if MAX_ANALYZE_CHAPTERS > 0:
        chapters_to_process = chapters[:MAX_ANALYZE_CHAPTERS]
        _report(f"⚠ Testing mode: analysing first {len(chapters_to_process)} of {len(chapters)} chapters")

    if ANALYZE_ENVIRONMENTS and not ANALYZE_SCENES:
        _report("⚠ Warning: Environment analysis is enabled but scene analysis is disabled. Environments won't be analyzed as they depend on scene locations.")

    char_map: dict[str, Character] = {}
    env_map: dict[str, Environment] = {}

    total = len(chapters_to_process)

    for idx, chapter in enumerate(chapters_to_process, start=1):
        if not chapter.raw_text.strip():
            continue

        _report(f"Analysing chapter {idx}/{total}: {chapter.title}")

        try:
            result = analyze_chapter(
                chapter.raw_text,
                existing_char_names=[c.name for c in char_map.values()] if char_map else None,
                existing_env_names=[e.name for e in env_map.values()] if env_map else None,
            )
        except Exception as exc:
            _report(f"⚠ Failed chapter '{chapter.title}': {exc}")
            continue

        for c_data in result.get("characters", []):
            name = c_data.get("name", "").strip()
            if not name:
                continue

            age = (c_data.get("age") or "").strip()
            gender = (c_data.get("gender") or "").strip()
            species = (c_data.get("species") or "").strip()
            size = (c_data.get("size") or "").strip()
            visual_desc = (c_data.get("visual_description") or c_data.get("description") or "").strip()

            key = name.lower()
            if key not in char_map:
                char_map[key] = Character(name=name)

            char = char_map[key]

            parts = []
            if age and age.lower() != "unknown":
                parts.append(f"Age: {age}")
            if gender and gender.lower() != "unknown":
                parts.append(f"Gender: {gender}")
            if species and species.lower() != "unknown":
                parts.append(f"Species: {species}")
            if size and size.lower() != "unknown":
                parts.append(f"Size: {size}")
            meta = ", ".join(parts)
            if meta and visual_desc:
                full_desc = f"{meta}. {visual_desc}"
            elif meta:
                full_desc = meta
            else:
                full_desc = visual_desc

            chapter_label = f"[{chapter.title}] {full_desc}"
            char.descriptions_by_chapter.append(chapter_label)

        for e_data in result.get("environments", []):
            name = e_data.get("name", "").strip()
            desc = e_data.get("description", "").strip()
            if not name:
                continue

            key = name.lower()
            if key not in env_map:
                env_map[key] = Environment(name=name)

            env = env_map[key]
            chapter_label = f"[{chapter.title}] {desc}"
            env.descriptions_by_chapter.append(chapter_label)

        if ANALYZE_SCENES and "scenes" in result:
            for s_data in result.get("scenes", []):
                title = s_data.get("name", s_data.get("title", "Untitled Scene")).strip()
                description = s_data.get("moment_description", s_data.get("description", "")).strip()
                env_name = s_data.get("environment", "").strip()
                raw_characters = s_data.get("characters", [])
                anchor_text = s_data.get("anchor_text", "").strip()

                char_names = []
                char_details_parts = []
                if isinstance(raw_characters, list):
                    for entry in raw_characters:
                        if isinstance(entry, str):
                            char_names.append(entry)
                        elif isinstance(entry, dict):
                            cname = entry.get("name", "").strip()
                            if cname:
                                char_names.append(cname)
                                detail_lines = [f"[{cname}]"]
                                if entry.get("pose"):
                                    detail_lines.append(f"  Pose: {entry['pose']}")
                                if entry.get("expression"):
                                    detail_lines.append(f"  Expression: {entry['expression']}")
                                if entry.get("position"):
                                    detail_lines.append(f"  Position: {entry['position']}")
                                if entry.get("gaze"):
                                    detail_lines.append(f"  Gaze: {entry['gaze']}")
                                if entry.get("interaction"):
                                    detail_lines.append(f"  Interaction: {entry['interaction']}")
                                char_details_parts.append("\n".join(detail_lines))

                if char_details_parts:
                    description = description + "\n\nCHARACTER DETAILS:\n" + "\n".join(char_details_parts)

                env_id = _resolve_env_id(env_name, env_map, ANALYZE_ENVIRONMENTS)

                c_ids = []
                for cn in char_names:
                    ck = cn.strip().lower()
                    if ck in char_map:
                        c_ids.append(char_map[ck].id)
                c_ids = list(dict.fromkeys(c_ids))[:5]

                scene = Scene(
                    title=title,
                    description=description,
                    environment_id=env_id,
                    character_ids=c_ids,
                    anchor_text=anchor_text,
                )
                chapter.scenes.append(scene)

                scene._raw_env_name = env_name
                scene._raw_char_names = char_names

        n_chars = len(result.get("characters", []))
        n_envs = len(result.get("environments", []))
        n_scenes = len(result.get("scenes", []))
        _report(f"✓ {chapter.title}: {n_chars} chars, {n_envs} envs, {n_scenes} scenes")

    _report(f"Done — {len(char_map)} unique characters, {len(env_map)} unique environments")

    # ── Second-pass: retry environment & character resolution ────────────
    # Now that ALL environments and characters are known, retry linking for
    # scenes that didn't get a match on the first pass.
    resolved_envs = 0
    resolved_chars = 0
    for ch in chapters_to_process:
        for sc in ch.scenes:
            if not sc.environment_id:
                raw_env = getattr(sc, '_raw_env_name', '')
                if raw_env:
                    sc.environment_id = _resolve_env_id(raw_env, env_map, ANALYZE_ENVIRONMENTS)
                    if sc.environment_id:
                        resolved_envs += 1
            raw_chars = getattr(sc, '_raw_char_names', [])
            if raw_chars and len(sc.character_ids) < len(raw_chars):
                existing_ids = set(sc.character_ids)
                for cn in raw_chars:
                    ck = cn.strip().lower()
                    if ck in char_map and char_map[ck].id not in existing_ids:
                        sc.character_ids.append(char_map[ck].id)
                        existing_ids.add(char_map[ck].id)
                        resolved_chars += 1
                sc.character_ids = sc.character_ids[:5]
            if hasattr(sc, '_raw_env_name'):
                del sc._raw_env_name
            if hasattr(sc, '_raw_char_names'):
                del sc._raw_char_names
    if resolved_envs or resolved_chars:
        _report(f"Second pass: resolved {resolved_envs} env links, {resolved_chars} char links")

    if character_threshold > 0 and total > 0:
        # Use ceiling so the required presence is truly "at least X%".
        min_chapters = max(1, math.ceil(total * character_threshold / 100))
        before_count = len(char_map)
        removed_ids = set()

        # Collect all character IDs referenced in any scene — these are always preserved
        scene_char_ids = set()
        for ch in chapters_to_process:
            for sc in ch.scenes:
                scene_char_ids.update(sc.character_ids)

        keys_to_remove = []
        preserved_by_scene = 0
        for key, char in char_map.items():
            if len(char.descriptions_by_chapter) < min_chapters:
                if char.id in scene_char_ids:
                    preserved_by_scene += 1
                else:
                    keys_to_remove.append(key)
                    removed_ids.add(char.id)

        for key in keys_to_remove:
            del char_map[key]

        if removed_ids:
            for ch in chapters_to_process:
                for sc in ch.scenes:
                    sc.character_ids = [cid for cid in sc.character_ids if cid not in removed_ids]

        removed_count = before_count - len(char_map)
        if removed_count or preserved_by_scene:
            msg = (
                f"Threshold {character_threshold}% (min {min_chapters}/{total} chapters): "
                f"removed {removed_count} minor characters, {len(char_map)} remaining"
            )
            if preserved_by_scene:
                msg += f" ({preserved_by_scene} kept because they appear in scenes)"
            _report(msg)

    _report("Merging character descriptions with AI...")
    for char in char_map.values():
        if char.descriptions_by_chapter:
            try:
                char.merged_description = merge_descriptions(char.descriptions_by_chapter)
            except Exception as exc:
                _report(f"⚠ Failed to merge descriptions for {char.name}: {exc}")
                char.merged_description = "\n\n".join(char.descriptions_by_chapter)

    _report("Merging environment descriptions with AI...")
    for env in env_map.values():
        if env.descriptions_by_chapter:
            try:
                env.merged_description = merge_descriptions(env.descriptions_by_chapter)
            except Exception as exc:
                _report(f"⚠ Failed to merge descriptions for {env.name}: {exc}")
                env.merged_description = "\n\n".join(env.descriptions_by_chapter)

    return list(char_map.values()), list(env_map.values())
