# 🎬 Slideshow Studio

Turn a story into a finished **TikTok photo slideshow** — with **consistent
characters** across every slide and **AI provenance metadata stripped** so the
post isn't auto-flagged as AI.

You paste a story → it auto-splits into scenes (Claude) → generates each slide
on **fal.ai** keyed to your reusable **cast** of characters → strips C2PA/EXIF
metadata → you review the slides + caption → one click sends it to TikTok.

Everything runs **locally** in your browser. No coding needed to use it.

---

## 1. Get your API keys

You need at least the first two to generate slideshows:

| Key | Where to get it | Used for |
|-----|-----------------|----------|
| `FAL_KEY` | https://fal.ai/dashboard/keys | generating the images |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys | splitting your story into scenes |
| `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` | https://developers.tiktok.com/ | posting to TikTok (optional) |

## 2. Run it

```bash
./run.sh
```

The first run creates a virtualenv, installs everything, and copies
`.env.example` → `.env`. **Open `.env`, paste your keys, save, then run
`./run.sh` again.** Then open <http://127.0.0.1:8000>.

> Optional: install `exiftool` (`apt install libimage-exiftool-perl` /
> `brew install exiftool`) for an extra metadata-stripping pass. Not required —
> the app re-encodes every image with Pillow, which already drops EXIF/C2PA.

## 3. Use it

1. **Cast tab** – add your recurring characters. For each one, either **upload**
   a reference photo or click **Generate ref** to make a character-sheet image
   from its description. These references are what keep the character looking the
   same on every slide.
2. **New Slideshow tab** – paste your story, pick how many slides, choose which
   cast members appear, and hit **Split into scenes**. Claude turns the story
   into per-slide image prompts.
3. **Review** – click **Generate all slides**. Watch them appear; **Regenerate**
   any you don't like. Edit the caption/hashtags. Every slide is automatically
   metadata-stripped and cropped to 9:16.
4. **Post** – connect TikTok in Settings, then **Approve & Post** (see caveats).

---

## How character consistency works

Each slide's prompt names which characters appear; the app uploads those
characters' reference images to fal and passes them as `image_urls` so the model
re-renders the *same* person in the new scene. More/clearer reference angles =
better consistency.

## About "not getting flagged as AI" (read this)

- **What we strip:** EXIF, XMP, and **C2PA Content Credentials** — the signed
  provenance block platforms read to auto-label content as AI. We drop it by
  re-encoding every image (Pillow) plus an optional `exiftool -all=` pass. ✅
- **What we can't strip:** Google's **SynthID**, an invisible pixel-level
  watermark baked into Gemini / Nano Banana images. It survives re-encoding and
  **cannot be reliably removed**. That's why the **default model is Seedream**
  (`fal-ai/bytedance/seedream/v4/edit`), which does **not** add SynthID. You can
  switch to Nano Banana in `.env` (`IMAGE_MODEL=nano`) for max consistency, but
  those images will carry SynthID.
- Defeating provenance signals may conflict with TikTok's policies — that's your
  call to make.

## About TikTok posting (read this too)

- Posting uses TikTok's **Content Posting API** (photo mode), which **pulls
  images from public URLs**. So the app must be reachable from the internet on a
  domain you've **verified** in the TikTok developer portal. Locally, run a
  tunnel (e.g. `cloudflared tunnel --url http://localhost:8000`) and paste the
  tunnel's HTTPS base URL into the **Public base URL** field on the Review page.
- **Unaudited apps can only post privately / as a draft.** Until your TikTok app
  passes audit, "Approve & Post" sends the slideshow to your **TikTok drafts**
  for a final tap-to-publish. Tick **Direct post** only once your app is audited.
- If you'd rather skip the API entirely: every generated slide is a normal JPG in
  `data/slideshows/<id>/slides/` — just AirDrop/transfer them and post manually.

## Configuration (`.env`)

| Var | Default | Notes |
|-----|---------|-------|
| `IMAGE_MODEL` | `seedream` | `seedream` (no SynthID), `nano`, `nano-pro` |
| `SCENE_MODEL` | `claude-sonnet-4-6` | Claude model for scene splitting |
| `ASPECT_RATIO` | `9:16` | TikTok vertical |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | server bind |

## Project layout

```
app/
  main.py        FastAPI routes + serves the UI + TikTok OAuth callback
  scenes.py      story -> scene prompts (Claude API, with prompt caching)
  characters.py  reusable cast library (CRUD + reference images)
  generate.py    fal.ai image generation (text-to-image + reference edit)
  metadata.py    strip C2PA/EXIF, normalize to 9:16
  slideshow.py   orchestration + on-disk slideshow records
  tiktok.py      OAuth + Content Posting API (photo mode)
  static/        the web UI (index.html, app.js, style.css)
data/            your cast + slideshows (git-ignored)
```
