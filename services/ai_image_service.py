from __future__ import annotations

from pathlib import Path
import random
import threading
import time
import warnings

import vertexai
from vertexai.preview.generative_models import GenerativeModel, Image, Part, GenerationConfig

warnings.filterwarnings("ignore", message=".*deprecated as of June 24, 2025.*")

from components.top_nav import get_active_model
from components.footer_bar import set_rate_limit_error

from config import VERTEX_PROJECT, VERTEX_LOCATION, VERTEX_API_KEY
from models.character import Character
from models.environment import Environment
from models.scene import Scene
from services.response_parser import save_image

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


def _extract_image_bytes(response) -> bytes | None:
    """Extract image bytes from a Gemini response containing inline_data."""
    if response.candidates:
        for candidate in response.candidates:
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        return part.inline_data.data
                    if hasattr(part, "byte_data"):
                        return part.byte_data
    return None


def _extract_text_fallback(response) -> str:
    try:
        if getattr(response, "text", None):
            return str(response.text)
    except Exception:
        pass

    try:
        candidates = getattr(response, "candidates", None) or []
        collected = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                text = getattr(part, "text", None)
                if text:
                    collected.append(str(text))
        return "\n".join(collected).strip()
    except Exception:
        return ""

    return ""


class ContentPolicyError(Exception):
    pass


def _is_content_policy_response(response) -> bool:
    try:
        for candidate in (getattr(response, "candidates", None) or []):
            if getattr(candidate, "finish_reason", None) == 12:
                return True
    except Exception:
        pass
    return False


def _call_with_retry(model, *args, max_retries: int = 15, on_retry_status=None, cancel_event: threading.Event = None, **kwargs):
    delay = 15
    for attempt in range(max_retries):
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("Generation cancelled")
        try:
            return model.generate_content(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) or "Resource has been exhausted" in str(e):
                if attempt < max_retries - 1:
                    for remaining in range(delay, 0, -1):
                        if cancel_event and cancel_event.is_set():
                            raise InterruptedError("Generation cancelled")
                        msg = f"Rate limited (429) — retrying in {remaining}s... (attempt {attempt + 1}/{max_retries})"
                        if on_retry_status:
                            try:
                                on_retry_status(msg)
                            except Exception:
                                pass
                        time.sleep(1)
                    delay = min(delay * 2, 60)
                else:
                    set_rate_limit_error("Reached tokens per minute limit, please try again later.")
                    raise
            else:
                raise


def _resolve_art_style(art_style: str) -> str:
    """If art_style is just an ID (e.g. 'epic_fantasy'), resolve it to 'Label - prompt'.
    If it already contains ' - ', return as-is."""
    if " - " in art_style:
        return art_style
    from components.art_style_selector import ART_STYLES
    for s in ART_STYLES:
        if s["id"] == art_style:
            return f"{s['label']} - {s.get('prompt', '')}"
    return art_style


# ── Character portrait (Text2Img) ───────────────────────────────────────

