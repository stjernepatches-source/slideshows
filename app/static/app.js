// Minimal vanilla-JS frontend for the slideshow studio.
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

// --- view switching ---------------------------------------------------------
function show(view) {
  $$(".view").forEach((v) => v.classList.remove("active"));
  $$("nav button").forEach((b) => b.classList.remove("active"));
  $("#view-" + view).classList.add("active");
  const btn = document.querySelector(`nav button[data-view="${view}"]`);
  if (btn) btn.classList.add("active");
  if (view === "cast") loadCast();
  if (view === "library") loadShows();
  if (view === "create") loadCreateForm();
  if (view === "settings") loadStatus();
}
$$("nav button").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));

// --- settings / status ------------------------------------------------------
let CONFIG = {};
async function loadStatus() {
  CONFIG = await api("/api/config");
  const yes = (b) => (b ? '<span class="ok">✓</span>' : '<span class="warn">✗</span>');
  $("#status-box").innerHTML = `
    <p>Image model: <b>${CONFIG.image_model}</b> ${
      CONFIG.model_has_synthid
        ? '<span class="warn">(adds SynthID — cannot be stripped)</span>'
        : '<span class="ok">(no SynthID)</span>'
    }</p>
    <p>fal.ai key: ${yes(CONFIG.fal_ready)} &nbsp; Claude key: ${yes(CONFIG.anthropic_ready)}</p>
    <p>exiftool installed: ${yes(CONFIG.exiftool)} ${
      CONFIG.exiftool ? "" : '<span class="hint">(optional; Pillow re-encode still strips metadata)</span>'
    }</p>
    <p>Site (caption CTA): <b>${CONFIG.site_url || "—"}</b></p>
    <p>Posting via Blotato: ${yes(CONFIG.blotato_configured)} ${
      CONFIG.blotato_configured ? '<span class="hint">(posts as TikTok drafts)</span>' : '<span class="hint">(set BLOTATO_API_KEY in .env)</span>'
    }</p>
    <p>Declare posts as AI to TikTok: ${CONFIG.label_ai ? '<span class="warn">yes</span>' : '<span class="ok">no</span>'}</p>`;
}

// --- create -----------------------------------------------------------------
async function loadCreateForm() {
  if (!CONFIG.models) CONFIG = await api("/api/config");
  $("#c-model").innerHTML = CONFIG.models
    .map((m) => `<option ${m === CONFIG.image_model ? "selected" : ""}>${m}</option>`)
    .join("");
  const cast = await api("/api/cast");
  $("#c-cast").innerHTML = cast.length
    ? cast.map((c) => `<label><input type="checkbox" value="${c.id}"> ${c.name}</label>`).join("")
    : '<span class="hint">No characters yet — add some in the Cast tab.</span>';
}

$("#c-go").addEventListener("click", async () => {
  const story = $("#c-story").value.trim();
  if (!story) return ($("#c-hint").textContent = "Paste a story first.");
  $("#c-hint").textContent = "Splitting story into scenes…";
  $("#c-go").disabled = true;
  try {
    const body = {
      title: $("#c-title").value,
      story,
      num_slides: parseInt($("#c-slides").value, 10),
      model: $("#c-model").value,
      character_ids: $$("#c-cast input:checked").map((i) => i.value),
    };
    const showData = await api("/api/slideshows", { method: "POST", body: JSON.stringify(body) });
    openReview(showData.id);
  } catch (e) {
    $("#c-hint").textContent = "Error: " + e.message;
  } finally {
    $("#c-go").disabled = false;
  }
});

// --- library ----------------------------------------------------------------
async function loadShows() {
  const shows = await api("/api/slideshows");
  $("#show-list").innerHTML = shows.length
    ? shows
        .map(
          (s) => `<div class="show-card" data-id="${s.id}">
            <b>${s.title}</b>
            <p><span class="badge ${s.status}">${s.status}</span> · ${s.slides.length} slides</p>
          </div>`
        )
        .join("")
    : '<p class="hint">No slideshows yet.</p>';
  $$(".show-card").forEach((c) => c.addEventListener("click", () => openReview(c.dataset.id)));
}

// --- review -----------------------------------------------------------------
let CURRENT = null;
let pollTimer = null;

$("#r-back").addEventListener("click", () => { stopPoll(); show("library"); });

function stopPoll() { if (pollTimer) clearInterval(pollTimer); pollTimer = null; }

async function openReview(id) {
  stopPoll();
  CURRENT = id;
  show("review");
  await renderReview();
}

