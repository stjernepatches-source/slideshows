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
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config

# Emoji / pictograph code blocks — stripped from on-image text (the bold font
# can't render them anyway, and the user wants clean text on the pics). The
# post caption keeps its emojis; this only affects burned-in slide text.
_EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"   # symbols, emoticons, transport, supplemental, ext-A
    "\U0001F1E6-\U0001F1FF"   # regional indicator (flags)
    "\U00002600-\U000027BF"   # misc symbols + dingbats (incl. sparkles)
    "\U00002B00-\U00002BFF"   # stars, arrows
    "\U00002300-\U000023FF"   # misc technical (hourglass, etc.)
    "\U00002190-\U000021FF"   # arrows
    "\U0000FE00-\U0000FE0F"   # variation selectors
    "\U00002000-\U0000200D"   # zero-width joiner + exotic spaces
    "\U000024C2\U00002122\U00002139"
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    """Remove emojis/pictographs and tidy the whitespace they leave behind."""
    cleaned = _EMOJI.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip(" \t-—–·")

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


def _draw_caption(
    img: Image.Image,
    text: str,
    top_frac: Optional[float] = None,
    bottom_reserve: Optional[float] = None,
) -> None:
    """Draw wrapped, centered, white-with-black-outline text in a safe band.

    top_frac        = where the text block starts (fraction of height)
    bottom_reserve  = fraction of height kept clear at the bottom (UI zone)
    """
    w, h = img.size
    draw = ImageDraw.Draw(img)

    top_frac = config.TEXT_SAFE_TOP if top_frac is None else top_frac
    bottom_reserve = config.TEXT_SAFE_BOTTOM if bottom_reserve is None else bottom_reserve

    side = config.TEXT_SAFE_SIDE * w          # left/right margin
    max_w = w - 2 * side
    top = top_frac * h                        # where the text block begins
    bottom_limit = (1 - bottom_reserve) * h   # never cross into UI

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


def compose_caption(
    image: bytes,
    text: Optional[str],
    bottom_text: Optional[str] = None,
) -> bytes:
    """Return JPEG bytes with `text` burned near the top and optional
    `bottom_text` (e.g. "Wait for it") burned lower down. Emojis are stripped
    from both. Output carries no metadata (fresh Pillow encode)."""
    img = Image.open(io.BytesIO(image)).convert("RGB")
    text = _strip_emoji(text) if text else ""
    if text:
        _draw_caption(img, text)
    bt = _strip_emoji(bottom_text) if bottom_text else ""
    if bt:
        _draw_caption(img, bt, top_frac=config.TEXT_WAIT_TOP, bottom_reserve=0.06)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=92, optimize=True)
    return out.getvalue()


def compose_file(path: Path, text: Optional[str], bottom_text: Optional[str] = None) -> bytes:
    """Compose caption (+ optional bottom text) onto a slide file's bytes."""
    return compose_caption(path.read_bytes(), text, bottom_text=bottom_text)
