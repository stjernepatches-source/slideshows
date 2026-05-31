"""Slideshow orchestration: story -> scenes -> images -> cleaned slides.

A slideshow lives at data/slideshows/<id>/ with:
  - slideshow.json   (story, slides metadata, captions, status)
  - slides/NN.jpg    (the cleaned, ready-to-post images)

Status flow: draft -> generating -> ready -> posted
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import characters, config, generate, metadata, scenes
from .storage import read_json, write_json


def _dir(show_id: str) -> Path:
    return config.SLIDESHOWS_DIR / show_id


def _meta_path(show_id: str) -> Path:
    return _dir(show_id) / "slideshow.json"


def _slides_dir(show_id: str) -> Path:
    d = _dir(show_id) / "slides"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_slideshows() -> list[dict[str, Any]]:
    config.ensure_dirs()
    shows = []
    for d in config.SLIDESHOWS_DIR.iterdir():
        if d.is_dir() and (d / "slideshow.json").exists():
            shows.append(read_json(d / "slideshow.json", default={}))
    shows.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return shows


def get_slideshow(show_id: str) -> dict[str, Any] | None:
    p = _meta_path(show_id)
    return read_json(p, default=None) if p.exists() else None


def _save(show: dict[str, Any]) -> None:
    write_json(_meta_path(show["id"]), show)


def create_slideshow(
    title: str,
    story: str,
    character_ids: list[str],
    num_slides: int = 6,
    model: str | None = None,
    aspect: str | None = None,
) -> dict[str, Any]:
    """Create a slideshow record and run the scene split immediately."""
    config.ensure_dirs()
    show_id = uuid.uuid4().hex[:12]
    cast = [c for c in (characters.get_character(cid) for cid in character_ids) if c]

    plan = scenes.split_story(story, num_slides=num_slides, cast=cast)

    show = {
        "id": show_id,
        "title": title.strip() or "Untitled",
        "story": story,
        "character_ids": character_ids,
        "model": (model or config.IMAGE_MODEL),
        "aspect": (aspect or config.ASPECT_RATIO),
        "status": "draft",
        "created_at": _now(),
        "post_caption": plan.get("post_caption", ""),
        "hashtags": plan.get("hashtags", []),
        "slides": [
            {
                "index": i,
                "image_prompt": s["image_prompt"],
                "caption": s.get("caption", ""),
                "characters": s.get("characters", []),
                "file": None,        # set once generated
                "synthid": False,    # true if rendered by a SynthID model
            }
            for i, s in enumerate(plan.get("slides", []))
        ],
    }
    _save(show)
    return show


def _refs_for_slide(show: dict[str, Any], slide: dict[str, Any]) -> list[Path]:
    """Reference images for the characters named in this slide (fallback: all
    characters attached to the slideshow)."""
    cast = [characters.get_character(cid) for cid in show["character_ids"]]
    cast = [c for c in cast if c]
    named = {n.lower() for n in slide.get("characters", [])}
    chosen = [c for c in cast if c["name"].lower() in named] or cast

    refs: list[Path] = []
    for c in chosen:
        refs.extend(characters.reference_paths(c["id"]))
    return refs


def generate_slide(show_id: str, index: int) -> dict[str, Any]:
    """(Re)generate a single slide image, then strip its metadata."""
    show = get_slideshow(show_id)
    if show is None:
        raise KeyError(show_id)
    slide = show["slides"][index]
    model = show["model"]
    aspect = show["aspect"]

    raw = generate.generate_slide(
        slide["image_prompt"],
        reference_paths=_refs_for_slide(show, slide),
        model=model,
        aspect=aspect,
    )

    fname = f"{index:02d}.jpg"
    out = _slides_dir(show_id) / fname
    out.write_bytes(raw)
    metadata.strip_file(out, aspect=aspect)  # remove C2PA/EXIF + normalize

    slide["file"] = fname
    slide["synthid"] = config.model_has_synthid(model)
    _save(show)
    return slide


def generate_all(show_id: str) -> dict[str, Any]:
    """Generate every slide in order. Marks the show ready when done."""
    show = get_slideshow(show_id)
    if show is None:
        raise KeyError(show_id)
    show["status"] = "generating"
    _save(show)
    for i in range(len(show["slides"])):
        generate_slide(show_id, i)
    show = get_slideshow(show_id)
    show["status"] = "ready"
    _save(show)
    return show


def update_text(
    show_id: str,
    post_caption: str | None = None,
    hashtags: list[str] | None = None,
    slide_captions: dict[int, str] | None = None,
) -> dict[str, Any]:
    show = get_slideshow(show_id)
    if show is None:
        raise KeyError(show_id)
    if post_caption is not None:
        show["post_caption"] = post_caption
    if hashtags is not None:
        show["hashtags"] = hashtags
    for idx, cap in (slide_captions or {}).items():
        show["slides"][int(idx)]["caption"] = cap
    _save(show)
    return show


def slide_file(show_id: str, index: int) -> Path | None:
    show = get_slideshow(show_id)
    if not show:
        return None
    fname = show["slides"][index].get("file")
    if not fname:
        return None
    p = _slides_dir(show_id) / fname
    return p if p.exists() else None


def ordered_slide_files(show_id: str) -> list[Path]:
    show = get_slideshow(show_id) or {}
    out = []
    for s in show.get("slides", []):
        if s.get("file"):
            out.append(_slides_dir(show_id) / s["file"])
    return out


def mark_posted(show_id: str, info: dict[str, Any]) -> dict[str, Any]:
    show = get_slideshow(show_id)
    if show is None:
        raise KeyError(show_id)
    show["status"] = "posted"
    show["tiktok"] = info
    _save(show)
    return show
