"""Per-track config consumed by the global import.py / generate.py.

A track only needs a scripts/import.py and scripts/generate.py of its own when
it deviates from the standard pipeline. Easy tracks just drop a source.json like:

    {
      "slug": "circuit-de-la-sarthe",
      "name": "Circuit de la Sarthe",
      "aka": ["La Sarthe", "Circuit des 24 Heures du Mans"],
      "country": "FR",
      "wikidata": "Q270760",
      "location": {"lat": 47.95, "lon": 0.224, "locality": "Le Mans"},
      "lovely": {"24h": "lmu/circuit-de-la-sarthe.json"},
      "osm": {"bbox": [47.90, 0.15, 47.98, 0.28]},
      "layouts": [
        {"id": "24h", "name": "Circuit des 24 Heures", "length_m": 13626,
         "direction": "clockwise", "lovely": "24h"}
      ]
    }

and the global scripts handle the rest.
"""
from __future__ import annotations

import json
from pathlib import Path

TRACKS = Path(__file__).resolve().parents[2] / "tracks"


def load_source(slug: str) -> dict:
    return json.loads((TRACKS / slug / "source.json").read_text())


def track_dir(slug: str) -> Path:
    return TRACKS / slug


def raw_dir(slug: str) -> Path:
    """Where every generated file lives (downloads + derived track.json, layers,
    renders, phases). Inputs (source.json, overrides.json, README.md) stay in
    track_dir; everything the build can recreate goes here."""
    return TRACKS / slug / "raw"


def track_json_path(slug: str) -> Path:
    return raw_dir(slug) / "track.json"
