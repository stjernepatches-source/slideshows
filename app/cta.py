"""Build the comparison / CTA slide from your software's results page.

You provide ONE screenshot of the results page as a fixed template
(assets/cta_template.png) plus the pixel boxes where the two compared photos sit
(assets/cta_boxes.json: a list of {"x","y","w","h"} in template pixels, in the
same order the faces should fill them). For each story we paste that story's two
characters' faces into the boxes — same branded layout, different people.

No face-detection dependency: photos are center-cover-cropped to each box's
aspect ratio. Boxes can optionally set "radius" for rounded corners.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from . import config


def is_ready() -> bool:
    """True when the template and box map are both present."""
    return config.CTA_TEMPLATE.exists() and config.CTA_BOXES_FILE.exists()


def _load_boxes() -> list[dict[str, Any]]:
    return json.loads(config.CTA_BOXES_FILE.read_text(encoding="utf-8"))


def _cover_crop(img: Image.Image, w: int, h: int) -> Image.Image:
    """Resize+center-crop img to exactly w×h (object-fit: cover)."""
    img = img.convert("RGB")
    src_w, src_h = img.size
    scale = max(w / src_w, h / src_h)
    new = img.resize((max(1, round(src_w * scale)), max(1, round(src_h * scale))))
    left = (new.width - w) // 2
    top = (new.height - h) // 2
    return new.crop((left, top, left + w, top + h))


def _paste_box(base: Image.Image, face: bytes, box: dict[str, Any]) -> None:
    x, y, w, h = int(box["x"]), int(box["y"]), int(box["w"]), int(box["h"])
    crop = _cover_crop(Image.open(io.BytesIO(face)), w, h)
    radius = int(box.get("radius", 0))
    if radius > 0:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
        base.paste(crop, (x, y), mask)
    else:
        base.paste(crop, (x, y))


def build_comparison(face_images: list[bytes]) -> bytes:
    """Composite the given faces into the template boxes; return JPEG bytes.

    Faces fill boxes in order; extra faces or boxes beyond the shorter list are
    ignored. Output is normalized to the configured 9:16 reel/slide size and
    carries no metadata.
    """
    if not is_ready():
        raise RuntimeError(
            "CTA template not set up. Add assets/cta_template.png and "
            "assets/cta_boxes.json (boxes for the comparison photos)."
        )
    base = Image.open(config.CTA_TEMPLATE).convert("RGB")
    boxes = _load_boxes()
    for face, box in zip(face_images, boxes):
        _paste_box(base, face, box)

    # Letterbox the WHOLE results page onto a 9:16 canvas (contain, not crop) so
    # the comparison cards are never cut off. Background matches the page color.
    from . import metadata
    cw, ch = config.REEL_WIDTH, config.REEL_HEIGHT
    scale = min(cw / base.width, ch / base.height)
    resized = base.resize((max(1, round(base.width * scale)), max(1, round(base.height * scale))))
    canvas = Image.new("RGB", (cw, ch), base.getpixel((2, 2)))
    canvas.paste(resized, ((cw - resized.width) // 2, (ch - resized.height) // 2))
    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=92, optimize=True)
    return metadata.clean_image_bytes(out.getvalue())
