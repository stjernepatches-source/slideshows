"""ICP registry — one targeted "engine" per TikTok account.

Each ICP (ideal customer profile) has its own audience (gender + age band), its
own fixed lead persona (reference photos under its lead_ref_dir), its own
narrative guidance for the story writer, and its own connected TikTok account.
The runner generates a story tailored to an ICP, renders it with that ICP's
lead, and posts to that ICP's account.

NOTE (assumption to confirm): "boy" ICPs use a MALE lead/protagonist and "girl"
ICPs a FEMALE one. Lead photos for each go in assets/leads/<id>/ (girls_25_40
reuses the existing assets/protagonist/ = Jen).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from . import config

# Each ICP: account_id is the Blotato account for that TikTok handle.
ICPS: list[dict[str, Any]] = [
    {
        "id": "boys_16_22", "label": "Boys 16-22", "account_id": "45072",
        "gender": "male", "age_min": 16, "age_max": 22,
        "lead_name": "Tyler", "lead_ref_dir": "assets/leads/boys_16_22",
        "lead_description": "guy 17-20, lean build, short modern haircut, casual hoodie/tee",
        "themes": "looksmaxxing, glow-up, gym beginnings, high-school/college "
                  "crushes, getting rejected then leveling up, rating his own SMV",
        "voice": "first-person teen guy, insecure-to-confident, a bit cocky",
        "slide_min": 2, "slide_max": 7,
    },
    {
        "id": "boys_20_30", "label": "Boys 20-30", "account_id": "45075",
        "gender": "male", "age_min": 20, "age_max": 30,
        "lead_name": "Jake", "lead_ref_dir": "assets/leads/boys_20_30",
        "lead_description": "guy mid-20s, athletic, stubble, casual streetwear",
        "themes": "dating-app struggles, getting ghosted, gym glow-up, comparing "
                  "himself to her ex, career+dating, becoming the prize",
        "voice": "first-person 20s guy, dry humor, self-improvement edge",
        "slide_min": 2, "slide_max": 8,
    },
    {
        "id": "boys_30_40", "label": "Boys 30-40", "account_id": "45074",
        "gender": "male", "age_min": 30, "age_max": 40,
        "lead_name": "Mark", "lead_ref_dir": "assets/leads/boys_30_40",
        "lead_description": "man early-mid 30s, well-groomed, light beard, simple casual",
        "themes": "dating after divorce, starting over, dad-bod-to-fit glow-up, "
                  "comparing to the ex's new guy, reclaiming confidence in his 30s",
        "voice": "first-person 30s man, grounded, a little jaded then hopeful",
        "slide_min": 2, "slide_max": 8,
    },
    {
        "id": "girls_16_25", "label": "Girls 16-25", "account_id": "45071",
        "gender": "female", "age_min": 16, "age_max": 25,
        "lead_name": "Mia", "lead_ref_dir": "assets/leads/girls_16_25",
        "lead_description": "girl 18-22, long hair, trendy casual outfits, natural makeup",
        "themes": "situationships, talking stages, crushes, glow-up, comparing "
                  "him vs the new guy, college dating, soft-launch drama",
        "voice": "first-person Gen-Z girl, playful, petty, relatable",
        "slide_min": 2, "slide_max": 8,
    },
    {
        "id": "girls_25_40", "label": "Girls 25-40", "account_id": "44909",
        "gender": "female", "age_min": 25, "age_max": 40,
        "lead_name": config.LEAD_NAME, "lead_ref_dir": "assets/protagonist",
        "lead_description": config.LEAD_DESCRIPTION,
        "themes": "relationship drama, cheating, closure, glow-up after a breakup, "
                  "comparing the ex vs the new man",
        "voice": "first-person woman 30s, petty-then-empowered",
        "slide_min": 2, "slide_max": 8,
    },
]

_BY_ID = {i["id"]: i for i in ICPS}


def all_icps() -> list[dict[str, Any]]:
    return ICPS


def get_icp(icp_id: str) -> Optional[dict[str, Any]]:
    return _BY_ID.get(icp_id)


def lead_reference_paths(icp: dict[str, Any]) -> list[Path]:
    d = config.PROJECT_ROOT / icp["lead_ref_dir"]
    if not d.exists():
        return []
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    return sorted(p for p in d.iterdir() if p.suffix.lower() in exts)


def lead_available(icp: dict[str, Any]) -> bool:
    return len(lead_reference_paths(icp)) > 0
