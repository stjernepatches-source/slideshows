"""Story -> scenes via the Claude API.

Takes the raw narrative you paste in and returns an ordered list of slides.
Each slide has an image prompt (a vivid, self-contained visual description) and
optional on-image caption text. We also ask Claude for a suggested TikTok
caption + hashtags for the post as a whole.

Prompt caching is used on the (static) system prompt so repeated runs are
cheaper and faster.
"""
from __future__ import annotations

import json
from typing import Optional, Any

from . import config

SYSTEM_PROMPT = """\
You are a visual director for short-form vertical (9:16) TikTok photo slideshows.
You turn a narrative into a sequence of image prompts that look like REAL CANDID
SNAPSHOTS, not polished AI art.

AESTHETIC — this is critical. Every slide must read as an ordinary candid
snapshot pulled straight from a normal person's camera roll:
- Describe ordinary, believable moments with flat everyday lighting (indoor
  light, overcast, plain daylight). Do NOT write "cinematic", "dramatic
  lighting", "high-contrast", "moody", "golden hour", "professional portrait",
  "studio", "bokeh", "shallow depth of field", or any glossy/film-look words.
- Lean casual and slightly imperfect: unposed body language, off-center or
  slightly awkward phone framing, normal rooms, real clutter.
- Keep each prompt concrete and physical (who, doing what, where) and let the
  global phone-camera style handle the "look". Don't over-art-direct.
- Describe only the CONTENT of the photo. Never ask for phone UI, screenshots,
  status bars, or a phone/device frame. A "selfie" means close arm's-length
  framing, NOT a picture of a phone or its screen.

CHARACTER CONSISTENCY:
- First identify the small set of RECURRING people in the story (usually 1-3).
  For each, write a SHORT, FIXED physical description that never changes:
  approximate age, build, hair (color/length/style), notable features, and a
  default everyday outfit. Put these in the top-level "cast" array.
- In every slide where a recurring person appears, (a) list their exact name in
  "characters", and (b) restate their key physical description inside the
  image_prompt. The same person must look the same in every slide.
- One-off background people who appear in only a single slide do NOT go in
  "cast"; just describe them inline.

OTHER RULES:
- Break the story into exactly the requested number of slides, in order.
- Each "image_prompt" is ONE self-contained moment. Never say "same as slide X".
- "caption" is OPTIONAL short on-image text (a few words) or "".
- Keep it platform-appropriate; avoid real public figures and trademarks.

Return ONLY valid JSON, no prose, in exactly this shape:
{
  "cast": [
    {"name": "ShortName", "description": "fixed physical description + default outfit"}
  ],
  "slides": [
    {"image_prompt": "...", "caption": "...", "characters": ["ShortName", ...]}
  ],
  "post_caption": "suggested TikTok caption",
  "hashtags": ["tag", "tag", ...]
}
"""


def _client():
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env to use auto "
            "scene-splitting."
        )
    import anthropic

    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def split_story(
    story: str,
    num_slides: int = 6,
    cast: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Return {slides:[...], post_caption, hashtags} for the given story."""
    cast = cast or []
    cast_block = "\n".join(f"- {c['name']}: {c['description']}" for c in cast) or "(none)"

    user_prompt = (
        f"Number of slides: {num_slides}\n\n"
        f"Available cast (use exact names when they appear):\n{cast_block}\n\n"
        f"Story:\n{story.strip()}"
    )

    client = _client()
    resp = client.messages.create(
        model=config.SCENE_MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    return _parse(text)


def _parse(text: str) -> dict[str, Any]:
    """Be forgiving: extract the JSON object even if wrapped in fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Claude did not return JSON. Got:\n{text[:500]}")
    data = json.loads(text[start : end + 1])
    data.setdefault("cast", [])
    data.setdefault("slides", [])
    data.setdefault("post_caption", "")
    data.setdefault("hashtags", [])
    for s in data["slides"]:
        s.setdefault("caption", "")
        s.setdefault("characters", [])
    return data
