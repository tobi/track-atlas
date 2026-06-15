#!/usr/bin/env python3
"""Emit schema/track.schema.json from the Pydantic models (the source of truth).

The committed JSON Schema is a generated artifact for external consumers; the
models in scripts/lib/models.py are authoritative. Run this whenever the models
change (it's also part of the build pipeline).

Usage:
    uv run python scripts/build_schema.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.models import Track  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "schema" / "track.schema.json"


def main() -> None:
    gen = Track.model_json_schema()
    gen.pop("title", None)
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/tobi/track-atlas/schema/track.schema.json",
        "title": "Track",
        "description": ("Clean, source-agnostic metadata for a single racing circuit "
                        "(tracks/<slug>/track.json). GENERATED from scripts/lib/models.py — "
                        "do not edit by hand; run scripts/build_schema.py."),
        **gen,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n")
    print(f"schema/track.schema.json written from models ({len(json.dumps(schema))} bytes)")


if __name__ == "__main__":
    main()
