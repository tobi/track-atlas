/* Track Atlas static browser. */
const REPO = "tobi/track-atlas";
const BRANCH = "main";

const $grid = document.getElementById("grid");
const $detail = document.getElementById("detail");
const $search = document.getElementById("search");
const $dlg = document.getElementById("editDlg");

let CATALOG = [];
let map = null;
let baseControl = null;
let currentLayout = null;
let currentGeojson = null;
let displayLayer = null;
let layerState = {};   // layout id -> { outline, point:{id:bool}, range:{id:bool} }
let mapGroups = [];
let hoverLayer = null; // { type: 'point'|'range'|'outline', id?: string }

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmtKm = (m) => m ? (m / 1000).toFixed(3) + " km" : "—";
const pct = (x) => x == null ? "—" : `${(x * 100).toFixed(1)}%`;
const pointLayer = (layout, id) => (layout?.point_layers || []).find((l) => l.id === id) || { items: [] };
const rangeLayer = (layout, id) => (layout?.range_layers || []).find((l) => l.id === id) || { items: [] };
const layoutPoint = (layout, id) => pointLayer(layout, "layout_points").items.find((p) => p.id === id) || null;
const cornerLayer = (layout) => pointLayer(layout, "corners").items;
const cornerRange = (layout, corner) => rangeLayer(layout, "corner_ranges").items.find((r) => r.anchor === corner.id || r.id === corner.id) || null;
const complexFor = (layout, corner) => rangeLayer(layout, "corner_complexes").items.find((r) => (r.members || []).includes(corner.id)) || null;

const RANGE_COLORS = ["#ff2d8d", "#5eead4", "#f6c945", "#60a5fa", "#a78bfa", "#fb7185", "#34d399"];

async function boot() {
  const txt = await (await fetch("tracks.jsonl")).text();
  CATALOG = txt.trim().split("\n").filter(Boolean).map((l) => JSON.parse(l));
  route();
  window.addEventListener("hashchange", route);
  $search.addEventListener("input", () => renderGrid($search.value));
}

