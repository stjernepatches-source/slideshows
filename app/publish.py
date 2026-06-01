"""Publish a generated slideshow to platforms via Blotato.

  TikTok            -> photo slideshow saved as a DRAFT (add music + publish in-app)
  Facebook / Instagram -> the stitched reel, posted directly

Shared by the web UI (Approve & Publish) and the hands-off runner so both behave
identically. Each platform fails independently; returns {results, errors}.
"""
from __future__ import annotations

from typing import Any, Optional

from . import blotato, config, slideshow


def post_text(show: dict[str, Any]) -> str:
    caption = show.get("post_caption", "")
    tags = " ".join(f"#{t.lstrip('#')}" for t in show.get("hashtags", []))
    return (caption + ("\n\n" + tags if tags else "")).strip()


def publish(
    show_id: str,
    platforms: list[str],
    facebook_page_id: Optional[str] = None,
    tiktok_account_id: Optional[str] = None,
) -> dict[str, Any]:
    show = slideshow.get_slideshow(show_id)
    if show is None:
        raise KeyError(show_id)
    if not any(s.get("file") for s in show["slides"]):
        raise ValueError("Generate the slides before publishing.")

    text = post_text(show)
    results: dict[str, Any] = {}
    errors: dict[str, str] = {}

    if "tiktok" in platforms:
        try:
            results["tiktok"] = blotato.post_tiktok_draft(
                image_bytes=slideshow.composited_slides(show_id),
                text=text, account_id=tiktok_account_id, title=show.get("title", ""),
            )
        except Exception as e:
            errors["tiktok"] = str(e)

    if "facebook" in platforms or "instagram" in platforms:
        video_url = None
        try:
            reel = slideshow.build_reel_video(show_id)
            video_url = blotato.upload_video(reel.read_bytes())
        except Exception as e:
            for p in ("facebook", "instagram"):
                if p in platforms:
                    errors[p] = f"reel build/upload failed: {e}"

        if video_url and "facebook" in platforms:
            try:
                page_id = facebook_page_id or config.FACEBOOK_PAGE_ID
                if not page_id:
                    raise RuntimeError("No Facebook Page id set (FACEBOOK_PAGE_ID).")
                acct = blotato.find_account_id("facebook")
                if not acct:
                    raise RuntimeError("No Facebook account connected in Blotato.")
                results["facebook"] = blotato.create_post(
                    acct, text, [video_url], blotato.facebook_reel_target(page_id))
            except Exception as e:
                errors["facebook"] = str(e)

        if video_url and "instagram" in platforms:
            try:
                acct = blotato.find_account_id("instagram")
                if not acct:
                    raise RuntimeError("No Instagram account connected in Blotato.")
                results["instagram"] = blotato.create_post(
                    acct, text, [video_url],
                    blotato.instagram_reel_target(config.INSTAGRAM_SHARE_TO_FEED))
            except Exception as e:
                errors["instagram"] = str(e)

    if results and not errors:
        slideshow.mark_posted(show_id, {"provider": "blotato", "results": results})
    return {"results": results, "errors": errors}
