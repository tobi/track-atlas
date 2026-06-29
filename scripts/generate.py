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
    corners_from_lovely, pit_from_lovely, sectors_s1s3, straights_from_lovely,
)
from lib.osm import (  # noqa: E402
    centroid, named_corner_ways, normalize,
    relation_centerline, align_markers_to_centerline,
    stitch_circuit_ways, orient_loop, pit_lane_centroid, rotate_loop_to,
    densify,
)
from lib.naming import (  # noqa: E402
    DEFAULT_LAYER, build_registry, numbered_for, resolve_name as _resolve,
)
from lib.phases import compute_phases  # noqa: E402

# Name layers an override may set (besides numbered, which is derived from code).
OVERRIDE_NAME_LAYERS = ("official", "driver", "historical", "sponsor", "local")


def _osm_corner_index(osm: dict) -> dict:
    """normalized name -> apex coordinate (centroid of the named way)."""
    idx = {}
    for name, coords in named_corner_ways(osm.get("elements", [])):
        idx.setdefault(normalize(name), (name, centroid(coords)))
    return idx


def resolve_label(item: dict, default_layer: str) -> str:
    return _resolve(item["labels"], default_layer)


def _corners_from_override(items: list[dict]) -> list[dict]:
    """Manual replacement corner list in the internal pre-layer shape.

    Use sparingly when an upstream source collapses or misnumbers corners (e.g.
    Watkins Glen iRacing data models the Esses as one turn). Generated track.json
    still flows through the normal placement/phases/layer pipeline.
    """
    out = []
    for item in items:
        num = item["number"]
        code = str(item.get("code", num))
        names = {"numbered": numbered_for(code)}
        for layer in OVERRIDE_NAME_LAYERS:
            if item.get(layer):
                names[layer] = item[layer]
        c = {"number": num, "code": code, "names": names}
        for k in ("marker", "start", "end", "direction", "scale", "complex", "match_osm"):
            if item.get(k) is not None:
                c[k] = item[k]
        out.append(c)
    return out


def _layer_geojson(layout_id: str, corners: list[dict], outline_coords=None,
                   default_layer: str = DEFAULT_LAYER, layout_points=None) -> dict:
    feats = []
    if outline_coords:
        feats.append({
            "type": "Feature",
            "properties": {"role": "outline", "layout": layout_id},
            "geometry": {"type": "LineString", "coordinates": outline_coords},
        })
    for p in (layout_points or []):
        if "location" not in p:
            continue
        feats.append({
            "type": "Feature",
            "properties": {"role": p["id"], "name": p.get("label"),
                           "marker": p.get("marker")},
            "geometry": {"type": "Point", "coordinates": p["location"]},
        })
    for c in corners:
        if "location" not in c:
            continue
        feats.append({
            "type": "Feature",
            "properties": {
                "role": "corner",
                "id": c["id"],
                "number": c["number"],
                "code": c.get("code", str(c["number"])),
                "display": resolve_label(c, default_layer),
                "labels": c["labels"],
                "direction": c.get("direction"),
                "scale": c.get("scale"),
                "marker": c.get("marker"),
            },
            "geometry": {"type": "Point", "coordinates": c["location"]},
        })
    return {"type": "FeatureCollection", "features": feats}


