#!/usr/bin/env python3
"""Convert an IMSA/Al Kamel Timing *Sector Map PDF into range_layers JSON.

Input is a JSON payload on stdin from scripts/lib/layer_runner.py. The runner has
already downloaded resources and resolved all track/layout context. This tool is
therefore pure: local PDF + params -> JSON on stdout.

Expected params:
  resource: resource key containing the PDF (default: "pdf")
  layer_id, kind, label, series, coverage
  count: number of sections to read
  item_prefix: output id prefix, e.g. "ms" or "s"
  item_label_prefix: label prefix, e.g. "MS" or "S"
  segment_refs: optional [[entry_ref, exit_ref], ...] length=count

The parser intentionally relies on official length tables, not image geometry.
It reads the first `count` values from the "Length (Inches)" column, computes
cumulative lap fractions, and emits a partition range layer.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

INCH_TO_M = 0.0254


def pdftotext(path: str) -> str:
    proc = subprocess.run(["pdftotext", path, "-"], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"pdftotext failed for {path}: {proc.stderr}")
    return proc.stdout


def length_inches(text: str, count: int) -> list[int]:
    marker = "Length (Inches)"
    idx = text.find(marker)
    if idx < 0:
        raise ValueError("PDF text does not contain 'Length (Inches)'")
    tail = text[idx + len(marker):]
    # Stop before speed/time columns or speed trap table when possible. The
    # section length values are the first large integer column after the marker.
    nums = [int(x) for x in re.findall(r"(?m)^\s*(\d{3,})\s*$", tail)]
    if len(nums) < count:
        raise ValueError(f"only found {len(nums)} length-inch values, need {count}")
    return nums[:count]


def main() -> None:
    payload = json.load(sys.stdin)
    params = payload.get("params") or {}
    resource_name = params.get("resource", "pdf")
    resource = payload["resources"][resource_name]
    pdf_path = resource["local_path"]
    count = int(params["count"])
    inches = length_inches(pdftotext(pdf_path), count)
    total = sum(inches)
    refs = params.get("segment_refs") or []
    if refs and len(refs) != count:
        raise ValueError(f"segment_refs length {len(refs)} does not match count {count}")

    item_prefix = params.get("item_prefix", "s").lower()
    label_prefix = params.get("item_label_prefix", item_prefix.upper())
    cum = 0
    items = []
    for i, value in enumerate(inches, 1):
        start = cum / total
        cum += value
        end = cum / total
        item = {
            "id": f"{item_prefix}{i}",
            "label": f"{label_prefix}{i}",
            "start": round(start, 8),
            "end": round(end, 8),
            "length_m": round(value * INCH_TO_M, 3),
        }
        if refs:
            item["entry_ref"], item["exit_ref"] = refs[i - 1]
        items.append(item)
    # Force exact partition endpoint after rounding.
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
            "source": params.get("source", "IMSA / Al Kamel timing section map"),
            "url": resource.get("url"),
            "local_path": resource.get("relative_path") or str(Path(pdf_path)),
            "length_unit": "inch",
            "total_length_m": round(total * INCH_TO_M, 3),
        },
        "items": items,
    }
    print(json.dumps({"range_layers": [layer]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
