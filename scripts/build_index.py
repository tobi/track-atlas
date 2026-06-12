#!/usr/bin/env python3
"""Build tracks/index.json -- the catalog the static site consumes.

Run after generate.py. Offline, deterministic.

Usage:
    python scripts/build_index.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import TRACKS  # noqa: E402


def main() -> None:
    entries = []
    for p in sorted(TRACKS.iterdir()):
        tj = p / "track.json"
        if not tj.exists():
            continue
        t = json.loads(tj.read_text())
        png = p / "render" / f"{p.name}.png"
        entries.append({
            "slug": t["slug"],
            "name": t["name"],
            "aka": t.get("aka", []),
            "country": t.get("country"),
            "location": t.get("location", {}),
            "series": t.get("series", []),
            "layouts": [
                {"id": lo["id"], "name": lo["name"],
                 "length_m": lo.get("length_m"),
                 "corners": len(lo.get("corners", [])),
                 "direction": lo.get("direction")}
                for lo in t.get("layouts", [])
            ],
            "poster": f"tracks/{t['slug']}/render/{t['slug']}.png" if png.exists() else None,
        })
    out = TRACKS / "index.json"
    out.write_text(json.dumps({"tracks": entries}, ensure_ascii=False, indent=2))
    print(f"tracks/index.json written ({len(entries)} tracks)")


if __name__ == "__main__":
    main()
