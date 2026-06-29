# Track Atlas Layer Tools

Use this skill when adding data-derived point/range layers to Track Atlas: IMSA microsectors, IMSA timing sectors, WEC slow zones, WEC/Le Mans microsectors, speed traps, timing loops, DRS zones, or any other source that should become a `point_layers[]` or `range_layers[]` entry.

## Core model

Track Atlas is layout-first:

- `tracks/<slug>/source.json` defines the facility/layout basics and base data imports.
- `tracks/<slug>/generation-config.json` defines additional generated layer inputs.
- `scripts/generate.py <slug>` writes the base `raw/track.json`, then automatically runs the generation config.
- `scripts/build_layers.py <slug>` reruns only `generation-config.json` against an existing `raw/track.json`.
- Converter tools live in `scripts/layer_tools/*.py`.

Generated layer output is first written under `tracks/<slug>/raw/generated-layers/` and then merged into the target layout:

- `point_layers[]` for discrete lap locations, e.g. timing loops, marshal posts.
- `range_layers[]` for lap intervals, e.g. timing sectors, IMSA microsectors, slow zones.

## Important design rule

Resolve everything the tool needs **before** invoking the tool.

The runner (`scripts/lib/layer_runner.py`) reads `generation-config.json`, downloads/copies every declared resource into:

```text
tracks/<slug>/raw/layer-sources/<config-id>/
```

Then it invokes the converter as a pure stdin/stdout process:

```text
resolved local files + track/layout context JSON on stdin
→ produced point_layers/range_layers JSON on stdout
→ raw/generated-layers/<config-id>.json
→ merged into raw/track.json
```

Converter tools must not assume current working directory, fetch URLs themselves, or read arbitrary repo files. If they need data, add it to `generation-config.json` as a resource or param so the runner resolves it first. Generated layer JSON must exist in `raw/generated-layers/` as an inspectable artifact before it is baked into `raw/track.json`.

## generation-config.json format

Example:

```jsonc
{
  "layers": [
    {
      "id": "imsa_microsectors_2026",
      "layout": "gp",
      "tool": "imsa_timing_pdf",
      "resources": {
        "pdf": {
          "url": "https://imsa.results.alkamelcloud.com/Results_NoticeBoard/26-2026/14_Watkins%20Glen%20International/03_Timing%20All%20Sections%20Map.pdf",
          "filename": "imsa-2026-timing-all-sections-map.pdf"
        }
      },
      "params": {
        "resource": "pdf",
        "layer_id": "imsa_microsectors",
        "kind": "microsectors",
        "label": "IMSA Microsectors",
        "series": ["imsa"],
        "coverage": "partition",
        "count": 11,
        "item_prefix": "ms",
        "item_label_prefix": "MS",
        "source": "IMSA / Al Kamel Timing All Sections Map",
        "segment_refs": [["T1", "T2"], ["T2", "T3"]]
      }
    }
  ]
}
```

`id` is the config/run id. `layer_id` is the actual layer id in `track.json`. Multiple configs may target existing generated layers; later configs replace layers with the same `id`.

## Tool contract

A layer tool is an executable Python script at:

```text
scripts/layer_tools/<tool>.py
```

It receives JSON on stdin:

```jsonc
{
  "config_id": "imsa_microsectors_2026",
  "slug": "watkins-glen",
  "track": { /* full current raw/track.json */ },
  "layout": { /* selected layout object */ },
  "resources": {
    "pdf": {
      "name": "pdf",
      "url": "https://...",
      "local_path": "tracks/watkins-glen/raw/layer-sources/.../file.pdf"
    }
  },
  "params": { /* config params */ }
}
```

It prints JSON on stdout:

```jsonc
{
  "range_layers": [
    {
      "id": "imsa_microsectors",
      "kind": "microsectors",
      "label": "IMSA Microsectors",
      "series": ["imsa"],
      "coverage": "partition",
      "provenance": {"source": "...", "url": "..."},
      "items": [
        {"id": "ms1", "label": "MS1", "start": 0.0, "end": 0.03926739}
      ]
    }
  ]
}
```

No prose, no markdown, stdout must be JSON. Diagnostics go to stderr.

## Range-internal points

A `range_layers[].items[]` object may include `points[]` for landmarks inside the interval:

```jsonc
{
  "id": "t1",
  "label": "The 90",
  "start": 0.03288,
  "end": 0.08992,
  "anchor": "t1",
  "points": [
    {"id": "apex", "role": "apex", "label": "Apex", "marker": 0.066, "point_ref": "t1"}
  ]
}
```

Use this instead of overloading `start`/`end`: a corner range covers braking → apex → exit, while the apex remains a point inside it. `point_ref` should point to an item in a layout point layer when that point exists; otherwise generated tools can embed `marker` and/or `location` directly.

Keep corner layer labels cohesive:

- `point_layers[id="corners"].label` = `Corner Apexes`
- `range_layers[id="corner_ranges"].label` = `Each Corner`
- `range_layers[id="corner_complexes"].label` = `Corner Complexes`

`corner_complexes` is a corner-group layer, not just "the special multi-corner things". It should be the corners list after merging adjacent named complexes, with one exception: omit solo high-speed corners/kinks (`scale` 5 or 6) because they clutter the layer without adding useful grouping information. A complex like Porsche Curves still has several `members[]` and several `points[{role:"apex"}]`, even when those apexes are fast. Do not create fake complexes for separated corners just because they share a straight or sector (Le Mans first/second Mulsanne chicanes stay separate).

## Existing tools

### `curvature_apexes`

Computes a smooth 1D curvature profile `κ(s)` from a layout centerline GeoJSON and emits:

- `point_layers[id="curvature_apexes"]`: candidate apex points with marker, location, direction, and severity scale.
- `range_layers[id="curvature_corner_ranges"]`: candidate corner influence ranges around each apex.

This is the first practical piece of a minimum-lap-time / Frenet toolchain: uniform arc-length resampling, finite-difference curvature, circular smoothing, local curvature maxima, then thresholded ranges padded before/after the apex. It is meant for verification and curation, not as an authoritative corner source.

The same engine is wired into check/QA tools:

```bash
uv run python scripts/verify.py <slug>                  # warns when named corners are far from κ apexes
uv run python scripts/check_apexes.py <slug>            # detailed nearest-apex table
uv run python scripts/check_corner_curation.py <slug>   # names/groups/OSM curation signals
uv run python scripts/suggest_phases.py <slug>          # includes κΔ column beside phase ranges
```

`annotate.py` also includes curvature-derived apex candidates in the model prompt so name/number cleanup can use geometry evidence.

Example config:

```jsonc
{
  "id": "curvature_apexes_gp",
  "layout": "gp",
  "tool": "curvature_apexes",
  "resources": {
    "centerline": {"path": "raw/layers/gp.geojson"}
  },
  "params": {
    "max_apexes": 20,
    "step_m": 4,
    "smooth_window_m": 90,
    "min_separation_m": 90,
    "pre_brake_m": 75,
    "post_accel_m": 55
  }
}
```

Useful params:

- `resource`: resource key, default `centerline`.
- `point_layer_id`, `range_layer_id`: override output layer ids.
- `max_apexes`: cap candidates after strength sorting and separation filtering.
- `step_m`: centerline resample spacing.
- `smooth_window_m`: curvature smoothing window. Increase for noisy OSM or long fast complexes.
- `min_abs_curvature`: explicit threshold; if omitted the tool chooses one from a curvature percentile.
- `curvature_percentile`: auto-threshold percentile, default `0.82`.
- `min_separation_m`: minimum distance between apex candidates.
- `range_threshold_ratio`, `range_min_abs_curvature`: range-growth threshold around each apex.
- `pre_brake_m`, `post_accel_m`: padding before/after the thresholded corner body. These exist because Track Atlas corner ranges should start before the brake zone and last a bit into acceleration, while the apex remains a distinct point.

### `imsa_timing_pdf`

Converts IMSA / Al Kamel timing-section PDFs into a partition `range_layer` by parsing the official `Length (Inches)` column with `pdftotext`.

Use for:

- `Timing 3 Sector Map.pdf` → `timing_sectors`
- `Timing All Sections Map.pdf` → `imsa_microsectors`

Required params:

- `layer_id`
- `count`
- `item_prefix`
- `item_label_prefix`

Optional params:

- `kind`
- `label`
- `series`
- `coverage`
- `source`
- `segment_refs`: list of `[entry_ref, exit_ref]` pairs.

