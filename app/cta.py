"""Render the comparison / CTA slide to look like the real Nordiva results UI.

Drawn from scratch with Pillow so every value is dynamic and story-driven, but
styled to match the actual product: a gradient headline, two separate shadowed
cards with full-bleed photos, a WINNER badge, a gradient SCORE, a gradient
X-FACTOR pill, and individual up/down trait pills.
"""
from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from . import config

# --- palette ----------------------------------------------------------------
BG = (250, 250, 251)          # page
CARD = (255, 255, 255)        # card surface
INK = (17, 18, 22)            # primary text
MUTED = (150, 156, 165)       # labels / secondary
PILL_LINE = (228, 230, 234)   # trait pill border
UP = (139, 92, 246)           # purple up-arrow (a strength)
DOWN = (165, 170, 178)        # gray down-arrow (a weakness)
# Brand gradient (purple -> blue -> teal), used for accents.
GRAD = [(150, 86, 240), (86, 132, 242), (40, 198, 176)]

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
    "/System/Library/Fonts/HelveticaNeue.ttc",
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
    img = img.convert("RGB")
    sw, sh = img.size
    scale = max(w / sw, h / sh)
    new = img.resize((max(1, round(sw * scale)), max(1, round(sh * scale))))
    left = (new.width - w) // 2
    top = (new.height - h) // 2
    return new.crop((left, top, left + w, top + h))


def _gradient(w: int, h: int, stops: list) -> Image.Image:
    """A horizontal gradient image across the given RGB stops."""
    w, h = max(1, int(w)), max(1, int(h))
    row = Image.new("RGB", (w, 1))
    px = row.load()
    n = len(stops) - 1
    for x in range(w):
        t = x / (w - 1) if w > 1 else 0.0
        seg = t * n
        i = min(int(seg), n - 1)
        f = seg - i
        a, b = stops[i], stops[i + 1]
        px[x, 0] = (
            int(a[0] + (b[0] - a[0]) * f),
            int(a[1] + (b[1] - a[1]) * f),
            int(a[2] + (b[2] - a[2]) * f),
        )
    return row.resize((w, h))


def _grad_text(text: str, font: ImageFont.FreeTypeFont, stops: list) -> Image.Image:
    """An RGBA image of `text` filled with a horizontal gradient (sized to text)."""
    scratch = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t, r, b = scratch.textbbox((0, 0), text, font=font)
    w, h = max(1, r - l), max(1, b - t)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((-l, -t), text, font=font, fill=255)
    grad = _gradient(w, h, stops).convert("RGBA")
    grad.putalpha(mask)
    return grad


def _sparkle(draw: ImageDraw.ImageDraw, cx: float, cy: float, R: float, color) -> None:
    """A small 4-point star (✦)."""
    pts = []
    for i in range(8):
        rad = R if i % 2 == 0 else R * 0.36
        a = -math.pi / 2 + i * (math.pi / 4)
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    draw.polygon(pts, fill=color)


def _arrow(draw: ImageDraw.ImageDraw, x: float, cy: float, up: bool, size: int) -> None:
    half = size / 2
    color = UP if up else DOWN
    if up:
        pts = [(x, cy - half), (x - half, cy + half), (x + half, cy + half)]
    else:
        pts = [(x - half, cy - half), (x + half, cy - half), (x, cy + half)]
    draw.polygon(pts, fill=color)


