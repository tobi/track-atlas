#!/usr/bin/env python3
"""Global generator: build clean track.json + layers/*.geojson from raw/ artifacts.

Pure transform -- no network. Reads tracks/<slug>/raw/, merges Lovely corner
metadata with OSM named-corner geometry, and writes:
  - tracks/<slug>/track.json          (schema-validated metadata)
  - tracks/<slug>/layers/<id>.geojson (outline + named corner points)

Corner-name -> coordinate join strategy:
  Lovely gives the canonical ordered corner list (number, name, apex fraction,
  direction, scale). OSM gives named way segments with real coordinates. We
  match them by normalized name; matched corners get a location. Unmatched
  corners keep their lap-fraction marker so a downstream consumer can still
  place them once a full racing-line outline is available.

Usage:
    python scripts/generate.py circuit-de-la-sarthe
    python scripts/generate.py --all
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import TRACKS, load_source, track_dir  # noqa: E402
from lib.lovely import (  # noqa: E402
    corners_from_lovely, pit_from_lovely, sectors_from_lovely, straights_from_lovely,
)
from lib.osm import centroid, named_corner_ways, normalize  # noqa: E402


def _osm_corner_index(osm: dict) -> dict:
    """normalized name -> apex coordinate (centroid of the named way)."""
    idx = {}
    for name, coords in named_corner_ways(osm.get("elements", [])):
        idx.setdefault(normalize(name), (name, centroid(coords)))
    return idx


def resolve_name(corner: dict, default_layer: str) -> str:
    """Pick a display name for a corner: try the track's preferred layer, then
    fall back colloquial -> official -> numbered (numbered always exists)."""
    names = corner["names"]
    order = [default_layer, "colloquial", "official", "numbered"]
    for layer in order:
        if names.get(layer):
            return names[layer]
    return names["numbered"]


def _layer_geojson(layout_id: str, corners: list[dict], outline_coords=None,
                   default_layer: str = "colloquial") -> dict:
    feats = []
    if outline_coords:
        feats.append({
            "type": "Feature",
            "properties": {"role": "outline", "layout": layout_id},
            "geometry": {"type": "LineString", "coordinates": outline_coords},
        })
    for c in corners:
        if "location" not in c:
            continue
        feats.append({
            "type": "Feature",
            "properties": {
                "role": "corner",
                "number": c["number"],
                "display": resolve_name(c, default_layer),
                "names": c["names"],
                "complex": c.get("complex"),
                "direction": c.get("direction"),
                "scale": c.get("scale"),
            },
            "geometry": {"type": "Point", "coordinates": c["location"]},
        })
    return {"type": "FeatureCollection", "features": feats}


def generate_track(slug: str) -> dict:
    src = load_source(slug)
    tdir = track_dir(slug)
    raw = tdir / "raw"
    (tdir / "layers").mkdir(exist_ok=True)

    osm = json.loads((raw / "osm.json").read_text()) if (raw / "osm.json").exists() else {}
    osm_idx = _osm_corner_index(osm) if osm else {}

    track = {
        "slug": src["slug"],
        "name": src["name"],
        "aka": src.get("aka", []),
        "country": src.get("country"),
        "location": src["location"],
        "layouts": [],
    }
    if src.get("wikidata"):
        track["wikidata"] = src["wikidata"]

    matched_total = 0
    corner_total = 0
    for layout in src["layouts"]:
        lid = layout["id"]
        lkey = layout.get("lovely")
        lovely = {}
        if lkey:
            lf = raw / f"lovely-{lkey}.json"
            if lf.exists():
                lovely = json.loads(lf.read_text())

        corners = corners_from_lovely(lovely)
        # Join OSM coordinates onto corners by matching the corner's best known
        # name (colloquial preferred, then official) against OSM way names, with
        # a fuzzy fallback for upstream typos (Lovely "Arange" -> OSM "Arnage").
        import difflib
        osm_keys = list(osm_idx.keys())
        for c in corners:
            corner_total += 1
            match_name = c["names"].get("colloquial") or c["names"].get("official")
            if match_name:
                key = normalize(match_name)
                hit = osm_idx.get(key)
                if not hit and osm_keys:
                    near = difflib.get_close_matches(key, osm_keys, n=1, cutoff=0.82)
                    if near:
                        hit = osm_idx[near[0]]
                if hit:
                    c["location"] = [round(hit[1][0], 6), round(hit[1][1], 6)]
                    matched_total += 1

        # Curated overrides: layer in official/colloquial names + complex group
        # that upstream sources lack. tracks/<slug>/overrides.json, keyed by
        # layout id then corner number:
        #   {"24h": {"corners": {"14": {"official": "Virage Porsche",
        #                               "colloquial": "Porsche Curves",
        #                               "complex": "Porsche Curves"}}}}
        ov_file = tdir / "overrides.json"
        if ov_file.exists():
            ov = json.loads(ov_file.read_text()).get(lid, {}).get("corners", {})
            for c in corners:
                o = ov.get(str(c["number"]))
                if not o:
                    continue
                for layer in ("official", "colloquial", "numbered"):
                    if layer in o:
                        c["names"][layer] = o[layer]
                for k in ("complex", "direction", "scale"):
                    if k in o:
                        c[k] = o[k]
        # Build an ordered corner-trace outline: matched corners sorted by lap
        # fraction give a faithful (if coarse) geographic loop. A precise
        # stitched centerline from OSM ways is a documented TODO.
        outline_path = f"layers/{lid}.geojson"
        traced = sorted(
            (c for c in corners if "location" in c and "marker" in c),
            key=lambda c: c["marker"],
        )
        outline_coords = [c["location"] for c in traced]
        if len(outline_coords) >= 3:
            outline_coords.append(outline_coords[0])  # close the loop
        default_layer = layout.get("name_default", src.get("name_default", "colloquial"))
        gj = _layer_geojson(lid, corners, outline_coords or None, default_layer)
        (tdir / outline_path).write_text(json.dumps(gj, ensure_ascii=False, indent=2))

        lo = {
            "id": lid,
            "name": layout["name"],
            "aka": layout.get("aka", []),
            "name_default": default_layer,
            "geometry": {"outline": outline_path, "crs": "EPSG:4326"},
            "corners": corners,
            "straights": straights_from_lovely(lovely),
            "sectors": sectors_from_lovely(lovely),
            "pit": pit_from_lovely(lovely),
        }
        for k in ("length_m", "direction", "active_years"):
            if k in layout:
                lo[k] = layout[k]
        track["layouts"].append(lo)

    track["provenance"] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "sources": [
            {"name": "Lovely-Sim-Racing/lovely-track-data",
             "url": "https://github.com/Lovely-Sim-Racing/lovely-track-data",
             "license": "see upstream", "provides": ["corners", "straights", "sectors", "pit"]},
            {"name": "OpenStreetMap (Overpass)",
             "url": "https://www.openstreetmap.org", "license": "ODbL",
             "provides": ["geometry", "named-corner-coordinates"]},
        ],
        "corner_match": {"matched": matched_total, "total": corner_total},
    }

    (tdir / "track.json").write_text(json.dumps(track, ensure_ascii=False, indent=2))
    print(f"[{slug}] track.json written -- corners matched to OSM geometry: "
          f"{matched_total}/{corner_total}")
    return track


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.all:
        slugs = [p.name for p in TRACKS.iterdir() if (p / "source.json").exists()]
    elif args.slug:
        slugs = [args.slug]
    else:
        ap.error("give a slug or --all")

    for slug in slugs:
        custom = TRACKS / slug / "scripts" / "generate.py"
        if custom.exists():
            print(f"[{slug}] using custom generate.py")
            import runpy
            runpy.run_path(str(custom), run_name="__main__")
        else:
            generate_track(slug)


if __name__ == "__main__":
    main()
