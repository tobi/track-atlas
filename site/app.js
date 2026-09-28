/* Track Atlas site. Light-DOM lit components; data from atlas.json + tracks.jsonl. */
import { LitElement, html, svg, nothing } from "https://esm.sh/lit@3.2.1";
import { TrackMap, RANGE_COLORS } from "./map.js";
import { BRANCH, FLAGS, GH, Lap, TIERS, cornerName, corners, inRange, km, m1, pct, place, tierOf, turnCode } from "./lib.js";

class Light extends LitElement { createRenderRoot() { return this; } }

// --- data ------------------------------------------------------------------------
let ATLAS = null, TRACKS = null;
const atlas = async () => (ATLAS ??= await (await fetch("atlas.json")).json());
async function track(slug) {
  TRACKS ??= fetch("tracks.jsonl").then((r) => r.text()).then((t) =>
    new Map(t.trim().split("\n").filter(Boolean).map((l) => { const j = JSON.parse(l); return [j.slug, j]; })));
  return (await TRACKS).get(slug);
}
const geo = (slug, name) => fetch(`geojson/${slug}_${name}`).then((r) => (r.ok ? r.json() : null));

const bestLayout = (a) => a.layouts.reduce((b, l) => (l.measured && (!b.measured || l.ce95_m < b.ce95_m) ? l : b), a.layouts[0]);
const tierBadge = (s) => { const t = tierOf(s); return html`<span class="tier" style="--c:${t.color}">${t.label}${s?.measured ? html` <b>${m1(s.ce95_m)}</b>` : nothing}</span>`; };

function silhouette(pts, color, w = 2.2) {
  if (!pts?.length) return nothing;
  return svg`<svg viewBox="-6 -6 112 112" class="sil"><path d="M${pts.map((p) => p.join(",")).join("L")}Z"
    fill="none" stroke="${color}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`;
}

// --- app shell / router -------------------------------------------------------------
class AtlasApp extends Light {
  static properties = { route: { state: true } };
  constructor() { super(); this.route = this.parse(); addEventListener("hashchange", () => { this.route = this.parse(); scrollTo(0, 0); }); }
  parse() {
    const [a, b] = location.hash.replace(/^#\/?/, "").split("/");
    if (!a) return { page: "home" };
    if (a === "method") return { page: "method" };
    return { page: "track", slug: decodeURIComponent(a), layout: b && decodeURIComponent(b) };
  }
  render() {
    const r = this.route;
    return html`
      <header class="top ${r.page === "track" ? "compact" : ""}">
        <a href="#/" class="brand"><span class="mark">${svg`<svg viewBox="0 0 24 24"><path d="M4 16c0-6 5-11 11-11 3 0 5 2 5 4s-2 3-4 3-3 1-3 3 1 4-2 5-7 0-7-4z" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/></svg>`}</span>Track Atlas</a>
        <nav>
          <a href="#/" class=${r.page === "home" ? "on" : ""}>Atlas</a>
          <a href="#/method" class=${r.page === "method" ? "on" : ""}>Method</a>
          <a href="tracks.jsonl" download>tracks.jsonl</a>
          <a href=${GH} target="_blank" rel="noopener">GitHub</a>
        </nav>
      </header>
      ${r.page === "home" ? html`<atlas-home></atlas-home>`
        : r.page === "method" ? html`<atlas-method></atlas-method>`
        : html`<track-page .slug=${r.slug} .layoutId=${r.layout}></track-page>`}`;
  }
}

// --- home ---------------------------------------------------------------------------
class AtlasHome extends Light {
  static properties = { data: { state: true }, q: { state: true }, tier: { state: true }, sort: { state: true }, hot: { state: true } };
  constructor() { super(); this.q = ""; this.tier = "all"; this.sort = "accuracy"; atlas().then((d) => (this.data = d)); }

  filtered() {
    const q = this.q.toLowerCase().trim();
    let xs = this.data.filter((a) => {
      const s = bestLayout(a), t = tierOf(s).id;
      if (this.tier === "measured" && !s.measured) return false;
      if (this.tier === "survey" && t !== "survey") return false;
      if (this.tier === "traced" && s.measured) return false;
      if (!q) return true;
      const hay = [a.name, a.slug, a.country, a.locality, a.region, ...(a.aka || []), ...(a.series || [])].join(" ").toLowerCase();
      return q.split(/\s+/).every((w) => hay.includes(w));
    });
    const acc = (a) => { const s = bestLayout(a); return s.measured ? s.ce95_m : 99; };
    const cmp = { accuracy: (a, b) => acc(a) - acc(b) || a.name.localeCompare(b.name),
                  name: (a, b) => a.name.localeCompare(b.name),
                  country: (a, b) => (a.country || "").localeCompare(b.country || "") || a.name.localeCompare(b.name) }[this.sort];
    return xs.sort(cmp);
  }

