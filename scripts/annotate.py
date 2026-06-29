#!/usr/bin/env python3
"""
annotate.py — ask a model to fill corner names, complexes, direction, scale
and flag any data errors it spots.

Usage:
    python scripts/annotate.py <slug>            # writes tracks/<slug>/overrides.json
    python scripts/annotate.py silverstone --dry  # print proposed overrides, don't write

The model is given:
  - the ordered corner list (number, current names, marker, location_source)
  - the GeoJSON outline + corner point coordinates
  - the track's declared metadata (length, direction, country, series)

It returns structured JSON we merge into overrides.json.

Model: reads ANTHROPIC_API_KEY from env; calls the model set in ANNOTATE_MODEL
(default: claude-fable-5 via the anthropic messages API directly -- no DSPy
needed, this is just "give the superintelligence the data and ask it to think").
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent))
from layer_tools.curvature_apexes import compute_layers as compute_curvature_layers  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TRACKS = ROOT / "tracks"

# --------------------------------------------------------------------------- #
# Schema we ask the model to fill out (described in natural language in the   #
# prompt; returned as JSON we validate here)                                  #
# --------------------------------------------------------------------------- #

CORNER_FIELDS = """
For EACH corner return a JSON object with:
  "number":     int  (same as input — required)
  "colloquial": str | null   — what drivers call it  ("Becketts", "Chapel", "The Loop")
  "official":   str | null   — circuit/governing-body name ("Becketts Corner")
  "complex":    str | null   — multi-corner SECTION name drivers say as one word
                               ("Maggotts-Becketts-Chapel", "Copse" is NOT a complex,
                                a complex is only when 2+ consecutive corners share a name)
  "direction":  "left" | "right" | null
  "scale":      1-6 | null   — 1=hairpin, 6=barely a kink
  "error":      str | null   — any data problem you spotted:
                               wrong direction, implausible marker, coordinate off track,
                               numbering gap, corner that shouldn't exist, etc.
                               null if clean.
"""

SYSTEM = """\
You are a motorsport circuit data expert. You have deep knowledge of racing circuit
corner names — both official FIA/circuit names and the colloquial names drivers use.
You will be given a circuit's metadata and corner list and asked to fill in the names,
complexes, direction, severity scale, and flag any data errors.

Rules:
- Prefer the colloquial name drivers actually say in radio/interviews.
- "complex" is ONLY for a sequence of 2+ consecutive corners that share a collective name
  that a driver would say as a single unit ("Maggotts-Becketts", "Esses", "Porsche Curves").
  Don't mark a single named corner as a complex.
- direction = the way the car turns AT the apex (not the runoff).
- scale: 1=tight hairpin (90°+), 2=slow corner (<120°), 3=medium, 4=fast,
  5=very fast, 6=barely a deflection.
- error: be specific. "corner 7 direction should be right not left",
  "T14 marker 0.72 looks too late — probably 0.62", etc.
