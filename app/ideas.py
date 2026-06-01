"""Story ideation via Grok (xAI).

For hands-off runs we need the system to invent the story itself. Grok is used
here (more unfiltered than Claude for spicy relationship drama). It returns a
short, vertical-slideshow-friendly narrative that:
  - stars the fixed lead woman as protagonist,
  - builds naturally toward ONE beat where two people get compared with the
    product (that beat becomes the comparison/CTA slide),
  - is dramatic and scroll-stopping but not an ad.

xAI exposes an OpenAI-compatible API at https://api.x.ai/v1.
"""
from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from . import config

XAI_URL = "https://api.x.ai/v1/chat/completions"

SYSTEM_PROMPT = """\
You are a viral short-form storyteller for TikTok / Reels photo-slideshows in
the dating, relationships and "sexual market value" niche. You write punchy,
first-person, dramatic micro-stories that stop the scroll.

Hard requirements:
- The PROTAGONIST is always the same woman (described below). Write in her POV.
- Tell a complete arc in {n} beats (one beat per slide), emotional and bingeable.
- Exactly ONE beat is the "comparison" payoff: she runs two people through the
  product to compare their dating-market value / SMV. Make it feel natural and
  earned by the story (curiosity, pettiness, closure) — NOT an ad. Name the two
  people being compared.
- Keep it believable and platform-appropriate; no real public figures.

Return ONLY valid JSON in exactly this shape:
{
  "title": "short internal title",
  "story": "the full narrative as plain prose, a few sentences per beat",
  "compare": ["PersonA", "PersonB"],
  "theme": "one-line theme"
}
The "compare" pair are the two people whose photos belong in the comparison slide.
"""


def is_configured() -> bool:
    return bool(config.XAI_API_KEY)


def invent_story(theme: Optional[str] = None, num_beats: Optional[int] = None) -> dict[str, Any]:
    """Ask Grok for a fresh story. Returns {title, story, compare[], theme}."""
    if not config.XAI_API_KEY:
        raise RuntimeError("XAI_API_KEY is not set. Add it to your .env (console.x.ai).")
    num_beats = num_beats or config.AUTO_NUM_SLIDES

    system = SYSTEM_PROMPT.replace("{n}", str(num_beats))
    user = (
        f"Protagonist (the fixed lead): {config.LEAD_NAME} — {config.LEAD_DESCRIPTION}.\n"
        f"Product to weave into the comparison beat: {config.PRODUCT_NAME}, "
        f"{config.PRODUCT_PITCH} (site {config.SITE_URL}).\n"
        f"Theme: {theme or 'her choice — dating / cheating / glow-up / closure drama'}.\n"
        f"Write the story now."
    )
    body = {
        "model": config.GROK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 1.05,
    }
    with httpx.Client(timeout=120) as c:
        r = c.post(
            XAI_URL,
            headers={"Authorization": f"Bearer {config.XAI_API_KEY}"},
            json=body,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
    return _parse(text)


def _parse(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Grok did not return JSON. Got:\n{text[:500]}")
    data = json.loads(text[start : end + 1])
    data.setdefault("title", "Untitled")
    data.setdefault("story", "")
    data.setdefault("compare", [])
    data.setdefault("theme", "")
    return data
