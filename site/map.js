/* Track Atlas site: the Leaflet map of one layout. */
import L from "https://esm.sh/leaflet@1.9.4";
import { Lap, cornerName, corners, exportImageUrl, turnCode } from "./lib.js";

const ll = (c) => [c[1], c[0]];
const COL = { edge: "#f4f1e8", unseen: "#ffb020", entry: "#34d399", exit: "#f43f5e", apex: "#ffd84d",
              mid: "#7dd3fc", brake: "#fb923c", sf: "#ffffff", sector: "#c4b5fd", pit: "#94a3b8", outline: "#7dd3fc" };
const SPEED_RAMP = [[80, [239, 68, 68]], [130, [245, 158, 11]], [180, [250, 204, 21]], [230, [52, 211, 153]], [280, [56, 189, 248]]];
export const speedColor = (v) => {
  const r = SPEED_RAMP;
  if (v <= r[0][0]) return `rgb(${r[0][1]})`;
  for (let k = 1; k < r.length; k++) if (v <= r[k][0]) {
    const t = (v - r[k - 1][0]) / (r[k][0] - r[k - 1][0]);
    return `rgb(${r[k - 1][1].map((c, j) => Math.round(c + (r[k][1][j] - c) * t))})`;
  }
  return `rgb(${r[r.length - 1][1]})`;
};
export const RANGE_COLORS = ["#7dd3fc", "#fbbf24", "#c084fc", "#34d399", "#fb7185", "#60a5fa", "#a3e635",
                             "#f97316", "#22d3ee", "#e879f9", "#facc15", "#94a3b8"];

/** The orthophoto the edges were measured on, moved by the recorded registration + datum step. */
const SourceImagery = L.Layer.extend({
  initialize(service, shift, opts) { this.service = service; this.shift = shift || { east: 0, north: 0 }; L.setOptions(this, opts); },
  onAdd(map) { this._map = map; map.on("moveend", this._update, this); this._update(); },
  onRemove(map) { map.getContainer().classList.remove("img-loading"); map.off("moveend", this._update, this); this._img?.remove(); this._img = null; },
  _update() {
    const map = this._map, size = map.getSize(), b = map.getBounds();
    const crs = L.CRS.EPSG3857, sw = crs.project(b.getSouthWest()), ne = crs.project(b.getNorthEast());
    const k = 1 / Math.cos((b.getCenter().lat * Math.PI) / 180);   // ground metres -> mercator metres
    const dx = this.shift.east * k, dy = this.shift.north * k;
    // the service frame is where the atlas frame minus the shift is
    const url = exportImageUrl(this.service, [sw.x - dx, sw.y - dy, ne.x - dx, ne.y - dy],
                               Math.min(size.x * 2, 4000), Math.min(size.y * 2, 4000));
    const next = L.imageOverlay(url, b, { opacity: 1, interactive: false, className: "src-imagery" });
    const box = map.getContainer();
    box.classList.add("img-loading");
    const done = () => { if (this._img && this._img !== next) this._img.remove(); this._img = next; box.classList.remove("img-loading"); };
    next.once("load", done).once("error", () => box.classList.remove("img-loading"));
    next.addTo(map);
    next.bringToBack();
  },
});

