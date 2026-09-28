/* Track Atlas site: data helpers shared by the pages (no DOM). */

export const REPO = "tobi/track-atlas";
export const BRANCH = "main";
export const GH = `https://github.com/${REPO}`;

// Accuracy tiers: what a consumer can do with the geometry.
export const TIERS = [
  { id: "survey", label: "Survey grade", max: 0.5, color: "var(--t-survey)",
    blurb: "≤ 0.5 m CE95: tested orthoimagery. Good enough for racing lines and apex positions." },
  { id: "measured", label: "Measured", max: 1.5, color: "var(--t-measured)",
    blurb: "≤ 1.5 m CE95: edges measured on open imagery and registered to USGS lidar." },
  { id: "coarse", label: "Measured, coarse", max: Infinity, color: "var(--t-coarse)",
    blurb: "Measured, but the budget is above 1.5 m." },
  { id: "traced", label: "OSM trace", max: null, color: "var(--t-traced)",
    blurb: "OpenStreetMap centerline only: no edges, no stated accuracy (typically 2–10 m)." },
];

export function tierOf(summary) {
  if (!summary?.measured || summary.ce95_m == null) return TIERS[3];
  return TIERS.find((t) => t.max != null && summary.ce95_m <= t.max);
}

export const esc = (s) => String(s ?? "");
export const km = (m) => (m ? `${(m / 1000).toFixed(3)} km` : "—");
export const m1 = (x) => (x == null ? "—" : `${Number(x).toFixed(x < 10 ? 2 : 1)} m`);
export const pct = (x) => (x == null ? "—" : `${Math.round(x * 100)}%`);

export const FLAGS = (cc) => cc && cc.length === 2
  ? String.fromCodePoint(...[...cc.toUpperCase()].map((c) => 0x1f1a5 + c.charCodeAt(0))) : "";

// --- track.json access ---------------------------------------------------------
export const pointLayer = (lo, id) => (lo?.point_layers || []).find((l) => l.id === id) || { items: [] };
export const rangeLayer = (lo, id) => (lo?.range_layers || []).find((l) => l.id === id) || { items: [] };
export const corners = (lo) => (lo?.point_layers || []).find((l) => l.kind === "corners")?.items || [];

export function cornerName(c, layer) {
  const n = c.labels || {};
  return n[layer] || n.numbered || c.label || c.id;
}

export function turnCode(c) {
  return c.code ? `T${c.code}` : c.id.toUpperCase();
}

// --- lap geometry ----------------------------------------------------------------
const R = 6371008.8;
export function hav(a, b) {
  const p1 = (a[1] * Math.PI) / 180, p2 = (b[1] * Math.PI) / 180;
  const dp = p2 - p1, dl = ((b[0] - a[0]) * Math.PI) / 180;
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** A closed lap polyline with arc-length lookups by lap fraction. */
export class Lap {
  constructor(coords) {
    this.c = coords;
    this.cum = [0];
    for (let i = 1; i < coords.length; i++) this.cum.push(this.cum[i - 1] + hav(coords[i - 1], coords[i]));
    this.total = this.cum[this.cum.length - 1] || 1;
  }
  at(frac) {
    const d = (((frac % 1) + 1) % 1) * this.total;
    let lo = 0, hi = this.cum.length - 1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (this.cum[mid] <= d) lo = mid; else hi = mid; }
    const seg = this.cum[hi] - this.cum[lo] || 1, t = (d - this.cum[lo]) / seg;
    const a = this.c[lo], b = this.c[hi];
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
  }
  /** Coordinates from fraction a to b in driving direction (wraps past the line). */
  slice(a, b) {
    if (b < a) return [...this.slice(a, 1), ...this.slice(0, b).slice(1)];
    const da = a * this.total, db = Math.min(b, 1) * this.total;
    const out = [this.at(a)];
    for (let i = 0; i < this.c.length; i++) if (this.cum[i] > da && this.cum[i] < db) out.push(this.c[i]);
    out.push(this.at(Math.min(b, 1 - 1e-9)));
    return out;
  }
  /** Lap fraction of the nearest point to [lon, lat]. */
  project(p) {
    let best = [Infinity, 0];
    const k = Math.cos((p[1] * Math.PI) / 180);
    for (let i = 1; i < this.c.length; i++) {
      const a = this.c[i - 1], b = this.c[i];
      const ax = (a[0] - p[0]) * k, ay = a[1] - p[1], bx = (b[0] - p[0]) * k, by = b[1] - p[1];
      const dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy || 1e-18;
      const t = Math.max(0, Math.min(1, -(ax * dx + ay * dy) / L));
      const d = (ax + dx * t) ** 2 + (ay + dy * t) ** 2;
      if (d < best[0]) best = [d, (this.cum[i - 1] + (this.cum[i] - this.cum[i - 1]) * t) / this.total, Math.sqrt(d) * 111320];
    }
    return { frac: best[1], dist_m: best[2] };
  }
}

export const inRange = (f, a, b) => (a <= b ? f >= a && f <= b : f >= a || f <= b);

// --- ArcGIS ImageServer export (the source orthophoto, for viewing) ---------------
export function exportImageUrl(service, bbox3857, w, h, wmsLayer = null) {
  if (wmsLayer) {   // OGC WMS 1.3.0 (IGN Géoplateforme)
    const q = new URLSearchParams({ SERVICE: "WMS", VERSION: "1.3.0", REQUEST: "GetMap", LAYERS: wmsLayer,
      STYLES: "", CRS: "EPSG:3857", BBOX: bbox3857.join(","), WIDTH: w, HEIGHT: h, FORMAT: "image/jpeg" });
    return `${service}?${q}`;
  }
  const q = new URLSearchParams({ bbox: bbox3857.join(","), bboxSR: "3857", imageSR: "3857",
    size: `${w},${h}`, format: "jpg", bandIds: "0,1,2", f: "image" });
  return `${service}/exportImage?${q}`;
}

/** "Lakeville, Connecticut", "Connecticut", "US" -> "Lakeville, Connecticut, US" */
export const place = (...parts) => {
  const xs = parts.filter(Boolean);
  return xs.filter((p, i) => !xs.slice(0, i).some((q) => q.includes(p))).join(", ");
};
