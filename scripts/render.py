#!/usr/bin/env python3
"""Render a track infographic (SVG -> PNG) from track-atlas data.

Pure data-driven: the track silhouette is the real OSM raceway geometry, the
corner dots sit at their real coordinates, and every fact comes from track.json.
Nothing is invented.

Usage:
    python scripts/render.py circuit-de-la-sarthe
    python scripts/render.py silverstone --layout gp --out /tmp/sil.svg
    python scripts/render.py --all

PNG export is attempted via cairosvg, then rsvg-convert, then Inkscape.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import TRACKS, load_source, track_dir  # noqa: E402
from lib.osm import way_coords, trace_loop, loop_length_m  # noqa: E402

# Ways that aren't part of the main circuit surface we want to draw.
DROP_WAY = re.compile(
    r"bugatti|prost|c\.?i\.?k|amateur|\bkart\b|karting|\bmoto\b|penalty|"
    r"safety car|long lap|pit ?lane|pit ?entry|pit ?exit",
    re.I,
)

# Per-track accent palette (background is always dark).
ACCENTS = {
    "circuit-de-la-sarthe": "#e6007e",   # Le Mans magenta/pink
    "silverstone": "#1e9bd7",            # British racing blue
    "_default": "#ff5a36",
}

W, H = 1600, 1000
MARGIN = 90


def project(coords, lat0):
    """Equirectangular lon/lat -> planar metres-ish, aspect-preserving."""
    k = math.cos(math.radians(lat0))
    return [(c[0] * k, c[1]) for c in coords]


def fit_transform(all_xy, w, h, margin, panel_w):
    xs = [p[0] for p in all_xy]
    ys = [p[1] for p in all_xy]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    draw_w = w - panel_w - 2 * margin
    draw_h = h - 2 * margin
    span_x = (maxx - minx) or 1e-9
    span_y = (maxy - miny) or 1e-9
    s = min(draw_w / span_x, draw_h / span_y)
    # center within the drawing area (left of the panel)
    ox = margin + (draw_w - span_x * s) / 2
    oy = margin + (draw_h - span_y * s) / 2

    def tf(x, y):
        px = ox + (x - minx) * s
        py = oy + (maxy - y) * s   # flip Y (north up)
        return px, py

    return tf


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(slug: str, layout_id: str | None) -> str:
    tdir = track_dir(slug)
    track = json.loads((tdir / "track.json").read_text())
    osm = json.loads((tdir / "raw" / "osm.json").read_text())
    layout = (next((l for l in track["layouts"] if l["id"] == layout_id), None)
              if layout_id else track["layouts"][0])
    lid = layout["id"]
    accent = ACCENTS.get(slug, ACCENTS["_default"])
    lat0 = track["location"]["lat"]
    panel_x_left = MARGIN + 470  # right edge of the title text band (top-left)

    # --- gather geometry ---
    # Primary: stitch the real OSM raceway geometry into a continuous loop,
    # ordered by lap fraction. This keeps actual chicane/corner shapes. Falls
    # back to a smooth spline through corner apexes only if tracing fails.
    corners = [c for c in layout.get("corners", []) if "location" in c]
    corners_ordered = sorted(corners, key=lambda c: c["number"])

    traced = trace_loop(osm.get("elements", []), layout.get("corners", []))
    use_real = traced is not None and len(traced) >= 8

    all_lonlat = list(traced) if use_real else []
    all_lonlat += [c["location"] for c in corners]
    all_xy = project(all_lonlat, lat0)
    tf = fit_transform(all_xy, W, H, MARGIN, panel_w=470)

    if use_real:
        outline_xy = [tf(*p) for p in project(traced, lat0)]
    else:
        outline_xy = [tf(*p) for p in project([c["location"] for c in corners_ordered], lat0)]
    loop_pts = [tf(*p) for p in project([c["location"] for c in corners_ordered], lat0)]

    # centroid for radial label placement
    cx = sum(p[0] for p in all_xy) / len(all_xy)
    cy = sum(p[1] for p in all_xy) / len(all_xy)
    cx, cy = tf(cx, cy)

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
               f'viewBox="0 0 {W} {H}" font-family="Helvetica, Arial, sans-serif">')
    # defs: gradients + glow
    svg.append(f'''<defs>
      <radialGradient id="bg" cx="38%" cy="34%" r="85%">
        <stop offset="0%" stop-color="#1b2030"/>
        <stop offset="55%" stop-color="#12151f"/>
        <stop offset="100%" stop-color="#0a0c12"/>
      </radialGradient>
      <linearGradient id="accent" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="{accent}"/>
        <stop offset="100%" stop-color="#ffffff"/>
      </linearGradient>
      <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
        <feGaussianBlur stdDeviation="6" result="b"/>
        <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
    </defs>''')
    svg.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
    # faint grid
    for gx in range(0, W, 56):
        svg.append(f'<line x1="{gx}" y1="0" x2="{gx}" y2="{H}" stroke="#ffffff" stroke-opacity="0.025"/>')
    for gy in range(0, H, 56):
        svg.append(f'<line x1="0" y1="{gy}" x2="{W}" y2="{gy}" stroke="#ffffff" stroke-opacity="0.025"/>')

    # --- track ribbon ---
    def catmull_rom_closed(pts):
        """Closed smooth curve through pts (fallback when no real geometry)."""
        n = len(pts)
        if n < 3:
            return "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        d = [f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"]
        for i in range(n):
            p0 = pts[(i - 1) % n]
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            p3 = pts[(i + 2) % n]
            c1x = p1[0] + (p2[0] - p0[0]) / 6
            c1y = p1[1] + (p2[1] - p0[1]) / 6
            c2x = p2[0] - (p3[0] - p1[0]) / 6
            c2y = p2[1] - (p3[1] - p1[1]) / 6
            d.append(f"C {c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {p2[0]:.1f},{p2[1]:.1f}")
        d.append("Z")
        return " ".join(d)

    if use_real:
        # Real OSM geometry: draw as a polyline (preserves chicanes), close it.
        loop_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in outline_xy) + " Z"
    else:
        loop_d = catmull_rom_closed(loop_pts)

    # outer dark casing
    svg.append(f'<path d="{loop_d}" fill="none" stroke="#000000" stroke-opacity="0.5" '
               f'stroke-width="13" stroke-linejoin="round" stroke-linecap="round"/>')
    # asphalt
    svg.append(f'<path d="{loop_d}" fill="none" stroke="#39404f" '
               f'stroke-width="8.5" stroke-linejoin="round" stroke-linecap="round"/>')
    # bright racing line
    svg.append(f'<path d="{loop_d}" fill="none" stroke="#e7edf8" '
               f'stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>')
    # accent centerline glow
    svg.append(f'<path d="{loop_d}" fill="none" stroke="{accent}" stroke-opacity="0.55" '
               f'stroke-width="1.2" stroke-linejoin="round" filter="url(#glow)"/>')

    # --- start/finish ---
    sf = None
    if corners:
        sfc = min(corners, key=lambda c: c.get("marker", 1))
        sx, sy = tf(*project([sfc["location"]], lat0)[0])
        sf = (sx, sy)
        svg.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="13" fill="none" '
                   f'stroke="#ffffff" stroke-width="3"/>')
        svg.append(f'<rect x="{sx-4:.1f}" y="{sy-22:.1f}" width="8" height="18" fill="#ffffff"/>')

    # --- corners: dots first, then decluttered radial labels ---
    def resolve(c):
        n = c.get("names", {})
        return n.get(layout.get("name_default", "colloquial")) or n.get("colloquial") \
            or n.get("official") or n.get("numbered")

    dot_pos = {}
    for c in corners:
        px, py = tf(*project([c["location"]], lat0)[0])
        dot_pos[c["number"]] = (px, py)
        svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="7" fill="{accent}" '
                   f'stroke="#0a0c12" stroke-width="2.5" filter="url(#glow)"/>')
        svg.append(f'<text x="{px:.1f}" y="{py+3.4:.1f}" font-size="9" font-weight="700" '
                   f'fill="#0a0c12" text-anchor="middle">{c["number"]}</text>')

    # Build label set: one entry per complex (anchored at its mid corner) plus
    # one per solo corner.
    seen_complex = {}
    labels = []  # dict: dot(x,y), text, side, desired_y
    for c in corners:
        comp = c.get("complex")
        if comp:
            if comp in seen_complex:
                continue
            seen_complex[comp] = True
            members = [x for x in corners if x.get("complex") == comp]
            mid = members[len(members) // 2]
            px, py = dot_pos[mid["number"]]
            text = comp
        else:
            px, py = dot_pos[c["number"]]
            text = resolve(c)
        vx, vy = px - cx, py - cy
        d = math.hypot(vx, vy) or 1
        lx = px + vx / d * 52
        ly = py + vy / d * 52
        side = "right" if lx >= px else "left"
        labels.append({"dot": (px, py), "text": text, "side": side,
                       "lx": lx, "ly": ly})

    # Declutter vertically within each side; keep left-side labels clear of the
    # title zone (top-left).
    GAP = 30
    title_zone_y = 162
    for side in ("left", "right"):
        grp = sorted([l for l in labels if l["side"] == side], key=lambda l: l["ly"])
        prev = -1e9
        for l in grp:
            y = l["ly"]
            if side == "left" and l["lx"] < panel_x_left and y < title_zone_y:
                y = title_zone_y
            if y - prev < GAP:
                y = prev + GAP
            l["ly"] = y
            prev = y

    for l in labels:
        px, py = l["dot"]
        anchor = "start" if l["side"] == "right" else "end"
        tx = l["lx"] + (8 if anchor == "start" else -8)
        svg.append(f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{l["lx"]:.1f}" y2="{l["ly"]:.1f}" '
                   f'stroke="{accent}" stroke-opacity="0.45" stroke-width="1.3"/>')
        svg.append(f'<text x="{tx:.1f}" y="{l["ly"]+4:.1f}" '
                   f'font-size="15" font-weight="600" fill="#eef2fb" '
                   f'text-anchor="{anchor}">{esc(l["text"])}</text>')

    # --- title block ---
    svg.append(f'<text x="{MARGIN}" y="64" font-size="20" letter-spacing="5" '
               f'fill="{accent}" font-weight="700">TRACK ATLAS</text>')
    svg.append(f'<text x="{MARGIN}" y="108" font-size="42" font-weight="800" '
               f'fill="#ffffff">{esc(track["name"]).upper()}</text>')
    aka = ", ".join(track.get("aka", [])[:2])
    if aka:
        svg.append(f'<text x="{MARGIN}" y="136" font-size="16" fill="#9aa6bd">'
                   f'{esc(aka)}</text>')

    # --- stats panel (right) ---
    panel_x = W - 430
    py0 = 200
    svg.append(f'<rect x="{panel_x}" y="{py0}" width="360" height="{H-py0-MARGIN}" '
               f'rx="16" fill="#ffffff" fill-opacity="0.04" stroke="{accent}" '
               f'stroke-opacity="0.5"/>')

    def fmt_len(m):
        return f"{m/1000:.3f} km" if m else "—"

    direction = layout.get("direction", "—")
    n_named = sum(1 for c in layout.get("corners", []) if c.get("names", {}).get("colloquial") or c.get("names", {}).get("official"))
    countries = {"FR": "France", "GB": "United Kingdom", "DE": "Germany",
                 "IT": "Italy", "BE": "Belgium", "ES": "Spain", "US": "USA",
                 "JP": "Japan", "AU": "Australia", "NL": "Netherlands"}
    country = countries.get(track.get("country", ""), track.get("country", "—"))
    locality = track["location"].get("locality") or \
        f'{track["location"]["lat"]:.3f}, {track["location"]["lon"]:.3f}'
    stats = [
        ("LAYOUT", layout["name"]),
        ("LENGTH", fmt_len(layout.get("length_m"))),
        ("CORNERS", str(len(layout.get("corners", [])))),
        ("NAMED CORNERS", str(n_named)),
        ("DIRECTION", direction.capitalize()),
        ("SECTORS", str(len(layout.get("sectors", [])))),
        ("COUNTRY", country),
        ("LOCATION", locality),
    ]
    ty = py0 + 50
    for k, v in stats:
        svg.append(f'<text x="{panel_x+28}" y="{ty}" font-size="13" letter-spacing="2" '
                   f'fill="#8794ab">{esc(k)}</text>')
        svg.append(f'<text x="{panel_x+28}" y="{ty+26}" font-size="22" font-weight="700" '
                   f'fill="#eef2fb">{esc(str(v))}</text>')
        ty += 70

    # complexes chips
    comps = []
    for c in layout.get("corners", []):
        cc = c.get("complex")
        if cc and cc not in comps:
            comps.append(cc)
    if comps:
        svg.append(f'<text x="{panel_x+28}" y="{ty}" font-size="13" letter-spacing="2" '
                   f'fill="#8794ab">COMPLEXES</text>')
        ty += 22
        chip_y = ty
        chip_x = panel_x + 28
        for cc in comps:
            wch = 14 + len(cc) * 8
            if chip_x + wch > panel_x + 350:
                chip_x = panel_x + 28
                chip_y += 34
            svg.append(f'<rect x="{chip_x}" y="{chip_y-16}" width="{wch}" height="24" rx="12" '
                       f'fill="{accent}" fill-opacity="0.16" stroke="{accent}" stroke-opacity="0.5"/>')
            svg.append(f'<text x="{chip_x+wch/2:.0f}" y="{chip_y+1}" font-size="12" '
                       f'fill="#eef2fb" text-anchor="middle">{esc(cc)}</text>')
            chip_x += wch + 10

    # footer / provenance
    svg.append(f'<text x="{MARGIN}" y="{H-34}" font-size="12" '
               f'fill="#566177">Geometry © OpenStreetMap contributors (ODbL) · '
               f'corner data: Lovely-Sim-Racing + curated · track-atlas</text>')
    # start/finish legend
    if sf:
        svg.append(f'<text x="{MARGIN}" y="{H-58}" font-size="12" fill="#8794ab">'
                   f'⚑ start / finish</text>')

    svg.append('</svg>')
    return "\n".join(svg)


def rasterize(svg_path: Path, png_path: Path) -> bool:
    # 1. cairosvg via uv
    try:
        subprocess.run(
            ["uv", "run", "--with", "cairosvg", "python", "-c",
             f"import cairosvg; cairosvg.svg2png(url='{svg_path}', write_to='{png_path}', "
             f"output_width={W*2}, output_height={H*2})"],
            check=True, capture_output=True, timeout=180)
        return png_path.exists()
    except Exception:
        pass
    for cmd in (["rsvg-convert", "-w", str(W*2), "-h", str(H*2), "-o", str(png_path), str(svg_path)],
                ["inkscape", str(svg_path), "--export-type=png", f"--export-filename={png_path}",
                 "-w", str(W*2)]):
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=180)
            if png_path.exists():
                return True
        except Exception:
            continue
    return False


def render(slug: str, layout_id: str | None, out: Path | None) -> Path:
    tdir = track_dir(slug)
    out_dir = tdir / "render"
    out_dir.mkdir(exist_ok=True)
    svg = build_svg(slug, layout_id)
    svg_path = out or (out_dir / f"{slug}.svg")
    svg_path.write_text(svg)
    png_path = svg_path.with_suffix(".png")
    ok = rasterize(svg_path, png_path)
    print(f"[{slug}] SVG -> {svg_path}" + (f"  PNG -> {png_path}" if ok else "  (PNG export unavailable)"))
    return png_path if ok else svg_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--layout", default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    slugs = ([p.name for p in TRACKS.iterdir() if (p / "track.json").exists()]
             if args.all else [args.slug])
    if not slugs or slugs == [None]:
        ap.error("give a slug or --all")
    for slug in slugs:
        render(slug, args.layout, args.out if not args.all else None)


if __name__ == "__main__":
    main()
