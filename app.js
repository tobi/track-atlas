/* Track Atlas static browser.
 *
 * Reads tracks/index.json (catalog) + tracks/<slug>/track.json +
 * layers/*.geojson straight from the repo (works on GitHub Pages, no build).
 *
 * Editing: every corner row has an "edit" affordance that opens a small form
 * and then deep-links to GitHub:
 *   - "Propose via issue": prefilled issue containing a ready-to-paste
 *     overrides.json patch (no account permissions needed beyond issues).
 *   - "Edit on GitHub": jumps into github.dev / the web editor on the track's
 *     overrides.json (GitHub turns a save into a fork + PR automatically).
 */
const REPO = "tobi/track-atlas";
const BRANCH = "main";

const $grid = document.getElementById("grid");
const $detail = document.getElementById("detail");
const $search = document.getElementById("search");
const $dlg = document.getElementById("editDlg");

let CATALOG = [];
let map = null;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmtKm = (m) => m ? (m / 1000).toFixed(3) + " km" : "—";

async function boot() {
  const res = await fetch("tracks/index.json");
  CATALOG = (await res.json()).tracks;
  route();
  window.addEventListener("hashchange", route);
  $search.addEventListener("input", () => renderGrid($search.value));
}

function route() {
  const slug = location.hash.replace(/^#\/?/, "");
  if (slug) showDetail(slug);
  else { $detail.style.display = "none"; $grid.style.display = "grid";
         $search.style.display = "block"; renderGrid($search.value); }
}

function renderGrid(q) {
  q = (q || "").toLowerCase().trim();
  const hits = CATALOG.filter((t) => {
    if (!q) return true;
    const hay = [t.name, t.slug, t.country, ...(t.aka || []), ...(t.series || []),
                 t.location?.locality, t.location?.region].join(" ").toLowerCase();
    return q.split(/\s+/).every((w) => hay.includes(w));
  });
  $grid.innerHTML = hits.map((t) => `
    <div class="card" onclick="location.hash='/${t.slug}'">
      ${t.poster ? `<img src="${t.poster}" alt="${esc(t.name)}" loading="lazy">` : ""}
      <div class="body">
        <h3>${esc(t.name)}</h3>
        <div class="meta">${esc(t.location?.locality || "")} · ${esc(t.country || "")}
          · ${t.layouts.map((l) => `${esc(l.name)} ${fmtKm(l.length_m)}`).join(" · ")}</div>
        <div style="margin-top:7px">${(t.series || []).map((s) =>
          `<span class="chip">${esc(s)}</span>`).join("")}</div>
      </div>
    </div>`).join("") || `<p class="muted">No tracks match.</p>`;
}

async function showDetail(slug) {
  const entry = CATALOG.find((t) => t.slug === slug);
  if (!entry) { location.hash = ""; return; }
  $grid.style.display = "none"; $search.style.display = "none";
  $detail.style.display = "block";

  const track = await (await fetch(`tracks/${slug}/raw/track.json`)).json();
  window.__track = track;
  const ghBase = `https://github.com/${REPO}`;

  $detail.innerHTML = `
    <span class="back" onclick="location.hash=''">&larr; all tracks</span>
    <div class="det-head">
      <h2>${esc(track.name)}</h2>
      <span class="aka">${esc((track.aka || []).join(", "))}</span>
    </div>
    <div class="det-actions">
      <button class="btn" onclick="window.open('${ghBase}/blob/${BRANCH}/tracks/${slug}/raw/track.json','_blank')">track.json</button>
      <button class="btn" onclick="window.open('${ghBase}/edit/${BRANCH}/tracks/${slug}/overrides.json','_blank')">Edit overrides on GitHub (PR)</button>
      <button class="btn" onclick="window.open('${ghBase}/edit/${BRANCH}/tracks/${slug}/source.json','_blank')">Edit source on GitHub (PR)</button>
      <button class="btn" onclick="proposeTrackIssue('${slug}')">Report a problem</button>
    </div>
    <div style="margin:16px 0;display:flex;align-items:baseline;gap:20px;flex-wrap:wrap">
      <label class="muted" style="font-size:13px">layout
        <select id="layoutPick" onchange="showLayout(this.value)">
          ${track.layouts.map((l) => `<option value="${esc(l.id)}">${esc(l.name)}${l.series && l.series.length ? ` — ${esc(l.series.join("/").toUpperCase())}` : ""} · ${fmtKm(l.length_m)}</option>`).join("")}
        </select></label>
      <label class="muted" style="font-size:13px">name layer
        <select id="layerPick" onchange="setDisplayLayer(this.value)"></select></label>
    </div>
    <div id="statsWrap"></div>
    <div class="det-cols">
      <div><div id="map"></div></div>
      <div class="poster">${entry.poster ? `<img src="${entry.poster}">` : ""}</div>
    </div>
    <h3 style="margin-top:26px">Corners</h3>
    <div id="cornersWrap"></div>
    <p class="muted">Spotted a wrong name or bad grouping? Hover a row and hit ✎ —
    it prefills a GitHub issue/PR. Empty a name layer to clear it (drivers then use the number).</p>`;

  showLayout(track.layouts[0].id);
}

// Render one layout: stats, name-layer picker, corner table, and the map. The
// layout <select> lets you browse every configuration; the name-layer <select>
// browses every naming layer the track declares.
async function showLayout(layoutId) {
  const track = window.__track;
  const layout = track.layouts.find((l) => l.id === layoutId) || track.layouts[0];
  currentLayout = layout;
  displayLayer = layout.name_default;

  const layers = Object.keys(track.name_layers || {numbered: 1});
  document.getElementById("layerPick").innerHTML = layers.map((code) =>
    `<option value="${esc(code)}" ${code === displayLayer ? "selected" : ""}>${esc((track.name_layers[code] || {}).label || code)}</option>`).join("");

  const stats = [
    ["Layout", layout.name], ["Length", fmtKm(layout.length_m)],
    ["Corners", (layout.corners || []).length],
    ["Direction", layout.direction || "—"],
    ["Sectors", (layout.sectors || []).length],
    ["Country", track.country || "—"],
    ["Series", (track.series || []).join(", ") || "—"],
  ];
  document.getElementById("statsWrap").innerHTML =
    `<div class="stats">${stats.map(([k, v]) =>
      `<div class="stat"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`).join("")}</div>`;

  renderCorners();
  const gj = await (await fetch(`tracks/${track.slug}/raw/${layout.geometry.outline}`)).json();
  renderMap(gj, track);
}

const SCALE_LABELS = {1: "Hairpin", 2: "Slow", 3: "Medium", 4: "Fast", 5: "Very fast", 6: "Kink"};
const scaleLabel = (s) => s == null ? "" : `${s} ${SCALE_LABELS[s] || ""}`.trim();

let displayLayer = null;   // selected name layer for the "display" column
let currentLayout = null;  // layout currently shown in the detail view

// Two-step resolution: the chosen layer if present, else the numbered identifier
// (no fall-through to other layers — an absent name means "use the number").
function resolveName(c, def) {
  const n = c.names || {};
  return n[def] || n.numbered;
}

// Overlay layers shown as table columns (numbered is just "Turn <code>", skip it).
function nameLayerColumns(track) {
  return Object.keys(track.name_layers || {}).filter((code) => code !== "numbered");
}

function setDisplayLayer(code) { displayLayer = code; renderCorners(); }

function renderCorners() {
  const track = window.__track;
  const layout = currentLayout || track.layouts[0];
  const cols = nameLayerColumns(track);
  document.getElementById("cornersWrap").innerHTML = `
    <table id="cornersTbl">
      <tr><th>#</th><th>code</th><th>display</th>
        ${cols.map((c) => `<th>${esc((track.name_layers[c] || {}).label || c)}</th>`).join("")}
        <th>complex</th><th>dir</th><th>scale</th><th>lap %</th><th></th></tr>
      ${(layout.corners || []).map((c) => `
        <tr>
          <td>${c.number}</td>
          <td class="muted">${esc(c.code ?? c.number)}</td>
          <td><b>${esc(resolveName(c, displayLayer))}</b></td>
          ${cols.map((L) => `<td>${esc((c.names || {})[L] || "")}</td>`).join("")}
          <td>${esc(c.complex || "")}</td>
          <td>${c.direction === "left" ? "←" : c.direction === "right" ? "→" : ""}</td>
          <td>${esc(scaleLabel(c.scale))}</td>
          <td class="muted">${c.marker != null ? (c.marker * 100).toFixed(1) : ""}</td>
          <td><span class="edit" onclick='openEdit(${JSON.stringify(track.slug)}, ${JSON.stringify(layout.id)}, ${c.number})'>✎ edit</span></td>
        </tr>`).join("")}
    </table>`;
}

function renderMap(gj, track) {
  if (map) { map.remove(); map = null; }
  map = L.map("map", { scrollWheelZoom: false });
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: "&copy; OpenStreetMap contributors &copy; CARTO", maxZoom: 19,
  }).addTo(map);
  const accent = "#e6007e";
  const layer = L.geoJSON(gj, {
    style: (f) => f.properties.role === "outline"
      ? { color: accent, weight: 3, opacity: 0.95 } : {},
    pointToLayer: (f, latlng) => {
      const r = f.properties.role;
      if (r === "corner")
        return L.circleMarker(latlng, { radius: 6, color: "#0a0c12", weight: 1.5,
          fillColor: accent, fillOpacity: 1 })
          .bindTooltip(`T${f.properties.number} ${f.properties.display || ""}`);
      if (r === "start_finish")
        return L.circleMarker(latlng, { radius: 8, color: "#ffffff", weight: 3,
          fillColor: "#0a0c12", fillOpacity: 1 }).bindTooltip("Start / Finish");
      return L.circleMarker(latlng, { radius: 5, color: "#f6c945", weight: 2,
        fillColor: "#0a0c12", fillOpacity: 1 })
        .bindTooltip(r === "pit_entry" ? "Pit entry" : "Pit exit");
    },
  }).addTo(map);
  map.fitBounds(layer.getBounds(), { padding: [24, 24] });
}

