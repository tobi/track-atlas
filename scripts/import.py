#!/usr/bin/env python3
"""Global importer: fetch raw source artifacts for one or all tracks.

Reads tracks/<slug>/source.json, downloads every declared source, and writes
the raw payloads verbatim into tracks/<slug>/raw/. Idempotent and re-runnable;
raw/ is the cache of record. generate.py never touches the network.

Usage:
    python scripts/import.py circuit-de-la-sarthe
    python scripts/import.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import sources  # noqa: E402
from lib.config import TRACKS, load_source, track_dir  # noqa: E402
from lib.osm import ways_in_bbox, relation_geom  # noqa: E402


def import_track(slug: str) -> None:
    src = load_source(slug)
    tdir = track_dir(slug)
    print(f"[{slug}] importing...")

    # 1. Lovely (one file per layout key)
    for key, path in (src.get("lovely") or {}).items():
        data = sources.fetch_lovely(path)
        sources.write_raw(tdir, f"lovely-{key}.json", data)
        print(f"  lovely[{key}] <- {path} ({len(data.get('turn', []))} turns)")

    # 2. OSM via Overpass bbox (named raceway ways -> corner coordinates)
    osm = src.get("osm")
    if osm and "bbox" in osm:
        s, w, n, e = osm["bbox"]
        data = sources.overpass(ways_in_bbox(s, w, n, e))
        sources.write_raw(tdir, "osm.json", data)
        ways = [x for x in data.get("elements", []) if x.get("type") == "way"]
        print(f"  osm <- bbox {osm['bbox']} ({len(ways)} raceway ways)")

    # 3. OSM route relation (the official continuous lap -> true centerline).
    #    Optional: tracks without a mapped relation fall back to bbox tracing.
    if osm and osm.get("relation"):
        rid = osm["relation"]
        rel = sources.overpass(relation_geom(rid))
        sources.write_raw(tdir, "osm-relation.json", rel)
        rel_el = next((e for e in rel.get("elements", [])
                       if e.get("type") == "relation"), None)
        nways = len([m for m in (rel_el or {}).get("members", [])
                     if m.get("type") == "way"]) if rel_el else 0
        print(f"  osm relation <- {rid} ({nways} member ways)")

    print(f"[{slug}] raw/ updated.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?", help="track slug")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.all:
        slugs = [p.name for p in TRACKS.iterdir()
                 if (p / "source.json").exists()]
    elif args.slug:
        slugs = [args.slug]
    else:
        ap.error("give a slug or --all")

    for slug in slugs:
        # Per-track override hook
        custom = TRACKS / slug / "scripts" / "import.py"
        if custom.exists():
            print(f"[{slug}] using custom import.py")
            import runpy
            runpy.run_path(str(custom), run_name="__main__")
        else:
            import_track(slug)


if __name__ == "__main__":
    main()
