"""FastAPI app: serves the local web UI and the JSON API behind it.

Run with:  ./run.sh   (or: uvicorn app.main:app --reload)
Then open: http://127.0.0.1:8000
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import characters, config, metadata, slideshow, tiktok

config.ensure_dirs()

app = FastAPI(title="TikTok Slideshow Auto-Generator")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# CSRF state for the TikTok OAuth round-trip (single-user local app).
_oauth_state: dict[str, str] = {}


# --- Pages ------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return {
        "image_model": config.IMAGE_MODEL,
        "models": list(config.IMAGE_MODELS),
        "model_has_synthid": config.model_has_synthid(),
        "aspect_ratio": config.ASPECT_RATIO,
        "exiftool": metadata.exiftool_available(),
        "anthropic_ready": bool(config.ANTHROPIC_API_KEY),
        "fal_ready": bool(config.FAL_KEY),
        "tiktok_configured": tiktok.is_configured(),
        "tiktok_connected": tiktok.is_connected(),
    }


# --- Cast library -----------------------------------------------------------
class CastCreate(BaseModel):
    name: str
    description: str = ""


class RefGenerate(BaseModel):
    prompt: Optional[str] = None


@app.get("/api/cast")
def api_list_cast() -> list[dict[str, Any]]:
    return characters.list_characters()


@app.post("/api/cast")
def api_create_cast(body: CastCreate) -> dict[str, Any]:
    if not body.name.strip():
        raise HTTPException(400, "Character needs a name.")
    return characters.create_character(body.name, body.description)


@app.post("/api/cast/{char_id}/upload")
async def api_upload_ref(char_id: str, file: UploadFile) -> dict[str, Any]:
    if characters.get_character(char_id) is None:
        raise HTTPException(404, "No such character.")
    data = await file.read()
    return characters.add_reference_from_bytes(char_id, data, file.filename or "ref.png")


@app.post("/api/cast/{char_id}/generate")
def api_generate_ref(char_id: str, body: RefGenerate) -> dict[str, Any]:
    if characters.get_character(char_id) is None:
        raise HTTPException(404, "No such character.")
    try:
        return characters.generate_reference(char_id, body.prompt)
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/cast/{char_id}")
def api_delete_cast(char_id: str) -> dict[str, str]:
    characters.delete_character(char_id)
    return {"status": "deleted"}


@app.get("/api/cast/{char_id}/image/{filename}")
def api_cast_image(char_id: str, filename: str) -> FileResponse:
    path = config.CAST_DIR / char_id / filename
    if not path.exists():
        raise HTTPException(404, "Not found.")
    return FileResponse(path)


# --- Slideshows -------------------------------------------------------------
class SlideshowCreate(BaseModel):
    title: str = ""
    story: str
    character_ids: list[str] = []
    num_slides: int = 6
    model: Optional[str] = None
    aspect: Optional[str] = None


class TextUpdate(BaseModel):
    post_caption: Optional[str] = None
    hashtags: Optional[list[str]] = None
    slide_captions: Optional[dict[int, str]] = None


class PostRequest(BaseModel):
    public_base_url: Optional[str] = None  # e.g. https://abc.trycloudflare.com
    direct: bool = False


@app.get("/api/slideshows")
def api_list_shows() -> list[dict[str, Any]]:
    return slideshow.list_slideshows()


@app.post("/api/slideshows")
def api_create_show(body: SlideshowCreate) -> dict[str, Any]:
    if not body.story.strip():
        raise HTTPException(400, "Paste a story first.")
    try:
        return slideshow.create_slideshow(
            title=body.title,
            story=body.story,
            character_ids=body.character_ids,
            num_slides=body.num_slides,
            model=body.model,
            aspect=body.aspect,
        )
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.get("/api/slideshows/{show_id}")
def api_get_show(show_id: str) -> dict[str, Any]:
    show = slideshow.get_slideshow(show_id)
    if show is None:
        raise HTTPException(404, "No such slideshow.")
    return show


def _run_generation(show_id: str) -> None:
    try:
        slideshow.generate_all(show_id)
    except Exception as e:  # surface the failure in the record
        show = slideshow.get_slideshow(show_id)
        if show is not None:
            show["status"] = "error"
            show["error"] = str(e)
            slideshow._save(show)  # noqa: SLF001 (internal helper, single module)


@app.post("/api/slideshows/{show_id}/generate")
def api_generate_show(show_id: str) -> dict[str, Any]:
    show = slideshow.get_slideshow(show_id)
    if show is None:
        raise HTTPException(404, "No such slideshow.")
    # Run in a background thread; the UI polls GET .../{id} for progress.
    threading.Thread(target=_run_generation, args=(show_id,), daemon=True).start()
    return {"status": "generating"}


@app.post("/api/slideshows/{show_id}/slides/{index}/regenerate")
def api_regen_slide(show_id: str, index: int) -> dict[str, Any]:
    try:
        return slideshow.generate_slide(show_id, index)
    except (KeyError, IndexError):
        raise HTTPException(404, "No such slide.")
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.put("/api/slideshows/{show_id}/text")
def api_update_text(show_id: str, body: TextUpdate) -> dict[str, Any]:
    try:
        return slideshow.update_text(
            show_id,
            post_caption=body.post_caption,
            hashtags=body.hashtags,
            slide_captions=body.slide_captions,
        )
    except KeyError:
        raise HTTPException(404, "No such slideshow.")


@app.get("/api/slideshows/{show_id}/slides/{index}/image")
def api_slide_image(show_id: str, index: int) -> FileResponse:
    path = slideshow.slide_file(show_id, index)
    if path is None:
        raise HTTPException(404, "Slide not generated yet.")
    return FileResponse(path)


# Public, stable image URL used when TikTok pulls images (PULL_FROM_URL).
@app.get("/public/{show_id}/{index}.jpg")
def public_slide_image(show_id: str, index: int) -> FileResponse:
    path = slideshow.slide_file(show_id, index)
    if path is None:
        raise HTTPException(404, "Slide not generated yet.")
    return FileResponse(path, media_type="image/jpeg")


# --- TikTok -----------------------------------------------------------------
@app.get("/tiktok/login")
def tiktok_login() -> RedirectResponse:
    if not tiktok.is_configured():
        raise HTTPException(400, "Set TIKTOK_CLIENT_KEY / SECRET in .env first.")
    url, state = tiktok.build_auth_url()
    _oauth_state["state"] = state
    return RedirectResponse(url)


@app.get("/tiktok/callback", response_class=HTMLResponse)
def tiktok_callback(request: Request) -> HTMLResponse:
    params = request.query_params
    if params.get("error"):
        return HTMLResponse(f"<h3>TikTok error: {params.get('error_description')}</h3>")
    if params.get("state") != _oauth_state.get("state"):
        raise HTTPException(400, "OAuth state mismatch.")
    code = params.get("code")
    if not code:
        raise HTTPException(400, "No code returned.")
    tiktok.exchange_code(code)
    return HTMLResponse(
        "<h3>TikTok connected ✅</h3><p>You can close this tab and return to the app.</p>"
        "<script>setTimeout(()=>{window.location='/'},1500)</script>"
    )


@app.post("/api/slideshows/{show_id}/post")
def api_post_show(show_id: str, body: PostRequest) -> dict[str, Any]:
    show = slideshow.get_slideshow(show_id)
    if show is None:
        raise HTTPException(404, "No such slideshow.")
    files = slideshow.ordered_slide_files(show_id)
    if not files:
        raise HTTPException(400, "Generate the slides before posting.")
    if not tiktok.is_connected():
        raise HTTPException(400, "Connect TikTok first (Settings → Connect TikTok).")

    base = (body.public_base_url or "").rstrip("/")
    if not base:
        raise HTTPException(
            400,
            "TikTok pulls images from public URLs. Provide a public base URL "
            "(e.g. a cloudflared/ngrok tunnel pointed at this app) verified in "
            "your TikTok developer portal.",
        )
    image_urls = [
        f"{base}/public/{show_id}/{i}.jpg" for i in range(len(show["slides"])) if show["slides"][i].get("file")
    ]

    caption = show.get("post_caption", "")
    tags = " ".join(f"#{t.lstrip('#')}" for t in show.get("hashtags", []))
    description = (caption + ("\n\n" + tags if tags else "")).strip()

    try:
        resp = tiktok.post_photos(
            image_urls=image_urls,
            title=show.get("title", ""),
            description=description,
            direct=body.direct,
        )
    except Exception as e:
        raise HTTPException(400, f"TikTok post failed: {e}")

    info = {"direct": body.direct, "response": resp}
    slideshow.mark_posted(show_id, info)
    return info
