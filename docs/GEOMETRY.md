# Surface geometry: track edges, crossing lines and corner geometry

The OSM centerline says roughly where the lap goes. It does not say where the
track *is*: how wide it is, where its edges run, where
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
| `raw/imagery/<source>/` | `measure_surface.py` | no (gitignored cache, recreatable from the recorded request) | imagery tiles (RGB + NIR where the source has it), `manifest.json` |
| `raw/lidar/<survey>/` | `measure_surface.py` | no (gitignored cache) | 3DEP EPT hierarchy and point tiles along the lap |
| `raw/surface-<layout>.json` | `measure_surface.py` (network) | yes | the measurement: edges, midline, quality, sources |
| `raw/layers/<layout>.surface.geojson` | `build_geometry.py` / `generate.py` (offline) | yes | every surface feature (below) |
| `raw/track.json` | `build_geometry.py` / `generate.py` (offline) | yes | `layout.surface`, `geometry.surface`, crossing lines and apexes on items |

Pipeline for one track:

```bash
uv run python scripts/measure_surface.py road-atlanta   # network: imagery + lidar -> raw/surface-<layout>.json
uv run python scripts/generate.py road-atlanta          # offline: applies it (or build_geometry.py for surface-only)
uv run python scripts/verify.py road-atlanta
```

A track opts in with `source.json`:

```jsonc
"surface": {}                                        // auto imagery, auto lidar, every layout
"surface": {"layouts": ["imsa"]}                     // only these layouts
"surface": {"imagery": "naip", "lidar": ["GA_Statewide_B3_2018"]}   // pinned (debugging only)
```

**Auto selection** (the default; pin only to investigate a source):

- *Imagery*: every `lib/imagery.SOURCES` entry whose coverage box contains the
  lap is measured (`imagery.covering`, NAIP last). A candidate whose edges are
  seen on less than 20% of either side is refused (no real coverage). The rest
  are scored `absolute CE95 + 4 m x (1 - seen_both)` and the lowest wins: one
  number of metres for position and coverage. Every candidate's result is
  recorded in the measurement's `selection` (and `layout.surface.selection`).
- *Lidar*: the USGS 3DEP surveys covering at least 95% of the lap
  (`lidar.pick`): stated accuracy first (sharpest first), then newest; at most
  three. The first that registers is the reference, the others are checks.
  `measure_surface.py <slug> --find-lidar` lists every survey covering the lap.

## Conventions

