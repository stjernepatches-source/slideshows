"""Reusable cast library.

A "character" is a saved persona you can reuse across stories. Each one has a
name, a text description, and one or more reference images. Those reference
images are what we feed into the image model on every slide so the same
character looks consistent shot to shot.

Reference images can be (a) uploaded by you, or (b) generated from a text
prompt via fal (a one-off "character sheet" portrait).

Cast is stored as data/cast/cast.json plus image files under data/cast/<id>/.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional, Any

from . import config, generate
from .storage import read_json, write_json


def _index() -> list[dict[str, Any]]:
    return read_json(config.CAST_INDEX, default=[])


def _save_index(rows: list[dict[str, Any]]) -> None:
    write_json(config.CAST_INDEX, rows)


def list_characters() -> list[dict[str, Any]]:
    """All saved characters, newest first."""
    return list(reversed(_index()))


def get_character(char_id: str) -> Optional[dict[str, Any]]:
    for row in _index():
        if row["id"] == char_id:
            return row
    return None


def _char_dir(char_id: str) -> Path:
    d = config.CAST_DIR / char_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_character(name: str, description: str) -> dict[str, Any]:
    config.ensure_dirs()
    char = {
        "id": uuid.uuid4().hex[:12],
        "name": name.strip(),
        "description": description.strip(),
        "reference_images": [],  # list of relative paths under data/cast/<id>/
    }
    rows = _index()
    rows.append(char)
    _save_index(rows)
    return char


def _update(char_id: str, mutate) -> dict[str, Any]:
    rows = _index()
    for i, row in enumerate(rows):
        if row["id"] == char_id:
            mutate(row)
            rows[i] = row
            _save_index(rows)
            return row
    raise KeyError(f"No character with id {char_id}")


def add_reference_from_bytes(char_id: str, data: bytes, filename: str) -> dict[str, Any]:
    """Save an uploaded image file as a reference for this character."""
    d = _char_dir(char_id)
    suffix = Path(filename).suffix.lower() or ".png"
    fname = f"ref_{uuid.uuid4().hex[:8]}{suffix}"
    (d / fname).write_bytes(data)
    return _update(char_id, lambda r: r["reference_images"].append(fname))


def generate_reference(char_id: str, prompt: Optional[str] = None) -> dict[str, Any]:
    """Generate a clean character-sheet portrait from the description via fal.

    This gives you a reusable reference image for a character you don't have a
    photo of. It uses the text-to-image path (no input image).
    """
    char = get_character(char_id)
    if char is None:
        raise KeyError(f"No character with id {char_id}")

    full_prompt = prompt or (
        f"Full-body character reference sheet of {char['name']}: "
        f"{char['description']}. Neutral studio background, even lighting, "
        f"clear face, consistent design, single character."
    )
    image_bytes = generate.text_to_image(full_prompt)
    fname = f"ref_{uuid.uuid4().hex[:8]}.png"
    (_char_dir(char_id) / fname).write_bytes(image_bytes)
    return _update(char_id, lambda r: r["reference_images"].append(fname))


def delete_character(char_id: str) -> None:
    rows = [r for r in _index() if r["id"] != char_id]
    _save_index(rows)
    d = config.CAST_DIR / char_id
    if d.exists():
        for f in d.iterdir():
            f.unlink()
        d.rmdir()


def reference_paths(char_id: str) -> list[Path]:
    """Absolute paths to a character's reference image files."""
    char = get_character(char_id)
    if char is None:
        return []
    return [config.CAST_DIR / char_id / name for name in char["reference_images"]]
