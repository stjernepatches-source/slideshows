"""Hands-off pipeline for scheduled (cron) runs.

One run = invent a story with Grok -> generate the slideshow (fixed lead woman,
auto comparison/CTA slide) -> strip metadata -> publish: TikTok draft + Facebook
& Instagram reels. Designed to run in GitHub Actions twice a day, with the Mac off.

Usage:  python -m app.runner [optional theme]
"""
from __future__ import annotations

import json
import sys
from typing import Any, Optional

from . import config, ideas, publish, slideshow


def run_once(theme: Optional[str] = None) -> dict[str, Any]:
    # Preconditions that would otherwise fail mid-run with a vague error.
    if not config.lead_available():
        raise RuntimeError(
            "No lead reference photos found in assets/protagonist/. Add the "
            "woman's photos there (and commit them) before running automation."
        )
    if not ideas.is_configured():
        raise RuntimeError("XAI_API_KEY is not set (needed for Grok story ideation).")

    idea = ideas.invent_story(theme)
    show = slideshow.create_slideshow(
        title=idea.get("title", "Untitled"),
        story=idea["story"],
        character_ids=[],
        num_slides=config.AUTO_NUM_SLIDES,
    )
    slideshow.generate_all(show["id"])
    result = publish.publish(show["id"], config.AUTO_PLATFORMS)
    return {"id": show["id"], "title": show["title"], "theme": idea.get("theme", ""), **result}


def main() -> int:
    theme = sys.argv[1] if len(sys.argv) > 1 else None
    out = run_once(theme)
    print(json.dumps(out, indent=2))
    # Non-zero exit if every requested platform errored (so CI surfaces failures).
    return 0 if out.get("results") else 1


if __name__ == "__main__":
    raise SystemExit(main())