async function renderReview() {
  const s = await api("/api/slideshows/" + CURRENT);
  $("#r-title").textContent = s.title;
  $("#r-status").innerHTML = `<span class="badge ${s.status}">${s.status}</span>` +
    (s.error ? ` <span class="warn">${s.error}</span>` : "");
  $("#r-caption").value = s.post_caption || "";
  $("#r-hashtags").value = (s.hashtags || []).join(" ");

  const done = s.slides.filter((sl) => sl.file).length;
  $("#r-progress").textContent = `${done}/${s.slides.length} slides generated`;

  $("#r-slides").innerHTML = s.slides
    .map((sl, i) => {
      const img = sl.file
        ? `<img src="/api/slideshows/${CURRENT}/slides/${i}/image?t=${Date.now()}">`
        : `<div style="aspect-ratio:9/16;display:flex;align-items:center;justify-content:center;color:#666">slide ${i + 1}</div>`;
      return `<div class="slide">${img}
        <div class="body">
          <div class="prompt">${sl.image_prompt}</div>
          ${sl.caption ? `<div class="hint">📝 ${sl.caption}</div>` : ""}
          <button data-regen="${i}">↻ Regenerate</button>
        </div></div>`;
    })
    .join("");

  $$("[data-regen]").forEach((b) =>
    b.addEventListener("click", async () => {
      b.disabled = true; b.textContent = "Generating…";
      try { await api(`/api/slideshows/${CURRENT}/slides/${b.dataset.regen}/regenerate`, { method: "POST" }); }
      catch (e) { alert(e.message); }
      renderReview();
    })
  );

  if (s.status === "generating") pollTimer = pollTimer || setInterval(renderReview, 3000);
  else stopPoll();
}

$("#r-generate").addEventListener("click", async () => {
  await api(`/api/slideshows/${CURRENT}/generate`, { method: "POST" });
  renderReview();
});

$("#r-save").addEventListener("click", async () => {
  const hashtags = $("#r-hashtags").value.split(/[\s,]+/).map((t) => t.replace(/^#/, "")).filter(Boolean);
  await api(`/api/slideshows/${CURRENT}/text`, {
    method: "PUT",
    body: JSON.stringify({ post_caption: $("#r-caption").value, hashtags }),
  });
  $("#r-save").textContent = "Saved ✓";
  setTimeout(() => ($("#r-save").textContent = "Save text"), 1200);
});

$("#r-post").addEventListener("click", async () => {
  $("#r-postresult").textContent = "Uploading to Blotato + creating TikTok draft…";
  $("#r-post").disabled = true;
  try {
    const res = await api(`/api/slideshows/${CURRENT}/post`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    const st = (res.response && res.response.status) || "submitted";
    const ok = st === "published" || st === "submitted" || st === "in-progress";
    $("#r-postresult").innerHTML = ok
      ? `<span class="ok">✓ Delivered to TikTok as a DRAFT.</span> ` +
        `Open the TikTok app → Drafts to add music and publish.`
      : `<span class="warn">Post status: ${st}</span>`;
    renderReview();
  } catch (e) {
    $("#r-postresult").innerHTML = `<span class="warn">${e.message}</span>`;
  } finally {
    $("#r-post").disabled = false;
  }
});

// --- cast -------------------------------------------------------------------
async function loadCast() {
  const cast = await api("/api/cast");
  $("#cast-list").innerHTML = cast
    .map(
      (c) => `<div class="card">
        <b>${c.name}</b>
        <p class="hint">${c.description || ""}</p>
        <div class="thumb-row">${c.reference_images
          .map((f) => `<img src="/api/cast/${c.id}/image/${f}">`)
          .join("") || '<span class="hint">no reference yet</span>'}</div>
        <div class="row">
          <label class="btn" style="cursor:pointer;text-align:center">Upload
            <input type="file" accept="image/*" hidden data-upload="${c.id}"></label>
          <button data-gen="${c.id}">Generate ref</button>
        </div>
        <button data-del="${c.id}" style="margin-top:.5rem">Delete</button>
      </div>`
    )
    .join("");

  $$("[data-upload]").forEach((inp) =>
    inp.addEventListener("change", async () => {
      const fd = new FormData();
      fd.append("file", inp.files[0]);
      await fetch(`/api/cast/${inp.dataset.upload}/upload`, { method: "POST", body: fd });
      loadCast();
    })
  );
  $$("[data-gen]").forEach((b) =>
    b.addEventListener("click", async () => {
      b.disabled = true; b.textContent = "Generating…";
      try { await api(`/api/cast/${b.dataset.gen}/generate`, { method: "POST", body: "{}" }); }
      catch (e) { alert(e.message); }
      loadCast();
    })
  );
  $$("[data-del]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (confirm("Delete this character?")) {
        await api("/api/cast/" + b.dataset.del, { method: "DELETE" });
        loadCast();
      }
    })
  );
}

$("#ch-add").addEventListener("click", async () => {
  const name = $("#ch-name").value.trim();
  if (!name) return alert("Name required.");
  await api("/api/cast", {
    method: "POST",
    body: JSON.stringify({ name, description: $("#ch-desc").value }),
  });
  $("#ch-name").value = ""; $("#ch-desc").value = "";
  loadCast();
});

// --- boot -------------------------------------------------------------------
loadStatus().then(loadCreateForm);