- Return ONLY a JSON object, no prose, no markdown fences.
"""


def build_prompt(slug: str) -> tuple[str, dict]:
    """Return (prompt_text, layout_dict) for the first layout of a track."""
    track = json.loads((TRACKS / slug / "raw" / "track.json").read_text())
    lo = track["layouts"][0]
    gj_path = TRACKS / slug / "raw" / lo["geometry"]["centerline"]
    gj = json.loads(gj_path.read_text())

    # Build a compact corner summary
    corners_summary = []
    corners = next((l.get("items", []) for l in lo.get("point_layers", []) if l.get("id") == "corners"), [])
    complex_by_id = {}
    for comp in next((l.get("items", []) for l in lo.get("range_layers", []) if l.get("id") == "corner_complexes"), []):
        if len(comp.get("members", [])) <= 1:
            continue
        for mid in comp.get("members", []):
            complex_by_id[mid] = comp.get("label")
    for c in corners:
        row = {
            "number": c["number"],
            "marker": c.get("marker"),
            "location": c.get("location"),
            "location_source": c.get("location_source", "osm-way"),
            "current_labels": c.get("labels", {}),
            "current_complex": complex_by_id.get(c.get("id")),
            "current_direction": c.get("direction"),
            "current_scale": c.get("scale"),
        }
        corners_summary.append(row)

    # Build compact GeoJSON: just outline coords + corner points
    outline_coords = next(
        (f["geometry"]["coordinates"]
         for f in gj["features"] if f["properties"].get("role") == "outline"),
        []
    )
    # Downsample outline to ~150 pts for prompt size
    step = max(1, len(outline_coords) // 150)
    outline_sampled = outline_coords[::step]

    corner_pts = [
        {"n": f["properties"]["number"],
         "display": f["properties"].get("display"),
         "coord": f["geometry"]["coordinates"]}
        for f in gj["features"]
        if f["properties"].get("role") == "corner"
    ]

    try:
        curvature_layers = compute_curvature_layers(str(gj_path), {
            "max_apexes": max(16, len(corners) * 2),
            "min_separation_m": 60.0,
            "smooth_window_m": 70.0,
            "curvature_percentile": 0.65,
        }, {"relative_path": str(gj_path.relative_to(TRACKS / slug))})
        curvature_apexes = [
            {"marker": a.get("marker"), "location": a.get("location"), "direction": a.get("direction"), "scale": a.get("scale")}
            for a in curvature_layers.get("point_layers", [{}])[0].get("items", [])
        ]
    except Exception:
        curvature_apexes = []

    prompt = f"""
Circuit: {track['name']}
Slug: {slug}
Country: {track.get('country')}
Series: {', '.join(track.get('series', []))}
Layout: {lo['name']}  ({lo.get('length_m', '?')} m, {lo.get('direction', '?')})
Total corners: {len(corners)}

--- CURRENT CORNER DATA ---
{json.dumps(corners_summary, indent=2)}

--- GEOJSON OUTLINE (sampled, [lon,lat]) ---
{json.dumps(outline_sampled)}

--- GEOJSON CORNER POINTS ---
{json.dumps(corner_pts)}

--- CURVATURE-DERIVED APEX CANDIDATES ---
These are geometry-only candidates from a smoothed κ(s) profile. Use them to spot
misplaced/missing apexes, but do not treat labels/numbers as authoritative.
{json.dumps(curvature_apexes)}

--- YOUR TASK ---
{CORNER_FIELDS}

Return a JSON object like:
{{
  "{lo['id']}": {{
    "corners": {{
      "1": {{"colloquial": "...", "official": "...", "complex": null, "direction": "right", "scale": 4, "error": null}},
      "2": {{"colloquial": "...", ...}},
      ...
    }},
    "errors_summary": "one-line summary of any structural issues found, or null"
  }}
}}

