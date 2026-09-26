#!/usr/bin/env python3
"""Assemble the static site's data next to site/ (stdlib only; CI runs it too).

Writes (all gitignored, rebuilt on every deploy):
  site/tracks.jsonl                      the dataset, as committed
  site/geojson/<slug>_<layout>.geojson   layout outline + points
  site/geojson/<slug>_<layout>.surface.geojson   measured surface (edges, lines, apexes)
  site/atlas.json                        the home page index: per track a small
                                         outline silhouette and per layout its
                                         quality summary

Usage:
    uv run --no-project python scripts/build_site.py
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SILHOUETTE_POINTS = 160


def _silhouette(coords: list[list[float]]) -> list[list[float]]:
    """The outline in a 0..100 box (north up, equal scale), ~SILHOUETTE_POINTS points."""
    if len(coords) < 3:
        return []
    lat0 = sum(c[1] for c in coords) / len(coords)
    k = math.cos(math.radians(lat0))
    xy = [(c[0] * k, -c[1]) for c in coords]
    step = max(1, len(xy) // SILHOUETTE_POINTS)
    xy = xy[::step] + [xy[0]]
    x0, x1 = min(p[0] for p in xy), max(p[0] for p in xy)
    y0, y1 = min(p[1] for p in xy), max(p[1] for p in xy)
    s = 100.0 / max(x1 - x0, y1 - y0, 1e-12)
    ox, oy = (100 - (x1 - x0) * s) / 2, (100 - (y1 - y0) * s) / 2
    return [[round((x - x0) * s + ox, 2), round((y - y0) * s + oy, 2)] for x, y in xy]


def _layout_summary(lo: dict) -> dict:
    corners = next((p for p in lo.get("point_layers", []) if p.get("kind") == "corners"), {"items": []})["items"]
    out = {"id": lo["id"], "name": lo.get("name"), "series": lo.get("series", []),
           "length_m": lo.get("length_m"), "corners": len(corners),
           "basis": (lo.get("geometry") or {}).get("basis", "centerline"), "measured": False}
    s = lo.get("surface")
    if s:
        pos = s.get("position") or {}
        ref = pos.get("reference") or {}
        img = (s.get("sources") or {}).get("imagery") or {}
        out.update({
            "measured": True,
            "ce95_m": s.get("absolute_accuracy_ce95_m"),
            "precision_m": s.get("relative_precision_m"),
            "seen": s.get("seen_fraction"),
            "width_m": (s.get("width_m") or {}).get("median"),
            "imagery": img.get("id"), "imagery_name": img.get("name"),
            "reference": ref.get("name"), "reference_kind": ref.get("kind"),
            "reference_stated": ref.get("stated"),
            "placed": sum(1 for c in corners if (c.get("placement") or {}).get("basis") == "curvature"),
        })
    return out


def main() -> None:
    (SITE / "geojson").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "tracks.jsonl", SITE / "tracks.jsonl")
    atlas = []
    for line in (ROOT / "tracks.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        raw = ROOT / "tracks" / t["slug"] / "raw"
        outline = []
        for lo in t["layouts"]:
            for rel in filter(None, [(lo.get("geometry") or {}).get("centerline"), (lo.get("geometry") or {}).get("surface")]):
                src = raw / rel
                if src.exists():
                    dest = SITE / "geojson" / f"{t['slug']}_{Path(rel).name}"
                    shutil.copyfile(src, dest)
            if not outline:
                gj = raw / (lo.get("geometry") or {}).get("centerline", "")
                if gj.is_file():
                    feats = json.loads(gj.read_text())["features"]
                    f = next((f for f in feats if f["properties"].get("role") == "outline"), None)
                    if f:
                        outline = _silhouette(f["geometry"]["coordinates"])
        loc = t.get("location") or {}
        atlas.append({"slug": t["slug"], "name": t["name"], "aka": t.get("aka", []),
                      "country": t.get("country"), "locality": loc.get("locality"), "region": loc.get("region"),
                      "lat": loc.get("lat"), "lon": loc.get("lon"), "series": t.get("series", []),
                      "layouts": [_layout_summary(lo) for lo in t["layouts"]], "silhouette": outline})
    (SITE / "atlas.json").write_text(json.dumps(atlas, ensure_ascii=False, separators=(",", ":")))
    n = sum(1 for a in atlas if any(l["measured"] for l in a["layouts"]))
    print(f"site data: {len(atlas)} tracks ({n} measured) -> site/atlas.json, site/geojson/, site/tracks.jsonl")


if __name__ == "__main__":
    main()