- Coordinates are GeoJSON `[lon, lat]` in **WGS 84 (G2139) ~ ITRF2014 at
  epoch 2026.0**, the frame a GNSS receiver reports today (see "Absolute
  position" below). US sources are delivered in NAD83(2011) and are moved.
- **Left / right are in the driving direction.** Every edge polyline starts at
  the lap origin (start/finish) and runs in the driving direction.
- On a measured layout the **midline is the geometry and the lap-fraction
  basis** (`geometry.basis: "midline"`): the layout's outline GeoJSON is the
  midline rotated to start/finish, and every `marker` is a fraction of its
  length (`surface.lap_length_m`). Unmeasured layouts (outside the US) stay on
  the OSM centerline (`basis: "centerline"`).
- A **crossing line** is a 2-point segment `[left_point, right_point]`, from the
  left edge to the right edge, perpendicular to the midline.

## track.json additions

### `layout.geometry.surface`

Path (relative to `raw/`) of the surface GeoJSON, e.g. `layers/gp.surface.geojson`.

### `layout.surface` (summary)

| field | meaning |
|---|---|
| `file` | same as `geometry.surface` |
| `method` | `edges/2` (method and version) |
| `measured_at` | when the measurement ran |
| `lap_length_m` | lap length along the measured midline |
| `width_m` | `{p05, median, p95}` of the measured width |
| `seen_fraction` | `{left, right, both}` share of the lap where the edge was actually seen |
| `relative_precision_m` | 1-sigma precision of a seen edge relative to the rest of the geometry |
| `absolute_accuracy_ce95_m` | absolute horizontal accuracy (95%) in the atlas frame: `position.budget_ce95_m.total` |
| `position` | frame, epoch, datum and registration shifts, reference, CE95 budget and independent checks (below) |
| `unnamed_corners` | curvature peaks tighter than 80 m that no atlas corner claimed (curation hints) |
| `sources` | `imagery` (id, service, rasters, acquisition dates, licence, accuracy statement), `reference` (the lidar surveys) and `seed` (the OSM centerline, used only to seed the search) |

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

- `source`: the imagery id (`naip`, `ct-2023`, ...), `osm`, `survey` or `derived`.
- `accuracy_m`: absolute, 95%: `hypot(surface absolute CE95, relative_accuracy_m)`.
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

## The midline is the basis (`lib/surface.apply_layout`)

The OSM centerline sits up to ~5 m off the asphalt centre
(`quality.seed_offset_m` p95: Daytona 5.1 m), its length differs from the
measured midline by up to a few percent, and it is in whatever frame its
tracer used. The measured midline is centred on the asphalt, in the atlas
frame, with a stated accuracy. So on a measured layout:

1. The OSM centerline only **seeds** the edge search. The layout's outline is
   the midline, rotated so fraction 0 is start/finish (the seed's origin
   projected onto the midline), simplified at 2 cm and densified to segments
   of at most 20 m.
2. Every input marker (Lovely, overrides, OSM, layer tools: all on the seed's
   basis) is **re-expressed by projection**, not rescaling:
   `m' = s_mid(project(P_seed(m))) / L_mid`. Range ends at 1.0 stay 1.0.
3. A corner the surface places (a curvature lobe) takes the **apex station** as
   its marker, the midline point there as its `location` (`location_source:
   "midline"`) and entry..exit as its `start`/`end`. How far the input marker
   was from the apex stays in `placement.marker_offset_m`. Unplaced corners and
   other point layers are projected.
4. Corner ranges with a placed corner use its entry..exit; a complex runs from
   its first member's entry to its last member's exit when those are placed,
   otherwise its projected bounds.
5. Re-applying to an already rebased `track.json` (`build_geometry.py`) is
   idempotent: drift < 0.1 m.

Consumers that prefer coordinates should use the crossing lines and apex
points directly; they do not depend on any basis.

## Measuring the edges (`lib/edges.py`, `measure_surface.py`)

Imagery: **USDA NAIP** via the USGS National Map ImageServer (public domain,
compatible with the atlas's ODbL; commercial basemaps may not be traced), or a
state orthophoto programme from `lib/imagery.SOURCES` (see docs/SOURCES.md for
licences). It is exported as Web-Mercator tiles at 0.5 m (NAIP) or 0.25 m
ground sample, natural colour plus near-infrared where the source has it, and
cached. RGB-only sources use chroma and brightness (no NDVI).

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
7. **Loop removal.** Offsetting a tight inside edge (or a V-shaped kink in the
   seed) can fold it into a swallowtail. `geo.remove_loops` cuts every loop
   shorter than 150 m at the self-intersection of non-adjacent segments;
   `quality.loops_removed` counts them per side.
8. **Precision.** `relative_precision_m` = robust spread of the raw DP path
   against the smoothed edge, combined with half a ground pixel.

The edges are stored simplified (Douglas-Peucker, 0.05 m).

## Absolute position (`lib/position.py`, `lib/register.py`, `lib/datum.py`)

The edges are traced in the imagery's own frame. Where that frame sits on the
Earth is decided separately, in three steps, each recorded in
`layout.surface.position`:

1. **Reference.** The imagery's stated accuracy is compared with each lidar
   survey's (`lib/lidar.PROJECTS`: the producer's stated horizontal accuracy,
   converted to CE95; 1.0 m CE95 assumed and flagged `stated: false` when the
   metadata gives none). The sharper one is the reference. For NAIP (4 m
   contract) that is always the lidar.
2. **Registration.** USGS 3DEP airborne lidar (public domain, EPT on S3) is
   read along the lap and its ground/road last-return intensity is rasterised at
   0.5 m (per-flight-line normalised, Gaussian-splatted, canopy masked). Both
   the lidar and the imagery see the track at ~1 um: asphalt dark, grass and
   paint bright. The imagery's NIR (pseudo-NIR for RGB sources) is high-passed
   (3 m) like the lidar and correlated (NCC) in 120 m windows every 100 m of
   lap, +/- 8 m search, sub-pixel peak. Windows with weak, ambiguous or
   search-limit peaks are dropped; the kept shifts give a Tukey-robust mean.
   Lidar is the reference, not the tracer: at 2-20 returns/m2 it cannot draw
   a sharp edge, but its absolute position is sub-metre.
3. **Datum.** The *reference's* frame is stepped to the atlas frame
   (`lib/datum.py`):
   - 3DEP lidar is delivered in NAD83(2011) and EPT relabels it "WGS 84"
     through PROJ's identity step (checked against a raw LAZ tile: 0.000 m).
     That is 0.9-1.6 m off in the conterminous US, so the NGS NAD83(2011) ->
     ITRF2014 time-dependent transformation at epoch 2026.0 is applied.
   - Imagery from ArcGIS ImageServers (NAIP, the state orthos) is stored in Web
     Mercator: the producer converted NAD83(2011) to WGS 84 when building the
     service, with an unstated transformation. At all ten venues NAIP registers
     onto the NAD83 lidar with a shift close to *minus* the step above, so a
     real transformation was applied. This frame is `WGS84-service`: assumed
     ITRF at epoch 2010.0, plate motion since then applied (~0.3 m), and the
     epoch (2002-2010) and transformation ambiguity carried in the budget
     (~0.3 m CE95). It matters only when the imagery is its own reference.
   - Not every service does this: Indiana 2025 was built with the identity
     step (it registers onto the NAD83 lidar at ~0 shift). So when imagery is
     its own reference and lidar exists, both hypotheses (~1 m apart) are
     tested against the lidar registrations and the closer one is used
     (`position.imagery_frame`, `imagery_frame_basis`).

The applied shift (registration + datum) is added to every traced coordinate.

**Budget (95 %, horizontal)** = hypot(reference, registration, datum):

- reference: the survey's CE95 (stated or assumed);
- registration: the window shifts scatter around the applied mean because of
  estimator noise and real non-rigid distortion of the imagery (which one shift
  leaves in place). With two lidar surveys the per-window difference of the two
  registrations cancels the imagery's distortion and measures the noise alone
  (noise^2 = var(diff)/2); the registration term is then the non-rigid part plus
  the standard error of the mean. With one survey the whole scatter counts;
- datum: 0.05 m on the stable plate, 0.35 m west of the San Andreas system
  (Pacific-plate motion NAD83(2011) models only to 2010).

**Checks** (`position.checks`): the registration against every listed survey,
its distance from the applied shift, and the agreement of two independent
surveys (different years, vendors and flights), which bounds both references'
errors empirically.

## Placing corners (`lib/surface.py`)

Edge points per midline station are the nearest hit of the station normal on
each edge within 40 m (`MAX_HALF_WIDTH_M`); where the normal hits nothing (a
removed loop, a sharp kink) the nearest point on that edge is used, so every
crossing line ends on both edges.

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
5. **Geometric apex** (`geometric_apex`): the curvature peak of the **inside
   edge** within +/- 15 m of the midline peak, placed on that edge. The
   corner's `apex` and `marker` are the racing-line apex (next section); the
   geometric apex is only the fallback (`apex.basis = "curvature"`).
6. The measured direction is authoritative for `apex.edge`; a disagreeing
   curated direction is recorded in `placement.declared_direction` and warned
   by `verify.py` (fix it in `overrides.json`).

Crossing lines are the edge-to-edge segment along the midline normal at the
station. Pit-lane features are OSM ways named or tagged as pit lane whose ends
come within 60 m of the lap (a trace, not measured).

## Racing line and phases (`lib/racing.py`)

A model lap on the measured surface, so a corner's apex, braking zone and
character describe how it is driven, not only how it is drawn. It is a
model (a GT3/GTD car on a flat track), labelled as such everywhere:
`dynamics.model`, `apex.basis = "racing_line"`, `surface.racing_line`.

1. **Line**: minimum curvature. Lateral offsets along the midline normals at
   every 3rd station, bounded so the car (2.05 m wide) keeps its half-width
   off each edge. Curvature is linearised as
   `n_i . (p_{i-1} - 2 p_i + p_{i+1}) / (ds_{i-1} ds_i)` and re-linearised 3
   times; each round is a box-constrained QP solved by warm-started ADMM
   (rho = 1e-4 x mean diag). Resampled to 2 m, curvature smoothed with sigma 4 m.
2. **Speed**: quasi-steady-state. Lateral limit `mu (g + downforce)`; forward
   pass limited by power (330 kW), traction (60% drive share) and the friction
   ellipse; backward pass by braking plus drag. Car: 1350 kg, mu 1.5,
   ClA 2.8, CdA 1.0.
3. **Racing apex**: the closest approach of the line to the inside edge between
   turn-in and exit (one line step inside both); ties within 0.15 m resolve to
   the middle of the run. `apex.gap_m` is that distance.
4. **Phases** per corner:
   - minimum-speed point on the line;
   - **braking point**: back from the minimum while the speed keeps rising;
     under 10 m of braking counts as none;
   - **full throttle**: first power-limited, non-braking point after the minimum;
   - **range** (`dynamics.start/end`, the corner and complex ranges): from
     0.5 s before braking (or turn-in, if earlier) to 0.5 s after full
     throttle (or the exit, if later). Where neighbouring corners overlap they
     meet at the fastest point between the apexes. Ranges do not wrap
     start/finish; they are clamped to 0 / 1.
5. **Character**: `kink` = taken flat (no braking and v < 98% of the grip
   limit); `high_speed` = minimum >= 160 km/h; `medium` 100-160 km/h; `slow`
   below 100 km/h.
6. **Corner Complexes**: consecutive non-fast corners (not `kink` /
   `high_speed`) whose phase ranges overlap, or that curation already grouped.
   Fast corners stay tagged on the corner list but out of the complexes.

Limitations (in `surface.racing_line.limitations`): no elevation, banking,
kerbs or bumps, one car setup, no tyre or fuel state. Model laps land within
about +/- 5% of IMSA GTD laps; banked or bumpy tracks (Daytona, Sebring) come
out fast.

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
Position: error when the budget does not add up to
`absolute_accuracy_ce95_m` or the applied shift is not registration + datum;
warning when the reference's accuracy is assumed, when two surveys (or a check
against the applied shift) disagree by more than 1 m, or when a surface has no
position record. Info: the budget line; absolute accuracy above the 2 m
racing-line gate.

