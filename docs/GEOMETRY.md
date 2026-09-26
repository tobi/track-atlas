# Surface geometry: track edges, crossing lines and corner geometry

The centerline (`layers/<id>.geojson`, role `outline`) says where the lap goes.
It does not say where the track *is*: how wide it is, where its edges run, where
a corner turns in, where its apex sits on the inside edge. This document
specifies the per-layout **surface geometry** that answers that, how it is
measured, and how good it is.

Everything here is generated, offline-reproducible from committed inputs, and
carries its own provenance and accuracy. Nothing is invented: where an edge was
not seen it is bridged and marked as such; where a corner has no geometric
peak it gets no entry/apex/exit.

## Files

| file | written by | committed | content |
|---|---|---|---|
| `raw/imagery/` | `measure_surface.py` | no (gitignored cache, recreatable from the recorded request) | NAIP RGB + NIR tiles, `manifest.json` |
| `raw/surface-<layout>.json` | `measure_surface.py` (network) | yes | the measurement: edges, midline, quality, sources |
| `raw/layers/<layout>.surface.geojson` | `build_geometry.py` / `generate.py` (offline) | yes | every surface feature (below) |
| `raw/track.json` | `build_geometry.py` / `generate.py` (offline) | yes | `layout.surface`, `geometry.surface`, crossing lines and apexes on items |

Pipeline for one track:

```bash
uv run python scripts/measure_surface.py road-atlanta   # network: NAIP -> raw/surface-<layout>.json
uv run python scripts/generate.py road-atlanta          # offline: applies it (or build_geometry.py for surface-only)
uv run python scripts/verify.py road-atlanta
```

A track opts in with `source.json`:

```json
"surface": {"imagery": "naip"}                        // every layout
"surface": {"imagery": "naip", "layouts": ["imsa"]}   // only these
```

## Conventions

- Coordinates are GeoJSON `[lon, lat]`, WGS84.
- **Left / right are in the driving direction.** Every edge polyline starts at
  the lap origin (start/finish) and runs in the driving direction.
- Every lap fraction (`marker`) stays on the **layout centerline's basis**, the
  same basis as every legacy marker, so new and old fields are comparable.
  (The measured midline has its own length, `surface.lap_length_m`; stations
  are mapped to centerline fractions by projection.)
- A **crossing line** is a 2-point segment `[left_point, right_point]`, from the
  left edge to the right edge, perpendicular to the midline.

## track.json additions

### `layout.geometry.surface`

Path (relative to `raw/`) of the surface GeoJSON, e.g. `layers/gp.surface.geojson`.

### `layout.surface` (summary)

| field | meaning |
|---|---|
| `file` | same as `geometry.surface` |
| `method` | `naip-edges/1` (method and version) |
| `measured_at` | when the measurement ran |
| `lap_length_m` | lap length along the measured midline |
| `width_m` | `{p05, median, p95}` of the measured width |
| `seen_fraction` | `{left, right, both}` share of the lap where the edge was actually seen |
| `relative_precision_m` | 1-sigma precision of a seen edge relative to the rest of the geometry |
| `absolute_accuracy_ce95_m` | the imagery's absolute horizontal accuracy (95%) |
| `unnamed_corners` | curvature peaks tighter than 80 m that no atlas corner claimed (curation hints) |
| `sources` | `naip` (service, rasters, acquisition dates, request, accuracy statement) and `seed` (the OSM centerline, used only to seed the search) |

### Corner items (`point_layers[corners].items[]`)

| field | meaning |
|---|---|
| `entry` | Crossing: geometric turn-in, where curvature rises through 35% of the peak |
| `apex` | `{marker, location, edge, quality}`: the curvature peak of the **inside edge**; `edge` is the inside side |
| `exit` | Crossing: geometric track-out, where curvature falls through 35% of the peak |
| `placement` | how it was placed: `basis` (`curvature` or `none`), `shape` (`corner`, or `kink` when R > 250 m), measured `direction`, `radius_m` (minimum midline radius), `marker_offset_m` (peak minus legacy marker, m), `declared_direction` (only when the curated direction disagrees) |

`number`, `code`, `labels` (numbered / official / driver), `direction`,
`scale`, `marker`, `location` are unchanged. `marker` stays the legacy apex
fraction for compatibility; `apex.marker` is the measured one.

Example (Road Atlanta Turn 7):

