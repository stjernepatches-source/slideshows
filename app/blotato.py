"""Post slideshows to TikTok via Blotato (as drafts).

Why Blotato instead of TikTok's own Content Posting API: TikTok only lets
*audited* apps post, and even then pulls images from a verified public domain.
Blotato already holds the TikTok connection, accepts images as base64 (no public
URL / tunnel needed), and can create the post as a DRAFT — so you skip TikTok's
app audit entirely and just tap publish (and add music) in the TikTok app.

API: base https://backend.blotato.com/v2, header `blotato-api-key`.
  GET  /v2/users/me/accounts   -> connected social accounts
  POST /v2/media   {url}       -> uploads (public URL or base64) -> {url: hosted}
  POST /v2/posts   {post,...}  -> creates the post (isDraft=true) -> {postSubmissionId}
"""
from __future__ import annotations

import base64
import time
from typing import Any, Optional

import httpx

from . import config

BASE = "https://backend.blotato.com/v2"


def is_configured() -> bool:
    return bool(config.BLOTATO_API_KEY)


def _headers() -> dict[str, str]:
    if not config.BLOTATO_API_KEY:
        raise RuntimeError(
            "BLOTATO_API_KEY is not set. Add it to your .env (get it at "
            "https://my.blotato.com/settings/api)."
        )
    return {
        "blotato-api-key": config.BLOTATO_API_KEY,
        "Content-Type": "application/json",
    }


def list_accounts() -> list[dict[str, Any]]:
    """Connected social accounts on the Blotato side."""
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{BASE}/users/me/accounts", headers=_headers())
        r.raise_for_status()
        data = r.json()
    # Be tolerant of shape: a bare list, or wrapped under a key.
    if isinstance(data, list):
        return data
    for key in ("accounts", "items", "data"):
        if isinstance(data.get(key), list):
            return data[key]
    return []


def _account_platform(acc: dict[str, Any]) -> str:
    for k in ("platform", "targetType", "type", "provider"):
        v = acc.get(k)
        if isinstance(v, str):
            return v.lower()
    return ""


def _account_id(acc: dict[str, Any]) -> str:
    for k in ("id", "accountId", "_id"):
        if acc.get(k) is not None:
            return str(acc[k])
    return ""


_ACCOUNT_ID_ENV = {
    "tiktok": "BLOTATO_TIKTOK_ACCOUNT_ID",
    "facebook": "BLOTATO_FACEBOOK_ACCOUNT_ID",
    "instagram": "BLOTATO_INSTAGRAM_ACCOUNT_ID",
}


def find_account_id(platform: str) -> Optional[str]:
    """Connected account id for a platform. Uses the .env override if set, else
    auto-detects when exactly one account of that platform is connected."""
    override = getattr(config, _ACCOUNT_ID_ENV.get(platform, ""), "")
    if override:
        return override
    matches = [a for a in list_accounts() if platform in _account_platform(a)]
    if len(matches) == 1:
        return _account_id(matches[0])
    return None


def find_tiktok_account_id() -> Optional[str]:
    return find_account_id("tiktok")


def upload_media(data: bytes, content_type: str) -> str:
    """Upload raw bytes (base64) to Blotato; return the hosted media URL."""
    b64 = base64.b64encode(data).decode("ascii")
    payload = {"url": f"data:{content_type};base64,{b64}"}
    with httpx.Client(timeout=300) as c:
        r = c.post(f"{BASE}/media", headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()["url"]


def upload_image(data: bytes) -> str:
    return upload_media(data, "image/jpeg")


def upload_video(data: bytes) -> str:
    return upload_media(data, "video/mp4")


# --- Target builders --------------------------------------------------------
def tiktok_target(cover_index: int = 0, title: str = "", draft: bool = True) -> dict[str, Any]:
    return {
        "targetType": "tiktok",
        "isDraft": draft,                  # draft -> no TikTok audit needed
        "privacyLevel": "SELF_ONLY",       # finalized when you publish
        "isAiGenerated": config.TIKTOK_LABEL_AI,
        "disabledComments": False,
        "disabledDuet": False,
        "disabledStitch": False,
        "isBrandedContent": False,
        "isYourBrand": False,
        "autoAddMusic": False,             # you add music manually
        "imageCoverIndex": cover_index,
        "title": title or "",
    }


def facebook_reel_target(page_id: str) -> dict[str, Any]:
    return {"targetType": "facebook", "pageId": str(page_id), "mediaType": "reel"}


def instagram_reel_target(share_to_feed: bool = True) -> dict[str, Any]:
    return {"targetType": "instagram", "mediaType": "reel", "shareToFeed": share_to_feed}


# --- Posting ----------------------------------------------------------------
def create_post(
    account_id: str,
    text: str,
    media_urls: list[str],
    target: dict[str, Any],
    poll: bool = True,
) -> dict[str, Any]:
    """Create a post on Blotato and (optionally) wait for delivery.

    Returns Blotato's response merged with the final submission status. Raises
    if the platform rejects the post.
    """
    if not account_id:
        raise RuntimeError("Missing account id for this platform.")
    if not media_urls:
        raise ValueError("No media to post.")

    payload = {
        "post": {
            "accountId": str(account_id),
            "content": {
                "text": text or "",
                "mediaUrls": media_urls,
                "platform": target["targetType"],
            },
            "target": target,
        }
    }
    with httpx.Client(timeout=120) as c:
        r = c.post(f"{BASE}/posts", headers=_headers(), json=payload)
        r.raise_for_status()
        resp = r.json()

    sub_id = resp.get("postSubmissionId")
    if poll and sub_id:
        final = _await_submission(sub_id)
        resp.update(final)
        if final.get("status") == "failed":
            raise RuntimeError(final.get("errorMessage", "post rejected by platform"))
    return resp


def post_tiktok_draft(
    image_bytes: list[bytes],
    text: str,
    account_id: Optional[str] = None,
    cover_index: int = 0,
    title: str = "",
) -> dict[str, Any]:
    """Upload slides and create a TikTok DRAFT photo post."""
    account_id = account_id or find_account_id("tiktok")
    if not account_id:
        raise RuntimeError(
            "No TikTok account id. Connect TikTok in Blotato and set "
            "BLOTATO_TIKTOK_ACCOUNT_ID in .env (or connect exactly one)."
        )
    media_urls = [upload_image(b) for b in image_bytes]
    return create_post(account_id, text, media_urls,
                       tiktok_target(cover_index=cover_index, title=title, draft=True))


def get_submission(submission_id: str) -> dict[str, Any]:
    """Status of a submitted post: in-progress | published | failed."""
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{BASE}/posts/{submission_id}", headers=_headers())
        r.raise_for_status()
        return r.json()


def _await_submission(submission_id: str, tries: int = 12, delay: float = 3.0) -> dict[str, Any]:
    """Poll until the submission is published or failed (or we give up)."""
    last: dict[str, Any] = {}
    for _ in range(tries):
        last = get_submission(submission_id)
        if last.get("status") in ("published", "failed"):
            return last
        time.sleep(delay)
    return last  # still in-progress; report whatever we have