function route() {
  const slug = location.hash.replace(/^#\/?/, "");
  if (slug) showDetail(slug);
  else {
    if (map) { map.remove(); map = null; }
    $detail.style.display = "none"; $grid.style.display = "grid";
    $search.style.display = "block"; renderGrid($search.value);
  }
}

function renderGrid(q) {
  q = (q || "").toLowerCase().trim();
  const hits = CATALOG.filter((t) => {
    if (!q) return true;
    const hay = [t.name, t.slug, t.country, ...(t.aka || []), ...(t.series || []),
                 t.location?.locality, t.location?.region].join(" ").toLowerCase();
    return q.split(/\s+/).every((w) => hay.includes(w));
  });
  $grid.innerHTML = hits.map((t) => {
    const first = t.layouts[0] || {};
    const corners = cornerLayer(first).length;
    const ranges = (first.range_layers || []).length;
    return `<div class="card" onclick="location.hash='/${t.slug}'">
      <div class="body">
        <h3>${esc(t.name)}</h3>
        <div class="meta">${esc(t.location?.locality || "")} · ${esc(t.country || "")}
          · ${t.layouts.map((l) => `${esc(l.name)} ${fmtKm(l.length_m)}`).join(" · ")}
          · ${corners} corners · ${ranges} range layers</div>
        <div style="margin-top:10px">${(t.series || []).map((s) => `<span class="chip">${esc(s)}</span>`).join("")}</div>
      </div>
    </div>`;
  }).join("") || `<p class="muted">No tracks match.</p>`;
}

async function showDetail(slug) {
  const track = CATALOG.find((t) => t.slug === slug);
  if (!track) { location.hash = ""; return; }
  $grid.style.display = "none"; $search.style.display = "none"; $detail.style.display = "block";
  window.__track = track;
  const ghBase = `https://github.com/${REPO}`;

  $detail.innerHTML = `
    <span class="back" onclick="location.hash=''">← all tracks</span>
    <div class="hero">
      <div>
        <h2>${esc(track.name)}</h2>
        <div class="aka">${esc((track.aka || []).join(", "))}</div>
      </div>
      <div class="det-actions">
        <button class="btn" onclick="window.open('${ghBase}/blob/${BRANCH}/tracks/${slug}/raw/track.json','_blank')">track.json</button>
        <button class="btn" onclick="window.open('${ghBase}/edit/${BRANCH}/tracks/${slug}/generation-config.json','_blank')">generation config</button>
        <button class="btn" onclick="window.open('${ghBase}/edit/${BRANCH}/tracks/${slug}/overrides.json','_blank')">overrides</button>
        <button class="btn" onclick="proposeTrackIssue('${slug}')">report</button>
      </div>
    </div>
    <div id="statsWrap"></div>
    <div class="toolbar" style="margin:16px 0 0">
      <label class="control">layout
        <select id="layoutPick" onchange="showLayout(this.value)">
          ${track.layouts.map((l) => `<option value="${esc(l.id)}">${esc(l.name)}${l.series?.length ? ` — ${esc(l.series.join("/").toUpperCase())}` : ""} · ${fmtKm(l.length_m)}</option>`).join("")}
        </select>
      </label>
      <label class="control">label
        <select id="layerPick" onchange="setDisplayLayer(this.value)"></select>
      </label>
    </div>
    <div class="map-wrap">
      <div id="map"></div>
      <aside id="layerPanel" class="layer-panel"></aside>
    </div>
    <h3 class="section-title">Corners</h3>
    <div id="cornersWrap"></div>
    <div class="copy-wrap">
      <div><b>Export current view</b><br><code>Copies full track JSON plus _view_config for selected layout/layers.</code></div>
      <div style="display:flex;gap:10px;align-items:center"><span id="copyStatus" class="muted"></span><button class="btn primary" onclick="copyCurrentTrackJson()">Copy JSON</button></div>
    </div>`;

  showLayout(track.layouts[0].id);
}

async function showLayout(layoutId) {
  const track = window.__track;
  const layout = track.layouts.find((l) => l.id === layoutId) || track.layouts[0];
  currentLayout = layout;
  displayLayer = layout.label_default;

  const labelRegistry = track.label_layers || {numbered: 1};
  const layers = Object.keys(labelRegistry);
  document.getElementById("layerPick").innerHTML = layers.map((code) =>
    `<option value="${esc(code)}" ${code === displayLayer ? "selected" : ""}>${esc((labelRegistry[code] || {}).label || code)}</option>`).join("");

  renderStats(track, layout);
  renderCorners();
  ensureLayerState(layout);
  renderLayerPanel(layout);
  try {
    const gj = await (await fetch(`geojson/${track.slug}_${layout.id}.geojson`)).json();
    currentGeojson = gj;
    renderMap(gj, track, layout);
  } catch (e) {
    currentGeojson = null;
    document.getElementById("map").innerHTML = `<div style="padding:18px;color:var(--muted)">Could not load layout GeoJSON: ${esc(e.message || e)}</div>`;
  }
}

function renderStats(track, layout) {
  const timingSectors = rangeLayer(layout, "timing_sectors").items;
  const sectors = timingSectors.map((s) => `${s.label} ${pct(s.start)}–${pct(s.end)}`).join("  ");
  const stats = [
    ["Layout", layout.name], ["Length", fmtKm(layout.length_m)],
    ["Point layers", (layout.point_layers || []).length], ["Range layers", (layout.range_layers || []).length],
    ["Corners", cornerLayer(layout).length], ["Direction", layout.direction || "—"],
    ["Sectors", sectors || "—"], ["Series", [...(track.series || []), ...(layout.series || [])].join(", ") || "—"],
  ];
  document.getElementById("statsWrap").innerHTML = `<div class="stats">${stats.map(([k, v]) =>
    `<div class="stat"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`).join("")}</div>`;
}

const SCALE_LABELS = {1:"Hairpin", 2:"Slow", 3:"Medium", 4:"Fast", 5:"Very fast", 6:"Kink"};
const scaleLabel = (s) => s == null ? "" : `${s} ${SCALE_LABELS[s] || ""}`.trim();
function resolveName(c, def) { const n = c.labels || {}; return n[def] || n.numbered || c.label || c.id; }
function nameLayerColumns(track) { return Object.keys(track.label_layers || {}).filter((code) => code !== "numbered"); }
function setDisplayLayer(code) { displayLayer = code; renderCorners(); redrawMapOverlays(); }
function sectorOf(c, layout) {
  const m = c.marker; if (m == null) return "";
  const s = rangeLayer(layout, "timing_sectors").items.find((x) => m >= x.start && m < x.end);
  return s ? s.label : "";
}
function phaseText(c, layout) {
  const r = cornerRange(layout, c);
  if (!r || r.start == null || r.end == null) return "—";
  return `${pct(r.start)} → ${pct(r.end)}`;
}
function renderCorners() {
  const track = window.__track, layout = currentLayout || track.layouts[0];
  const cols = nameLayerColumns(track), corners = cornerLayer(layout);
  document.getElementById("cornersWrap").innerHTML = `<table id="cornersTbl">
    <tr><th>#</th><th>code</th><th>display</th>${cols.map((c) => `<th>${esc((track.label_layers[c] || {}).label || c)}</th>`).join("")}
      <th>complex</th><th>sec</th><th>dir</th><th>scale</th><th>apex</th><th>range</th><th></th></tr>
    ${corners.map((c) => `<tr>
      <td>${c.number}</td><td class="muted">${esc(c.code ?? c.number)}</td><td><b>${esc(resolveName(c, displayLayer))}</b></td>
      ${cols.map((L) => `<td>${esc((c.labels || {})[L] || "")}</td>`).join("")}
      <td>${esc(complexFor(layout, c)?.label || "")}</td><td class="muted">${esc(sectorOf(c, layout))}</td>
      <td>${c.direction === "left" ? "←" : c.direction === "right" ? "→" : ""}</td><td>${esc(scaleLabel(c.scale))}</td>
      <td class="muted">${pct(c.marker)}</td><td class="muted">${phaseText(c, layout)}</td>
      <td><span class="edit" onclick='openEdit(${JSON.stringify(track.slug)}, ${JSON.stringify(layout.id)}, ${c.number})'>✎ edit</span></td>
    </tr>`).join("")}</table>`;
}

function ensureLayerState(layout) {
  if (layerState[layout.id]) return;
  const state = { outline: true, point: {}, range: {} };
  (layout.point_layers || []).forEach((l) => state.point[l.id] = true);
  (layout.range_layers || []).forEach((l) => state.range[l.id] = ["timing_sectors", "imsa_microsectors", "slow_zones"].includes(l.id));
  layerState[layout.id] = state;
}
function currentState() { ensureLayerState(currentLayout); return layerState[currentLayout.id]; }
function layerCount(layer) { return (layer.items || []).length; }
function layerMeta(layer) {
  const bits = [`${layerCount(layer)} item${layerCount(layer) === 1 ? "" : "s"}`];
  if (layer.series?.length) bits.push(layer.series.join("/"));
  if (layer.coverage) bits.push(layer.coverage);
  if (layer.provenance?.source) bits.push(layer.provenance.source);
  return bits.join(" · ");
}
function renderLayerPanel(layout) {
  const st = currentState();
  const panel = document.getElementById("layerPanel");
  if (!panel) return;
  panel.innerHTML = `<h4>Layers</h4>
    <div class="mini-actions"><button onclick="setAllLayers(true)">all on</button><button onclick="setAllLayers(false)">all off</button></div>
    <div class="layer-toggle" onmouseenter="hoverMapLayer('outline')" onmouseleave="clearMapHover()"><input type="checkbox" ${st.outline ? "checked" : ""} onchange="toggleOutline(this.checked)">
      <div><b>Track centerline</b><div class="meta">GeoJSON layout over OpenStreetMap</div></div></div>
    <div class="layer-group-title">Point layers</div>
    ${(layout.point_layers || []).map((l) => `<label class="layer-toggle" onmouseenter='hoverMapLayer("point", ${JSON.stringify(l.id)})' onmouseleave="clearMapHover()"><input type="checkbox" ${st.point[l.id] ? "checked" : ""} onchange='togglePointLayer(${JSON.stringify(l.id)}, this.checked)'>
      <div><b>${esc(l.label || l.id)}</b><div class="meta">${esc(layerMeta(l))}</div></div></label>`).join("") || `<div class="muted">No point layers</div>`}
    <div class="layer-group-title">Range layers</div>
    ${(layout.range_layers || []).map((l, i) => `<label class="layer-toggle" onmouseenter='hoverMapLayer("range", ${JSON.stringify(l.id)})' onmouseleave="clearMapHover()"><input type="checkbox" ${st.range[l.id] ? "checked" : ""} onchange='toggleRangeLayer(${JSON.stringify(l.id)}, this.checked)'>
      <div><b><span style="color:${RANGE_COLORS[i % RANGE_COLORS.length]}">●</span> ${esc(l.label || l.id)}</b><div class="meta">${esc(layerMeta(l))}</div></div></label>`).join("") || `<div class="muted">No range layers</div>`}`;
}
function hoverMapLayer(type, id=null) { hoverLayer = { type, id }; redrawMapOverlays(); }
function clearMapHover() { hoverLayer = null; redrawMapOverlays(); }
function toggleOutline(v) { currentState().outline = v; redrawMapOverlays(); }
function togglePointLayer(id, v) { currentState().point[id] = v; redrawMapOverlays(); }
function toggleRangeLayer(id, v) { currentState().range[id] = v; redrawMapOverlays(); }
function setAllLayers(v) {
  const st = currentState(); st.outline = v;
  Object.keys(st.point).forEach((k) => st.point[k] = v);
  Object.keys(st.range).forEach((k) => st.range[k] = v);
  renderLayerPanel(currentLayout); redrawMapOverlays();
}

function renderMap(gj, track, layout) {
  if (map) { map.remove(); map = null; }
  map = L.map("map", { scrollWheelZoom: true, preferCanvas: false });
  const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "&copy; OpenStreetMap contributors", maxZoom: 20 });
  const dark = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", { attribution: "&copy; OpenStreetMap contributors &copy; CARTO", maxZoom: 20 });
  osm.addTo(map);
  baseControl = L.control.layers({ "OpenStreetMap": osm, "Dark verification": dark }, {}, { position: "topleft" }).addTo(map);
  renderLayerPanel(layout);
  redrawMapOverlays(true);
}
function outlineCoords() {
  const f = (currentGeojson?.features || []).find((x) => x.properties?.role === "outline");
  return f?.geometry?.coordinates || [];
}
function redrawMapOverlays(fit=false) {
  if (!map || !currentGeojson || !currentLayout) return;
  mapGroups.forEach((g) => map.removeLayer(g)); mapGroups = [];
  const st = currentState();
  const coords = outlineCoords();
  const boundsLayers = [];
  const outlineHot = hoverLayer?.type === "outline";
  if ((st.outline || outlineHot) && coords.length) {
    const g = L.polyline(coords.map(ll), { color: outlineHot ? "#5eead4" : "#ffffff", weight: outlineHot ? 8 : 5, opacity: outlineHot ? 1 : .85, className: outlineHot ? "layer-range-highlight" : "" }).addTo(map).bindTooltip("Track centerline");
    mapGroups.push(g); boundsLayers.push(g);
  }
  (currentLayout.range_layers || []).forEach((layer, i) => {
    const hot = hoverLayer?.type === "range" && hoverLayer.id === layer.id;
    if (!st.range[layer.id] && !hot) return;
    const group = L.layerGroup().addTo(map);
    const color = hot ? "#ffffff" : RANGE_COLORS[i % RANGE_COLORS.length];
    (layer.items || []).forEach((r) => {
      const seg = sliceLine(coords, r.start, r.end);
      if (seg.length < 2) return;
      L.polyline(seg.map(ll), { color, weight: hot ? 13 : layer.coverage === "partition" ? 8 : 6, opacity: hot ? .98 : .68, lineCap:"round", className: hot ? "layer-range-highlight" : "" })
        .bindTooltip(`<b>${esc(layer.label || layer.id)} · ${esc(r.label || r.id)}</b><br>${pct(r.start)} → ${pct(r.end)}${r.entry_ref ? `<br>${esc(r.entry_ref)} → ${esc(r.exit_ref)}` : ""}`)
        .addTo(group);
    });
    mapGroups.push(group); boundsLayers.push(group);
  });
  (currentLayout.point_layers || []).forEach((layer) => {
    const hot = hoverLayer?.type === "point" && hoverLayer.id === layer.id;
    if (!st.point[layer.id] && !hot) return;
    const group = L.layerGroup().addTo(map);
    (layer.items || []).filter((p) => p.location).forEach((p) => addPoint(group, layer, p, hot));
    mapGroups.push(group); boundsLayers.push(group);
  });
  if (fit) {
    const outline = coords.length ? L.polyline(coords.map(ll)) : null;
    if (outline) map.fitBounds(outline.getBounds(), { padding:[28,28] });
  }
}
function addPoint(group, layer, p, hot=false) {
  const isCorner = layer.id === "corners";
  const isSf = p.id === "start_finish";
  const marker = L.circleMarker(ll(p.location), {
    radius: hot ? (isSf ? 11 : isCorner ? 9 : 8) : isSf ? 8 : isCorner ? 6 : 5,
    color: hot ? "#ffffff" : isSf ? "#111722" : "#080a0f", weight: hot ? 3 : isSf ? 3 : 1.5,
    fillColor: isSf ? "#ffffff" : isCorner ? "#ff2d8d" : "#f6c945", fillOpacity: 1,
    className: hot ? "layer-point-highlight" : "",
  });
  const label = isCorner ? `T${p.number} ${resolveName(p, displayLayer)}` : (p.label || p.id);
  marker.bindTooltip(`<b>${esc(label)}</b>${p.marker != null ? `<br>${pct(p.marker)}` : ""}<br><span class="muted">${esc(layer.label || layer.id)}</span>`);
  marker.addTo(group);
}
function ll(c) { return [c[1], c[0]]; }
function hav(a,b) {
  const R=6371000, toRad=(x)=>x*Math.PI/180;
  const dLat=toRad(b[1]-a[1]), dLon=toRad(b[0]-a[0]);
  const lat1=toRad(a[1]), lat2=toRad(b[1]);
  const s=Math.sin(dLat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dLon/2)**2;
  return 2*R*Math.asin(Math.sqrt(s));
}
function lineMetrics(coords) {
  const cum=[0]; let total=0;
  for (let i=0;i<coords.length-1;i++) { total += hav(coords[i], coords[i+1]); cum.push(total); }
  return {cum,total};
}
function pointAtDistance(coords, cum, dist) {
  if (!coords.length) return null;
  if (dist <= 0) return coords[0];
  if (dist >= cum[cum.length-1]) return coords[coords.length-1];
  let i=0; while (i < cum.length-1 && cum[i+1] < dist) i++;
  const seg = cum[i+1]-cum[i] || 1, t=(dist-cum[i])/seg;
  return [coords[i][0] + (coords[i+1][0]-coords[i][0])*t, coords[i][1] + (coords[i+1][1]-coords[i][1])*t];
}
function sliceLine(coords, start, end) {
  if (!coords.length || start == null || end == null || start >= end) return [];
  const {cum,total} = lineMetrics(coords);
  const a = start*total, b = end*total;
  const out = [pointAtDistance(coords,cum,a)];
  for (let i=1;i<coords.length-1;i++) if (cum[i] > a && cum[i] < b) out.push(coords[i]);
  out.push(pointAtDistance(coords,cum,b));
  return out.filter(Boolean);
}