def _round_top(img: Image.Image, radius: int) -> Image.Image:
    """Round only the TOP two corners (photo sits flush with the card body)."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
    d.rectangle([0, radius, w, h], fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def _norm_traits(person: dict[str, Any]) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    for t in (person.get("traits") or [])[:6]:
        if isinstance(t, dict):
            label, up = str(t.get("label", "")).strip(), bool(t.get("up", True))
        else:
            label, up = str(t).strip(), True
        if label:
            out.append((label, up))
    return out


# --- layout constants -------------------------------------------------------
W, H = 1080, 1920
MARGIN = 44
GUTTER = 32
CARD_W = (W - 2 * MARGIN - GUTTER) // 2
CARD_R = 30
PHOTO_H = 536
PAD = 30                       # inner padding of the info area
PILL_H = 50


def _trait_rows(draw, traits, x0, content_w, font):
    """Greedy-wrap trait pills; return list of rows, each a list of
    (label, up, pill_w, text_w)."""
    pad_x, arrow_w, arrow_gap, gap_x = 18, 15, 9, 11
    rows, row, cx = [], [], 0
    for label, up in traits:
        tw = draw.textlength(label, font=font)
        pw = pad_x + arrow_w + arrow_gap + tw + pad_x
        if row and cx + pw > content_w:
            rows.append(row)
            row, cx = [], 0
        row.append((label, up, pw, tw))
        cx += pw + gap_x
    if row:
        rows.append(row)
    return rows


def _info_bottom(draw, person, content_w, font_tr) -> int:
    """Height of the info block below the photo (for equalizing card heights)."""
    rows = _trait_rows(draw, _norm_traits(person), 0, content_w, font_tr)
    y = PAD                      # top pad
    y += 30 + 6                  # SCORE label
    y += 96                      # score number
    y += 34 + 20                 # X-FACTOR label
    y += 54 + 18                 # headline pill
    y += len(rows) * (PILL_H + 12)
    return y + PAD - 12


def _draw_card(base, draw, x0, y0, card_h, face, person, winner, fonts):
    # shadow
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x0, y0 + 10, x0 + CARD_W, y0 + card_h + 10], radius=CARD_R, fill=(20, 24, 40, 55))
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(16)))

    # card surface
    draw.rounded_rectangle([x0, y0, x0 + CARD_W, y0 + card_h], radius=CARD_R, fill=CARD)

    # full-bleed photo (rounded top only)
    photo = _round_top(_cover_crop(Image.open(io.BytesIO(face)), CARD_W, PHOTO_H), CARD_R)
    base.alpha_composite(photo, (x0, y0))

    # WINNER badge
    if winner:
        bx, by = x0 + 18, y0 + 18
        btxt = "WINNER"
        bw = 30 + draw.textlength(btxt, font=fonts["badge"]) + 22
        draw.rounded_rectangle([bx, by, bx + bw, by + 40], radius=20, fill=(255, 255, 255))
        _sparkle(draw, bx + 18, by + 20, 7, UP)
        draw.text((bx + 30, by + 20), btxt, font=fonts["badge"], fill=INK, anchor="lm")

    cx0 = x0 + PAD
    content_w = CARD_W - 2 * PAD
    y = y0 + PHOTO_H + PAD

    # SCORE
    draw.text((cx0, y), "SCORE", font=fonts["label"], fill=MUTED)
    y += 36
    score = person.get("score")
    s = f"{float(score):.2f}" if isinstance(score, (int, float)) else str(score or "—")
    if winner:
        g = _grad_text(s, fonts["score"], GRAD)
        base.alpha_composite(g, (cx0, y))
        num_w = g.width
    else:
        draw.text((cx0, y), s, font=fonts["score"], fill=INK)
        num_w = draw.textlength(s, font=fonts["score"])
    draw.text((cx0 + num_w + 8, y + 46), "/10", font=fonts["den"], fill=MUTED)
    y += 96

    # X-FACTOR
    draw.text((cx0, y), "X - F A C T O R", font=fonts["label"], fill=MUTED)
    y += 34 + 20
    headline = str(person.get("headline", "")).strip() or "overall"
    htxt = headline
    ph = 54
    pw = 30 + 8 + draw.textlength(htxt, font=fonts["pill"]) + 24
    # gradient-border pill
    ring = _gradient(int(pw), ph, GRAD)
    rmask = Image.new("L", (int(pw), ph), 0)
    rd = ImageDraw.Draw(rmask)
    rd.rounded_rectangle([0, 0, int(pw) - 1, ph - 1], radius=ph // 2, fill=255)
    rd.rounded_rectangle([3, 3, int(pw) - 4, ph - 4], radius=ph // 2 - 3, fill=0)
    base.paste(ring, (cx0, y), rmask)
    _sparkle(draw, cx0 + 22, y + ph / 2, 8, UP)
    draw.text((cx0 + 38, y + ph / 2), htxt, font=fonts["pill"], fill=INK, anchor="lm")
    y += ph + 18

    # trait pills
    rows = _trait_rows(draw, _norm_traits(person), cx0, content_w, fonts["trait"])
    for row in rows:
        px = cx0
        for label, up, pwd, tw in row:
            draw.rounded_rectangle([px, y, px + pwd, y + PILL_H], radius=PILL_H // 2,
                                   outline=PILL_LINE, width=2, fill=CARD)
            _arrow(draw, px + 18 + 7, y + PILL_H / 2, up, 15)
            draw.text((px + 18 + 15 + 9, y + PILL_H / 2), label,
                      font=fonts["trait"], fill=INK if up else MUTED, anchor="lm")
            px += pwd + 11
        y += PILL_H + 12


def _draw_title(base, draw, text, y0, fonts) -> int:
    """Centered headline; the final word is rendered in the brand gradient."""
    text = (text or "").strip() or "left one wins."
    max_w = W - 2 * 56
    for size in (92, 84, 76, 68, 60, 54):
        font = _font(size, bold=True)
        words = text.split()
        lines, cur = [], ""
        for w_ in words:
            trial = f"{cur} {w_}".strip()
            if cur and draw.textlength(trial, font=font) > max_w:
                lines.append(cur)
                cur = w_
            else:
                cur = trial
        if cur:
            lines.append(cur)
        if len(lines) <= 2:
            break
    lh = int(size * 1.16)
    y = y0
    for li, line in enumerate(lines):
        last = li == len(lines) - 1
        if not last:
            draw.text((W / 2, y), line, font=font, fill=INK, anchor="ma")
        else:
            parts = line.rsplit(" ", 1)
            head = parts[0] + " " if len(parts) == 2 else ""
            tail = parts[-1]
            head_w = draw.textlength(head, font=font)
            g = _grad_text(tail, font, GRAD)
            total = head_w + g.width
            sx = (W - total) / 2
            draw.text((sx, y), head, font=font, fill=INK, anchor="la")
            base.alpha_composite(g, (int(sx + head_w), int(y)))
        y += lh
    return y


def build_comparison(
    faces: list[bytes],
    names: Optional[list[str]] = None,
    scorecard: Optional[dict[str, Any]] = None,
    title: Optional[str] = None,
) -> bytes:
    """Render the results screen for [winner, loser]; return JPEG bytes."""
    if not faces:
        raise RuntimeError("No faces available for the comparison slide.")
    scorecard = scorecard or {}
    winner = dict(scorecard.get("winner") or {})
    loser = dict(scorecard.get("loser") or {})
    winner.setdefault("score", 8.0)
    loser.setdefault("score", 5.5)

    fonts = {
        "label": _font(24, bold=True),
        "score": _font(86, bold=True),
        "den": _font(30, bold=True),
        "pill": _font(28, bold=True),
        "trait": _font(27, bold=False),
        "badge": _font(24, bold=True),
    }

    base = Image.new("RGBA", (W, H), BG + (255,))
    draw = ImageDraw.Draw(base)

    # title
    title_bottom = _draw_title(base, draw, title, 150, fonts)
    cards_top = int(title_bottom + 70)

    # equal card heights (taller of the two info blocks)
    info_h = max(_info_bottom(draw, winner, CARD_W - 2 * PAD, fonts["trait"]),
                 _info_bottom(draw, loser, CARD_W - 2 * PAD, fonts["trait"]))
    card_h = PHOTO_H + info_h

    lx, rx = MARGIN, MARGIN + CARD_W + GUTTER
    _draw_card(base, draw, lx, cards_top, card_h, faces[0], winner, True, fonts)
    if len(faces) > 1:
        _draw_card(base, draw, rx, cards_top, card_h, faces[1], loser, False, fonts)

    from . import metadata
    out = io.BytesIO()
    base.convert("RGB").save(out, format="JPEG", quality=92, optimize=True)
    return metadata.clean_image_bytes(out.getvalue())
