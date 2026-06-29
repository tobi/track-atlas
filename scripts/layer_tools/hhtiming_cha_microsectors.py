#!/usr/bin/env python3
"""Convert an HH Timing .cha Micro Sectors option into a range_layer.

The .cha file provides authoritative names and timing-loop pairs. Fractions are
supplied explicitly by params because the .cha does not contain loop distances.
This keeps source parsing and atlas-specific lap placement separate.
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def micro_sector_string(path: str) -> str:
    root = ET.parse(path).getroot()
    values = list(root.iter())
    for i, el in enumerate(values):
        if el.tag == "Key" and (el.text or "").strip() == "Micro Sectors":
            # In the .cha structure the sibling Value is usually next, but be
            # tolerant and scan the parent first.
            parent = None
            for p in root.iter():
                if el in list(p):
                    parent = p
                    break
            if parent is not None:
                for child in parent:
                    if child.tag == "Value":
                        return (child.text or "").strip()
            if i + 1 < len(values) and values[i + 1].tag == "Value":
                return (values[i + 1].text or "").strip()
    raise ValueError("No 'Micro Sectors' option found in .cha")


def parse_segments(s: str) -> list[dict]:
    if not s or s == "auto-generated":
        raise ValueError("This tool needs explicit microsector definitions, not auto-generated")
    out = []
    for part in [p.strip() for p in s.split(";") if p.strip()]:
        bits = [b.strip() for b in part.split(",")]
        if len(bits) == 3:
            name, entry, exit = bits
        elif len(bits) == 2:
            name, entry, exit = f"seg{len(out)+1}", bits[0], bits[1]
        else:
            raise ValueError(f"Bad segment definition: {part!r}")
        out.append({"id": name.lower(), "label": name, "entry_ref": entry, "exit_ref": exit})
    return out


def main() -> None:
    payload = json.load(sys.stdin)
    params = payload.get("params") or {}
    resource_name = params.get("resource", "cha")
    resource = payload["resources"][resource_name]
    segs = parse_segments(micro_sector_string(resource["local_path"]))

    item_meta = {x["id"].lower(): x for x in params.get("items", [])}
    boundaries = params.get("boundaries")
    if boundaries and len(boundaries) != len(segs) + 1:
        raise ValueError(f"boundaries length {len(boundaries)} must be segments+1 ({len(segs)+1})")

    items = []
    for i, seg in enumerate(segs):
        meta = item_meta.get(seg["id"], {})
        if boundaries:
            start, end = boundaries[i], boundaries[i + 1]
        else:
            start, end = meta.get("start"), meta.get("end")
        if start is None or end is None:
            raise ValueError(f"No start/end supplied for {seg['id']}")
        items.append({
            "id": seg["id"],
            "label": meta.get("label") or seg["label"],
            "start": start,
            "end": end,
            "entry_ref": seg["entry_ref"],
            "exit_ref": seg["exit_ref"],
        })
    if items:
        items[0]["start"] = 0.0
        items[-1]["end"] = 1.0

    layer = {
        "id": params["layer_id"],
        "kind": params.get("kind", params["layer_id"]),
        "label": params.get("label", params["layer_id"].replace("_", " ").title()),
        "series": params.get("series", []),
        "coverage": params.get("coverage", "partition"),
        "provenance": {
            "source": params.get("source", "HH Timing championship configuration"),
            "url": resource.get("url"),
            "local_path": resource.get("relative_path") or resource.get("local_path"),
        },
        "items": items,
    }
    print(json.dumps({"range_layers": [layer]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
