"""Central configuration and on-disk paths.

All settings come from environment variables (loaded from a local .env via
python-dotenv). Nothing here requires keys to import, so the app boots even
before you've filled in .env — you'll just get a clear error when you try an
action that needs a missing key.
"""
from __future__ import annotations

from typing import Optional

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (one level up from this file's package).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- API keys ---------------------------------------------------------------
FAL_KEY = os.getenv("FAL_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# --- Model selection --------------------------------------------------------
# Friendly name -> fal endpoint id. Seedream is the default because it does not
# embed Google's SynthID invisible watermark (better for "don't get flagged").
IMAGE_MODELS = {
    "seedream": "fal-ai/bytedance/seedream/v4/edit",
    "nano": "fal-ai/nano-banana/edit",
    "nano-pro": "fal-ai/nano-banana-pro/edit",
}
# Text-to-image (no reference image) variants. The "/edit" endpoints above
# REQUIRE an input image, so the no-reference path (e.g. generating a brand-new
# character reference sheet from a description) must use these instead.
IMAGE_MODELS_T2I = {
    "seedream": "fal-ai/bytedance/seedream/v4/text-to-image",
    "nano": "fal-ai/nano-banana",
    "nano-pro": "fal-ai/nano-banana-pro",
}
# Models that embed Google's SynthID watermark (cannot be reliably stripped).
SYNTHID_MODELS = {"nano", "nano-pro"}

IMAGE_MODEL = os.getenv("IMAGE_MODEL", "seedream").strip().lower()
SCENE_MODEL = os.getenv("SCENE_MODEL", "claude-sonnet-4-6")
ASPECT_RATIO = os.getenv("ASPECT_RATIO", "9:16")

# --- Look & feel ------------------------------------------------------------
# Force-appended to EVERY image prompt so slides look like a real phone camera
# roll instead of glossy AI art. This is the single biggest lever on "does it
# look AI-generated." Override the whole thing via STYLE_PROMPT in .env.
DEFAULT_STYLE_PROMPT = (
    "A candid, casual amateur snapshot — the kind of ordinary everyday photo a "
    "normal person takes, not a professional shot. Flat, ordinary lighting "
    "(overcast, indoor, or plain daylight); NOT cinematic, no dramatic shadows, "
    "no moody color grading, no golden-hour glow. Authentic and a little "
    "imperfect: subtle lens smudge, mild grain and sensor noise, slightly soft "
    "or imperfect focus, a touch of motion blur, real true-to-life skin with "
    "pores, blemishes and stray hairs. Slightly awkward, unposed, off-center "
    "framing. Plain, believable realism. Absolutely NOT: studio lighting, "
    "professional retouching, glamour, HDR, glossy magazine look, polished AI "
    "rendering, illustration, or 3D render. "
    "VERY IMPORTANT: this is a normal full-frame photograph. Render ONLY the "
    "scene itself, filling the entire frame edge to edge. Do NOT draw any "
    "phone, smartphone, screen, monitor, device, frame, border, bezel, rounded "
    "corners, camera notch, status bar, clock, battery or signal icons, "
    "screenshot, or any app/camera/phone interface of any kind."
)
STYLE_PROMPT = os.getenv("STYLE_PROMPT", DEFAULT_STYLE_PROMPT)

# --- On-image caption text --------------------------------------------------
# TikTok-style burned-in text: bold white fill + black outline, kept in the
# safe zone (clear of TikTok's UI). Fractions are of the image width/height.
TIKTOK_FONT = os.getenv("TIKTOK_FONT", "/System/Library/Fonts/Supplemental/Arial Bold.ttf")
TEXT_SIZE_FRAC = float(os.getenv("TEXT_SIZE_FRAC", "0.058"))    # ~big TikTok text
TEXT_STROKE_FRAC = float(os.getenv("TEXT_STROKE_FRAC", "0.12"))  # outline thickness
TEXT_SAFE_SIDE = float(os.getenv("TEXT_SAFE_SIDE", "0.07"))     # L/R margin
TEXT_SAFE_TOP = float(os.getenv("TEXT_SAFE_TOP", "0.12"))       # text starts here
TEXT_SAFE_BOTTOM = float(os.getenv("TEXT_SAFE_BOTTOM", "0.34"))  # reserved for UI

# --- Brand / CTA ------------------------------------------------------------
# The post caption always opens with a casual, non-salesy nudge to this site.
SITE_URL = os.getenv("SITE_URL", "nordiva.ai")

# --- Blotato (posts to TikTok as drafts; no TikTok app audit needed) ---------
BLOTATO_API_KEY = os.getenv("BLOTATO_API_KEY", "")
BLOTATO_TIKTOK_ACCOUNT_ID = os.getenv("BLOTATO_TIKTOK_ACCOUNT_ID", "")
# Whether to declare the post as AI-generated to TikTok. Default False to match
# the "don't get auto-flagged" goal.
TIKTOK_LABEL_AI = os.getenv("TIKTOK_LABEL_AI", "false").strip().lower() == "true"

# --- TikTok (legacy direct Content Posting API — optional) ------------------
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "http://localhost:8000/tiktok/callback")

# --- Server -----------------------------------------------------------------
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# --- Storage layout ---------------------------------------------------------
DATA_DIR = PROJECT_ROOT / "data"
CAST_DIR = DATA_DIR / "cast"
SLIDESHOWS_DIR = DATA_DIR / "slideshows"
CAST_INDEX = CAST_DIR / "cast.json"
TIKTOK_TOKEN_FILE = DATA_DIR / "tiktok_token.json"


def ensure_dirs() -> None:
    """Create the runtime data directories if they don't exist yet."""
    CAST_DIR.mkdir(parents=True, exist_ok=True)
    SLIDESHOWS_DIR.mkdir(parents=True, exist_ok=True)


def resolve_image_endpoint(model: Optional[str] = None) -> str:
    """Map a friendly model name to its fal edit endpoint id (needs references)."""
    key = (model or IMAGE_MODEL).strip().lower()
    if key not in IMAGE_MODELS:
        raise ValueError(
            f"Unknown IMAGE_MODEL '{key}'. Valid options: {', '.join(IMAGE_MODELS)}"
        )
    return IMAGE_MODELS[key]


def resolve_t2i_endpoint(model: Optional[str] = None) -> str:
    """Map a friendly model name to its fal text-to-image endpoint id."""
    key = (model or IMAGE_MODEL).strip().lower()
    if key not in IMAGE_MODELS_T2I:
        raise ValueError(
            f"Unknown IMAGE_MODEL '{key}'. Valid options: {', '.join(IMAGE_MODELS_T2I)}"
        )
    return IMAGE_MODELS_T2I[key]


def model_has_synthid(model: Optional[str] = None) -> bool:
    return (model or IMAGE_MODEL).strip().lower() in SYNTHID_MODELS
