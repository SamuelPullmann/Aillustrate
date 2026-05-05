from __future__ import annotations

import json
import re
from pathlib import Path


def parse_chapter_analysis(raw_text: str) -> dict:
    """Parse the raw AI response text into a structured dict.

    Strips markdown code fences and attempts JSON parsing.
    Returns a dict with ``characters``, ``environments`` and ``scenes`` lists.
    Returns empty lists for all keys on parse failure.
    """
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"characters": [], "environments": [], "scenes": []}

    # Validate structure
    if not isinstance(data, dict):
        return {"characters": [], "environments": [], "scenes": []}

    for key in ("characters", "environments", "scenes"):
        if key not in data or not isinstance(data[key], list):
            data[key] = []

    return data


def save_image(image_bytes: bytes, output_path: str | Path) -> str:
    """Write raw image bytes to disk and return the absolute path as a string.

    Creates parent directories automatically if they do not exist.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(image_bytes)
    return str(p.resolve())

