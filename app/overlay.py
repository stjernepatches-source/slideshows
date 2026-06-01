"""Burn caption text onto a slide, TikTok-style.

Look: bold white fill with a thick black outline — the default TikTok caption
sticker style. Text is kept inside the safe zone (clear of TikTok's right-side
action buttons and the bottom caption/username/music bar) so nothing the user
writes ever gets covered by the app UI.

The base slide files on disk stay clean (no text). We compose the text on the
fly for review previews and again when uploading to Blotato, so editing a
caption never requires re-generating the image.
"""
from __future__ import annotations

from typing import Optional

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config

# Candidate bold fonts, best match first. Arial Bold is the closest common
# stand-in for TikTok's caption font. Override with TIKTOK_FONT in .env.
_FONT_CANDIDATES = [
    config.TIKTOK_FONT,
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if path and Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: float) -> list[str]:
    """Greedy word-wrap so each line fits within max_w pixels."""
    lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        cur = ""
        for word in paragraph.split():
            trial = f"{cur} {word}".strip()
            if cur and draw.textlength(trial, font=font) > max_w:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        lines.append(cur)
    return [ln for ln in lines if ln != ""] or [text]


def _draw_caption(img: Image.Image, text: str) -> None:
    """Draw wrapped, centered, white-with-black-outline text in the safe zone."""
    w, h = img.size
    draw = ImageDraw.Draw(img)

    side = config.TEXT_SAFE_SIDE * w          # left/right margin
    max_w = w - 2 * side
    top = config.TEXT_SAFE_TOP * h            # where the text block begins
    bottom_limit = (1 - config.TEXT_SAFE_BOTTOM) * h  # never cross into UI

    # Pick the largest font size (from a sensible cap downward) whose wrapped
    # lines fit the width AND don't run past the bottom safe limit.
    size = max(16, int(h * config.TEXT_SIZE_FRAC))
    while size >= 16:
        font = _font(size)
        lines = _wrap(draw, text, font, max_w)
        line_h = (font.getbbox("Ag")[3] - font.getbbox("Ag")[1]) * 1.25
        block_h = line_h * len(lines)
        widest = max((draw.textlength(ln, font=font) for ln in lines), default=0)
        if widest <= max_w and top + block_h <= bottom_limit:
            break
        size -= 4
    else:
        font, lines, line_h = _font(16), _wrap(draw, text, _font(16), max_w), 20

    stroke = max(2, int(size * config.TEXT_STROKE_FRAC))
    y = top
    for line in lines:
        draw.text(
            (w / 2, y),
            line,
            font=font,
            fill="white",
            stroke_width=stroke,
            stroke_fill="black",
            anchor="ma",  # middle-x, ascender-y -> horizontally centered
        )
        y += line_h


def compose_caption(image: bytes, text: Optional[str]) -> bytes:
    """Return JPEG bytes of the image with `text` burned on (or unchanged if no
    text). Output carries no metadata (fresh Pillow encode)."""
    img = Image.open(io.BytesIO(image)).convert("RGB")
    if text and text.strip():
        _draw_caption(img, text.strip())
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=92, optimize=True)
    return out.getvalue()


def compose_file(path: Path, text: Optional[str]) -> bytes:
    """Compose the caption onto a slide file's bytes (file left untouched)."""
    return compose_caption(path.read_bytes(), text)