/* ---------------- editing ---------------- */

function openEdit(slug, layoutId, number) {
  const track = window.__track;
  const layout = track.layouts.find((l) => l.id === layoutId);
  const c = layout.corners.find((x) => x.number === number);
  const cols = nameLayerColumns(window.__track);
  const reg = window.__track.name_layers || {};
  $dlg.innerHTML = `
    <h3>Edit T${c.number} — ${esc(resolveName(c, layout.name_default))}</h3>
    <p>Changes become an <code>overrides.json</code> patch delivered as a GitHub
       issue or PR. Nothing is saved locally. Empty a name layer to clear it
       (the display then falls back to the number).</p>
    <div class="row">
      <div><label>Code</label><input id="e_code" value="${esc(c.code ?? c.number)}"></div>
      ${cols.map((L) => `<div><label>${esc((reg[L] || {}).label || L)}</label>
        <input id="e_name_${esc(L)}" value="${esc((c.names || {})[L] || "")}"></div>`).join("")}
    </div>
    <div class="row">
      <div><label>Complex</label><input id="e_comp" value="${esc(c.complex || "")}"></div>
      <div><label>Direction</label>
        <select id="e_dir">
          <option value="" ${!c.direction ? "selected" : ""}>—</option>
          <option value="left" ${c.direction === "left" ? "selected" : ""}>left</option>
          <option value="right" ${c.direction === "right" ? "selected" : ""}>right</option>
        </select></div>
      <div><label>Scale 1–6</label><input id="e_scale" type="number" min="1" max="6"
           value="${c.scale ?? ""}"></div>
    </div>
    <div class="actions">
      <button class="btn" onclick="editDlg.close()">Cancel</button>
      <button class="btn" onclick='submitEdit(${JSON.stringify(slug)}, ${JSON.stringify(layoutId)}, ${number}, "issue")'>Propose via issue</button>
      <button class="btn" style="border-color:#e6007e"
              onclick='submitEdit(${JSON.stringify(slug)}, ${JSON.stringify(layoutId)}, ${number}, "pr")'>Edit on GitHub (PR)</button>
    </div>`;
  $dlg.showModal();
}