Only include corners where you have something to add or correct. Omit corners
you have nothing useful to say about (no known name, no error, existing data already correct).
"""
    return prompt.strip(), lo


def call_model(prompt: str, model: str) -> str:
    # Pick up key from env or hermes .env file
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        import re
        env_path = Path.home() / ".hermes" / ".env"
        if env_path.exists():
            m = re.search(r'ANTHROPIC_API_KEY=([^\s\n]+)', env_path.read_text())
            if m:
                api_key = m.group(1).strip()
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_text(msg.content)


def _extract_text(content) -> str:
    """Pull text out of the response, skipping ThinkingBlocks."""
    for block in content:
        if hasattr(block, "text"):
            return block.text.strip()
    raise ValueError("No text block in model response")


def parse_response(text: str) -> dict:
    # Strip any accidental markdown fences
    t = text
    if t.startswith("```"):
        t = "\n".join(t.split("\n")[1:])
    if t.endswith("```"):
        t = "\n".join(t.split("\n")[:-1])
    return json.loads(t)


def merge_overrides(existing: dict, new_data: dict) -> dict:
    """Deep-merge new_data into existing overrides (new wins on conflicts)."""
    result = json.loads(json.dumps(existing))
    for layout_id, layout_data in new_data.items():
        if layout_id not in result:
            result[layout_id] = {}
        for key, val in layout_data.items():
            if key == "corners":
                if "corners" not in result[layout_id]:
                    result[layout_id]["corners"] = {}
                for num, cdata in val.items():
                    result[layout_id]["corners"][num] = {
                        **result[layout_id]["corners"].get(num, {}),
                        **{k: v for k, v in cdata.items() if v is not None}
                    }
            else:
                result[layout_id][key] = val
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--dry", action="store_true", help="print result, don't write file")
    ap.add_argument("--model", default=os.environ.get("ANNOTATE_MODEL", "claude-fable-5"))
    args = ap.parse_args()

    slug = args.slug
    print(f"[annotate] {slug} via {args.model}")

    prompt, lo = build_prompt(slug)
    print(f"[annotate] prompt ~{len(prompt)} chars, calling model...")

    raw = call_model(prompt, args.model)

    try:
        new_data = parse_response(raw)
    except json.JSONDecodeError as e:
        print("ERROR: model returned non-JSON:")
        print(raw[:2000])
        sys.exit(1)

    # Print a summary
    layout_id = lo["id"]
    corners_annotated = new_data.get(layout_id, {}).get("corners", {})
    errors_summary = new_data.get(layout_id, {}).get("errors_summary")
    print(f"\n[annotate] {len(corners_annotated)} corners annotated/corrected")
    if errors_summary:
        print(f"[annotate] errors_summary: {errors_summary}")

    # Show diff vs current
    track = json.loads((TRACKS / slug / "raw" / "track.json").read_text())
    existing_items = next((l.get("items", []) for l in track["layouts"][0].get("point_layers", []) if l.get("id") == "corners"), [])
    existing_corners = {str(c["number"]): c for c in existing_items}
    existing_complex = {}
    for comp in next((l.get("items", []) for l in track["layouts"][0].get("range_layers", []) if l.get("id") == "corner_complexes"), []):
        if len(comp.get("members", [])) <= 1:
            continue
        for mid in comp.get("members", []):
            existing_complex[mid] = comp.get("label")
    for num, patch in sorted(corners_annotated.items(), key=lambda x: int(x[0])):
        cur = existing_corners.get(num, {})
        changes = []
        if patch.get("colloquial") and patch["colloquial"] != cur.get("labels", {}).get("driver"):
            changes.append(f"colloquial: {patch['colloquial']!r}")
        if patch.get("official") and patch["official"] != cur.get("labels", {}).get("official"):
            changes.append(f"official: {patch['official']!r}")
        if patch.get("complex") and patch["complex"] != existing_complex.get(cur.get("id")):
            changes.append(f"complex: {patch['complex']!r}")
        if patch.get("direction") and patch["direction"] != cur.get("direction"):
            changes.append(f"direction: {patch['direction']!r}")
        if patch.get("scale") and patch["scale"] != cur.get("scale"):
            changes.append(f"scale: {patch['scale']}")
        if patch.get("error"):
            changes.append(f"⚠ ERROR: {patch['error']}")
        if changes:
            cname = (patch.get("colloquial") or patch.get("official")
                     or cur.get("labels", {}).get("driver") or f"T{num}")
            print(f"  T{num:>2} {cname:<22}  " + "  |  ".join(changes))

    if args.dry:
        print("\n[dry run] proposed overrides.json content:")
        print(json.dumps(new_data, indent=2))
        return

    # Merge into existing overrides.json
    ov_path = TRACKS / slug / "overrides.json"
    existing = json.loads(ov_path.read_text()) if ov_path.exists() else {}
    merged = merge_overrides(existing, new_data)
    ov_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
    print(f"\n[annotate] wrote {ov_path}")
    print("Run: python scripts/generate.py", slug, "&& python scripts/verify.py", slug)


if __name__ == "__main__":
    main()