```json
{
  "id": "t7", "number": 7, "code": "7", "labels": {"numbered": "Turn 7"},
  "direction": "right", "scale": 1, "marker": 0.4855, "location": [-83.8173, 34.136191],
  "placement": {"basis": "curvature", "shape": "corner", "direction": "right",
                "radius_m": 23.3, "marker_offset_m": 96.1},
  "entry": {"marker": 0.5034, "width_m": 12.47,
            "line": [[-83.8180834, 34.1360944], [-83.8180865, 34.1362067]],
            "quality": {"source": "naip", "accuracy_m": 4.0, "relative_accuracy_m": 0.25,
                        "measured": true, "date": "2023-10-22"}},
  "apex":  {"marker": 0.51297, "location": [-83.8183204, 34.1363396], "edge": "right",
            "quality": {"source": "naip", "accuracy_m": 4.0, "relative_accuracy_m": 0.25,
                        "measured": true, "date": "2023-10-22"}},
  "exit":  {"marker": 0.51542, "width_m": 12.39,
            "line": [[-83.8184607, 34.1364224], [-83.8183268, 34.136413]],
            "quality": {"source": "naip", "accuracy_m": 4.0, "relative_accuracy_m": 0.25,
                        "measured": true, "date": "2023-10-22"}}
}
```

### Layout points and ranges

- `layout_points` items (start/finish, pit entry, pit exit) get `line`: the
  crossing at their marker.
- Every range item gets `start_line` / `end_line` (timing-sector boundaries,
  corner ranges, complexes, microsectors…).
- `corner_complexes` items also get `entry` / `exit`: the entry line of the
  first member corner with a geometric placement and the exit line of the last.
  Membership is unchanged; a complex is never inferred from adjacency.
- `corner_ranges` stay the braking-inclusive analysis zones they were; the
  geometric turn-in / track-out are the corner's `entry` / `exit`.

### Quality (every geometric feature)

```json
{"source": "naip", "accuracy_m": 4.0, "relative_accuracy_m": 0.25, "measured": true, "date": "2023-10-22"}
```

- `source`: `naip`, `osm`, `survey` or `derived`.
- `accuracy_m`: absolute, 95%: `hypot(imagery CE95, relative_accuracy_m)`.
- `relative_accuracy_m`: against the rest of the layout's geometry (what widths,
  lines and apexes relative to the edges depend on). A feature on a bridged
  (unseen) span adds 1.5 m.
- `measured`: false when the feature rests on a bridged span or a trace.

## `layers/<id>.surface.geojson`

| role | geometry | properties |
|---|---|---|
| `edge_left`, `edge_right` | LineString, closed, driving direction from the origin | `unseen_spans` (lap-fraction intervals that were bridged), `quality` (+ `measured_fraction`) |
| `midline` | LineString, closed | derived from the edges; `quality.source = derived` |
| `surface` | Polygon (outer ring = the edge away from the lap interior, hole = the other) | only when both edges are simple and the polygon is valid |
| `pit_lane` | LineString | `name`, `osm_way`, `quality` (OSM trace, 5 m, not measured) |
| `start_finish`, `pit_entry`, `pit_exit` | LineString (crossing) | `marker`, `width_m`, `quality` |
| `corner_entry`, `corner_exit` | LineString (crossing) | `corner`, `marker`, `width_m`, `quality` |
| `apex` | Point | `corner`, `edge`, `marker`, `quality` |
| `complex_entry`, `complex_exit` | LineString (crossing) | `complex` (only complexes of two or more corners) |
| `sector_boundary` | LineString (crossing) | `range` (the timing sector starting there) |

## The centerline: still needed, for two reasons

1. It is the **lap-fraction basis** of every existing marker, range and
   consumer (Omatrack maps GPS to lap fraction along it). Changing it would
   shift every legacy marker.
2. It **seeds** the edge search (lap order, origin, direction and the rough
   corridor).

The measured `midline` is geometrically better (it is centred on the measured
asphalt; OSM ways traced from TIGER road data are often metres off). A future
schema version could make the midline the basis and re-express legacy markers
on it; until then the centerline stays and the midline is derived.

## Measuring the edges (`lib/edges.py`, `measure_surface.py`)

Imagery: **USDA NAIP** via the USGS National Map ImageServer (public domain,
compatible with the atlas's ODbL; commercial basemaps may not be traced). It is
exported as Web-Mercator tiles at 0.5 m ground sample (native 0.6 m in recent
years), natural colour plus the near-infrared band, and cached.

1. **Straightened grid.** The seed centerline is resampled at 1 m and smoothed
   (sigma 4 m) for its normals. Imagery is sampled on a station x lateral-offset
   grid (1 m x 0.25 m, +/- 26 m), bilinear in RGB + NIR.
2. **Self-calibrated asphalt model.** Samples within 1.5 m of the seed are mostly
   racing surface; samples 16-26 m out mostly are not. Each sample gets a robust
   log-likelihood ratio (Cauchy over median/MAD models) of chroma, NDVI and
   brightness, squashed to p(asphalt). No per-track tuning.
3. **Edge evidence** per side and offset: mean p(asphalt) over the 1.5 m inside
   minus the 1.5 m outside, plus a bonus for a painted line (a narrow, neutral,
   bright ridge). Dark (shadowed) windows give neutral evidence, and a station
   whose outside window is dark is flagged as occluded.
4. **Optimal path.** Dynamic programming per side through (station, offset):
   maximum total evidence, at most 0.5 m lateral change per metre of lap with a
   linear penalty, and a soft prior around the lap's typical half-width (free
   within 2.5 m). The closed lap is solved by unrolling it three times and
   keeping the middle copy. On the inside of a tight turn the search stops at
   85% of the local radius (normals cross beyond it).
