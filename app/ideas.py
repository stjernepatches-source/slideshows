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
You are a viral short-form storyteller for TikTok photo-slideshows in the dating
/ "sexual market value" (SMV) self-improvement niche. You write punchy,
first-person, dramatic micro-stories tuned to a specific audience.

Hard requirements:
- The PROTAGONIST is always the same fixed person described below — write in
  THEIR point of view, and make the story land for the target audience given.
- LENGTH: pick a slide count in the allowed range and put it in "num_slides".
  VARY it deliberately: sometimes a punchy 2-3 slide piece (e.g. a before/after
  glow-up), sometimes a 6-8 slide arc. Short can go viral too — don't default long.
- Exactly ONE beat is the "comparison" payoff: the product compares two people's
  SMV side by side. It can be two different people (e.g. the ex vs the new one),
  OR the SAME person before vs after a glow-up. Make it feel earned (curiosity,
  pettiness, closure, proof of the glow-up) — NEVER an ad. Name the two compared.
- Believable and platform-appropriate; no real public figures.

Return ONLY valid JSON in exactly this shape:
{
  "title": "short internal title",
  "num_slides": <integer in the allowed range>,
  "story": "the full narrative as plain prose, a few sentences per beat",
  "compare": ["PersonA", "PersonB"],
  "theme": "one-line theme"
}
"""


def is_configured() -> bool:
    return bool(config.XAI_API_KEY)


def invent_story(icp: dict[str, Any]) -> dict[str, Any]:
    """Ask Grok for a fresh story tuned to an ICP. Returns
    {title, num_slides, story, compare[], theme}."""
    if not config.XAI_API_KEY:
        raise RuntimeError("XAI_API_KEY is not set. Add it to your .env (console.x.ai).")
    smin = int(icp.get("slide_min", 2))
    smax = int(icp.get("slide_max", 8))

    user = (
        f"Target audience: {icp['label']} — {icp['gender']}, ages "
        f"{icp['age_min']}-{icp['age_max']}. Write what THIS audience binge-watches.\n"
        f"Protagonist (FIXED LEAD, their POV): {icp['lead_name']} — "
        f"{icp['lead_description']}.\n"
        f"Story themes that resonate here: {icp['themes']}.\n"
        f"Narrative voice: {icp['voice']}.\n"
        f"Product woven into the comparison beat: {config.PRODUCT_NAME}, "
        f"{config.PRODUCT_PITCH} (site {config.SITE_URL}).\n"
        f"Allowed slide count: {smin} to {smax}. Choose one and set num_slides; "
        f"favor variety (sometimes {smin}-3, sometimes longer).\n"
        f"Write the story now."
    )
    body = {
        "model": config.GROK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
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
    data = _parse(text)
    # Clamp the model's chosen length into the ICP's allowed range.
    try:
        n = int(data.get("num_slides") or config.AUTO_NUM_SLIDES)
    except (TypeError, ValueError):
        n = config.AUTO_NUM_SLIDES
    data["num_slides"] = max(smin, min(smax, n))
    return data


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
