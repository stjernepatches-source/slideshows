"""Stitch slides into a vertical reel video (for Instagram / Facebook reels).

Each slide is shown for a fixed number of seconds. The first slide carries a
"Wait for it" hook burned at the bottom so the reel doesn't read as a frozen
image when someone lands on it. Requires ffmpeg on PATH.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from . import config


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def build_reel(frames: list[bytes], out_path: Path, seconds_per: Optional[float] = None) -> Path:
    """Encode the given (already composited) JPEG frames into a 9:16 mp4 reel.

    Each frame shows for `seconds_per` seconds. Output is H.264 + a silent AAC
    track (platforms expect an audio stream), faststart for streaming.
    """
    if not frames:
        raise ValueError("No frames to stitch.")
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg is not installed. Run: brew install ffmpeg")

    seconds_per = seconds_per or config.REEL_SECONDS_PER_SLIDE
    w, h = config.REEL_WIDTH, config.REEL_HEIGHT
    tmp = Path(tempfile.mkdtemp(prefix="reel_"))
    try:
        paths: list[Path] = []
        lines: list[str] = []
        for i, data in enumerate(frames):
            p = tmp / f"f{i:03d}.jpg"
            p.write_bytes(data)
            paths.append(p)
            lines.append(f"file '{p}'")
            lines.append(f"duration {seconds_per}")
        # concat demuxer ignores the last entry's duration -> repeat last frame.
        lines.append(f"file '{paths[-1]}'")
        listfile = tmp / "list.txt"
        listfile.write_text("\n".join(lines), encoding="utf-8")

        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p"
        )
        total = len(frames) * seconds_per  # exact length (avoids concat last-frame overrun)
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(listfile),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(total),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(out_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError("ffmpeg failed:\n" + res.stderr[-800:])
        return out_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