  ladder() {
    const measured = this.data.map((a) => [a, bestLayout(a)]).filter(([, s]) => s.measured).sort((x, y) => x[1].ce95_m - y[1].ce95_m);
    const W = 640, x = (m) => 30 + ((Math.log10(m) + 1) / 2) * (W - 60);   // 0.1 m .. 10 m, log
    const short = (n) => n.replace(/ (International|Motor|Raceway|Speedway|Circuit|Park|Grand Prix|Street).*$/, "");
    // greedy lanes so no two labels overlap
    const ends = [];
    const dots = measured.map(([a, s]) => {
      const cx = x(s.ce95_m), label = `${short(a.name)} ${s.ce95_m.toFixed(2)}`, w = label.length * 6.1 + 14;
      let lane = ends.findIndex((e) => e < cx - 4);
      if (lane < 0) { lane = ends.length; ends.push(0); }
      ends[lane] = cx + w;
      return { a, s, cx, label, lane };
    });
    const top = 40, lh = 15, axis = top + ends.length * lh + 4, H = axis + 44;
    const ticks = [0.1, 0.2, 0.5, 1, 2, 5, 10];
    return html`
      <figure class="ladder">
        <figcaption>Absolute accuracy, 95% (CE95), log scale</figcaption>
        <svg viewBox="0 0 ${W} ${H}">
          ${svg`
          <rect x=${x(2)} y="26" width=${x(10) - x(2)} height=${axis - 26} rx="6" class="osm-band"/>
          <text x=${(x(2) + x(10)) / 2} y=${axis + 18} class="band-label" text-anchor="middle">OpenStreetMap trace: 2–10 m, unstated</text>
          <rect x=${x(0.1)} y="26" width=${x(0.5) - x(0.1)} height=${axis - 26} rx="6" class="survey-band"/>
          <text x=${(x(0.1) + x(0.5)) / 2} y=${axis + 18} class="band-label" text-anchor="middle">survey grade</text>
          <line x1="30" x2=${W - 30} y1=${axis} y2=${axis} class="axis"/>
          ${ticks.map((t) => svg`<line x1=${x(t)} x2=${x(t)} y1=${axis - 4} y2=${axis + 4} class="axis"/><text x=${x(t)} y=${axis + 36} text-anchor="middle" class="tick">${t} m</text>`)}
          <line x1=${x(1)} x2=${x(1)} y1="20" y2=${axis} class="goal"/><text x=${x(1) + 4} y="18" class="goal-label">sub-metre goal</text>
          ${dots.map(({ a, s, cx, label, lane }) => {
            const cy = top + lane * lh, t = tierOf(s);
            return svg`<g class="dot ${this.hot === a.slug ? "hot" : ""}" @mouseenter=${() => (this.hot = a.slug)} @mouseleave=${() => (this.hot = null)}
                         @click=${() => (location.hash = `/${a.slug}`)}>
              <line x1=${cx} x2=${cx} y1=${cy} y2=${axis} class="stem"/>
              <circle cx=${cx} cy=${cy} r="5" fill=${t.color}/>
              <text x=${cx + 8} y=${cy + 4} class="dot-label">${label}</text></g>`;
          })}`}
        </svg>
      </figure>`;
  }

  render() {
    if (!this.data) return html`<div class="loading">Loading the atlas…</div>`;
    const all = this.data, meas = all.filter((a) => bestLayout(a).measured);
    const best = Math.min(...meas.map((a) => bestLayout(a).ce95_m));
    const corners = all.reduce((n, a) => n + a.layouts[0].corners, 0);
    const list = this.filtered();
    return html`
      <section class="hero">
        <div class="hero-text">
          <p class="eyebrow">Open racing-circuit geometry · ODbL</p>
          <h1>Every corner, <em>measured</em>,<br>with its error bar.</h1>
          <p class="lede">${all.length} circuits, ${corners} named corners. ${meas.length} US circuits have measured track edges.
            They are traced from open orthoimagery and positioned against national lidar (USGS 3DEP, IGN LiDAR HD), down to ${best.toFixed(2)} m absolute accuracy.
            Each corner has its turn-in, apex and exit, and every figure states its own accuracy.</p>
          <div class="cta">
            <a class="btn primary" href="tracks.jsonl" download>Download tracks.jsonl</a>
            <a class="btn" href="#/method">How it is measured</a>
          </div>
        </div>
        ${this.ladder()}
      </section>

      <section class="filters">
        <input type="search" placeholder="Search circuit, country, series…" .value=${this.q} @input=${(e) => (this.q = e.target.value)}>
        <div class="seg">
          ${[["all", "All", all.length], ["measured", "Measured", meas.length],
             ["survey", "Survey grade", all.filter((a) => tierOf(bestLayout(a)).id === "survey").length],
             ["traced", "OSM trace", all.length - meas.length]].map(([id, label, n]) =>
            html`<button class=${this.tier === id ? "on" : ""} @click=${() => (this.tier = id)}>${label} <span>${n}</span></button>`)}
        </div>
        <label class="sort">Sort
          <select @change=${(e) => (this.sort = e.target.value)}>
            <option value="accuracy">by accuracy</option><option value="name">by name</option><option value="country">by country</option>
          </select></label>
      </section>

      <section class="grid">
        ${list.map((a) => {
          const s = bestLayout(a), t = tierOf(s);
          return html`<a class="card ${this.hot === a.slug ? "hot" : ""}" href="#/${a.slug}" @mouseenter=${() => (this.hot = a.slug)} @mouseleave=${() => (this.hot = null)}>
            <div class="card-sil" style="--c:${t.color}">${silhouette(a.silhouette, t.color)}</div>
            <div class="card-body">
              <h3>${a.name}</h3>
              <div class="where">${FLAGS(a.country)} ${place(a.locality, a.country)}</div>
              <div class="facts"><span>${km(s.length_m)}</span><span>${s.corners} corners</span>${a.layouts.length > 1 ? html`<span>${a.layouts.length} layouts</span>` : nothing}</div>
              <div class="card-q">${tierBadge(s)}
                ${s.measured ? html`<span class="seen" title="share of the lap where both edges were seen in the imagery">
                  <i style="width:${Math.round((s.seen?.both ?? 0) * 100)}%"></i></span><small>${pct(s.seen?.both)} seen</small>` : nothing}</div>
            </div></a>`;
        })}
        ${list.length ? nothing : html`<p class="muted">No circuit matches.</p>`}
      </section>

      <section class="legend">
        ${TIERS.map((t) => html`<div><span class="tier" style="--c:${t.color}">${t.label}</span><p>${t.blurb}</p></div>`)}
      </section>`;
  }
}

// --- track page -------------------------------------------------------------------------
const fmtLap = (t) => `${Math.floor(t / 60)}:${(t % 60).toFixed(2).padStart(5, "0")}`;
const CHARACTER = { kink: "kink", high_speed: "high speed", medium: "medium", slow: "slow" };
const LAYER_TOGGLES = [["edges", "Edges"], ["racing", "Racing line"], ["brakes", "Braking points"], ["crossings", "Turn-in / exit"],
                       ["apexes", "Apexes"], ["midline", "Midline"],
                       ["surface", "Asphalt"], ["sectors", "Sector lines"], ["labels", "Labels"]];

class TrackPage extends Light {
  static properties = { slug: {}, layoutId: {}, t: { state: true }, tab: { state: true }, sel: { state: true },
                        hover: { state: true }, base: { state: true }, show: { state: true }, label: { state: true }, range: { state: true } };
  constructor() { super(); this.tab = "quality"; this.show = {}; this.range = null; }

