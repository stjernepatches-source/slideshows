"""Strip AI provenance metadata from generated slides.

What this removes (reliably):
  - EXIF / XMP tags
  - C2PA "Content Credentials" (the signed provenance block TikTok and others
    read to auto-apply an "AI-generated" label)

How:
  1. Re-encode the pixels with Pillow into a fresh file with NO metadata. This
     alone drops EXIF/XMP/C2PA because none of it is copied over.
  2. If the `exiftool` binary is available, also run `exiftool -all=` as a
     belt-and-suspenders pass. It's optional — install it for extra assurance.

What this CANNOT remove (be honest):
  - Google SynthID, an invisible pixel-level watermark on Gemini / nano-banana
    outputs. It survives re-encoding. Use the default Seedream model to avoid
    it entirely (Seedream does not embed SynthID).

Also normalizes each slide to a target vertical aspect ratio (center-crop) so
the whole set is uniform for TikTok.
"""
from __future__ import annotations

from typing import Optional

import io
import shutil
import subprocess
from pathlib import Path

from PIL import Image

ASPECT_FRACTIONS = {
    "9:16": (9, 16),
    "16:9": (16, 9),
    "1:1": (1, 1),
    "4:3": (4, 3),
    "3:4": (3, 4),
}


def _center_crop_to_aspect(img: Image.Image, aspect: str) -> Image.Image:
    if aspect not in ASPECT_FRACTIONS:
        return img
    aw, ah = ASPECT_FRACTIONS[aspect]
    target = aw / ah
    w, h = img.size
    current = w / h
    if abs(current - target) < 1e-3:
        return img
    if current > target:  # too wide -> crop width
        new_w = int(round(h * target))
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    new_h = int(round(w / target))  # too tall -> crop height
    top = (h - new_h) // 2
    return img.crop((0, top, w, top + new_h))


def clean_image_bytes(data: bytes, aspect: Optional[str] = None) -> bytes:
    """Re-encode image bytes with no metadata, optionally normalizing aspect."""
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGB")  # drop alpha + any embedded profiles
    if aspect:
        img = _center_crop_to_aspect(img, aspect)
    out = io.BytesIO()
    # A brand-new image with no info dict => no EXIF/XMP/C2PA carried over.
    img.save(out, format="JPEG", quality=92, optimize=True)
    return out.getvalue()


def exiftool_available() -> bool:
    return shutil.which("exiftool") is not None


def strip_file(path: Path, aspect: Optional[str] = None) -> Path:
    """Clean a saved image file in place. Returns the path."""
    cleaned = clean_image_bytes(path.read_bytes(), aspect=aspect)
    path.write_bytes(cleaned)
    if exiftool_available():
        subprocess.run(
            ["exiftool", "-all=", "-overwrite_original", str(path)],
            check=False,
            capture_output=True,
        )
    return path


def has_c2pa(path: Path) -> bool:
    """Best-effort check for leftover C2PA/credentials (needs exiftool)."""
    if not exiftool_available():
        return False
    res = subprocess.run(
        ["exiftool", str(path)], check=False, capture_output=True, text=True
    )
    blob = res.stdout.lower()
    return "c2pa" in blob or "content credential" in blob or "jumbf" in blob
