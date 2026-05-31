"""Image generation via the fal.ai queue.

Two entry points:
- text_to_image(prompt)            -> bytes   (used for character sheets)
- generate_slide(prompt, refs, ..) -> bytes   (edit/consistency path with refs)

Both return raw image bytes. The caller decides where to save them. We upload
local reference files to fal's CDN first, then pass their URLs in image_urls so
the model keeps the character consistent.
"""
from __future__ import annotations

from typing import Optional

import os
from pathlib import Path

import httpx

from . import config

# Aspect ratio -> Seedream image_size enum. fal's Gemini/nano models take an
# "aspect_ratio" string directly; Seedream takes a named size or {width,height}.
_SEEDREAM_SIZE = {
    "9:16": "portrait_16_9",
    "16:9": "landscape_16_9",
    "1:1": "square_hd",
    "4:3": "landscape_4_3",
    "3:4": "portrait_4_3",
}


def _ensure_key() -> None:
    if not config.FAL_KEY:
        raise RuntimeError(
            "FAL_KEY is not set. Add it to your .env to generate images."
        )
    # fal_client reads FAL_KEY from the environment.
    os.environ.setdefault("FAL_KEY", config.FAL_KEY)


def _client():
    _ensure_key()
    import fal_client

    return fal_client


def _download(url: str) -> bytes:
    with httpx.Client(timeout=120) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content


def _first_image_url(result: dict) -> str:
    images = result.get("images") or []
    if not images:
        raise RuntimeError(f"fal returned no images. Raw result: {result}")
    return images[0]["url"]


def _is_seedream(endpoint: str) -> bool:
    return "seedream" in endpoint


def _size_args(endpoint: str, aspect: str) -> dict:
    """Aspect-ratio arguments differ per model family."""
    if _is_seedream(endpoint):
        return {"image_size": _SEEDREAM_SIZE.get(aspect, "portrait_16_9")}
    return {"aspect_ratio": aspect}  # Gemini / nano-banana family


def text_to_image(prompt: str, model: Optional[str] = None, aspect: Optional[str] = None) -> bytes:
    """Generate an image from a prompt alone (no reference image)."""
    fal_client = _client()
    endpoint = config.resolve_image_endpoint(model)
    aspect = aspect or config.ASPECT_RATIO

    args = {"prompt": prompt, "num_images": 1, **_size_args(endpoint, aspect)}
    result = fal_client.subscribe(endpoint, arguments=args)
    return _download(_first_image_url(result))


def generate_slide(
    prompt: str,
    reference_paths: Optional[list[Path]] = None,
    model: Optional[str] = None,
    aspect: Optional[str] = None,
) -> bytes:
    """Generate one slide, keyed to the given reference images for consistency.

    If no references are supplied, falls back to plain text-to-image.
    """
    reference_paths = reference_paths or []
    if not reference_paths:
        return text_to_image(prompt, model=model, aspect=aspect)

    fal_client = _client()
    endpoint = config.resolve_image_endpoint(model)
    aspect = aspect or config.ASPECT_RATIO

    image_urls = [fal_client.upload_file(str(p)) for p in reference_paths if p.exists()]

    args = {
        "prompt": prompt,
        "image_urls": image_urls,
        "num_images": 1,
        **_size_args(endpoint, aspect),
    }
    result = fal_client.subscribe(endpoint, arguments=args)
    return _download(_first_image_url(result))