A curator who has checked an unnamed peak or an unplaceable corner records the
verdict in `tracks/<slug>/overrides.json` (per layout, or `"*"`):

```json
{"gp": {"surface_review": {
  "unnamed": [{"marker": 0.0515, "direction": "left", "verdict": "artefact",
               "note": "pit-lane split pulls the midline"}],
  "corners": {"9": "straight-line kink, R 350 m / 6 deg"}}}}
```

Review markers are on the output (midline) basis, as `surface.unnamed_corners`
reports them. An unnamed peak matches a review entry of the same direction within 25 m; the
warning becomes an info line. Verdicts: `artefact` (edge/midline error, not a
bend), `part_of_corner` (a second apex or lobe of a numbered corner),
`unnumbered_bend` (a real bend the numbering skips). The evidence belongs in
the track README "Curation notes".

## Accuracy, honestly

- **Relative** geometry (width, edge shape, where the apex sits against the
  edge) is good to about 0.25-0.5 m where the edge was seen.
- **Absolute** position is whatever `position.budget_ce95_m.total` says: the
  imagery registered to 3DEP lidar and moved to ITRF2014. NAIP alone would be
  its **4 m** contract (6 m before 2016). The dominant term is usually the lidar
  reference itself, and most 3DEP surveys do not state a horizontal accuracy:
  the 1.0 m CE95 then used is an assumption (flagged), supported but not proven
  by the agreement of two independent surveys. Sub-metre claims need a stated
  reference, or ground control (survey marks, CORS-referenced GNSS).
- **Bridged spans** (tree shadow, bridges, paved run-off without a painted line,
  pit merges) are interpolated and marked `measured: false` with 1.5 m added.
- **Outside the conterminous US** NAIP does not exist; those tracks have no
  surface until another open imagery source is added (see TODO.md).
