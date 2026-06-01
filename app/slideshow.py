"""Slideshow orchestration: story -> scenes -> images -> cleaned slides.

A slideshow lives at data/slideshows/<id>/ with:
  - slideshow.json   (story, slides metadata, captions, status)
  - slides/NN.jpg    (the cleaned, ready-to-post images)

Status flow: draft -> generating -> ready -> posted
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

from . import characters, config, generate, metadata, overlay, scenes, video
from .storage import read_json, write_json


def _dir(show_id: str) -> Path:
    return config.SLIDESHOWS_DIR / show_id


def _meta_path(show_id: str) -> Path:
    return _dir(show_id) / "slideshow.json"


def _slides_dir(show_id: str) -> Path:
    d = _dir(show_id) / "slides"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _refs_dir(show_id: str) -> Path:
    d = _dir(show_id) / "refs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "char"


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


def get_slideshow(show_id: str) -> Optional[dict[str, Any]]:
    p = _meta_path(show_id)
    return read_json(p, default=None) if p.exists() else None


def _save(show: dict[str, Any]) -> None:
    write_json(_meta_path(show["id"]), show)


def create_slideshow(
    title: str,
    story: str,
    character_ids: list[str],
    num_slides: int = 6,
    model: Optional[str] = None,
    aspect: Optional[str] = None,
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
        # Recurring characters the LLM identified (used for auto-consistency
        # when you didn't attach a manual cast). auto_cast maps name -> ref path,
        # filled in lazily at generation time.
        "cast": plan.get("cast", []),
        "auto_cast": {},
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


def _ensure_auto_cast(show: dict[str, Any]) -> None:
    """Generate one reference portrait per recurring character so the same face
    carries across slides. Only runs when no manual cast was attached. Mutates
    `show` in place (fills show["auto_cast"]) and persists it.
    """
    if show.get("character_ids"):
        return  # manual cast attached -> use the cast library instead
    cast = show.get("cast") or []
    if not cast:
        return
    auto = show.setdefault("auto_cast", {})
    refs_dir = _refs_dir(show["id"])
    changed = False
    for ch in cast:
        name = ch.get("name", "").strip()
        if not name:
            continue
        existing = auto.get(name)
        if existing and (refs_dir / Path(existing).name).exists():
            continue
        portrait_prompt = (
            f"A casual phone photo of {name}: {ch.get('description', '')}. "
            "Head-and-shoulders, facing the camera, neutral expression, plain "
            "everyday setting. Clear, well-lit face for identity reference."
        )
        img = generate.text_to_image(
            portrait_prompt, model=show["model"], aspect=show["aspect"]
        )
        fname = f"{_slug(name)}.jpg"
        (refs_dir / fname).write_bytes(img)
        auto[name] = f"refs/{fname}"
        changed = True
    if changed:
        _save(show)


def _refs_for_slide(show: dict[str, Any], slide: dict[str, Any]) -> list[Path]:
    """Reference images for the characters named in this slide.

    Two sources: a manually attached cast (the reusable cast library), or the
    auto-generated per-character portraits created for this slideshow.
    """
    names = slide.get("characters", [])

    # Manual cast attached -> use the cast library (named match, else all).
    if show.get("character_ids"):
        cast = [characters.get_character(cid) for cid in show["character_ids"]]
        cast = [c for c in cast if c]
        named = {n.lower() for n in names}
        chosen = [c for c in cast if c["name"].lower() in named] or cast
        refs: list[Path] = []
        for c in chosen:
            refs.extend(characters.reference_paths(c["id"]))
        return refs

    # Auto cast -> the per-character reference portraits for this slideshow.
    auto = show.get("auto_cast", {})
    refs_dir = _refs_dir(show["id"])
    out: list[Path] = []
    for name in names:
        rel = auto.get(name)
        if rel:
            p = refs_dir / Path(rel).name
            if p.exists():
                out.append(p)
    return out


def generate_slide(show_id: str, index: int) -> dict[str, Any]:
    """(Re)generate a single slide image, then strip its metadata."""
    show = get_slideshow(show_id)
    if show is None:
        raise KeyError(show_id)
    _ensure_auto_cast(show)  # make sure character reference faces exist
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
    _ensure_auto_cast(show)  # build character reference faces up front
    for i in range(len(show["slides"])):
        generate_slide(show_id, i)
    show = get_slideshow(show_id)
    show["status"] = "ready"
    _save(show)
    return show


def update_text(
    show_id: str,
    post_caption: Optional[str] = None,
    hashtags: Optional[list[str]] = None,
    slide_captions: Optional[dict[int, str]] = None,
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


def slide_file(show_id: str, index: int) -> Optional[Path]:
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


def composited_slides(show_id: str) -> list[bytes]:
    """Each generated slide with its caption text burned in (post/preview)."""
    show = get_slideshow(show_id) or {}
    frames: list[bytes] = []
    for s in show.get("slides", []):
        if s.get("file"):
            path = _slides_dir(show_id) / s["file"]
            frames.append(overlay.compose_file(path, s.get("caption", "")))
    return frames


def build_reel_video(show_id: str) -> Path:
    """Stitch the generated slides into a 9:16 reel mp4. The first slide gets a
    'Wait for it' hook so the reel doesn't read as a frozen image."""
    show = get_slideshow(show_id)
    if show is None:
        raise KeyError(show_id)
    generated = [s for s in show["slides"] if s.get("file")]
    if not generated:
        raise ValueError("Generate the slides before building a reel.")

    # "Wait for it" stays pinned to the bottom of EVERY slide so the stitched
    # reel keeps retention the whole way through (not just the first frame).
    bottom = config.REEL_WAIT_TEXT if config.REEL_WAIT_ENABLED else None
    frames: list[bytes] = []
    for s in generated:
        path = _slides_dir(show_id) / s["file"]
        frames.append(overlay.compose_file(path, s.get("caption", ""), bottom_text=bottom))

    out = _dir(show_id) / "reel.mp4"
    return video.build_reel(frames, out)


def mark_posted(show_id: str, info: dict[str, Any]) -> dict[str, Any]:
    show = get_slideshow(show_id)
    if show is None:
        raise KeyError(show_id)
    show["status"] = "posted"
    show["tiktok"] = info
    _save(show)
    return show