def generate_character_portrait(
    character: Character,
    art_style: str,
    project_dir: Path,
    on_status=None,
    cancel_event: threading.Event = None,
) -> str:
    set_rate_limit_error(None)
    art_style = _resolve_art_style(art_style)
    _init_vertex()

    if getattr(character, "seed", None) is None:
        character.seed = random.randint(0, 2147483647)

    template = _load_prompt("character_portrait.txt")
    prompt = template.replace("{{style}}", art_style)
    prompt = prompt.replace("{{character_description}}", character.merged_description or character.name)
    prompt += "\n\nIMPORTANT: Generate this image in Portrait orientation (aspect ratio 9:16)."

    generation_config = {
        "response_modalities": ["IMAGE", "TEXT"],
        "image_config": {"aspect_ratio": "9:16"}
    }
    if getattr(character, "seed", None) is not None:
        try:
            s_val = int(character.seed)
            if s_val > 2147483647:
                s_val = s_val % 2147483647
            generation_config["seed"] = s_val
        except Exception:
            pass

    def _status(msg: str):
        if on_status:
            on_status(msg)

    def _do_generate() -> bytes:
        nonlocal prompt
        image_model = get_active_model("Characters")
        _resp = None
        try:
            model = GenerativeModel(image_model)
            _resp = _call_with_retry(model, prompt, generation_config=generation_config, on_retry_status=_status, cancel_event=cancel_event)
        except InterruptedError:
            raise
        except Exception as e:
            raise RuntimeError(f"API call failed: {e}") from e

        if _is_content_policy_response(_resp):
            raise ContentPolicyError("Image blocked by content policy (finish_reason=12)")

        _bytes = _extract_image_bytes(_resp)
        if not _bytes:
            fallback = _extract_text_fallback(_resp)
            raise RuntimeError(
                "No image was returned by the model for character portrait."
                + (f" Model response: {fallback[:500]}" if fallback else "")
            )
        return _bytes

    sanitize_attempts = 0
    while True:
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("Generation cancelled")
        try:
            image_bytes = _do_generate()
            break
        except ContentPolicyError:
            if sanitize_attempts >= 2:
                raise
            sanitize_attempts += 1
            _status(f"Description flagged by content policy, sanitizing description (attempt {sanitize_attempts}/2)...")
            from services.ai_text_service import sanitize_description
            character.merged_description = sanitize_description(
                character.merged_description or character.name
            )
            # Rebuild prompt with sanitized description
            prompt = _load_prompt("character_portrait.txt")
            prompt = prompt.replace("{{style}}", art_style)
            prompt = prompt.replace("{{character_description}}", character.merged_description)
            prompt += "\n\nIMPORTANT: Generate this image in Portrait orientation (aspect ratio 9:16)."
            _status("Retrying generation with sanitized description...")

    import time
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in character.name).strip("_")
    timestamp = int(time.time())

    save_dir = Path(project_dir) / "images" / "characters"
    save_dir.mkdir(parents=True, exist_ok=True)

    output_path = save_dir / f"{safe_name}_{timestamp}.png"

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    character.image_path = str(output_path)
    return str(output_path)


# ── Environment landscape (Text2Img) ─────────────────────────────────────

def generate_environment_image(
    environment: Environment,
    art_style: str,
    project_dir: Path,
    on_status=None,
    cancel_event: threading.Event = None,
) -> str:
    set_rate_limit_error(None)
    art_style = _resolve_art_style(art_style)
    _init_vertex()

    if getattr(environment, "seed", None) is None:
        environment.seed = random.randint(0, 2147483647)

    template = _load_prompt("environment_landscape.txt")
    prompt = template.replace("{{style}}", art_style)
    prompt = prompt.replace("{{environment_description}}", environment.merged_description or environment.name)
    aspect_ratio = getattr(environment, "aspect_ratio", "16:9")
    if "9:16" in aspect_ratio or "3:4" in aspect_ratio:
        prompt += f"\n\nIMPORTANT: Generate this image in Portrait orientation (aspect ratio {aspect_ratio})."
    elif "1:1" in aspect_ratio:
        prompt += "\n\nIMPORTANT: Generate this image in Square orientation (1:1)."
    else:
        prompt += f"\n\nIMPORTANT: Generate this image in Landscape orientation ({aspect_ratio})."

    generation_config = {
        "response_modalities": ["IMAGE", "TEXT"],
        "image_config": {"aspect_ratio": aspect_ratio}
    }
    if getattr(environment, "seed", None) is not None:
        try:
            s_val = int(environment.seed)
            if s_val > 2147483647:
                s_val = s_val % 2147483647
            generation_config["seed"] = s_val
        except Exception:
            pass

    def _env_status(msg: str):
        if on_status:
            on_status(msg)

    def _do_generate_env() -> bytes:
        nonlocal prompt
        image_model = get_active_model("Environments")
        try:
            model = GenerativeModel(image_model)
            _resp = _call_with_retry(model, prompt, generation_config=generation_config, on_retry_status=_env_status, cancel_event=cancel_event)
        except InterruptedError:
            raise
        except Exception as e:
            raise RuntimeError(f"API call failed: {e}") from e

        if _is_content_policy_response(_resp):
            raise ContentPolicyError("Image blocked by content policy (finish_reason=12)")

        _bytes = _extract_image_bytes(_resp)
        if not _bytes:
            fallback = _extract_text_fallback(_resp)
            raise RuntimeError(
                "No image was returned by the model for environment."
                + (f" Model response: {fallback[:500]}" if fallback else "")
            )
        return _bytes

    sanitize_attempts = 0
    while True:
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("Generation cancelled")
        try:
            image_bytes = _do_generate_env()
            break
        except ContentPolicyError:
            if sanitize_attempts >= 2:
                raise
            sanitize_attempts += 1
            _env_status(f"Description flagged by content policy, sanitizing description (attempt {sanitize_attempts}/2)...")
            from services.ai_text_service import sanitize_description
            environment.merged_description = sanitize_description(
                environment.merged_description or environment.name
            )
            # Rebuild prompt with sanitized description
            template = _load_prompt("environment_landscape.txt")
            prompt = template.replace("{{style}}", art_style)
            prompt = prompt.replace("{{environment_description}}", environment.merged_description)
            aspect_ratio = getattr(environment, "aspect_ratio", "16:9")
            if "9:16" in aspect_ratio or "3:4" in aspect_ratio:
                prompt += f"\n\nIMPORTANT: Generate this image in Portrait orientation (aspect ratio {aspect_ratio})."
            elif "1:1" in aspect_ratio:
                prompt += "\n\nIMPORTANT: Generate this image in Square orientation (1:1)."
            else:
                prompt += f"\n\nIMPORTANT: Generate this image in Landscape orientation ({aspect_ratio})."
            _env_status("Retrying generation with sanitized description...")

    import time
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in environment.name).strip("_")
    timestamp = int(time.time())
    output_path = Path(project_dir) / "images" / "environments" / f"{safe_name}_{timestamp}.png"
    saved_path = save_image(image_bytes, output_path)
    environment.image_path = saved_path

    return saved_path