## Known source patterns

### IMSA / Al Kamel Noticeboard

Public IMSA event noticeboards expose timing maps such as:

```text
https://imsa.results.alkamelcloud.com/noticeBoard.php
```

Useful PDFs under `Results_NoticeBoard/<season>/<event>/`:

- `03_Timing 3 Sector Map.pdf`
- `03_Timing All Sections Map.pdf`
- `04_Track Map.pdf`

The “Timing All Sections Map” is the preferred IMSA microsector source because it has official section lengths. The Watkins Glen example is implemented in `tracks/watkins-glen/generation-config.json`.

HH Timing also documents IMSA Al Kamel V2 loop pairs here:

```text
https://help.hhtiming.com/series-specific-info/imsa/
```

Use it to cross-check loop names and per-track microsector sequences.

### WEC / Le Mans slow zones

HH Timing documents the Le Mans slow-zone and microsector loop definitions:

```text
https://help.hhtiming.com/series-specific-info/lm24/
```

The downloadable `.cha` configs are also parseable and contain exact strings, e.g.:

```text
SZ1,FL,Z4;SZ2,Z4,IP1;SZ3,IP1,Z12;SZ4,Z12,A7-1;SZ5,A7-1,A8-1;SZ6,A8-1,SCLB;SZ7,SCLB,PORIN;SZ8,PORIN,POROUT;SZ9,POROUT,FL
```

WEC / Al Kamel results pages expose circuit maps:

```text
https://fiawec.alkamelsystems.com/
```

For exact fractions, prefer official lengths when a timing-section table exists. If only loop pairs exist, do not invent fractions: either use already-curated marker data, parse a map with distances, or build a tool that snaps loop coordinates to the centerline from a declared source.

## Workflow

1. Find a source and save the URL in `generation-config.json`.
2. Pick or write a `scripts/layer_tools/<tool>.py` converter.
3. Put every converter input in `resources` or `params`.
4. Run:

```bash
uv run python scripts/generate.py <slug>
# or, after only editing generation-config.json:
uv run python scripts/build_layers.py <slug>
```

5. Inspect the raw generated layer artifact:

```text
tracks/<slug>/raw/generated-layers/<config-id>.json
```

6. Validate:

```bash
uv run python scripts/verify.py <slug>
```

7. Inspect `tracks/<slug>/raw/track.json` and ensure the layer has provenance.

## Lessons learned / gotchas

- Range layer fractions are only correct visually if the layout GeoJSON centerline starts at marker `0.0` / start-finish. `generate.py` rotates generated centerlines to start at `layout_points.start_finish`; do not remove this.
- Generated layers must be inspectable raw artifacts first: `raw/generated-layers/<config-id>.json`, then baked into `raw/track.json`.
- Do not create a `straights` layer by default. It clutters the UI and is not usually a useful verification layer. If a series publishes official straight/timing-zone data, add it deliberately as a sourced range layer with provenance.
- The site is layer-first. Timing sectors are just `range_layers[id="timing_sectors"]`; do not add separate sector-only UI/data paths.
- For tracks with many range items (microsectors/slow zones), keep item controls compact (chips/swatches) and use hover to preview individual segments.
- Avoid competing map popups. The app uses one cursor readout in the side panel plus map highlights.
- Corners have two related but different shapes: an apex is a point; the corner/range starts before the braking zone and ends after initial acceleration. Use `range_layers[].items[].points[]` for internal landmarks such as `role: "apex"`, usually with `point_ref` back to the corner point item.
- If an upstream source collapses/misnumbers corners (Watkins Glen iRacing did), use a curated `replace_corners` override rather than trying to patch names one-by-one.

## Rules for adding new tools

- Tools must be deterministic.
- Tools must read one JSON object from stdin and print one JSON object to stdout.
- Do not fetch URLs inside tools; add URLs to `generation-config.json` resources.
- Do not rely on CWD; use `resources.*.local_path`.
- Include provenance: source name, URL, local path, unit assumptions.
- For partition layers, output exact `start: 0.0` and `end: 1.0` after rounding.
- If a source gives loop pairs but not lengths/coordinates, output loop refs only if the schema supports it or stop and add a better source/tool. Do not guess lap fractions from a screenshot unless marked explicitly as estimated.
