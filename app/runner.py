"""Hands-off pipeline for scheduled (cron) runs — per ICP.

One run for an ICP = invent a story tuned to that audience (Grok) -> generate the
slideshow with that ICP's fixed lead -> strip metadata -> post to that ICP's
TikTok account (draft). Each TikTok account is one ICP; the scheduler fires this
for every ICP at each posting time.

Usage:
  python -m app.runner <icp_id>     # one ICP
  python -m app.runner all          # every ICP with lead photos present
"""
from __future__ import annotations

import json
import sys
from typing import Any

from . import icps, ideas, publish, slideshow


def run_once(icp_id: str) -> dict[str, Any]:
    icp = icps.get_icp(icp_id)
    if icp is None:
        raise ValueError(f"Unknown ICP '{icp_id}'. Known: {[i['id'] for i in icps.all_icps()]}")
    if not icps.lead_available(icp):
        raise RuntimeError(
            f"No lead photos for ICP '{icp_id}' in {icp['lead_ref_dir']}/. "
            "Add the persona's reference photos (and commit them) first."
        )
    if not ideas.is_configured():
        raise RuntimeError("XAI_API_KEY is not set (needed for Grok story ideation).")

    idea = ideas.invent_story(icp)
    lead = {
        "name": icp["lead_name"],
        "description": icp["lead_description"],
        "ref_dir": icp["lead_ref_dir"],
    }
    show = slideshow.create_slideshow(
        title=idea.get("title", "Untitled"),
        story=idea["story"],
        character_ids=[],
        num_slides=idea["num_slides"],
        lead=lead,
        icp_id=icp_id,
    )
    slideshow.generate_all(show["id"])
    # Each ICP posts to its own TikTok account (draft).
    result = publish.publish(show["id"], ["tiktok"], tiktok_account_id=icp["account_id"])
    return {"icp": icp_id, "account": icp["account_id"], "id": show["id"],
            "title": show["title"], "slides": len(show["slides"]), **result}


def run_all() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for icp in icps.all_icps():
        if not icps.lead_available(icp):
            out.append({"icp": icp["id"], "skipped": "no lead photos"})
            continue
        try:
            out.append(run_once(icp["id"]))
        except Exception as e:
            out.append({"icp": icp["id"], "error": str(e)})
    return out


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target != "all":
        icp = icps.get_icp(target)
        # An ICP with no lead photos yet is a clean SKIP (green), not a failure —
        # so the live schedule no-ops until you add that persona's photos.
        if icp is not None and not icps.lead_available(icp):
            print(json.dumps([{"icp": target, "skipped": "no lead photos yet"}]))
            return 0
        out = [run_once(target)]
    else:
        out = run_all()
    print(json.dumps(out, indent=2))
    real_error = any(r.get("error") or r.get("errors") for r in out)
    return 1 if real_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
