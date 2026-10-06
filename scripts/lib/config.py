"""Per-track config consumed by the global import.py / generate.py.

Each track is defined by `tracks/<slug>/track.py` (lib/dsl.py): sources,
layouts, curation and generated layers in one file. It compiles to three
documents, loaded here:

- `load_source(slug)`: identity, sources, layouts, surface (was source.json)
- `load_overrides(slug)`: curated corners and surface review (was overrides.json)
- `load_generation(slug)`: generated-layer configs (was generation-config.json)
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

TRACKS = Path(__file__).resolve().parents[2] / "tracks"


def slugs() -> list[str]:
    """Every track with a definition."""
    return sorted(p.name for p in TRACKS.iterdir() if (p / "track.py").exists())


@functools.lru_cache(maxsize=None)
def _track(slug: str):
    from . import dsl
    return dsl.load(TRACKS / slug / "track.py")


def load_source(slug: str) -> dict:
    return _track(slug).source()


def load_overrides(slug: str) -> dict:
    return _track(slug).overrides()


def load_generation(slug: str) -> dict | None:
    return _track(slug).generation()


def track_dir(slug: str) -> Path:
    return TRACKS / slug


def raw_dir(slug: str) -> Path:
    """Where every generated file lives (downloads + derived track.json, layers,
    renders, phases). Inputs (track.py, README.md) stay in
    track_dir; everything the build can recreate goes here."""
    return TRACKS / slug / "raw"


def track_json_path(slug: str) -> Path:
    return raw_dir(slug) / "track.json"
