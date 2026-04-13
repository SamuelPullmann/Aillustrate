from __future__ import annotations

from pathlib import Path


def get_refreshable_image_src(image_path: str | None) -> str | None:
    """Return a Flet-compatible local image src.

    Simply returns the absolute path.  Cache-busting is handled at the
    generation layer: every generation (text2img *and* img2img) saves
    to a new file with a unique name, so the ``src`` string naturally
    changes and Flet reloads the image.
    """
    if not image_path:
        return None

    source = Path(image_path)
    if not source.is_file():
        return None

    return str(source.absolute())