# ── Scene illustration (Text2Img with reference info) ─────────────────────

def generate_scene_image(
    scene: Scene,
    characters: list[Character],
    environment: Environment | None,
    art_style: str,
    project_dir: Path,
    all_characters: list[Character] | None = None,
    on_status=None,
    cancel_event: threading.Event = None,
) -> str:
    set_rate_limit_error(None)
    art_style = _resolve_art_style(art_style)
    _init_vertex()

    template = _load_prompt("scene_composition.txt")
    style_label = art_style
    style_extra = ""
    if isinstance(art_style, str) and " - " in art_style:
        style_label, style_extra = art_style.split(" - ", 1)

    prompt = template.replace("{{style}}", style_label)

    scene_title = (scene.title or "").strip()
    scene_desc = (scene.description or "").strip()
    if scene_title and scene_desc:
        scene_text = f"{scene_title}. {scene_desc}"
    else:
        scene_text = scene_desc or scene_title or ""
    prompt = prompt.replace("{{scene_description}}", scene_text)

    if style_extra:
        prompt = prompt + "\n\nSTYLE_INSTRUCTIONS: " + style_extra

    chars_info_parts = []
    for c in characters[:5]:
        if c.image_path and Path(c.image_path).is_file():
            chars_info_parts.append(f"CHARACTER IN SCENE: {c.name}. {c.merged_description}")
        elif all_characters:
            chars_info_parts.append(f"CHARACTER NAME: {c.name}")

    if chars_info_parts:
        prompt += "\n\nCHARACTER INFO:\n" + "\n".join(chars_info_parts)

    content_parts = []

    if environment and environment.image_path and Path(environment.image_path).is_file():
        content_parts.append(f"REFERENCE IMAGE FOR ENVIRONMENT")
        img_bytes = Path(environment.image_path).read_bytes()
        content_parts.append(Part.from_data(data=img_bytes, mime_type="image/png"))

    for c in characters[:5]:
        if c.image_path and Path(c.image_path).is_file():
            content_parts.append(f"REFERENCE IMAGE FOR CHARACTER: {c.name}")
            img_bytes = Path(c.image_path).read_bytes()
            content_parts.append(Part.from_data(data=img_bytes, mime_type="image/png"))

    content_parts.append(prompt)

    if getattr(scene, "seed", None) is None:
        scene.seed = random.randint(0, 2147483647)

    aspect_ratio = getattr(scene, "aspect_ratio", "9:16")

    if "9:16" in aspect_ratio or "3:4" in aspect_ratio:
        content_parts[-1] = content_parts[-1] + f"\n\nIMPORTANT: Generate this image in Portrait orientation (aspect ratio {aspect_ratio})."
    else:
        content_parts[-1] = content_parts[-1] + f"\n\nIMPORTANT: Generate this image in Landscape orientation (aspect ratio {aspect_ratio})."

    generation_config = {
        "response_modalities": ["IMAGE", "TEXT"],
        "image_config": {"aspect_ratio": aspect_ratio}
    }
    if getattr(scene, "seed", None) is not None:
        try:
            s_val = int(scene.seed)
            if s_val > 2147483647:
                s_val = s_val % 2147483647
            generation_config["seed"] = s_val
        except Exception:
            pass

    def _scene_status(msg: str):
        if on_status:
            on_status(msg)

    def _do_generate_scene() -> bytes:
        image_model = get_active_model("Scenes")
        try:
            model = GenerativeModel(image_model)
            _resp = _call_with_retry(model, content_parts, generation_config=generation_config, on_retry_status=_scene_status, cancel_event=cancel_event)
        except InterruptedError:
            raise
        except Exception as e:
            raise RuntimeError(f"API call failed: {e}") from e

        if _is_content_policy_response(_resp):
            raise ContentPolicyError("Image blocked by content policy (finish_reason=12)")

        _bytes = _extract_image_bytes(_resp)
        if not _bytes:
            fallback = _extract_text_fallback(_resp)
            raise RuntimeError(
                "No image was returned by the model for scene."
                + (f" Model response: {fallback[:500]}" if fallback else "")
            )
        return _bytes

    sanitize_attempts = 0
    while True:
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("Generation cancelled")
        try:
            image_bytes = _do_generate_scene()
            break
        except ContentPolicyError:
            if sanitize_attempts >= 2:
                raise
            sanitize_attempts += 1
            _scene_status(f"Scene description flagged by content policy, sanitizing (attempt {sanitize_attempts}/2)...")
            from services.ai_text_service import sanitize_description
            scene.description = sanitize_description(scene.description or scene.title or "")
            # Rebuild the prompt (last element of content_parts) with sanitized description
            san_title = (scene.title or "").strip()
            san_desc = (scene.description or "").strip()
            san_text = f"{san_title}. {san_desc}" if san_title and san_desc else san_desc or san_title or ""
            new_prompt = template.replace("{{style}}", style_label)
            new_prompt = new_prompt.replace("{{scene_description}}", san_text)
            if style_extra:
                new_prompt += "\n\nSTYLE_INSTRUCTIONS: " + style_extra
            if chars_info_parts:
                new_prompt += "\n\nCHARACTER INFO:\n" + "\n".join(chars_info_parts)
            if "9:16" in aspect_ratio or "3:4" in aspect_ratio:
                new_prompt += f"\n\nIMPORTANT: Generate this image in Portrait orientation (aspect ratio {aspect_ratio})."
            elif "1:1" in aspect_ratio:
                new_prompt += "\n\nIMPORTANT: Generate this image in Square orientation (1:1)."
            else:
                new_prompt += f"\n\nIMPORTANT: Generate this image in Landscape orientation (aspect ratio {aspect_ratio})."
            content_parts[-1] = new_prompt
            _scene_status("Retrying scene generation with sanitized description...")

    import time
    safe_title = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in scene.title).strip("_")
    timestamp = int(time.time())
    output_path = Path(project_dir) / "images" / "scenes" / f"{safe_title}_{timestamp}.png"
    saved_path = save_image(image_bytes, output_path)
    scene.image_path = saved_path

    return saved_path


