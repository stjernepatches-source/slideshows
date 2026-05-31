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
# Models that embed Google's SynthID watermark (cannot be reliably stripped).
SYNTHID_MODELS = {"nano", "nano-pro"}

IMAGE_MODEL = os.getenv("IMAGE_MODEL", "seedream").strip().lower()
SCENE_MODEL = os.getenv("SCENE_MODEL", "claude-sonnet-4-6")
ASPECT_RATIO = os.getenv("ASPECT_RATIO", "9:16")

# --- TikTok -----------------------------------------------------------------
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
    """Map a friendly model name to its fal endpoint id."""
    key = (model or IMAGE_MODEL).strip().lower()
    if key not in IMAGE_MODELS:
        raise ValueError(
            f"Unknown IMAGE_MODEL '{key}'. Valid options: {', '.join(IMAGE_MODELS)}"
        )
    return IMAGE_MODELS[key]


def model_has_synthid(model: Optional[str] = None) -> bool:
    return (model or IMAGE_MODEL).strip().lower() in SYNTHID_MODELS