5. **Recentre** three times: the midline of the two edges becomes the seed and
   steps 1-4 run again, so a seed metres off the asphalt is corrected
   (`quality.seed_offset_m` in the measurement records how far).
6. **Robust smoothing and bridging.** Each half-width is smoothed with
   iteratively reweighted Gaussian smoothing (sigma 10 m, Tukey weights at
   0.5 m) over the stations that were seen. Unseen spans (weak contrast,
   occlusion) are bridged linearly between seen neighbours and listed in
   `unseen_spans`, never hidden.
7. **Precision.** `relative_precision_m` = robust spread of the raw DP path
   against the smoothed edge, combined with half a ground pixel.

The edges are stored simplified (Douglas-Peucker, 0.05 m).

## Placing corners (`lib/surface.py`)

1. **Curvature** of the measured midline, smoothed with sigma 8 m.
2. **Lobes**: maximal runs of one turning sign with |kappa| > 1/600 m.
   Every local maximum inside a lobe is a peak; two peaks merge unless the dip
   between them falls below 60% of the smaller one; a lobe with several peaks
   is split at the minima between them. Peaks with R > 400 m are dropped.
3. **Matching** atlas corners (in number order) to peaks (in lap order) by an
   order-preserving dynamic programme. Cost of corner k on peak j:

   ```
   |peak - legacy marker| / 80 m
   + 5    if the curated direction disagrees with the peak's
   - 1.5 * ln(kappa_peak * 600 m)          (tighter peaks are preferred)
   ```

   A corner may stay unmatched (cost 1); a peak serves at most one corner; a
   peak more than 150 m from the marker is never matched. Unclaimed peaks
   tighter than R 80 m are reported in `surface.unnamed_corners`.
4. **Entry / exit**: walk out from the peak, within its share of the lobe, while
   curvature stays above max(1/600 m, 35% of the peak). Entry and exit are at
   least 3 m from the apex.
5. **Apex**: the curvature peak of the **inside edge** within +/- 15 m of the
   midline peak, placed on that edge.
6. The measured direction is authoritative for `apex.edge`; a disagreeing
   curated direction is recorded in `placement.declared_direction` and warned
   by `verify.py` (fix it in `overrides.json`).

Crossing lines are the edge-to-edge segment along the midline normal at the
station. Pit-lane features are OSM ways named or tagged as pit lane whose ends
come within 60 m of the lap (a trace, not measured).

## Validation (`lib/surface_checks.py`, run by `verify.py`)

Errors:

- an edge is not closed, or self-intersects; the two edges cross;
- the edges are not left / right of the driving direction (probed every 50 m);
- the measured lap runs against `layout.direction`;
- the surface polygon is invalid;
- a crossing line's endpoints are more than 0.3 m from their edges, or its
  width is outside 4-45 m;
- an apex is not strictly between its corner's entry and exit, is more than
  0.3 m off its inside edge, or is on the edge opposite the corner's direction.

Warnings: curated direction disagrees with geometry; a corner without a
curvature peak; an unnamed tight peak; an edge seen on less than 80% of the lap.
Info: absolute accuracy above the 2 m racing-line gate.

## Accuracy, honestly

- **Relative** geometry (width, edge shape, where the apex sits against the
  edge) is good to about 0.25-0.5 m where the edge was seen.
- **Absolute** position is bounded by the imagery's registration: NAIP's
  contract is 95% of well-defined points within **4 m** (6 m before 2016).
  Individual acquisitions are often better, but that is not guaranteed and has
  not been measured here, so `accuracy_m` reports the contract. A consumer gating on 2 m
  absolute accuracy (Omatrack's racing-line and apex rendering) should treat
  NAIP geometry as not meeting the gate unless it registers its GPS against the
  edges (for example, by fitting a lap's GPS trace into the surface polygon).
- **Bridged spans** (tree shadow, bridges, paved run-off without a painted line,
  pit merges) are interpolated and marked `measured: false` with 1.5 m added.
- **Outside the conterminous US** NAIP does not exist; those tracks have no
  surface until another open imagery source is added (see TODO.md).