def generate_track(slug: str) -> dict:
    src = load_source(slug)
    tdir = track_dir(slug)
    raw = tdir / "raw"
    # All generated files live under raw/ (downloads + derived). track.json's
    # geometry.centerline paths are relative to track.json's own dir (raw/).
    (raw / "layers").mkdir(parents=True, exist_ok=True)

    osm = json.loads((raw / "osm.json").read_text()) if (raw / "osm.json").exists() else {}
    osm_idx = _osm_corner_index(osm) if osm else {}

    track = {
        "slug": src["slug"],
        "name": src["name"],
        "aka": src.get("aka", []),
        "country": src.get("country"),
        "location": src["location"],
        "label_layers": {},   # filled after layouts, from the layers actually used
        "layouts": [],
    }
    name_layer_codes = set()
    if src.get("wikidata"):
        track["wikidata"] = src["wikidata"]
    if src.get("series"):
        track["series"] = src["series"]
    if src.get("external_ids"):
        track["external_ids"] = src["external_ids"]

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

        ov_file = tdir / "overrides.json"
        ov_all = json.loads(ov_file.read_text()) if ov_file.exists() else {}
        layout_ov = {**ov_all.get("*", {}), **ov_all.get(lid, {})}
        corners = (_corners_from_override(layout_ov["replace_corners"])
                   if layout_ov.get("replace_corners") else corners_from_lovely(lovely))
        # Join OSM coordinates onto corners by matching any known display/official
        # name against OSM way names, with a fuzzy fallback for upstream typos.
        import difflib
        osm_keys = list(osm_idx.keys())
        for c in corners:
            corner_total += 1
            candidates = [c["names"].get("driver"), c["names"].get("official")]
            for match_name in ([] if c.get("match_osm") is False else [x for x in candidates if x]):
                key = normalize(match_name)
                hit = osm_idx.get(key)
                if not hit and osm_keys:
                    near = difflib.get_close_matches(key, osm_keys, n=1, cutoff=0.82)
                    if near:
                        hit = osm_idx[near[0]]
                if hit:
                    c["location"] = [round(hit[1][0], 6), round(hit[1][1], 6)]
                    matched_total += 1
                    break

        # Curated overrides: name layers + complex group / direction / scale /
        # code that upstream sources lack. tracks/<slug>/overrides.json, keyed
        # by layout id then corner number:
        #   {"24h": {"corners": {"14": {"official": "Virage Porsche",
        #                               "driver": "Porsche Curves",
        #                               "complex": "Porsche Curves"}}}}
        cleared_driver = set()   # corners whose driver layer an override cleared
        if ov_all:
            # Overrides are keyed by layout id; a "*" block applies to every
            # layout (curation shared by series variants that use the same
            # geometry -- Sebring WEC/IMSA). Layout-specific fields win per corner.
            shared = ov_all.get("*", {}).get("corners", {})
            specific = ov_all.get(lid, {}).get("corners", {})
            ov = {n: {**shared.get(n, {}), **specific.get(n, {})}
                  for n in set(shared) | set(specific)}
            for c in corners:
                o = ov.get(str(c["number"]))
                if not o:
                    continue
                if "code" in o:
                    c["code"] = str(o["code"])
                for layer in OVERRIDE_NAME_LAYERS:
                    if layer in o:
                        # null / "" deletes the layer (e.g. promote a Lovely
                        # name to 'official' and clear 'driver' so the display
                        # falls back to the number -- Sebring "Sunset Bend").
                        if o[layer] in (None, ""):
                            c["names"].pop(layer, None)
                            if layer == "driver":
                                cleared_driver.add(c["number"])
                        else:
                            c["names"][layer] = o[layer]
                for k in ("complex", "direction", "scale"):
                    if k in o:
                        c[k] = o[k]

        # Normalize the name layers:
        #   - 'numbered' always tracks the (possibly overridden) code;
        #   - drop any overlay that merely repeats the numbered identifier
        #     ("official": "Turn 3" is a placeholder, not a real name);
        #   - default 'driver' to the official name when no distinct driver
        #     nickname is known and it wasn't explicitly cleared -- drivers use
        #     the official name unless they say something else (or just the
        #     number, e.g. Sebring T17, which clears driver via an override).
        for c in corners:
            c.setdefault("code", str(c["number"]))
            c["names"]["numbered"] = numbered_for(c["code"])
            num = c["names"]["numbered"]
            for layer in list(c["names"]):
                if layer != "numbered" and c["names"][layer] == num:
                    del c["names"][layer]
            if ("driver" not in c["names"] and c["names"].get("official")
                    and c["number"] not in cleared_driver):
                c["names"]["driver"] = c["names"]["official"]
        # --- Build the outline + place every corner on the real track ---
        # Prefer the OSM route relation centerline (the official continuous lap,
        # public-road sections and all). With it we can (a) draw the true track
        # surface and (b) place corners that have NO highway=raceway way of their
        # own (e.g. Le Mans Indianapolis) by their lap fraction. Falls back to
        # the coarse matched-corner trace when no relation is mapped.
        outline_path = f"layers/{lid}.geojson"
        rel_file = raw / "osm-relation.json"
        centerline = None
        if rel_file.exists():
            try:
                centerline = relation_centerline(json.loads(rel_file.read_text()),
                                                 expected_m=layout.get("length_m"))
                # A relation can describe a DIFFERENT layout (Bahrain's circuit
                # relation is the 6.3 km endurance loop, not the 5.4 km GP).
                # If it's >10% off the declared length, fall through to stitch.
                decl = layout.get("length_m")
                if centerline and decl:
                    from lib.osm import loop_length_m
                    L = loop_length_m(centerline)
                    if abs(L - decl) / decl > 0.10:
                        print(f"[{slug}] relation centerline {L:,.0f} m is "
                              f">10% off declared {decl:,.0f} m -- ignoring relation")
                        centerline = None
            except Exception:
                centerline = None

        outline_coords = None
        sf_point = None       # start/finish {marker, location}
        pit_points = {}       # {"pit_entry"/"pit_exit": {marker, location}}
        pit = pit_from_lovely(lovely)
        # A source layout may override pit in/out -- e.g. series that share the
        # same circuit geometry but use a different pit configuration (Sebring
        # IMSA vs WEC). "separate full layouts": one layout entry per config.
        if isinstance(layout.get("pit"), dict):
            pit = layout["pit"]
        if centerline and len(centerline) >= 8:
            centerline = densify(centerline)
            matched_pts = [(c["marker"], c["location"]) for c in corners
                           if "location" in c and "marker" in c]
            place, oriented = align_markers_to_centerline(centerline, matched_pts)
            # Place corners that never matched an OSM way, by lap fraction.
            for c in corners:
                if "location" not in c and "marker" in c:
                    p = place(c["marker"])
                    c["location"] = [round(p[0], 6), round(p[1], 6)]
                    c["location_source"] = "centerline"
            # Start/finish = lap fraction 0.0 (Lovely markers are measured from
            # the timing line), unless the source pins it manually.
            sf_src = layout.get("start_finish")
            if sf_src and sf_src.get("location"):
                sf_point = {"marker": sf_src.get("marker", 0.0),
                            "location": sf_src["location"]}
            else:
                p = place(0.0)
                sf_point = {"marker": 0.0,
                            "location": [round(p[0], 6), round(p[1], 6)]}
            for key, role in (("entry", "pit_entry"), ("exit", "pit_exit")):
                m = (pit or {}).get(key)
                if m is not None:
                    p = place(m)
                    pit_points[role] = {"marker": m,
                                        "location": [round(p[0], 6), round(p[1], 6)]}
            outline_coords = [[round(x, 6), round(y, 6)] for x, y in oriented]
            if outline_coords[0] != outline_coords[-1]:
                outline_coords.append(outline_coords[0])  # close the loop
        else:
            # Spatial-stitch fallback: chain the bbox raceway ways into a
            # closed loop (works when ways are named after the circuit, not
            # corners -- Fuji, Miami, Losail, Jeddah, Laguna Seca).
            stitched = stitch_circuit_ways(osm.get("elements", []),
                                           expected_m=layout.get("length_m"))
            if stitched and len(stitched) >= 8:
                stitched = densify(orient_loop(stitched, layout.get("direction")))
                matched_pts = [(c["marker"], c["location"]) for c in corners
                               if "location" in c and "marker" in c]
                if len(matched_pts) >= 2:
                    place, oriented = align_markers_to_centerline(stitched, matched_pts)
                else:
                    # No named-corner anchors: anchor lap origin at the pit
                    # lane (it flanks the start/finish straight) and place
                    # corners by raw lap fraction.
                    anchor = pit_lane_centroid(osm.get("elements", []))
                    oriented = rotate_loop_to(stitched, anchor) if anchor else stitched
                    from lib.osm import arc_lengths, point_at_fraction
                    cum, total = arc_lengths(oriented + [oriented[0]])
                    closed = oriented + [oriented[0]]
                    place = lambda m: point_at_fraction(closed, cum, total, m)  # noqa: E731
                for c in corners:
                    if "location" not in c and "marker" in c:
                        p = place(c["marker"])
                        c["location"] = [round(p[0], 6), round(p[1], 6)]
                        c["location_source"] = "centerline"
                p = place(0.0)
                sf_point = {"marker": 0.0,
                            "location": [round(p[0], 6), round(p[1], 6)]}
                for key, role in (("entry", "pit_entry"), ("exit", "pit_exit")):
                    m = (pit or {}).get(key)
                    if m is not None:
                        p = place(m)
                        pit_points[role] = {"marker": m,
                                            "location": [round(p[0], 6), round(p[1], 6)]}
                outline_coords = [[round(x, 6), round(y, 6)] for x, y in oriented]
                if outline_coords[0] != outline_coords[-1]:
                    outline_coords.append(outline_coords[0])
            else:
                # Last resort: ordered matched corners as a rough loop.
                traced = sorted(
                    (c for c in corners if "location" in c and "marker" in c),
                    key=lambda c: c["marker"],
                )
                outline_coords = [c["location"] for c in traced]
                if len(outline_coords) >= 3:
                    outline_coords.append(outline_coords[0])  # close the loop
        # Corner phases: brake-zone start / apex / exit as lap fractions, written
        # onto each corner's start/end (apex stays the marker).
        total_m = layout.get("length_m")
        if not total_m and outline_coords:
            from lib.osm import loop_length_m
            total_m = loop_length_m(outline_coords)
        if total_m:
            phases = compute_phases(corners, total_m)
            for c in corners:
                p = phases.get(c["number"])
                if p:
                    c["start"], c["end"] = p["start"], p["end"]

        # Pick the default display layer: the configured preference if any corner
        # actually carries it, else the best populated layer (driver -> official
        # -> numbered). Number-only tracks honestly default to 'numbered'; the
        # thin-naming warning in verify.py is the curation signal.
        populated = set()
        for c in corners:
            populated.update(c["names"].keys())
        name_layer_codes.update(populated)
        preferred = layout.get("label_default") or src.get("label_default") or DEFAULT_LAYER
        default_layer = preferred if preferred in populated else next(
            (l for l in (DEFAULT_LAYER, "official", "numbered") if l in populated),
            "numbered")

        corner_points = []
        for c in sorted(corners, key=lambda x: x["number"]):
            item = {
                "id": f"t{c['number']}",
                "number": c["number"],
                "code": c.get("code", str(c["number"])),
                "label": _resolve(c["names"], default_layer),
                "labels": c["names"],
            }
            for k in ("marker", "location", "location_source", "direction", "scale"):
                if k in c and c[k] is not None:
                    item[k] = c[k]
            corner_points.append(item)

        layout_points = []
        if sf_point:
            layout_points.append({"id": "start_finish", "label": "Start / Finish", **sf_point})
        for role in ("pit_entry", "pit_exit"):
            if role in pit_points:
                layout_points.append({"id": role, "label": role.replace("_", " ").title(), **pit_points[role]})

        point_layers = []
        if layout_points:
            point_layers.append({"id": "layout_points", "kind": "layout_points", "label": "Layout Points", "items": layout_points})
        point_layers.append({"id": "corners", "kind": "corners", "label": "Corners", "items": corner_points})

        range_layers = []
        sectors = sectors_s1s3(lovely)
        if sectors:
            range_layers.append({
                "id": "timing_sectors", "kind": "timing_sectors", "label": "Timing Sectors", "coverage": "partition",
                "items": [{"id": s["name"].lower(), "label": s["name"], "start": s["start"], "end": s["end"]} for s in sectors],
            })
        corner_ranges = []
        for c in sorted(corners, key=lambda x: x["number"]):
            if c.get("start") is not None and c.get("end") is not None and c["start"] < c["end"]:
                corner_ranges.append({
                    "id": f"t{c['number']}", "label": _resolve(c["names"], default_layer),
                    "start": c["start"], "end": c["end"], "anchor": f"t{c['number']}",
                })
        if corner_ranges:
            range_layers.append({"id": "corner_ranges", "kind": "corner_ranges", "label": "Corners", "generated": True, "items": corner_ranges})

        complexes = []
        seen_complexes = []
        for c in sorted(corners, key=lambda x: x["number"]):
            comp = c.get("complex")
            if comp and comp not in seen_complexes:
                seen_complexes.append(comp)
                members = [x for x in corners if x.get("complex") == comp]
                starts = [x.get("start", x.get("marker")) for x in members if x.get("start", x.get("marker")) is not None]
                ends = [x.get("end", x.get("marker")) for x in members if x.get("end", x.get("marker")) is not None]
                if starts and ends and min(starts) < max(ends):
                    complexes.append({
                        "id": normalize(comp) or f"complex-{len(complexes) + 1}", "label": comp,
                        "start": min(starts), "end": max(ends),
                        "members": [f"t{x['number']}" for x in sorted(members, key=lambda y: y["number"])],
                    })
        if complexes:
            range_layers.append({"id": "corner_complexes", "kind": "corner_complexes", "label": "Corner Complexes", "items": complexes})

        slow_zones = layout.get("slow_zones", [])
        if slow_zones:
            range_layers.append({
                "id": "slow_zones", "kind": "slow_zones", "label": "Slow Zones",
                "items": [{"id": z["id"], "label": z.get("name"), "start": z["start"], "end": z["end"]} for z in slow_zones],
            })

        gj = _layer_geojson(lid, corner_points, outline_coords or None, default_layer,
                            layout_points=layout_points)
        (raw / outline_path).write_text(json.dumps(gj, ensure_ascii=False, indent=2))

        lo = {
            "id": lid,
            "name": layout["name"],
            "aka": layout.get("aka", []),
            "label_default": default_layer,
            "geometry": {"centerline": outline_path, "crs": "EPSG:4326"},
            "point_layers": point_layers,
            "range_layers": range_layers,
        }
        for k in ("length_m", "direction", "active_years", "series"):
            if k in layout:
                lo[k] = layout[k]
        track["layouts"].append(lo)

    track["label_layers"] = build_registry(name_layer_codes)

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

    (raw / "track.json").write_text(json.dumps(track, ensure_ascii=False, indent=2))
    # Optional per-track layer configs can fetch/parse external timing maps and
    # merge additional point/range layers. The runner resolves every URL/file to
    # local raw/layer-sources before invoking a pure converter tool.
    from lib.layer_runner import run_layer_configs
    track = run_layer_configs(slug, write=True)
    print(f"[{slug}] raw/track.json written -- corners matched to OSM geometry: "
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

    # keep the site catalog + the headline tracks.jsonl dataset fresh
    import runpy as _rp
    here = Path(__file__).resolve().parent
    _rp.run_path(str(here / "build_index.py"), run_name="__main__")
    _rp.run_path(str(here / "build_jsonl.py"), run_name="__main__")


if __name__ == "__main__":
    main()
