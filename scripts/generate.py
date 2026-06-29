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
    corners_from_lovely, pit_from_lovely, sectors_s1s3,
)
from lib.osm import (  # noqa: E402
    centroid, named_corner_ways, normalize,
    relation_centerline, align_markers_to_centerline,
    stitch_circuit_ways, orient_loop, pit_lane_centroid, rotate_loop_to,
    densify, haversine, loop_length_m, arc_lengths, point_at_fraction,
)
from lib.naming import (  # noqa: E402
    DEFAULT_LAYER, build_registry, numbered_for, resolve_name as _resolve,
)
from lib.phases import compute_phases  # noqa: E402

# Name layers an override may set (besides numbered, which is derived from code).
OVERRIDE_NAME_LAYERS = ("official", "driver", "historical", "sponsor", "local")


def _centerline_quality(loop: list, expected_m: float | None = None) -> tuple[float, list[str]]:
    """Score candidate centerlines; lower is better.

    Relation geometry is often the official lap, but some OSM relations include
    old layouts or connector stubs. Densification means segments much over 30 m
    or near-180° backtracks are strong stitch-smell penalties.
    """
    if not loop or len(loop) < 8:
        return float("inf"), ["too short"]
    reasons = []
    length = loop_length_m(loop)
    score = abs(length - expected_m) if expected_m else 0.0
    if expected_m:
        reasons.append(f"length {length:,.0f} m (Δ {abs(length - expected_m):,.0f} m)")
    qloop = densify(loop)
    closed = qloop + [qloop[0]] if qloop[0] != qloop[-1] else qloop
    for i, (a, b) in enumerate(zip(closed, closed[1:])):
        d = haversine(a, b)
        if d > 60:
            score += (d - 60) * 8
            reasons.append(f"long seg {i} {d:.0f} m")
    import math
    for i in range(1, len(closed) - 1):
        a, b, c = closed[i - 1], closed[i], closed[i + 1]
        lat = math.radians(b[1]); k = math.cos(lat)
        v1 = ((b[0] - a[0]) * k * 111320, (b[1] - a[1]) * 111320)
        v2 = ((c[0] - b[0]) * k * 111320, (c[1] - b[1]) * 111320)
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        if l1 < 10 or l2 < 10:
            continue
        dot = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)))
        angle = math.degrees(math.acos(dot))
        if angle > 145:
            score += (angle - 145) * 25
            reasons.append(f"backtrack {i} {angle:.0f}°")
    return score, reasons


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
    geometry_summaries = []
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
        candidates = []
        rel_centerline = None
        if rel_file.exists():
            try:
                rel_centerline = relation_centerline(json.loads(rel_file.read_text()),
                                                     expected_m=layout.get("length_m"))
                if rel_centerline:
                    score, reasons = _centerline_quality(rel_centerline, layout.get("length_m"))
                    candidates.append((score, "relation", rel_centerline, reasons))
            except Exception as e:
                print(f"[{slug}] relation centerline candidate failed: {e}")
        # Only compare the stitched way graph here when there is a relation to
        # challenge. If there is no relation, leave `centerline` unset and use
        # the older stitch fallback below, which has pit-lane anchoring behavior
        # for tracks with no matched corner anchors.
        if rel_centerline:
            try:
                stitched_candidate = stitch_circuit_ways(osm.get("elements", []),
                                                         expected_m=layout.get("length_m"))
                if stitched_candidate:
                    score, reasons = _centerline_quality(stitched_candidate, layout.get("length_m"))
                    candidates.append((score, "stitched", stitched_candidate, reasons))
            except Exception as e:
                print(f"[{slug}] stitched centerline candidate failed during relation comparison: {e}")
        geometry_summary = {"layout": lid, "candidates": []}
        if candidates:
            candidates.sort(key=lambda x: x[0])
            best_score, best_name, centerline, best_reasons = candidates[0]
            geometry_summary["selected"] = best_name
            geometry_summary["selected_score"] = round(best_score, 3)
            geometry_summary["candidates"] = [
                {"source": name, "score": round(score, 3), "reasons": reasons[:8]}
                for score, name, _, reasons in candidates
            ]
            for score, name, _, reasons in candidates[1:]:
                if name == "relation" and score - best_score > 100:
                    print(f"[{slug}] ignoring OSM relation centerline in favor of {best_name}: "
                          f"relation quality {score:.0f} ({'; '.join(reasons[:3])}) vs "
                          f"{best_name} {best_score:.0f} ({'; '.join(best_reasons[:3])})")

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
            sf_src = layout.get("start_finish")
            if sf_src and sf_src.get("location"):
                matched_pts.append((sf_src.get("marker", 0.0), sf_src["location"]))
            place, oriented = align_markers_to_centerline(centerline, matched_pts)
            # OSM named ways identify/align named sections, but their centroids
            # are not reliable apexes (a named way can cover an entire complex,
            # and repeated names can otherwise collapse to one coordinate). Once
            # marker→centerline alignment is learned, place every apex by its lap
            # marker on the centerline.
            for c in corners:
                if "marker" in c:
                    p = place(c["marker"])
                    c["location"] = [round(p[0], 6), round(p[1], 6)]
                    c["location_source"] = "centerline"
            # Start/finish = lap fraction 0.0 (Lovely markers are measured from
            # the timing line), unless the source pins it manually.
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
            # GeoJSON centerlines are the canonical lap coordinate frame for UI
            # range layers, so vertex 0 must be marker 0.0 (start/finish), not
            # OSM's arbitrary relation start node. `place()` was learned from the
            # unrotated oriented loop, but rotation does not change geometry.
            draw_loop = rotate_loop_to(oriented, sf_point["location"])
            outline_coords = [[round(x, 6), round(y, 6)] for x, y in draw_loop]
            if outline_coords[0] != outline_coords[-1]:
                outline_coords.append(outline_coords[0])  # close the loop
        else:
            # Spatial-stitch fallback: chain the bbox raceway ways into a
            # closed loop (works when ways are named after the circuit, not
            # corners -- Fuji, Miami, Losail, Jeddah, Laguna Seca).
            stitched = stitch_circuit_ways(osm.get("elements", []),
                                           expected_m=layout.get("length_m"))
            if stitched and len(stitched) >= 8:
                geometry_summary.setdefault("selected", "stitched_fallback")
                score, reasons = _centerline_quality(stitched, layout.get("length_m"))
                geometry_summary.setdefault("selected_score", round(score, 3))
                geometry_summary.setdefault("candidates", []).append({"source": "stitched_fallback", "score": round(score, 3), "reasons": reasons[:8]})
                stitched = densify(orient_loop(stitched, layout.get("direction")))
                matched_pts = [(c["marker"], c["location"]) for c in corners
                               if "location" in c and "marker" in c]
                sf_src = layout.get("start_finish")
                if sf_src and sf_src.get("location"):
                    matched_pts.append((sf_src.get("marker", 0.0), sf_src["location"]))
                if len(matched_pts) >= 1:
                    place, oriented = align_markers_to_centerline(stitched, matched_pts)
                else:
                    # No named-corner anchors: anchor lap origin at the pit
                    # lane (it flanks the start/finish straight) and place
                    # corners by raw lap fraction.
                    anchor = pit_lane_centroid(osm.get("elements", []))
                    oriented = rotate_loop_to(stitched, anchor) if anchor else stitched
                    cum, total = arc_lengths(oriented + [oriented[0]])
                    closed = oriented + [oriented[0]]
                    place = lambda m: point_at_fraction(closed, cum, total, m)  # noqa: E731
                for c in corners:
                    if "marker" in c:
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
                draw_loop = rotate_loop_to(oriented, sf_point["location"])
                outline_coords = [[round(x, 6), round(y, 6)] for x, y in draw_loop]
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
                    geometry_summary.setdefault("selected", "matched_corner_trace")
                    geometry_summary.setdefault("selected_score", None)
                    outline_coords.append(outline_coords[0])  # close the loop
        geometry_summaries.append(geometry_summary)
        # Final invariant: marker fractions are measured on the emitted GeoJSON
        # centerline. OSM way centroids and piecewise alignment are useful to
        # choose/orient the lap, but clients slice ranges directly by raw marker
        # fractions, so every point carrying a marker must be placed from the
        # final emitted coordinate frame.
        if outline_coords and len(outline_coords) >= 2:
            cum_final, total_final = arc_lengths(outline_coords)
            for c in corners:
                if c.get("marker") is not None:
                    p = point_at_fraction(outline_coords, cum_final, total_final, c["marker"])
                    c["location"] = [round(p[0], 6), round(p[1], 6)]
                    c["location_source"] = "centerline"
            if sf_point and sf_point.get("marker") is not None:
                p = point_at_fraction(outline_coords, cum_final, total_final, sf_point["marker"])
                sf_point["location"] = [round(p[0], 6), round(p[1], 6)]
            for pp in pit_points.values():
                if pp.get("marker") is not None:
                    p = point_at_fraction(outline_coords, cum_final, total_final, pp["marker"])
                    pp["location"] = [round(p[0], 6), round(p[1], 6)]

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
        point_layers.append({"id": "corners", "kind": "corners", "label": "Corner Apexes", "items": corner_points})

        range_layers = []
        sectors = sectors_s1s3(lovely)
        if sectors:
            range_layers.append({
                "id": "timing_sectors", "kind": "timing_sectors", "label": "Timing Sectors", "coverage": "partition",
                "items": [{"id": s["name"].lower(), "label": s["name"], "start": s["start"], "end": s["end"]} for s in sectors],
            })
        def usable_range_bounds(member_list):
            starts = [x.get("start", x.get("marker")) for x in member_list if x.get("start", x.get("marker")) is not None]
            ends = [x.get("end", x.get("marker")) for x in member_list if x.get("end", x.get("marker")) is not None]
            if starts and ends and min(starts) < max(ends):
                return min(starts), max(ends)
            markers = [x.get("marker") for x in member_list if x.get("marker") is not None]
            if not markers:
                return None
            # Flat-out kinks can have no brake/exit phase but still need to be
            # represented in complete corner-group layers. Give them a tiny
            # inspectable interval around the apex rather than dropping them.
            center = sum(markers) / len(markers)
            half = (15.0 / total_m) if total_m else 0.001
            return max(0.0, center - half), min(1.0, center + half)

        corner_ranges = []
        for c in sorted(corners, key=lambda x: x["number"]):
            bounds = usable_range_bounds([c])
            if bounds:
                start, end = bounds
                item = {
                    "id": f"t{c['number']}", "label": _resolve(c["names"], default_layer),
                    "start": round(start, 5), "end": round(end, 5), "anchor": f"t{c['number']}",
                }
                if c.get("marker") is not None and start <= c["marker"] <= end:
                    item["points"] = [{
                        "id": "apex", "role": "apex", "label": "Apex",
                        "marker": c["marker"], "point_ref": f"t{c['number']}",
                    }]
                corner_ranges.append(item)
        if corner_ranges:
            range_layers.append({"id": "corner_ranges", "kind": "corner_ranges", "label": "Each Corner", "generated": True, "items": corner_ranges})

        # Corner Complexes is the de-cluttered grouping layer: explicit complex
        # overrides win; otherwise adjacent corners with the same real name are
        # merged automatically. Solo scale 5/6 kinks are omitted unless they are
        # part of a multi-apex complex.
        groups = []
        sorted_corners = sorted(corners, key=lambda x: x["number"])
        processed = set()
        used_ids = set()

        def has_real_name(c):
            return any(k != "numbered" for k in c.get("names", {}))

        for c in sorted_corners:
            if c["number"] in processed:
                continue
            comp = c.get("complex")
            if comp:
                members = [x for x in sorted_corners if x.get("complex") == comp]
                if len(members) == 1 and (members[0].get("scale") or 0) >= 5:
                    processed.add(c["number"])
                    continue
                base_id = normalize(comp) or f"complex-{len(groups) + 1}"
                label = comp
            else:
                label = _resolve(c["names"], default_layer)
                members = [c]
                if has_real_name(c):
                    idx = sorted_corners.index(c) + 1
                    while idx < len(sorted_corners):
                        nxt = sorted_corners[idx]
                        if nxt.get("complex") or not has_real_name(nxt):
                            break
                        if _resolve(nxt["names"], default_layer) != label:
                            break
                        members.append(nxt)
                        idx += 1
                if len(members) == 1 and (c.get("scale") or 0) >= 5:
                    processed.add(c["number"])
                    continue
                base_id = normalize(label) if len(members) > 1 else f"t{c['number']}"

            for x in members:
                processed.add(x["number"])
            bounds = usable_range_bounds(members)
            if not bounds:
                continue
            start, end = bounds
            group_id = base_id or f"complex-{len(groups) + 1}"
            suffix = 2
            while group_id in used_ids:
                group_id = f"{base_id}-{suffix}"
                suffix += 1
            used_ids.add(group_id)
            points = []
            for x in members:
                if x.get("marker") is not None and start <= x["marker"] <= end:
                    points.append({
                        "id": f"t{x['number']}-apex", "role": "apex",
                        "label": _resolve(x["names"], default_layer),
                        "marker": x["marker"], "point_ref": f"t{x['number']}",
                    })
            groups.append({
                "id": group_id, "label": label,
                "start": round(start, 5), "end": round(end, 5),
                "members": [f"t{x['number']}" for x in members],
                "points": points,
            })
        if groups:
            range_layers.append({"id": "corner_complexes", "kind": "corner_complexes", "label": "Corner Complexes", "items": groups})

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
             "license": "see upstream", "provides": ["corners", "sectors", "pit"]},
            {"name": "OpenStreetMap (Overpass)",
             "url": "https://www.openstreetmap.org", "license": "ODbL",
             "provides": ["geometry", "named-corner-coordinates"]},
        ],
        "corner_match": {"matched": matched_total, "total": corner_total},
        "geometry": geometry_summaries,
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
