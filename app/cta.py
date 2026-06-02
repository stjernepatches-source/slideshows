"""Render the comparison / CTA slide as our software's results screen.

This is NOT a static template anymore. We draw a clean phone-app "results"
screen from scratch with Pillow so every value is dynamic and story-driven:
the two compared people's faces, their SCORE /10, an X-FACTOR headline tag, and
a short list of up/down trait rows. The scene writer (scenes.py) produces the
numbers and traits for the specific story; here we just lay them out so the
slide reads as a real screenshot of the product in use.

The whole frame is the app screen (light background + app header) so viewers
read it as "they actually ran the tool", not an AI picture of a chart.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont

from . import config

# --- palette (a clean, neutral product UI) ----------------------------------
BG = (244, 245, 247)          # phone screen behind the card
CARD = (255, 255, 255)        # the results card
INK = (24, 26, 32)            # primary text
MUTED = (140, 146, 156)       # labels / secondary text
LINE = (232, 234, 238)        # hairlines / dividers
ACCENT = (124, 92, 255)       # winner score + brand (purple)
UP = (34, 178, 110)           # green, an improvement / strength
DOWN = (150, 156, 166)        # muted, a weakness
PILL_BG = (244, 241, 255)     # headline pill background (accent tint)
PILL_INK = (108, 78, 240)

_BOLD = [
    config.TIKTOK_FONT,
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_REG = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def is_ready() -> bool:
    """The card is drawn in code, so it's always available."""
    return True


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for path in (_BOLD if bold else _REG):
        if path and Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _cover_crop(img: Image.Image, w: int, h: int) -> Image.Image:
    """Resize+center-crop img to exactly w×h (object-fit: cover)."""
    img = img.convert("RGB")
    sw, sh = img.size
    scale = max(w / sw, h / sh)
    new = img.resize((max(1, round(sw * scale)), max(1, round(sh * scale))))
    left = (new.width - w) // 2
    top = (new.height - h) // 2
    return new.crop((left, top, left + w, top + h))


def _rounded(img: Image.Image, radius: int) -> Image.Image:
    """Apply rounded corners to an RGB image (returns RGBA)."""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width, img.height], radius=radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def _norm_traits(person: dict[str, Any]) -> list[tuple[str, bool]]:
    """Return [(label, is_up)] for a person's traits, tolerant of shapes."""
    out: list[tuple[str, bool]] = []
    for t in (person.get("traits") or [])[:6]:
        if isinstance(t, dict):
            label = str(t.get("label", "")).strip()
            up = bool(t.get("up", True))
        else:
            label = str(t).strip()
            up = True
        if label:
            out.append((label, up))
    return out


def _draw_arrow(draw: ImageDraw.ImageDraw, x: int, cy: int, up: bool, size: int) -> None:
    """Draw a small solid up/down triangle (no font-glyph dependency)."""
    half = size // 2
    color = UP if up else DOWN
    if up:
        pts = [(x, cy - half), (x - half, cy + half), (x + half, cy + half)]
    else:
        pts = [(x - half, cy - half), (x + half, cy - half), (x, cy + half)]
    draw.polygon(pts, fill=color)