  get layout() { return this.t?.layouts.find((l) => l.id === this.layoutId) || this.t?.layouts[0]; }

  async willUpdate(ch) {
    if (ch.has("slug")) {
      this.t = await track(this.slug);
      if (!this.t) { location.hash = "/"; return; }
      this.label = this.layout.label_default || "numbered";
      document.title = `${this.t.name} · Track Atlas`;
    }
  }

  async updated(ch) {
    if (!this.t) return;
    if (ch.has("t") || ch.has("layoutId")) await this.loadMap();
    if (ch.has("show") || ch.has("label") || ch.has("base")) this.redraw();
    if (ch.has("range") || ch.has("t") || ch.has("layoutId")) this.map?.drawRanges(this.rangeSpec());
  }

  disconnectedCallback() { super.disconnectedCallback(); this.map?.destroy(); this.map = null; }

  async loadMap() {
    const lo = this.layout, el = this.querySelector("#map");
    if (!el) return;
    if (!this.map) this.map = new TrackMap(el, { onHover: (h) => (this.hover = h), onCorner: (id) => this.pick(id, true) });
    const outline = await geo(this.t.slug, lo.geometry.centerline.split("/").pop());
    const surface = lo.geometry.surface ? await geo(this.t.slug, lo.geometry.surface.split("/").pop()) : null;
    this.lap = new Lap(outline.features.find((f) => f.properties.role === "outline").geometry.coordinates);
    this.map.load(this.t, lo, outline, surface);
    this.base = this.map.baseId;
    this.redraw();
    this.map.drawRanges(this.rangeSpec());
    this.requestUpdate();
  }

  redraw() { this.map?.draw({ labels: this.show.labels !== false, labelLayer: this.label, show: this.show }); }

  rangeSpec() {
    const lo = this.layout;
    const L_ = (lo?.range_layers || []).find((r) => r.id === this.range);
    if (!L_) return null;
    const items = L_.items.map((it, k) => {
      if (L_.kind === "corner_ranges") {
        const c = corners(lo).find((c) => c.id === (it.anchor || it.id));
        return { ...it, color: c?.direction === "left" ? "#7dd3fc" : c?.direction === "right" ? "#fbbf24" : "#94a3b8" };
      }
      return it;
    });
    return { items };
  }

