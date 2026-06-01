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


def find_tiktok_account_id() -> Optional[str]:
    """Return the connected TikTok account id, if there's exactly a TikTok one."""
    if config.BLOTATO_TIKTOK_ACCOUNT_ID:
        return config.BLOTATO_TIKTOK_ACCOUNT_ID
    tiktoks = [a for a in list_accounts() if "tiktok" in _account_platform(a)]
    if len(tiktoks) == 1:
        return _account_id(tiktoks[0])
    return None


def upload_image(data: bytes, content_type: str = "image/jpeg") -> str:
    """Upload raw image bytes (base64) to Blotato; return the hosted URL."""
    b64 = base64.b64encode(data).decode("ascii")
    payload = {"url": f"data:{content_type};base64,{b64}"}
    with httpx.Client(timeout=120) as c:
        r = c.post(f"{BASE}/media", headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()["url"]


def post_tiktok_draft(
    image_bytes: list[bytes],
    text: str,
    account_id: Optional[str] = None,
    cover_index: int = 0,
    title: str = "",
) -> dict[str, Any]:
    """Upload slides and create a TikTok DRAFT photo post. Returns Blotato's
    response (incl. postSubmissionId). You finish/publish + add music in the app.
    """
    if not image_bytes:
        raise ValueError("No slides to post.")
    account_id = account_id or find_tiktok_account_id()
    if not account_id:
        raise RuntimeError(
            "No TikTok account id. Connect TikTok in Blotato and set "
            "BLOTATO_TIKTOK_ACCOUNT_ID in .env (or ensure exactly one TikTok "
            "account is connected so it can be auto-detected)."
        )

    media_urls = [upload_image(b) for b in image_bytes]

    payload = {
        "post": {
            "accountId": str(account_id),
            "content": {
                "text": text or "",
                "mediaUrls": media_urls,
                "platform": "tiktok",
            },
            "target": {
                "targetType": "tiktok",
                "isDraft": True,                 # draft -> no TikTok audit needed
                "privacyLevel": "SELF_ONLY",     # finalized when you publish
                "isAiGenerated": config.TIKTOK_LABEL_AI,
                "disabledComments": False,
                "disabledDuet": False,
                "disabledStitch": False,
                "isBrandedContent": False,
                "isYourBrand": False,
                "autoAddMusic": False,           # you add music manually
                "imageCoverIndex": cover_index,
                "title": title or "",
            },
        }
    }

    with httpx.Client(timeout=120) as c:
        r = c.post(f"{BASE}/posts", headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()