def _draw_person(
    base: Image.Image,
    draw: ImageDraw.ImageDraw,
    col_x: int,
    col_w: int,
    top: int,
    face: bytes,
    person: dict[str, Any],
    winner: bool,
) -> None:
    pad = 0
    fx = col_x + pad
    fw = col_w - 2 * pad
    fh = int(fw * 0.72)
    # Face
    crop = _rounded(_cover_crop(Image.open(io.BytesIO(face)), fw, fh), 28)
    base.paste(crop, (fx, top), crop)

    y = top + fh + 34
    # SCORE label
    f_lbl = _font(26, bold=True)
    draw.text((fx, y), "SCORE", font=f_lbl, fill=MUTED)
    y += 38
    # Big score + /10
    score = person.get("score")
    score_str = f"{float(score):.2f}" if isinstance(score, (int, float)) else str(score or "—")
    f_num = _font(96, bold=True)
    draw.text((fx, y), score_str, font=f_num, fill=(ACCENT if winner else INK))
    num_w = draw.textlength(score_str, font=f_num)
    f_den = _font(34, bold=True)
    draw.text((fx + num_w + 8, y + 52), "/10", font=f_den, fill=MUTED)
    y += 118

    # X-FACTOR label
    draw.text((fx, y), "X - F A C T O R", font=_font(22, bold=True), fill=MUTED)
    y += 38
    # Headline pill (+ tag)
    headline = str(person.get("headline", "")).strip()
    if headline:
        f_pill = _font(28, bold=True)
        txt = f"+ {headline}"
        tw = draw.textlength(txt, font=f_pill)
        ph = 52
        draw.rounded_rectangle([fx, y, fx + tw + 36, y + ph], radius=ph // 2, fill=PILL_BG)
        draw.text((fx + 18, y + ph // 2), txt, font=f_pill, fill=PILL_INK, anchor="lm")
        y += ph + 22

    # Trait rows
    f_tr = _font(28, bold=False)
    for label, up in _norm_traits(person):
        cy = y + 18
        _draw_arrow(draw, fx + 9, cy, up, 22)
        draw.text((fx + 30, cy), label, font=f_tr, fill=(INK if up else MUTED), anchor="lm")
        y += 44


def build_comparison(
    faces: list[bytes],
    names: Optional[list[str]] = None,
    scorecard: Optional[dict[str, Any]] = None,
) -> bytes:
    """Render the results screen for [winner, loser]; return JPEG bytes.

    faces[0]/names[0] is the winner (higher score), faces[1] the loser. The
    scorecard supplies each side's score/headline/traits; missing pieces fall
    back to sensible defaults so the slide always renders.
    """
    if not faces:
        raise RuntimeError("No faces available for the comparison slide.")
    scorecard = scorecard or {}
    winner = dict(scorecard.get("winner") or {})
    loser = dict(scorecard.get("loser") or {})
    # Defaults so a thin/missing scorecard still produces a believable card.
    winner.setdefault("score", 8.0)
    loser.setdefault("score", 5.5)

    W, H = config.REEL_WIDTH, config.REEL_HEIGHT
    base = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(base)

    # --- card frame ---------------------------------------------------------
    # Card sits in the lower-middle so the burned-in caption (added later by
    # overlay.compose_caption near the top) has clear room above the faces.
    mx = 36
    cx0, cx1 = mx, W - mx
    cy0, cy1 = 470, 1640
    draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=44, fill=CARD)

    # --- app header (sells "this is the real software") ---------------------
    hx = cx0 + 44
    hy = cy0 + 40
    # brand dot + name (left), "Results" (right)
    draw.ellipse([hx, hy + 4, hx + 30, hy + 34], fill=ACCENT)
    draw.text((hx + 42, hy + 6), config.SITE_URL, font=_font(34, bold=True), fill=INK)
    rtxt = "Results"
    draw.text((cx1 - 44, hy + 8), rtxt, font=_font(30, bold=True), fill=MUTED, anchor="ra")
    hdr_b = hy + 64
    draw.line([cx0 + 32, hdr_b, cx1 - 32, hdr_b], fill=LINE, width=2)

    # --- two columns --------------------------------------------------------
    gutter = 40
    inner = (cx1 - cx0) - 2 * 44
    col_w = (inner - gutter) // 2
    left_x = cx0 + 44
    right_x = left_x + col_w + gutter
    content_top = hdr_b + 40
    names = names or ["", ""]
    _draw_person(base, draw, left_x, col_w, content_top, faces[0], winner, winner=True)
    if len(faces) > 1:
        _draw_person(base, draw, right_x, col_w, content_top, faces[1], loser, winner=False)

    # vertical divider between columns
    div_x = left_x + col_w + gutter // 2
    draw.line([div_x, content_top + 10, div_x, cy1 - 150], fill=LINE, width=2)

    # --- footer CTA bar -----------------------------------------------------
    fy = cy1 - 96
    draw.line([cx0 + 32, fy - 24, cx1 - 32, fy - 24], fill=LINE, width=2)
    cta = f"Compare yours at {config.SITE_URL}"
    draw.text(((cx0 + cx1) // 2, fy + 18), cta, font=_font(30, bold=True), fill=ACCENT, anchor="mm")

    from . import metadata
    out = io.BytesIO()
    base.save(out, format="JPEG", quality=92, optimize=True)
    return metadata.clean_image_bytes(out.getvalue())
