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
from typing import Any

from . import config

SYSTEM_PROMPT = """\
You are a visual director for short-form vertical (9:16) TikTok photo slideshows.
You turn a narrative into a sequence of striking, scroll-stopping image prompts.

Rules:
- Break the story into the requested number of slides that flow as a sequence.
- Each slide's "image_prompt" must be a single vivid, self-contained visual
  description of ONE moment: subject, action, setting, mood, lighting, framing.
  Write it for an image model. Do NOT reference other slides or say "same as".
- When characters from the provided cast appear in a slide, refer to them by
  their exact name so the renderer can attach their reference image. List those
  names in "characters".
- "caption" is OPTIONAL short on-image text (a few words) or "" if none.
- Keep it platform-appropriate; avoid real public figures and trademarks.

Return ONLY valid JSON, no prose, in exactly this shape:
{
  "slides": [
    {"image_prompt": "...", "caption": "...", "characters": ["Name", ...]}
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
    cast: list[dict[str, Any]] | None = None,
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
    data.setdefault("slides", [])
    data.setdefault("post_caption", "")
    data.setdefault("hashtags", [])
    for s in data["slides"]:
        s.setdefault("caption", "")
        s.setdefault("characters", [])
    return data
