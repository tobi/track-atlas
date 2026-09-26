# Track Atlas Surface Tools

Use this skill when measuring or re-measuring a track's surface: edges, midline, crossing lines, corner entry/apex/exit, and the absolute position of all of it. Also when adding an imagery or lidar source, or when a `verify.py` surface/position warning needs fixing.

## Core model

- The OSM centerline only **seeds** the search. The measured **midline** becomes the layout's geometry and lap-fraction basis (`geometry.basis: "midline"`).
- Edges are traced in open orthoimagery (`lib/edges.py`). Their absolute position comes from registering the imagery onto USGS 3DEP lidar intensity (`lib/register.py`, `lib/position.py`), followed by the datum step from NAD83(2011) to WGS 84 ~ ITRF2014 at epoch 2026.0 (`lib/datum.py`).
- Accuracy is a budget, never a claim: `CE95 = hypot(reference, registration, datum)`. It is recorded in `position.budget_ce95_m`.

Specs: `docs/GEOMETRY.md`. Sources, licences and served frames: `docs/SOURCES.md`.

## Workflow

```bash
# 1. opt in: tracks/<slug>/source.json
#    "surface": {}                      auto imagery + auto lidar, every layout
#    "surface": {"layouts": ["imsa"]}   only some layouts
uv run python scripts/measure_surface.py <slug> --find-lidar   # optional: every 3DEP survey on the lap
uv run python scripts/measure_surface.py <slug>                # network, minutes; writes raw/surface-<layout>.json
uv run python scripts/generate.py <slug>                       # offline: applies it (midline basis)
uv run python scripts/verify.py <slug>                         # must be green
```

Surface-only reapply (no Lovely/OSM rebuild): `uv run python scripts/build_geometry.py <slug>`.

## Auto selection

- **Imagery.** `lib/imagery.covering(lap)` returns every source whose `coverage` box contains the lap, with NAIP last. Each one is measured.
  - A candidate is refused if either edge is seen on less than 20% of the lap. That means no real coverage (e.g. FDEP outside its counties).
  - The rest are scored `absolute CE95 + 4 m x (1 - seen_both)`, and the lowest wins.
  - The comparison is written to `selection` in the measurement and in `layout.surface.selection`. Read it before questioning the choice.
- **Lidar.** `lib/lidar.pick(lap)` takes surveys covering at least 95% of the lap. Those with a stated accuracy come first (sharpest first), then the newest. At most three are used.
  - The first survey that registers is the reference. The others are checks.
  - With two surveys, their per-window difference separates estimator noise from real non-rigid imagery distortion.
- Pin `"imagery": "<id>"` or `"lidar": [...]` only to investigate one source. Unpin before committing.

## Adding an imagery source

Add an entry to `lib/imagery.SOURCES` with:

- `service`
- `license`: it must allow ODbL-derived geometry. Esri, Google, Bing and Mapbox are never allowed.
- `ce95_m` plus `accuracy_basis`: tested beats specified. Use `None` if not stated.
- `frame`: what the service really serves. Usually `"WGS84-service"`.
- `coverage`: a `[w, s, e, n]` box.

The served frame is re-tested against lidar on every run. See `position.imagery_frame_basis`: e.g. Indiana 2025 turned out to be identity-labelled NAD83. Record new findings in docs/SOURCES.md.

A source with a tested accuracy better than the lidar becomes the reference itself (CT 2023). Otherwise lidar positions it.

## Reading the result

The console and `raw/surface-<layout>.json` report:

- `quality.seen_fraction`: the share of each edge observed rather than bridged. `unseen_spans` lists where.
- `quality.relative_precision_m`: the precision of the edge shape.
- `position.checks`: per-survey registration, `residual_vs_applied_m` (must be < 1 m), and survey-to-survey agreement.
- `position.reference.stated`: `false` means an assumed 1.0 m CE95. `verify.py` flags it.

## Failure spots

- Paved run-off without a painted line, pit merges, bridges and tree shadow. Look at the edges over the imagery at every corner before committing.
- Registration refused (`no reliable registration`): the window spread exceeded 1.5 m. The imagery is not coherent with that survey.
- A curvature lobe matched one lobe off in esses (COTA T7-T9). Check `placement.marker_offset_m` for outliers.
- Curated direction disagrees with the measured one: fix `direction` in `overrides.json`, never in `raw/track.json`.

## Rules

- Never use owner telemetry or GPS logs. Never trace commercial basemaps.
- Caches (`raw/imagery/`, `raw/lidar/`) are gitignored. Commit `raw/surface-*.json`, `raw/track.json` and `raw/layers/*`.