function collectEdit(slug, layoutId, number) {
  const track = window.__track;
  const c = track.layouts.find((l) => l.id === layoutId)
              .corners.find((x) => x.number === number) || { names: {} };
  const v = (id) => { const el = document.getElementById(id); return el ? el.value.trim() : ""; };
  const patch = {};
  const code = v("e_code");
  if (code && code !== String(c.code ?? c.number)) patch.code = code;
  for (const L of nameLayerColumns(track)) {
    const el = document.getElementById(`e_name_${L}`);
    if (!el) continue;
    const val = el.value.trim();
    const cur = (c.names || {})[L] || "";
    if (val !== cur) patch[L] = val === "" ? null : val; // null clears the layer
  }
  if (v("e_comp")) patch.complex = v("e_comp");
  if (v("e_dir")) patch.direction = v("e_dir");
  if (v("e_scale")) patch.scale = Number(v("e_scale"));
  return { [layoutId]: { corners: { [String(number)]: patch } } };
}

function submitEdit(slug, layoutId, number, mode) {
  const ov = collectEdit(slug, layoutId, number);
  const snippet = JSON.stringify(ov, null, 2);
  if (mode === "issue") {
    const title = `[${slug}] corner data: T${number} (${layoutId})`;
    const body = [
      `Proposed correction for \`tracks/${slug}\`, layout \`${layoutId}\`, turn ${number}.`,
      "", "Merge this into `tracks/" + slug + "/overrides.json`:",
      "```json", snippet, "```", "",
      "Then re-run: `generate.py && render.py && verify.py " + slug + "`.",
      "", "_Filed from the Track Atlas site._",
    ].join("\n");
    window.open(`https://github.com/${REPO}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}&labels=data`,
      "_blank");
  } else {
    // GitHub's web editor: saving a change on a repo you can't push to
    // automatically offers fork + PR. Copy the snippet for pasting.
    navigator.clipboard?.writeText(snippet).catch(() => {});
    window.open(`https://github.com/${REPO}/edit/${BRANCH}/tracks/${slug}/overrides.json`,
      "_blank");
    alert("Override snippet copied to clipboard — merge it into overrides.json in the GitHub editor, then commit (GitHub will open a PR).");
  }
  $dlg.close();
}

function proposeTrackIssue(slug) {
  const title = `[${slug}] data problem`;
  const body = [
    `Track: \`tracks/${slug}\``, "",
    "**What's wrong?** (misplaced corner, wrong length, missing layout, geometry glitch…)",
    "", "", "_Filed from the Track Atlas site._",
  ].join("\n");
  window.open(`https://github.com/${REPO}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}&labels=data`,
    "_blank");
}

boot();