function currentViewConfig() {
  const st = currentState();
  return {
    layout: currentLayout?.id,
    label_layer: displayLayer,
    visible: {
      outline: !!st.outline,
      point_layers: Object.fromEntries(Object.entries(st.point).filter(([,v]) => v)),
      range_layers: Object.fromEntries(Object.entries(st.range).filter(([,v]) => v)),
    },
  };
}
async function copyCurrentTrackJson() {
  const payload = { ...window.__track, _view_config: currentViewConfig() };
  const text = JSON.stringify(payload, null, 2);
  const status = document.getElementById("copyStatus");
  try {
    await navigator.clipboard.writeText(text);
    if (status) status.textContent = "copied";
  } catch {
    if (status) status.textContent = "copy failed";
  }
  setTimeout(() => { if (status) status.textContent = ""; }, 1800);
}

/* ---------------- editing ---------------- */
function openEdit(slug, layoutId, number) {
  const track = window.__track;
  const layout = track.layouts.find((l) => l.id === layoutId);
  const c = cornerLayer(layout).find((x) => x.number === number);
  const cols = nameLayerColumns(window.__track);
  const reg = window.__track.label_layers || {};
  $dlg.innerHTML = `<h3>Edit T${c.number} — ${esc(resolveName(c, layout.label_default))}</h3>
    <p>Changes become an <code>overrides.json</code> patch delivered as a GitHub issue or PR.</p>
    <div class="row"><div><label>Code</label><input id="e_code" value="${esc(c.code ?? c.number)}"></div>
      ${cols.map((L) => `<div><label>${esc((reg[L] || {}).label || L)}</label><input id="e_name_${esc(L)}" value="${esc((c.labels || {})[L] || "")}"></div>`).join("")}</div>
    <div class="row"><div><label>Complex</label><input id="e_comp" value="${esc(complexFor(layout, c)?.label || "")}"></div>
      <div><label>Direction</label><select id="e_dir"><option value="" ${!c.direction ? "selected" : ""}>—</option><option value="left" ${c.direction === "left" ? "selected" : ""}>left</option><option value="right" ${c.direction === "right" ? "selected" : ""}>right</option></select></div>
      <div><label>Scale 1–6</label><input id="e_scale" type="number" min="1" max="6" value="${c.scale ?? ""}"></div></div>
    <div class="actions"><button class="btn" onclick="editDlg.close()">Cancel</button>
      <button class="btn" onclick='submitEdit(${JSON.stringify(slug)}, ${JSON.stringify(layoutId)}, ${number}, "issue")'>Propose via issue</button>
      <button class="btn primary" onclick='submitEdit(${JSON.stringify(slug)}, ${JSON.stringify(layoutId)}, ${number}, "pr")'>Edit on GitHub</button></div>`;
  $dlg.showModal();
}
function collectEdit(slug, layoutId, number) {
  const track = window.__track, layout = track.layouts.find((l) => l.id === layoutId);
  const c = cornerLayer(layout).find((x) => x.number === number) || { labels: {} };
  const v = (id) => { const el = document.getElementById(id); return el ? el.value.trim() : ""; };
  const patch = {};
  const code = v("e_code"); if (code && code !== String(c.code ?? c.number)) patch.code = code;
  for (const L of nameLayerColumns(track)) {
    const el = document.getElementById(`e_name_${L}`); if (!el) continue;
    const val = el.value.trim(), cur = (c.labels || {})[L] || "";
    if (val !== cur) patch[L] = val === "" ? null : val;
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
    const body = [`Proposed correction for \`tracks/${slug}\`, layout \`${layoutId}\`, turn ${number}.`, "", "Merge this into `tracks/" + slug + "/overrides.json`:", "```json", snippet, "```", "", "Then re-run: `generate.py && render.py && verify.py " + slug + "`.", "", "_Filed from the Track Atlas site._"].join("\n");
    window.open(`https://github.com/${REPO}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}&labels=data`, "_blank");
  } else {
    navigator.clipboard?.writeText(snippet).catch(() => {});
    window.open(`https://github.com/${REPO}/edit/${BRANCH}/tracks/${slug}/overrides.json`, "_blank");
    alert("Override snippet copied to clipboard — merge it into overrides.json in the GitHub editor, then commit.");
  }
  $dlg.close();
}
function proposeTrackIssue(slug) {
  const title = `[${slug}] data problem`;
  const body = [`Track: \`tracks/${slug}\``, "", "**What's wrong?** (misplaced corner, wrong length, missing layout, geometry glitch…)", "", "", "_Filed from the Track Atlas site._"].join("\n");
  window.open(`https://github.com/${REPO}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}&labels=data`, "_blank");
}

boot();
