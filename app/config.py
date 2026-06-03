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
# Friendly name -> fal endpoint id. Default is nano-banana-pro: its faces/eyes
# are far more photorealistic than Seedream's (which cooked eyes). Trade-off:
# nano models embed Google's SynthID invisible watermark (can't be stripped).
# Switch IMAGE_MODEL back to "seedream" in .env if avoiding SynthID matters more.
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

IMAGE_MODEL = os.getenv("IMAGE_MODEL", "nano-pro").strip().lower()
SCENE_MODEL = os.getenv("SCENE_MODEL", "claude-sonnet-4-6")
ASPECT_RATIO = os.getenv("ASPECT_RATIO", "9:16")

# --- Look & feel ------------------------------------------------------------
# Force-appended to EVERY image prompt so slides look like a real phone camera
# roll instead of glossy AI art. This is the single biggest lever on "does it
# look AI-generated." Override the whole thing via STYLE_PROMPT in .env.
DEFAULT_STYLE_PROMPT = (
    "ABSOLUTE RULES (highest priority): (1) Render NO text of any kind — no "
    "words, letters, captions, subtitles, quotes, watermarks, logos, signs, "
    "numbers, or UI — anywhere in the image. (2) Eyes must be natural, real "
    "human eyes with true skin-toned lids and normal iris color and realistic "
    "catchlights — NEVER glassy, doll-like, airbrushed, plasticky, glowing, "
    "neon, or oversaturated. "
    "This must look like a RANDOM photo pulled from a normal person's phone — "
    "NOT a photoshoot, NOT a stock photo, NOT a content-creator shot. If it looks "
    "nice or intentional, it's wrong. Boring, ordinary, sometimes unflattering. "
    "Casual phone angles: mirror selfie, arm's-length selfie, or clearly taken by "
    "a friend; often a slightly crooked horizon or off-center, badly-cropped "
    "framing. Ugly ordinary lighting: flat overhead room light, dim indoor light, "
    "or harsh on-camera FLASH with hard shadows and shine on skin — NOT soft, "
    "NOT flattering, NOT golden hour, NOT cinematic. Imperfect exposure (a bit too "
    "dark or slightly blown-out), mild grain and sensor noise, smartphone "
    "over-sharpening, subtle motion blur, a smudged lens. Real lived-in cluttered "
    "backgrounds (mess, random objects). Real true-to-life skin with pores, "
    "blemishes, oil and stray hairs. Absolutely NOT: studio or soft window "
    "lighting, shallow-depth bokeh, professional retouching, glamour, HDR, glossy "
    "magazine/editorial look, polished AI rendering, illustration, or 3D render. "
    "VERY IMPORTANT: this is a normal full-frame photograph. Render ONLY the "
    "scene itself, filling the entire frame edge to edge. Do NOT draw any "
    "phone, smartphone, screen, monitor, device, frame, border, bezel, rounded "
    "corners, camera notch, status bar, clock, battery or signal icons, "
    "screenshot, or any app/camera/phone interface of any kind. "
    "Do NOT render ANY text, letters, words, captions, subtitles, watermarks, "
    "logos, signs, or numbers anywhere in the image. "
    "Eyes must look natural and true-to-life — normal human iris color with "
    "realistic catchlights; NEVER glowing, oversaturated, neon, or unnaturally "
    "bright eyes."
)
STYLE_PROMPT = os.getenv("STYLE_PROMPT", DEFAULT_STYLE_PROMPT)

# --- Glow-up "before" state -------------------------------------------------
# Many stories are before/after glow-ups. We only have GOOD reference photos, so
# we generate ONE controlled, identity-locked "before" portrait per glow-up
# subject (a full-physical down-glow) and reuse it for every pre-glow-up slide —
# instead of letting each slide improvise the downgrade (which yields a different,
# grotesquely fat/ugly person every time). Tune the severity here.
GLOWDOWN_PROMPT = os.getenv(
    "GLOWDOWN_PROMPT",
    "Transform THIS EXACT person into a believable 'before a glow-up' version of "
    "themselves — an unflattering, ordinary candid phone snapshot. Make them "
    "noticeably heavier and softer: fuller rounder face, heavier cheeks, a soft "
    "double chin, a fuller body. Dull uneven skin with mild blemishes and "
    "redness, tired puffy under-eyes, unkempt greasy unstyled hair, no makeup, "
    "thicker unshaped brows, a frumpy oversized ill-fitting outfit, flat "
    "unflattering overhead fluorescent light. CRUCIAL: it must still be "
    "UNMISTAKABLY THE SAME PERSON — keep the same identity, same eye color, same "
    "underlying facial structure and same hair color; do NOT change their "
    "ethnicity, age, or gender. Heavier and less groomed, but a real believable "
    "person, NOT a grotesque caricature.",
)