export class TrackMap {
  constructor(el, { onHover, onCorner } = {}) {
    this.map = L.map(el, { zoomControl: false, attributionControl: true, preferCanvas: false, zoomSnap: 0.25 });
    L.control.zoom({ position: "bottomright" }).addTo(this.map);
    L.control.scale({ position: "bottomleft", imperial: false, maxWidth: 160 }).addTo(this.map);
    this.bases = {
      esri: L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 21, maxNativeZoom: 19, attribution: "Imagery © Esri (view only, never traced)" }),
      dark: L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 21, maxNativeZoom: 16, attribution: "Basemap © Esri, HERE, Garmin, © OpenStreetMap contributors" }),
    };
    this.base = null;
    this.groups = { surface: L.layerGroup(), lines: L.layerGroup(), labels: L.layerGroup(), ranges: L.layerGroup(),
                    points: L.layerGroup(), focus: L.layerGroup() };
    for (const g of Object.values(this.groups)) g.addTo(this.map);
    this.onHover = onHover; this.onCorner = onCorner;
    this.cursor = L.circleMarker([0, 0], { radius: 5, color: "#fff", weight: 2, fillColor: "#0b0f14", fillOpacity: 1, interactive: false });
    this.map.on("mousemove", (e) => this._hover(e));
    this.map.on("mouseout", () => { this.cursor.remove(); this.onHover?.(null); });
  }

  destroy() { this.map.remove(); }

  setBase(id) {
    if (this.base) this.map.removeLayer(this.base);
    this.base = id === "source" && this.sourceLayer ? this.sourceLayer : this.bases[id] || this.bases.dark;
    this.base.addTo(this.map);
    this.baseId = id;
    this.map.getContainer().dataset.base = id;
  }

  load(track, layout, outlineGj, surfaceGj) {
    this.track = track; this.layout = layout; this.surface = surfaceGj;
    const outline = outlineGj.features.find((f) => f.properties.role === "outline");
    this.lap = new Lap(outline.geometry.coordinates);
    const s = layout.surface;
    const svc = s?.sources?.imagery?.url;
    this.sourceLayer = svc ? new SourceImagery(svc, s.position?.applied_shift_m,
      { attribution: `${s.sources.imagery.name} (${s.sources.imagery.license})` }) : null;
    if (this.sourceLayer) this.sourceLayer.getAttribution = () => `${s.sources.imagery.name}`;
    this.map.fitBounds(L.latLngBounds(this.lap.c.map(ll)), { paddingTopLeft: [30, 110], paddingBottomRight: [30, 190] });
    this.setBase(this.baseId && (this.baseId !== "source" || this.sourceLayer) ? this.baseId : (this.sourceLayer ? "source" : "dark"));
    this.draw();
  }

  draw(opts = this.opts || {}) {
    this.opts = opts;
    const { labels = true, labelLayer = "numbered", show = {} } = opts;
    const g = this.groups;
    Object.values(g).forEach((x) => x.clearLayers());
    const feats = this.surface?.features || [];
    const by = (role) => feats.filter((f) => f.properties.role === role);
    const on = (k) => show[k] !== false;

    if (this.surface) {
      if (on("surface")) for (const f of by("surface"))
        L.geoJSON(f, { style: { stroke: false, fillColor: "#ffffff", fillOpacity: this.baseId === "dark" ? 0.12 : 0.06 }, interactive: false }).addTo(g.surface);
      if (on("pit")) for (const f of by("pit_lane"))
        L.geoJSON(f, { style: { color: COL.pit, weight: 2, dashArray: "2 5", opacity: 0.9 }, interactive: false }).addTo(g.surface);
      if (on("edges")) {
        for (const side of ["edge_left", "edge_right"]) for (const f of by(side))
          L.geoJSON(f, { style: { color: COL.edge, weight: 2, opacity: 0.95 }, interactive: false }).addTo(g.surface);
        for (const f of by("edge_unseen"))
          L.geoJSON(f, { style: { color: COL.unseen, weight: 3.5, opacity: 1, dashArray: "4 4", lineCap: "butt" },
            interactive: false }).addTo(g.surface);
      }
      if (on("midline")) for (const f of by("midline"))
        L.geoJSON(f, { style: { color: COL.mid, weight: 1, opacity: 0.7, dashArray: "6 6" }, interactive: false }).addTo(g.surface);
      if (on("racing")) for (const f of by("racing_line")) {
        const c = f.geometry.coordinates.map(ll), v = f.properties.speed_kmh;
        L.polyline([...c, c[0]], { color: "#000", weight: 6, opacity: 0.35, interactive: false }).addTo(g.surface);
        // runs of one 10 km/h bucket, drawn as one polyline each
        let run = [c[0]], bucket = Math.round(v[0] / 10);
        for (let k = 1; k <= c.length; k++) {
          const i = k % c.length, b = Math.round(v[i] / 10);
          run.push(c[i]);
          if (b !== bucket || k === c.length) {
            L.polyline(run, { color: speedColor(bucket * 10), weight: 3, opacity: 1, interactive: false }).addTo(g.surface);
            run = [c[i]]; bucket = b;
          }
        }
      }
      if (on("brakes")) for (const f of by("brake_point")) this._line(f, COL.brake, 3, g.lines, "2 3");
      if (on("crossings")) {
        for (const f of by("corner_entry")) this._line(f, COL.entry, 3, g.lines);
        for (const f of by("corner_exit")) this._line(f, COL.exit, 3, g.lines);
      }
      if (on("sectors")) for (const f of by("sector_boundary")) this._line(f, COL.sector, 3, g.lines, "3 3");
      for (const f of by("start_finish")) this._line(f, COL.sf, 5, g.lines, null, "sf-line");
      for (const f of [...by("pit_entry"), ...by("pit_exit")]) this._line(f, COL.pit, 3, g.lines);
      if (on("apexes")) for (const f of by("geometric_apex"))
        L.circleMarker(ll(f.geometry.coordinates), { radius: 3, color: COL.apex, weight: 1.5, fill: false, opacity: 0.8, interactive: false }).addTo(g.lines);
      if (on("apexes")) for (const f of by("apex"))
        L.circleMarker(ll(f.geometry.coordinates), { radius: 4.5, color: "#1a1300", weight: 1.5, fillColor: COL.apex, fillOpacity: 1, interactive: false }).addTo(g.lines);
    } else {
      L.polyline(this.lap.c.map(ll), { color: COL.outline, weight: 3, opacity: 0.95, interactive: false }).addTo(g.surface);
    }

    if (labels) for (const c of corners(this.layout)) {
      const at = c.apex?.location || c.location || (c.marker != null ? this.lap.at(c.marker) : null);
      if (!at) continue;
      const placed = c.placement?.basis === "curvature";
      const icon = L.divIcon({ className: "", iconSize: null,
        html: `<div class="pin ${placed ? "" : "pin-unplaced"} ${c.direction || ""}" title="${cornerName(c, labelLayer)}">${turnCode(c)}</div>` });
      L.marker(ll(at), { icon, keyboard: false, riseOnHover: true }).on("click", () => this.onCorner?.(c.id)).addTo(g.labels);
    }
    this.drawRanges(this.rangeSpec);
  }

  _line(f, color, weight, group, dash = null, className = "") {
    const coords = f.geometry.coordinates.map(ll);
    if (className === "sf-line") L.polyline(coords, { color: "#000", weight: weight + 3, opacity: 0.8, interactive: false }).addTo(group);
    L.polyline(coords, { color, weight, opacity: 1, dashArray: dash, lineCap: "butt", interactive: false, className }).addTo(group);
  }

  /** spec: {items: [{start, end, label}], colorBy: index} or null */
  drawRanges(spec) {
    this.rangeSpec = spec;
    const g = this.groups.ranges;
    g.clearLayers();
    if (!spec) return;
    spec.items.forEach((it, k) => {
      if (it.start == null || it.end == null) return;
      const color = it.color || RANGE_COLORS[k % RANGE_COLORS.length];
      L.polyline(this.lap.slice(it.start, it.end).map(ll), { color: "#000", weight: 9, opacity: 0.35, interactive: false }).addTo(g);
      L.polyline(this.lap.slice(it.start, it.end).map(ll), { color, weight: 5, opacity: 0.9, lineCap: "butt" })
        .bindTooltip(it.label || it.id, { sticky: true, className: "tip" }).addTo(g);
    });
  }

  focusCorner(c) {
    const g = this.groups.focus;
    g.clearLayers();
    if (!c) return;
    const pts = [];
    if (c.entry?.line) pts.push(...c.entry.line.map(ll));
    if (c.exit?.line) pts.push(...c.exit.line.map(ll));
    if (c.start != null && c.end != null) {
      const seg = this.lap.slice(c.start, c.end).map(ll);
      pts.push(...seg);
      L.polyline(seg, { color: "#fff", weight: 14, opacity: 0.14, interactive: false }).addTo(g);
    }
    const at = c.apex?.location || c.location;
    if (at) {
      pts.push(ll(at));
      L.circleMarker(ll(at), { radius: 13, color: "#fff", weight: 2, fill: false, interactive: false, className: "pulse" }).addTo(g);
    }
    if (pts.length) this.map.flyToBounds(L.latLngBounds(pts), { padding: [90, 90], maxZoom: 19, duration: 0.6 });
  }

  focusFraction(f) {
    const p = this.lap.at(f);
    this.map.flyTo(ll(p), Math.max(this.map.getZoom(), 17), { duration: 0.5 });
  }

  fit() { this.map.flyToBounds(L.latLngBounds(this.lap.c.map(ll)), { paddingTopLeft: [30, 110], paddingBottomRight: [30, 190], duration: 0.5 }); }

  _hover(e) {
    if (!this.lap) return;
    const p = [e.latlng.lng, e.latlng.lat];
    const { frac, dist_m } = this.lap.project(p);
    if (dist_m > 60) { this.cursor.remove(); this.onHover?.(null); return; }
    this.cursor.setLatLng(ll(this.lap.at(frac))).addTo(this.map);
    this.onHover?.({ frac, dist_m, lonlat: p });
  }
}