  pick(id, fromMap = false) {
    this.sel = this.sel === id && !fromMap ? null : id;
    const c = corners(this.layout).find((c) => c.id === this.sel);
    this.map?.focusCorner(c || null);
    if (!c) this.map?.fit();
    if (fromMap) { this.tab = "corners"; this.updateComplete.then(() => this.querySelector(`[data-c="${id}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" })); }
  }

  setLayout(id) { location.hash = `/${this.t.slug}/${id}`; this.sel = null; }

  render() {
    if (!this.t) return html`<div class="loading">Loading…</div>`;
    const t = this.t, lo = this.layout, s = lo.surface;
    const summary = s ? { measured: true, ce95_m: s.absolute_accuracy_ce95_m } : { measured: false };
    return html`
      <div class="track">
        <div class="mapcol">
          <div id="map"></div>
          <div class="map-title">
            <a href="#/" class="back">← Atlas</a>
            <h1>${t.name}</h1>
            <div class="where">${FLAGS(t.country)} ${place(t.location?.locality, t.location?.region, t.country)}
              ${(t.series || []).map((x) => html`<span class="series">${x}</span>`)}</div>
            <div class="title-row">
              ${t.layouts.length > 1 ? html`<select @change=${(e) => this.setLayout(e.target.value)}>
                ${t.layouts.map((l) => html`<option value=${l.id} ?selected=${l.id === lo.id}>${l.name}${l.series?.length ? ` · ${l.series.join("/").toUpperCase()}` : ""}</option>`)}</select>`
                : html`<span class="muted">${lo.name}</span>`}
              <span class="muted">${km(lo.length_m)} · ${lo.direction || ""}</span>
              ${tierBadge(summary)}
            </div>
          </div>
          <div class="map-tools">
            <div class="seg small">
              ${s ? html`<button class=${this.base === "source" ? "on" : ""} @click=${() => { this.map.setBase("source"); this.base = "source"; }}
                   title="The open orthophoto the edges were measured on, moved by the recorded registration and datum step">Source imagery</button>` : nothing}
              <button class=${this.base === "esri" ? "on" : ""} @click=${() => { this.map.setBase("esri"); this.base = "esri"; }} title="Esri World Imagery: for viewing only, never traced">Satellite</button>
              <button class=${this.base === "dark" ? "on" : ""} @click=${() => { this.map.setBase("dark"); this.base = "dark"; }}>Dark</button>
            </div>
            <details class="toggles"><summary>Layers</summary>
              ${LAYER_TOGGLES.filter(([k]) => s || k === "labels").map(([k, label]) => html`<label>
                <input type="checkbox" .checked=${this.show[k] !== false} @change=${(e) => (this.show = { ...this.show, [k]: e.target.checked })}> ${label}</label>`)}
            </details>
          </div>
          ${s ? html`<div class="map-key">
            <span><i class="k-edge"></i>edge, seen</span><span><i class="k-unseen"></i>edge, bridged</span>
            <span><i class="k-racing"></i>racing line, slow → fast</span><span><i class="k-brake"></i>braking</span>
            <span><i class="k-entry"></i>turn-in</span><span><i class="k-exit"></i>exit</span><span><i class="k-apex"></i>apex</span></div>` : nothing}
          <lap-strip .layout=${lo} .lap=${this.lap} .hover=${this.hover} .sel=${this.sel} .range=${this.rangeSpec()} .label=${this.label}
            @pick=${(e) => this.pick(e.detail)} @seek=${(e) => this.map?.focusFraction(e.detail)}></lap-strip>
        </div>
        <aside class="panel">
          <nav class="tabs">
            ${[["quality", "Quality"], ["corners", `Corners ${corners(lo).length}`], ["layers", "Layers"], ["data", "Data"]].map(([id, label]) =>
              html`<button class=${this.tab === id ? "on" : ""} @click=${() => (this.tab = id)}>${label}</button>`)}
          </nav>
          <div class="panel-body">
            ${this.tab === "quality" ? html`<quality-panel .track=${t} .layout=${lo}></quality-panel>`
              : this.tab === "corners" ? this.cornersTab(lo)
              : this.tab === "layers" ? this.layersTab(lo)
              : this.dataTab(t, lo)}
          </div>
        </aside>
      </div>`;
  }

  cornersTab(lo) {
    const cs = corners(lo), layers = Object.keys(this.t.label_layers || { numbered: 1 });
    const placed = cs.filter((c) => c.placement?.basis === "curvature").length;
    return html`
      <div class="row-between">
        <p class="muted small">${lo.surface ? `${placed} of ${cs.length} placed on a measured curvature peak.` : "Positions come from lap-fraction markers on the OSM centerline."}</p>
        <label class="sort">Names <select @change=${(e) => (this.label = e.target.value)}>
          ${layers.map((k) => html`<option value=${k} ?selected=${k === this.label}>${this.t.label_layers?.[k]?.label || k}</option>`)}</select></label>
      </div>
      <ol class="corner-list">
        ${cs.map((c) => {
          const pl = c.placement, open = this.sel === c.id;
          const len = c.entry && c.exit ? (((c.exit.marker - c.entry.marker + 1) % 1) * (lo.surface?.lap_length_m || lo.length_m)) : null;
          return html`<li data-c=${c.id} class=${open ? "open" : ""}>
            <button class="corner-row" @click=${() => this.pick(c.id)}>
              <span class="code ${c.direction || ""}">${turnCode(c)}</span>
              <span class="cname">${cornerName(c, this.label)}</span>
              <span class="dir" title=${c.direction || "direction unknown"}>${c.direction === "left" ? "↰" : c.direction === "right" ? "↱" : "·"}</span>
              <span class="rad">${c.dynamics ? `${Math.round(c.dynamics.min_speed_kmh)} km/h` : pl?.radius_m ? `R ${Math.round(pl.radius_m)}` : ""}</span>
              ${c.character ? html`<span class="char ${c.character}">${CHARACTER[c.character]}</span>`
                : html`<span class="state ${pl?.basis === "curvature" ? "ok" : lo.surface ? "warn" : ""}">${pl?.basis === "curvature" ? (pl.shape === "kink" ? "kink" : "measured") : lo.surface ? "no peak" : "marker"}</span>`}
            </button>
            ${open ? html`<div class="corner-detail">
              <dl>
                ${c.dynamics ? this.dynamicsRows(c, lo) : nothing}
                ${c.entry ? html`<dt>Turn-in</dt><dd>${pct(c.entry.marker)} of lap · ${m1(c.entry.width_m)} wide</dd>` : nothing}
                ${c.apex ? html`<dt>Apex</dt><dd>${pct(c.apex.marker)} · on the ${c.apex.edge} edge${c.apex.basis === "racing_line" ? " · racing line" : ""} · <code>${c.apex.location.map((v) => v.toFixed(6)).join(", ")}</code></dd>`
                  : c.location ? html`<dt>Location</dt><dd><code>${c.location.map((v) => v.toFixed(6)).join(", ")}</code> (${c.location_source})</dd>` : nothing}
                ${c.exit ? html`<dt>Exit</dt><dd>${pct(c.exit.marker)} · ${m1(c.exit.width_m)} wide</dd>` : nothing}
                ${len ? html`<dt>Length</dt><dd>${Math.round(len)} m turn-in to exit</dd>` : nothing}
                ${pl?.radius_m ? html`<dt>Radius</dt><dd>${pl.radius_m} m minimum (midline)</dd>` : nothing}
                ${pl?.marker_offset_m != null ? html`<dt>Legacy marker</dt><dd>${Math.abs(pl.marker_offset_m).toFixed(0)} m ${pl.marker_offset_m > 0 ? "before" : "after"} the measured apex</dd>` : nothing}
                ${c.apex?.quality ? html`<dt>Accuracy</dt><dd>${m1(c.apex.quality.accuracy_m)} absolute · ${m1(c.apex.quality.relative_accuracy_m)} relative · ${c.apex.quality.source} ${c.apex.quality.date || ""}</dd>` : nothing}
                <dt>Names</dt><dd>${Object.entries(c.labels || {}).map(([k, v]) => html`<span class="nm"><small>${k}</small> ${v}</span>`)}</dd>
                ${pl?.declared_direction ? html`<dt>Conflict</dt><dd class="warn-text">curated ${pl.declared_direction}, geometry turns ${pl.direction}</dd>` : nothing}
              </dl>
              <a class="small" target="_blank" rel="noopener" href=${this.issueUrl(c)}>Suggest a correction →</a>
            </div>` : nothing}
          </li>`;
        })}
      </ol>`;
  }

  dynamicsRows(c, lo) {
    const d = c.dynamics, L = lo.surface?.lap_length_m || lo.length_m;
    const dist = (a, b) => Math.round((((b - a) % 1) + 1) % 1 * L);
    const geo = c.geometric_apex;
    return html`
      <dt>Character</dt><dd><span class="char ${d.character}">${CHARACTER[d.character]}</span> · minimum ${Math.round(d.min_speed_kmh)} km/h <span class="muted">(${d.model.toUpperCase()} model)</span></dd>
      <dt>Braking</dt><dd>${d.brake ? html`from ${Math.round(d.brake.speed_kmh)} km/h at ${pct(d.brake.marker)} · ${Math.round(d.brake_m)} m to the slowest point` : d.character === "kink" ? "none, taken flat" : "none (a lift)"}</dd>
      <dt>Full throttle</dt><dd>${pct(d.full_throttle_marker)}</dd>
      <dt>Range</dt><dd>${pct(d.start)} → ${pct(d.end)} · ${dist(d.start, d.end)} m <span class="muted">(0.5 s before braking to 0.5 s after full throttle)</span></dd>
      ${geo ? html`<dt>vs geometry</dt><dd>racing apex ${Math.abs(dist(geo.marker, c.apex.marker)) > L / 2 ? `${dist(c.apex.marker, geo.marker)} m before` : `${dist(geo.marker, c.apex.marker)} m after`} the tightest point of the inside edge${c.apex.gap_m != null ? html` · clearance ${m1(Math.max(0, c.apex.gap_m))}` : nothing}</dd>` : nothing}`;
  }

  issueUrl(c) {
    const lo = this.layout;
    const body = `Track: ${this.t.slug} / layout ${lo.id}\nCorner: ${turnCode(c)} (${c.id})\n\nCurrent: ${JSON.stringify({ labels: c.labels, direction: c.direction, marker: c.marker })}\n\nProposed \`track.py\` line:\n\n\`\`\`python\nlap.corner(${c.number}, official=${JSON.stringify(c.labels?.official || "")}, direction=${JSON.stringify(c.direction)})\n\`\`\`\n\nEvidence / source:\n`;
    return `${GH}/issues/new?${new URLSearchParams({ title: `${this.t.name}: ${turnCode(c)} ${cornerName(c, "official")}`, body })}`;
  }

  layersTab(lo) {
    const rl = lo.range_layers || [], pl = (lo.point_layers || []).filter((p) => p.kind !== "corners");
    const cur = rl.find((r) => r.id === this.range);
    return html`
      <h3 class="h">Range layers</h3>
      <p class="muted small">Lap intervals drawn on the track. Fractions are of the ${lo.geometry?.basis === "midline" ? "measured midline" : "OSM centerline"}, from the start/finish line.</p>
      <div class="radio-list">
        <label><input type="radio" name="rl" .checked=${!cur} @change=${() => (this.range = null)}> None</label>
        ${rl.map((r) => html`<label><input type="radio" name="rl" .checked=${this.range === r.id} @change=${() => (this.range = r.id)}>
          ${r.label} <span class="muted">${r.items.length}${r.series?.length ? ` · ${r.series.join("/").toUpperCase()}` : ""}</span></label>`)}
      </div>
      ${cur ? html`<table class="mini">
        <thead><tr><th></th><th>Item</th><th>Start</th><th>End</th><th>Length</th></tr></thead>
        <tbody>${cur.items.map((it, k) => html`<tr>
          <td><i class="sw" style="background:${this.rangeSpec()?.items[k]?.color || RANGE_COLORS[k % RANGE_COLORS.length]}"></i></td>
          <td>${it.label || it.id}</td><td>${pct(it.start)}</td><td>${pct(it.end)}</td>
          <td>${it.start != null ? `${Math.round((((it.end - it.start + 1) % 1) || 1) * (lo.surface?.lap_length_m || lo.length_m))} m` : ""}</td></tr>`)}</tbody></table>
        ${cur.provenance ? html`<p class="muted small">Source: ${cur.provenance.url ? html`<a href=${cur.provenance.url} target="_blank" rel="noopener">${cur.provenance.source}</a>` : cur.provenance.source}</p>` : nothing}` : nothing}
      ${pl.map((p) => html`<h3 class="h">${p.label}</h3>
        <table class="mini"><tbody>${p.items.map((it) => html`<tr><td>${it.label || it.id}</td><td>${pct(it.marker)}</td>
          <td>${it.line ? html`<span class="ok-text">measured line</span>` : it.location ? "point" : ""}</td></tr>`)}</tbody></table>`)}`;
  }

  dataTab(t, lo) {
    const raw = `${GH}/blob/${BRANCH}/tracks/${t.slug}`;
    const outline = `geojson/${t.slug}_${lo.geometry.centerline.split("/").pop()}`;
    const surf = lo.geometry.surface ? `geojson/${t.slug}_${lo.geometry.surface.split("/").pop()}` : null;
    return html`
      <h3 class="h">Download</h3>
      <ul class="links">
        <li><a href=${`${raw}/raw/track.json`} target="_blank" rel="noopener">track.json</a><span>the full record for this circuit</span></li>
        <li><a href=${outline} download>${lo.id}.geojson</a><span>${lo.geometry.basis === "midline" ? "measured midline" : "OSM centerline"} + points</span></li>
        ${surf ? html`<li><a href=${surf} download>${lo.id}.surface.geojson</a><span>edges, asphalt, turn-in/exit lines, apexes</span></li>` : nothing}
        <li><a href="tracks.jsonl" download>tracks.jsonl</a><span>every circuit, one JSON per line</span></li>
      </ul>
      <button class="btn" @click=${(e) => navigator.clipboard.writeText(JSON.stringify(t, null, 2)).then(() => (e.target.textContent = "Copied"))}>Copy track JSON</button>
      <h3 class="h">Improve it</h3>
      <ul class="links">
        <li><a href=${`${GH}/edit/${BRANCH}/tracks/${t.slug}/track.py`} target="_blank" rel="noopener">Edit track.py</a><span>sources, layouts, curation</span></li>
        <li><a href=${`${raw}/README.md`} target="_blank" rel="noopener">Curation notes</a><span>what was checked and why</span></li>
      </ul>
      <h3 class="h">Licence</h3>
      <p class="muted small">Open Database License (ODbL). Geometry © OpenStreetMap contributors; measured edges from public-domain / open orthoimagery (US state programmes, IGN BD ORTHO) and lidar (USGS 3DEP, IGN LiDAR HD); corner data from Lovely-Sim-Racing plus curation.</p>`;
  }
}

// --- quality panel ------------------------------------------------------------------------
class QualityPanel extends Light {
  static properties = { track: {}, layout: {} };
  render() {
    const s = this.layout.surface;
    if (!s) return this.unmeasured();
    const pos = s.position || {}, b = pos.budget_ce95_m || {}, ref = pos.reference || {};
    const img = s.sources?.imagery || {}, tier = tierOf({ measured: true, ce95_m: s.absolute_accuracy_ce95_m });
    const parts = [["Reference", b.reference, ref.kind === "imagery" ? `${ref.name}: the imagery's own tested accuracy` : `${ref.name.startsWith("IGN") ? "IGN" : "USGS"} lidar ${ref.name}${ref.stated ? "" : " (accuracy not stated, 1 m assumed)"}`],
                   ["Registration", b.registration, pos.registration_model],
                   ["Datum", b.datum, `${pos.source_frame} → ${pos.frame} @ ${pos.epoch}`]];
    const tot2 = parts.reduce((n, p) => n + (p[1] || 0) ** 2, 0) || 1;
    const checks = (pos.checks || []).filter((c) => c.reference_agreement);
    return html`
      <div class="big-q" style="--c:${tier.color}">
        <div class="num">${(s.absolute_accuracy_ce95_m).toFixed(2)}<small> m</small></div>
        <div><span class="tier" style="--c:${tier.color}">${tier.label}</span>
          <p class="small">95% of the measured geometry is within this distance of its true position (CE95). Edge shape is precise to ${m1(s.relative_precision_m)}.</p></div>
      </div>

      <h3 class="h">Error budget <span class="muted">√(Σ²)</span></h3>
      <div class="budget">
        <div class="stack">${parts.map(([k, v], i) => html`<i class="b${i}" style="flex:${(v || 0) ** 2 / tot2}" title="${k} ${m1(v)}"></i>`)}</div>
        ${parts.map(([k, v, d], i) => html`<div class="brow"><i class="sw b${i}"></i><b>${k}</b><span class="mono">${m1(v)}</span><p>${d}</p></div>`)}
      </div>

      <h3 class="h">Edges</h3>
      <div class="seenbars">
        ${["left", "right"].map((side) => html`<div><span>${side}</span><span class="bar"><i style="width:${(s.seen_fraction?.[side] || 0) * 100}%"></i></span><b class="mono">${pct(s.seen_fraction?.[side])}</b></div>`)}
      </div>
      <p class="muted small">Share of the lap where the edge was seen in the imagery; the rest is bridged (dashed amber on the map) and flagged in the data.</p>
      <dl class="kv">
        <dt>Width</dt><dd>${m1(s.width_m?.median)} median · ${m1(s.width_m?.p05)} – ${m1(s.width_m?.p95)}</dd>
        <dt>Lap</dt><dd>${km(s.lap_length_m)} measured midline</dd>
        <dt>Measured</dt><dd>${(s.measured_at || "").slice(0, 10)} · ${s.method}</dd>
      </dl>

      <h3 class="h">Sources</h3>
      <dl class="kv">
        <dt>Imagery</dt><dd><a href=${img.url} target="_blank" rel="noopener">${img.name}</a><br>
          <span class="muted">${(img.acquisition_dates || []).join(", ")} · ${img.gsd_m ? `${img.gsd_m.map((g) => `${g} m`).join("/")} GSD` : ""} · ${img.license}</span><br>
          <span class="muted">${img.horizontal_accuracy}</span></dd>
        <dt>Position</dt><dd>${(s.sources?.reference || []).map((r) => html`<div>${r.name} <span class="muted">${r.year || ""} · ${r.horizontal_accuracy}</span></div>`)}</dd>
        <dt>Shift</dt><dd class="mono">${pos.applied_shift_m ? `E ${pos.applied_shift_m.east.toFixed(2)} m · N ${pos.applied_shift_m.north.toFixed(2)} m` : "—"}
          <span class="muted"> (registration ${pos.registration_shift_m?.east?.toFixed(2)}/${pos.registration_shift_m?.north?.toFixed(2)} + datum ${pos.datum_shift_m?.east?.toFixed(2)}/${pos.datum_shift_m?.north?.toFixed(2)})</span></dd>
        <dt>Seed</dt><dd>OpenStreetMap centerline, only to start the edge search</dd>
      </dl>
      ${checks.map((c) => html`<p class="small check">Two independent lidar surveys agree to <b>${m1(c.difference_m)}</b> (${c.reference_agreement.join(" vs ")}).</p>`)}

      ${s.selection?.candidates?.length > 1 ? html`
        <h3 class="h">Imagery chosen</h3>
        <table class="mini">
          <thead><tr><th>Source</th><th>CE95</th><th>Seen</th><th>Score</th></tr></thead>
          <tbody>${s.selection.candidates.map((c) => html`<tr class=${c.chosen ? "chosen" : ""}>
            <td>${c.imagery}${c.chosen ? " ✓" : ""}</td>
            ${c.result ? html`<td colspan="3" class="muted">${c.result.replace(/^refused: /, "refused: ")}</td>`
              : html`<td class="mono">${m1(c.absolute_accuracy_ce95_m)}</td><td class="mono">${pct(c.seen_both)}</td><td class="mono">${c.score_m}</td>`}</tr>`)}</tbody>
        </table>
        <p class="muted small">Score = CE95 + 4 m × unseen share: position and coverage in one number.</p>` : nothing}

      ${s.racing_line ? html`<h3 class="h">Racing line <span class="muted">model</span></h3>
        <dl class="kv">
          <dt>Car</dt><dd>${s.racing_line.car.name}</dd>
          <dt>Lap</dt><dd>${fmtLap(s.racing_line.lap_time_s)} · top ${Math.round(s.racing_line.top_speed_kmh)} km/h · ${km(s.racing_line.length_m)}</dd>
        </dl>
        <p class="muted small">Minimum-curvature line inside the measured edges and a quasi-steady-state lap. It gives the racing apex, braking points and each corner's character.
          ${s.racing_line.limitations}.</p>` : nothing}

      ${s.unnamed_corners?.length ? html`<h3 class="h">Unclaimed curvature peaks</h3>
        <p class="muted small">${s.unnamed_corners.length} tight bends in the measured midline match no atlas corner. They are either missing corners or second apexes; the curation notes say which.</p>` : nothing}`;
  }
  unmeasured() {
    return html`
      <div class="big-q" style="--c:var(--t-traced)">
        <div class="num">—</div>
        <div><span class="tier" style="--c:var(--t-traced)">OSM trace</span>
          <p class="small">This layout is the OpenStreetMap centerline. It has no measured edges and no stated accuracy; OSM traces at the venues checked are typically 2–10 m off.</p></div>
      </div>
      <h3 class="h">What is missing</h3>
      <ul class="plain small">
        <li>An open orthoimagery source for ${this.track.country} with a licence that allows derived geometry (ODbL).</li>
        <li>An open lidar or tested reference to position it.</li>
        <li>Corner markers are lap fractions from Lovely-Sim-Racing plus curation, not measured apexes.</li>
      </ul>
      <p class="muted small">See the <a href="#/method">method</a> for the European programmes (IGN, PNOA, PDOK…) that could be integrated next.</p>`;
  }
}

// --- lap strip ---------------------------------------------------------------------------
class LapStrip extends Light {
  static properties = { layout: {}, lap: {}, hover: {}, sel: {}, range: {}, label: {}, local: { state: true } };
  frac(e) { const r = e.currentTarget.getBoundingClientRect(); return Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)); }
  render() {
    const lo = this.layout;
    if (!lo) return nothing;
    const W = 1000, cs = corners(lo), s = lo.surface, L = s?.lap_length_m || lo.length_m;
    const x = (f) => f * W;
    const spans = (a, b) => (b >= a ? [[a, b]] : [[a, 1], [0, b]]);
    const cur = this.local ?? this.hover?.frac;
    const at = cur != null ? cs.find((c) => c.start != null && inRange(cur, c.start, c.end)) : null;
    return html`
      <div class="strip">
        <div class="strip-read">${cur != null ? html`<b class="mono">${(cur * 100).toFixed(1)}%</b> <span class="mono">${Math.round(cur * L)} m</span>
          ${at ? html`· <b>${turnCode(at)}</b> ${cornerName(at, this.label)}` : nothing}` : html`<span class="muted">Lap: hover the track or this strip · click to jump</span>`}</div>
        <svg viewBox="0 0 ${W} 46" preserveAspectRatio="none"
             @mousemove=${(e) => (this.local = this.frac(e))} @mouseleave=${() => (this.local = null)}
             @click=${(e) => this.dispatchEvent(new CustomEvent("seek", { detail: this.frac(e) }))}>
          ${svg`
          <rect x="0" y="0" width=${W} height="46" class="strip-bg"/>
          ${(this.range?.items || []).map((it, k) => it.start == null ? nothing : spans(it.start, it.end).map(([a, b]) =>
            svg`<rect x=${x(a)} y="4" width=${Math.max(0.5, x(b) - x(a))} height="8" fill=${it.color || RANGE_COLORS[k % RANGE_COLORS.length]} opacity=".85"/>`))}
          ${cs.map((c) => {
            const a = c.entry?.marker ?? c.start, b = c.exit?.marker ?? c.end;
            const sel = this.sel === c.id;
            return svg`<g class="sc ${sel ? "sel" : ""}" @click=${(e) => { e.stopPropagation(); this.dispatchEvent(new CustomEvent("pick", { detail: c.id })); }}>
              ${a != null && b != null ? spans(a, b).map(([p, q]) => svg`<rect x=${x(p)} y="16" width=${Math.max(1, x(q) - x(p))} height="14"
                   class="cr ${c.direction || ""} ${c.placement?.basis === "curvature" ? "" : "unplaced"}"/>`) : nothing}
              ${c.marker != null ? svg`<line x1=${x(c.marker)} x2=${x(c.marker)} y1="14" y2="32" class="apx"/>` : nothing}
            </g>`;
          })}
          ${s ? svg`<rect x="0" y="36" width=${W} height="3" class="seen-l"/><rect x="0" y="41" width=${W} height="3" class="seen-r"/>` : nothing}
          ${(s?.unseen_spans?.left || []).map(([a, b]) => spans(a, b).map(([p, q]) => svg`<rect x=${x(p)} y="36" width=${Math.max(0.6, x(q) - x(p))} height="3" class="unseen"/>`))}
          ${(s?.unseen_spans?.right || []).map(([a, b]) => spans(a, b).map(([p, q]) => svg`<rect x=${x(p)} y="41" width=${Math.max(0.6, x(q) - x(p))} height="3" class="unseen"/>`))}
          ${cur != null ? svg`<line x1=${x(cur)} x2=${x(cur)} y1="0" y2="46" class="cursor"/>` : nothing}`}
        </svg>
        <div class="strip-axis mono"><span>S/F</span><span>25%</span><span>50%</span><span>75%</span><span>S/F</span></div>
      </div>`;
  }
}

// --- method ----------------------------------------------------------------------------------
class AtlasMethod extends Light {
  render() {
    return html`<article class="method">
      <p class="eyebrow">Method</p>
      <h1>How a circuit gets measured</h1>
      <p class="lede">OpenStreetMap shows roughly where a lap goes. It does not show where the asphalt is, and at the venues we checked it is 2–10 m off.
        So each US circuit is measured again from open sources. Every figure keeps the budget of its own error.</p>
      <ol class="steps">
        <li><h3>Trace the edges</h3><p>Open orthoimagery is sampled along the lap: USDA NAIP, or a sharper state programme where one covers the circuit (Connecticut 2023, Indiana 2025, Texas 2021, Florida 2021).
          A self-calibrated asphalt model finds both edges. Where an edge is not visible (shadow, paved run-off, a bridge) it is bridged and flagged, never hidden.</p></li>
        <li><h3>Position them on lidar</h3><p>The imagery is registered onto lidar intensity (USGS 3DEP in the US, IGN LiDAR HD in France): grass is bright and asphalt dark in both.
          The lidar is surveyed with GNSS and ground control. Where two independent surveys exist, their agreement is recorded as a check.</p></li>
        <li><h3>Move to today's frame</h3><p>US sources are in NAD83(2011). Each result is moved to WGS 84 (G2139) ≈ ITRF2014 at epoch 2026.0, the frame a GNSS receiver reports today. That step is 0.9–1.6 m, and before this work it was silently ignored.</p></li>
        <li><h3>Place the corners</h3><p>The curvature of the measured midline gives each corner a turn-in line, an apex on the inside edge and an exit line.
          The midline becomes the lap: markers are fractions of it, measured from the start/finish line.</p></li>
        <li><h3>Drive a model lap</h3><p>A minimum-curvature racing line is fitted inside the measured edges and a generic GT3 car is run on it.
          That gives each corner its racing apex, braking point, minimum speed and character (kink, high speed, medium, slow). A complex runs from 0.5 s before braking to 0.5 s after full throttle.
          This is a model, stated as one: no elevation, no kerbs.</p></li>
        <li><h3>Choose the best source</h3><p>Every imagery source that covers the circuit is measured. The one with the lowest score wins, where score = CE95 + 4 m × unseen share. The comparison is published with the data.</p></li>
      </ol>
      <h2>Accuracy tiers</h2>
      <div class="legend">${TIERS.map((t) => html`<div><span class="tier" style="--c:${t.color}">${t.label}</span><p>${t.blurb}</p></div>`)}</div>
      <h2>What the numbers mean</h2>
      <p><b>CE95</b> is the radius that contains 95% of position errors. It is computed as √(reference² + registration² + datum²).
        <b>Relative precision</b> is how well the edge <i>shape</i> is known: it matters for widths and racing lines, independent of where the whole circuit sits.</p>
      <p>Most 3DEP lidar surveys do not state a horizontal accuracy. Where they don't, 1.0 m CE95 is assumed and flagged, so a measured circuit rarely claims better than about 1 m unless the imagery has its own tested accuracy (Connecticut: 0.16 m on 179 checkpoints).</p>
      <h2>Never used</h2>
      <p>No commercial basemap is ever traced: Esri, Google and Bing imagery appear here for viewing only. No private telemetry or GPS logs are used.</p>
      <p><a href=${`${GH}/blob/${BRANCH}/docs/GEOMETRY.md`} target="_blank" rel="noopener">Full specification (GEOMETRY.md)</a> ·
         <a href=${`${GH}/blob/${BRANCH}/docs/SOURCES.md`} target="_blank" rel="noopener">Sources and licences (SOURCES.md)</a></p>
    </article>`;
  }
}

customElements.define("atlas-app", AtlasApp);
customElements.define("atlas-home", AtlasHome);
customElements.define("track-page", TrackPage);
customElements.define("quality-panel", QualityPanel);
customElements.define("lap-strip", LapStrip);
customElements.define("atlas-method", AtlasMethod);
