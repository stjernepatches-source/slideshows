"""TikTok Login Kit (OAuth) + Content Posting API (photo mode).

Honest scope note
-----------------
TikTok only lets *audited* apps DIRECT_POST public content. Until your app
passes TikTok's audit it runs in sandbox and can only post privately / as a
draft. This module supports both:

  - draft  (post_mode = MEDIA_UPLOAD)  -> lands in your TikTok inbox/drafts;
            you tap publish in the app. Works for unaudited/sandbox apps.
  - direct (post_mode = DIRECT_POST)   -> goes live; requires an audited app.

Photo posting pulls images from public URLs (source = PULL_FROM_URL). That
means the slide image URLs must be reachable by TikTok's servers AND served
from a domain you've verified in the TikTok developer portal (URL prefix
verification). On localhost that means putting a tunnel (e.g. cloudflared /
ngrok) in front and verifying that domain. The functions here take the public
base URL to build those image links.

Tokens are cached in data/tiktok_token.json.
"""
from __future__ import annotations

import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from . import config
from .storage import read_json, write_json

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
CONTENT_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/content/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"

# user.info.basic for identity; video.upload for draft; video.publish for direct.
SCOPES = "user.info.basic,video.upload,video.publish"


# --- OAuth ------------------------------------------------------------------
def is_configured() -> bool:
    return bool(config.TIKTOK_CLIENT_KEY and config.TIKTOK_CLIENT_SECRET)


def build_auth_url() -> tuple[str, str]:
    """Return (authorize_url, csrf_state). Store state and check it on callback."""
    state = secrets.token_urlsafe(16)
    params = {
        "client_key": config.TIKTOK_CLIENT_KEY,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": config.TIKTOK_REDIRECT_URI,
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}", state


def exchange_code(code: str) -> dict[str, Any]:
    data = {
        "client_key": config.TIKTOK_CLIENT_KEY,
        "client_secret": config.TIKTOK_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": config.TIKTOK_REDIRECT_URI,
    }
    with httpx.Client(timeout=30) as client:
        r = client.post(
            TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        token = r.json()
    token["obtained_at"] = int(time.time())
    write_json(config.TIKTOK_TOKEN_FILE, token)
    return token


def _refresh(token: dict[str, Any]) -> dict[str, Any]:
    data = {
        "client_key": config.TIKTOK_CLIENT_KEY,
        "client_secret": config.TIKTOK_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": token["refresh_token"],
    }
    with httpx.Client(timeout=30) as client:
        r = client.post(
            TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        new = r.json()
    new["obtained_at"] = int(time.time())
    write_json(config.TIKTOK_TOKEN_FILE, new)
    return new


def get_access_token() -> str:
    token = read_json(config.TIKTOK_TOKEN_FILE, default=None)
    if not token:
        raise RuntimeError("Not connected to TikTok. Visit /tiktok/login first.")
    expires_in = token.get("expires_in", 0)
    if time.time() - token.get("obtained_at", 0) > expires_in - 60:
        token = _refresh(token)
    return token["access_token"]


def is_connected() -> bool:
    return read_json(config.TIKTOK_TOKEN_FILE, default=None) is not None


# --- Posting ----------------------------------------------------------------
def post_photos(
    image_urls: list[str],
    title: str,
    description: str,
    direct: bool = False,
    cover_index: int = 0,
) -> dict[str, Any]:
    """Initialize a photo post. Returns TikTok's init response (incl. publish_id).

    image_urls must be public URLs on a TikTok-verified domain.
    direct=False -> draft (MEDIA_UPLOAD); direct=True -> live (DIRECT_POST, audited apps).
    """
    if not image_urls:
        raise ValueError("No image URLs to post.")
    access_token = get_access_token()

    post_info: dict[str, Any] = {"title": title or "", "description": description or ""}
    if direct:
        # Direct posts must declare privacy + interaction settings.
        post_info.update(
            {
                "privacy_level": "SELF_ONLY",  # safest default; change as needed
                "disable_comment": False,
                "auto_add_music": True,
            }
        )

    payload = {
        "post_mode": "DIRECT_POST" if direct else "MEDIA_UPLOAD",
        "media_type": "PHOTO",
        "post_info": post_info,
        "source_info": {
            "source": "PULL_FROM_URL",
            "photo_cover_index": cover_index,
            "photo_images": image_urls,
        },
    }

    with httpx.Client(timeout=60) as client:
        r = client.post(
            CONTENT_INIT_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
        )
        r.raise_for_status()
        return r.json()


def fetch_status(publish_id: str) -> dict[str, Any]:
    access_token = get_access_token()
    with httpx.Client(timeout=30) as client:
        r = client.post(
            STATUS_URL,
            json={"publish_id": publish_id},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
        )
        r.raise_for_status()
        return r.json()