# ── Edit image (Img2Img) ─────────────────────────────────────────────────

def edit_image(
    image_path: str,
    instruction: str,
) -> str:
    """
    Take an existing image, send it to the model with an edit instruction,
    and save the result as a new file.  Returns the path to the new image.
    """
    _init_vertex()
    p = Path(image_path)
    if not p.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")

    img_bytes = p.read_bytes()

    content_parts = [
        Part.from_data(data=img_bytes, mime_type="image/png"),
        f"Edit this image according to the following instruction: {instruction}",
    ]

    image_model = get_active_model("Scenes")
    model = GenerativeModel(image_model)
    response = _call_with_retry(model, content_parts)

    new_bytes = _extract_image_bytes(response)
    if not new_bytes:
        fallback = _extract_text_fallback(response)
        raise RuntimeError(
            "No image was returned by the model for edit."
            + (f" Model response: {fallback[:500]}" if fallback else "")
        )

    import time
    timestamp = int(time.time())
    new_path = p.parent / f"{p.stem}_{timestamp}{p.suffix}"
    saved_path = save_image(new_bytes, new_path)
    return saved_path


def undo_image_edit(entity) -> bool:
    history = getattr(entity, "image_path_history", None)
    if not history:
        return False

    previous_path = history.pop()
    if previous_path and Path(previous_path).is_file():
        entity.image_path = previous_path
        ref_history = getattr(entity, "refinement_history", None)
        if ref_history:
            ref_history.pop()
        return True

    return False
