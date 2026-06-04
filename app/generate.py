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

import base64
import os
import re
from pathlib import Path

import httpx

from . import config

# --- Grok (xAI Imagine) image backend ---------------------------------------
# Aurora-based; better camera-roll realism than nano-pro, supports up to 3
# reference images for character consistency, respects aspect_ratio, sync, and
# (being xAI) carries NO Google SynthID watermark.
XAI_IMAGE_GEN = "https://api.x.ai/v1/images/generations"
XAI_IMAGE_EDIT = "https://api.x.ai/v1/images/edits"
GROK_IMAGE_MODEL = "grok-imagine-image-quality"


def _is_grok(model: Optional[str]) -> bool:
    return (model or config.IMAGE_MODEL).strip().lower() == "grok"


def _grok_image(prompt: str, aspect: str, reference_paths: Optional[list[Path]] = None) -> bytes:
    """Generate (or reference-edit) one image via xAI's Imagine API."""
    if not config.XAI_API_KEY:
        raise RuntimeError("XAI_API_KEY is not set (needed for the grok image model).")
    headers = {"Authorization": f"Bearer {config.XAI_API_KEY}", "Content-Type": "application/json"}
    payload: dict = {"model": GROK_IMAGE_MODEL, "prompt": prompt, "aspect_ratio": aspect}

    # Up to 3 reference images, passed as a list of base64 data-URI strings.
    uris: list[str] = []
    for p in (reference_paths or []):
        if Path(p).exists():
            mime = "image/png" if str(p).lower().endswith(".png") else "image/jpeg"
            uris.append(f"data:{mime};base64," + base64.b64encode(Path(p).read_bytes()).decode())
        if len(uris) == 3:
            break

    url = XAI_IMAGE_GEN
    if uris:
        # xAI quirk: a SINGLE reference must be one object; 2-3 must be a list of
        # strings (a 1-element list is rejected).
        payload["image"] = (
            {"url": uris[0], "type": "image_url"} if len(uris) == 1 else uris
        )
        url = XAI_IMAGE_EDIT

    with httpx.Client(timeout=180) as c:
        r = c.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return _download(r.json()["data"][0]["url"])

# Words that make image models render phone/screenshot UI (bezel, status bar,
# notch). We want RAW photos only, so neutralize them in any prompt before it
# reaches the model — belt-and-suspenders alongside the negative style text.
_UI_TRIGGERS = re.compile(
    r"\b(screenshots?|screen[\s-]?shots?|status\s*bar|phone\s*screen|"
    r"phone\s*ui|app\s*interface|home\s*screen|lock\s*screen|notch|bezel)\b",
    re.IGNORECASE,
)


def _strip_ui_triggers(prompt: str) -> str:
    return _UI_TRIGGERS.sub("photo", prompt)

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


def _styled(prompt: str) -> str:
    """Append the global camera-roll style so every slide looks like a real
    phone photo rather than glossy AI art."""
    prompt = _strip_ui_triggers(prompt).strip()
    style = config.STYLE_PROMPT.strip()
    if not style:
        return prompt
    return f"{prompt}\n\nPhoto style (apply strictly): {style}"


def text_to_image(prompt: str, model: Optional[str] = None, aspect: Optional[str] = None) -> bytes:
    """Generate an image from a prompt alone (no reference image)."""
    aspect = aspect or config.ASPECT_RATIO
    if _is_grok(model):
        return _grok_image(_styled(prompt), aspect)
    fal_client = _client()
    endpoint = config.resolve_t2i_endpoint(model)  # text-to-image, no input image
    aspect = aspect or config.ASPECT_RATIO

    args = {"prompt": _styled(prompt), "num_images": 1, **_size_args(endpoint, aspect)}
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
    aspect = aspect or config.ASPECT_RATIO
    if _is_grok(model):
        refs = [p for p in reference_paths if Path(p).exists()]
        return _grok_image(_styled(prompt), aspect, refs)
    if not reference_paths:
        return text_to_image(prompt, model=model, aspect=aspect)

    fal_client = _client()
    endpoint = config.resolve_image_endpoint(model)
    aspect = aspect or config.ASPECT_RATIO

    image_urls = [fal_client.upload_file(str(p)) for p in reference_paths if p.exists()]

    args = {
        "prompt": _styled(prompt),
        "image_urls": image_urls,
        "num_images": 1,
        **_size_args(endpoint, aspect),
    }
    result = fal_client.subscribe(endpoint, arguments=args)
    return _download(_first_image_url(result))