# --- On-image caption text --------------------------------------------------
# TikTok-style burned-in text: bold white fill + black outline, kept in the
# safe zone (clear of TikTok's UI). Fractions are of the image width/height.
TIKTOK_FONT = os.getenv("TIKTOK_FONT", "/System/Library/Fonts/Supplemental/Arial Bold.ttf")
TEXT_SIZE_FRAC = float(os.getenv("TEXT_SIZE_FRAC", "0.045"))    # caption size (kept modest so it doesn't cover the subject)
TEXT_STROKE_FRAC = float(os.getenv("TEXT_STROKE_FRAC", "0.06"))  # outline thickness (TikTok-default thin)
TEXT_SAFE_SIDE = float(os.getenv("TEXT_SAFE_SIDE", "0.07"))     # L/R margin
TEXT_SAFE_TOP = float(os.getenv("TEXT_SAFE_TOP", "0.12"))       # text starts here
TEXT_SAFE_BOTTOM = float(os.getenv("TEXT_SAFE_BOTTOM", "0.34"))  # reserved for UI
TEXT_WAIT_TOP = float(os.getenv("TEXT_WAIT_TOP", "0.74"))       # "Wait for it" band
# Small brand handle burned low on each (non-CTA) slide + reel frame.
BRAND_TAG = os.getenv("BRAND_TAG", os.getenv("SITE_URL", "nordiva.ai"))
TEXT_BRAND_TOP = float(os.getenv("TEXT_BRAND_TOP", "0.88"))     # bottom-third band
TEXT_BRAND_SIZE_FRAC = float(os.getenv("TEXT_BRAND_SIZE_FRAC", "0.026"))  # small

# --- Reel video (Instagram / Facebook) --------------------------------------
REEL_SECONDS_PER_SLIDE = float(os.getenv("REEL_SECONDS_PER_SLIDE", "3"))
REEL_WIDTH = int(os.getenv("REEL_WIDTH", "1080"))
REEL_HEIGHT = int(os.getenv("REEL_HEIGHT", "1920"))
# A "Wait for it" hook on the first slide so the reel doesn't look frozen.
REEL_WAIT_ENABLED = os.getenv("REEL_WAIT_ENABLED", "true").strip().lower() == "true"
REEL_WAIT_TEXT = os.getenv("REEL_WAIT_TEXT", "Wait for it")

# --- Brand / CTA ------------------------------------------------------------
# The post caption always opens with a casual, non-salesy nudge to this site.
SITE_URL = os.getenv("SITE_URL", "nordiva.ai")

# The product the stories quietly build toward (the SMV comparison software).
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "Nordiva")
PRODUCT_PITCH = os.getenv(
    "PRODUCT_PITCH",
    "a tool that compares two people's dating-market value (SMV) side by side",
)
# The comparison/CTA slide is now rendered in code as the product's results
# screen (see app/cta.py): two faces, a dynamic SCORE /10 each, and trait tags
# generated per story by the scene writer. No static template needed.

# --- Fixed lead character (the SAME woman in every video) -------------------
LEAD_NAME = os.getenv("LEAD_NAME", "Jen")
LEAD_DESCRIPTION = os.getenv(
    "LEAD_DESCRIPTION",
    # Keep this minimal — her reference photos define the face (incl. eye color).
    # Over-describing features (esp. eyes) makes the model exaggerate them.
    "woman in her early-to-mid 30s, long dark brown hair, fair skin, soft "
    "natural features; minimal makeup, casual everyday outfits",
)
LEAD_REF_DIR = PROJECT_ROOT / "assets" / "protagonist"

# --- Story ideation (Grok / xAI) -------------------------------------------
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
GROK_MODEL = os.getenv("GROK_MODEL", "grok-4")

# --- Automation (hands-off scheduled runs) ----------------------------------
AUTO_PLATFORMS = [p.strip() for p in os.getenv(
    "AUTO_PLATFORMS", "tiktok,facebook,instagram").split(",") if p.strip()]
AUTO_NUM_SLIDES = int(os.getenv("AUTO_NUM_SLIDES", "7"))

# --- Blotato (posts to TikTok as drafts; no TikTok app audit needed) ---------
BLOTATO_API_KEY = os.getenv("BLOTATO_API_KEY", "")
BLOTATO_TIKTOK_ACCOUNT_ID = os.getenv("BLOTATO_TIKTOK_ACCOUNT_ID", "")
BLOTATO_FACEBOOK_ACCOUNT_ID = os.getenv("BLOTATO_FACEBOOK_ACCOUNT_ID", "")
BLOTATO_INSTAGRAM_ACCOUNT_ID = os.getenv("BLOTATO_INSTAGRAM_ACCOUNT_ID", "")
# Facebook Page id to post the reel to (the numeric FB Page id, not the Blotato
# account id). Get it from GET /v2/users/me/accounts/{id}/subaccounts.
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
# Instagram reels: also show the reel on the profile feed grid.
INSTAGRAM_SHARE_TO_FEED = os.getenv("INSTAGRAM_SHARE_TO_FEED", "true").strip().lower() == "true"
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


def lead_reference_paths() -> list[Path]:
    """The fixed lead woman's reference images (committed under assets/)."""
    if not LEAD_REF_DIR.exists():
        return []
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    return sorted(p for p in LEAD_REF_DIR.iterdir() if p.suffix.lower() in exts)


def lead_available() -> bool:
    return len(lead_reference_paths()) > 0


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
