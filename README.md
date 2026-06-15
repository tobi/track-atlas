# track-atlas

Clean, source-agnostic metadata for racing circuits: corner names in layers
(numbered / official / driver + any others), corner coordinates, start/finish + pit markers, sector
splits, a real-geometry GeoJSON layer per layout, and a generated poster per
track.

The goal is the dataset that doesn't exist yet: **one place where a corner has
both its official name *and* what drivers actually call it, pinned to a real
coordinate, with a track outline that matches.** Eventually: every track in the
world.

Browse it: **https://tobi.github.io/track-atlas/** (search, inspect on a map,
propose edits via GitHub deep links).

## Directory structure

This is a [uv](https://docs.astral.sh/uv/) project; run the pipeline with
`uv run python scripts/<step>.py`.

```
track-atlas/
├── pyproject.toml               # uv project (pydantic, cairosvg, pillow)
├── schema/track.schema.json     # GENERATED from the models by build_schema.py
├── scripts/
│   ├── import.py                # global: fetch raw source artifacts -> tracks/<slug>/raw/
│   ├── generate.py              # global: raw/ -> clean track.json + layers/*.geojson
│   ├── render.py                # global: track.json -> render/<slug>.svg + compressed .png
│   ├── build_schema.py          # global: emit schema/track.schema.json from lib/models.py
│   ├── verify.py                # validates against the models + geometry/render checks (CI gate)
│   ├── suggest_phases.py        # global: suggest braking/apex/exit corner phases (for review)
│   └── lib/                     # models (pydantic SoT), naming, lovely, osm, sources, config
├── index.html / app.js          # GitHub Pages static browser (served from repo root)
└── tracks/
    ├── index.json               # GENERATED: the pulled-together catalog the site reads
    └── <slug>/
        ├── source.json          # INPUT: declares where this track's data comes from
        ├── overrides.json       # INPUT: curated names/fixes (hand- or LLM-authored)
        ├── README.md            # INPUT: state of this track's data
        ├── scripts/             # INPUT (optional): per-track import.py / generate.py
        └── raw/                 # GENERATED — everything the build can recreate:
            ├── osm.json, osm-relation.json, lovely-*.json  # source downloads
            ├── track.json       # clean metadata (validates against the models)
            ├── layers/<id>.geojson      # outline + corners + start/finish + pit
            ├── render/<slug>.svg + .png # poster the site shows + raster fallback
            └── phases.suggested.json    # review-only suggested corner phases
```

The schema is **generated from `scripts/lib/models.py`** (Pydantic) — the models
are the source of truth. Edit them and re-run `build_schema.py`; never hand-edit
`schema/track.schema.json`.

**INPUTS are authored (by hand or LLM); everything in `raw/` is GENERATED** and
never hand-edited — the build recreates it. The test for "input vs generated" is
reproducibility: the build *consumes* `source.json`/`overrides.json` but cannot
recreate them, so they're inputs (even when an LLM writes the overrides). The
flow:

```
source.json ──import.py──> raw/{osm,lovely}.json ──generate.py──> raw/track.json + raw/layers/*.geojson
overrides.json ──────────────────────────────────────────┘            │
                                       render.py        ──> raw/render/<slug>.{svg,png}
                                       suggest_phases.py──> raw/phases.suggested.json
                                       build_index.py   ──> tracks/index.json   (pulls it together)
                                       verify.py        ──> PASS/FAIL
```

## track.json field spec

Validated by [`schema/track.schema.json`](schema/track.schema.json). All
coordinates are GeoJSON axis order: `[longitude, latitude]`, WGS84.

### Top level

| field | type | req | description |
|---|---|---|---|
| `slug` | string | ✓ | Stable id, matches the folder name. `^[a-z0-9]+(-[a-z0-9]+)*$` |
| `name` | string | ✓ | Official circuit name (`"Circuit de la Sarthe"`) |
| `aka` | string[] | | Alternative names (`["La Sarthe", "Le Mans"]`) |
| `country` | string | | ISO 3166-1 alpha-2 (`"FR"`) |
| `location` | object | ✓ | `{lat, lon, locality?, region?, timezone?}` — circuit centroid |
| `wikidata` | string | | Wikidata QID (`"Q270760"`) |
| `series` | string[] | | Series that race here, lowercase codes (`["wec","elms"]`) |
| `external_ids` | object | | Crosswalk to other datasets (`{"imsa_data": "le-mans"}`) |
| `name_layers` | object | ✓ | Registry of corner-name layers `{code: {label, description?}}`. `numbered` + `official` mandatory; `driver` is the usual default. Clients enumerate these to offer a layer to display |
| `layouts` | layout[] | ✓ | One entry per configuration (GP / 24h / national / moto…) |
| `provenance` | object | | `generated_at`, `sources[]` (name/url/license/provides), `corner_match` |

### Layout

| field | type | req | description |
|---|---|---|---|
| `id` | string | ✓ | Unique within the track (`"24h"`, `"gp"`) |
| `name` | string | ✓ | `"Circuit des 24 Heures"` |
| `aka` | string[] | | |
| `length_m` | number | | Official lap length in metres |
| `direction` | enum | | `clockwise` \| `anticlockwise` |
| `active_years` | string | | Free-form (`"2018-"`, `"1972,1979-1989"`) |
| `geometry` | object | ✓ | `{outline: "layers/<id>.geojson", crs: "EPSG:4326"}` |
| `start_finish` | point_ref | | `{marker: 0.0, location: [lon,lat]}` — the timing line. Lap fractions throughout the dataset are measured from here |
| `name_default` | string | | Layer code (a key in `name_layers`) shown by default (usually `driver`). Resolution is two steps: `names[name_default]` if present, else `names.numbered` — no fall-through to other layers |
| `corners` | corner[] | | Ordered corner list (see below) |
| `straights` | straight[] | | `{name, aka?, start?, end?}` as lap fractions |
| `sectors` | object[] | | `{name, marker}` — sector boundary lap fractions |
| `pit` | object | | `{entry, exit}` lap fractions of pit entry/exit |
| `marshal_posts` | point_ref[] | | optional |
| `access_points` | point_ref[] | | optional |

### Corner

| field | type | req | description |
|---|---|---|---|
| `number` | int | ✓ | Sequential 1..N around the lap, no gaps — the ordering key |
| `code` | string | ✓ | Trackside identifier; usually `str(number)`, but split apexes use `"5a"`/`"5b"`. The `numbered` layer is `"Turn <code>"` |
| `names` | object | ✓ | Name layers keyed by layer code — see below. `numbered` always present |
| `names.numbered` | string | ✓ | The `"Turn <code>"` identifier, always present (covers unnamed corners) |
| `names.official` | string | | Circuit/governing-body name (`"Virage du Tertre Rouge"`) |
| `names.driver` | string | | What drivers say (`"Tertre Rouge"`); defaults to `official` when no distinct nickname is known |
| `names.<other>` | string | | Any further layer declared in `name_layers` (`historical`, `sponsor`, …) |
| `complex` | string | | Multi-corner section this turn belongs to (`"Porsche Curves"`). Members must be one gap-free consecutive run. Only for sections drivers say as one word — adjacent-but-distinct corners are NOT a complex |
| `direction` | enum | | `left` \| `right` |
| `scale` | int 1–6 | | Severity with labels: 1 Hairpin, 2 Slow, 3 Medium, 4 Fast, 5 Very fast, 6 Kink |
| `marker` | number | | Lap fraction [0,1] at the apex, from the start/finish line |
| `start` / `end` | number | | Lap fractions where the corner begins/ends |
| `location` | [lon,lat] | | Apex coordinate |
| `location_source` | enum | | `osm-way` (matched a named OSM way — default when absent), `centerline` (projected onto the centerline by lap fraction), `manual` |

### Naming model

Corner names are **a base identifier plus any number of sparse overlay layers**.
Every corner has a `code` and an always-present `numbered` layer (`"Turn <code>"`)
— that's the base, and it covers unnamed corners too (a kink drivers don't talk
about carries only `numbered`). Overlay layers (`official`, `driver`, and any
others declared in the track's `name_layers`) appear only when a name is known.

A layout's `name_default` (usually `driver`) picks the display layer. Resolution
is **two steps**: the default layer if the corner has it, else the `numbered`
identifier — it does **not** fall through other layers. So an absent default-layer
name means drivers just use the number (Sebring T17 is officially *Sunset Bend*
but drivers say *Turn 17* → its `driver` layer is cleared). By default `driver`
inherits the `official` name unless a distinct nickname is set or it's cleared.

## layers/<id>.geojson spec

A `FeatureCollection` per layout. Every feature carries a `role` property:

| role | geometry | properties |
|---|---|---|
| `outline` | LineString (closed: first == last point) | `layout` — the real centerline from the OSM route relation, every chicane preserved |
| `start_finish` | Point | `name`, `marker` (0.0) |
| `pit_entry` / `pit_exit` | Point | `marker` |
| `corner` | Point (one per located corner) | `number`, `code`, `display` (resolved name), `names` (all layers), `complex`, `direction`, `scale` |

The outline is the **OSM `type=route`/`type=circuit` relation centerline** —
the authoritative continuous lap, including public-road sections that aren't
tagged `highway=raceway` (Le Mans' Mulsanne straight is the D338). Pit-lane
members and duplicated way refs in the relation are filtered out.

## source.json (the only file you write for a new track)

```jsonc
{
  "slug": "circuit-de-la-sarthe",
  "name": "Circuit de la Sarthe",
  "aka": ["La Sarthe", "Le Mans"],
  "country": "FR",
  "wikidata": "Q270760",
  "series": ["wec"],
  "external_ids": {"imsa_data": "le-mans"},
  "location": {"lat": 47.95, "lon": 0.2247, "locality": "Le Mans",
               "region": "Pays de la Loire", "timezone": "Europe/Paris"},
  "lovely": {"24h": "lmu/circuit-de-la-sarthe.json"},   // layout key -> file in lovely-track-data
  "osm": {
    "bbox": [47.90, 0.15, 47.98, 0.28],                  // south, west, north, east
    "relation": 2126739                                  // OSM route/circuit relation id
  },
  "layouts": [
    {"id": "24h", "name": "Circuit des 24 Heures", "length_m": 13626,
     "direction": "clockwise", "active_years": "2018-", "lovely": "24h"}
  ]
}
```

## Adding a new track

1. **Find the OSM relation** (the single most valuable input). On
   [openstreetmap.org](https://www.openstreetmap.org) search the circuit, or
   query Overpass:
   ```
   [out:json];(relation["type"~"route|circuit"]({{bbox}});
              relation["sport"="motor"]({{bbox}}););out tags;
   ```
   Take the relation whose name matches the racing lap (e.g. Silverstone
   `51160 "Silverstone Grand Prix"`, Le Mans `2126739`). No relation? Leave it
   out — the pipeline falls back to stitching named `highway=raceway` ways from
   the bbox (lower quality; expect to add `overrides.json`).
2. **Find the Lovely file**: browse
   [Lovely-Sim-Racing/lovely-track-data](https://github.com/Lovely-Sim-Racing/lovely-track-data)
   `tracks/<sim>/<track>.json`. Pick the richest sim variant (lmu > f12025 >
   iracing > acc, roughly — prefer one with turn numbers AND names).
3. `mkdir tracks/<slug>` and write `source.json` (template above).
4. ```
   uv run python scripts/import.py <slug>      # network: fills raw/
   uv run python scripts/generate.py <slug>    # offline: track.json + layers/
   uv run python scripts/render.py <slug>      # poster (svg + compressed png)
   uv run python scripts/verify.py <slug>      # must PASS
   ```
   Watch the `corners matched to OSM geometry: N/M` line from generate.
5. **Curate** what the sources got wrong in `tracks/<slug>/overrides.json`
   (keyed by layout id, then corner number — `official`/`driver`/other name
   layers, `complex` grouping, `code`, direction/scale fixes). A name layer set
   to `null` clears it (so the display falls back to the number):
   ```jsonc
   {"24h": {"corners": {
     "14": {"official": "Virage Porsche", "driver": "Porsche Curves",
            "complex": "Porsche Curves"},
     "8":  {"official": "Sunset Bend", "driver": null}  // drivers say "Turn 8"
   }}}
   ```
   `driver` defaults to the `official` name when you don't set it. Re-run
   generate + render + verify after edits.
6. Write a short `tracks/<slug>/README.md` (data state, known gaps, sources)
   and commit everything **including `raw/`** (reproducibility artifacts).

A track only needs its own `scripts/import.py` / `scripts/generate.py` when it
deviates from the standard pipeline.

## Verifying

```
uv run python scripts/verify.py            # all tracks
uv run python scripts/verify.py <slug>     # one
uv run python scripts/verify.py --strict   # warnings fail too
```

`verify.py` validates each `track.json` against the **Pydantic models**
(`scripts/lib/models.py`) — types, enums, lon/lat shape, sequential corner
numbers, unique corner codes, contiguous complexes, mandatory + declared name
layers, `name_default` references a real layer — then runs geometry/alignment
checks it can't express as a schema: required files, every corner located,
closed outline, **traced length vs declared length_m** (warn >3%, fail >10%),
**every corner within 80 m of the outline**, corner lap-order vs geometric order
along the centerline, start/finish + pit markers on track, geojson ↔ track.json
coordinate agreement, render freshness, and a thin-naming warning. Exit code is
CI-friendly.

The committed `schema/track.schema.json` is regenerated from the models with
`uv run python scripts/build_schema.py` whenever the models change.

## Suggesting corner phases

`suggest_phases.py` proposes each corner's braking-zone **start / apex / exit**
as lap fractions, scaled by severity (a hairpin brakes far earlier than a kink),
resolving neighbours so phases never overlap and corners inside one complex meet
exactly. Output is a review artifact (`tracks/<slug>/phases.suggested.json`), not
authoritative data — eyeball and tune it.

```
uv run python scripts/suggest_phases.py <slug>      # writes phases.suggested.json + prints a table
uv run python scripts/suggest_phases.py --all
```

## The website

`index.html` + `app.js` at the repo root are a static browser served by GitHub
Pages: search by name/aka/country/series, posters, a Leaflet map per track
(outline + corners + start/finish + pit on real imagery), the full corner table
with all naming layers, and **propose-an-edit deep links** — corner edits
prefill a GitHub issue with a ready-to-paste `overrides.json` patch, and
"edit on GitHub" jumps straight into the web editor on `source.json` /
`overrides.json` to open a PR. `tracks/index.json` (the site's catalog) is
regenerated by `scripts/build_index.py` (also run by generate `--all`).

## Sources & licensing

- Corner metadata: [Lovely-Sim-Racing/lovely-track-data](https://github.com/Lovely-Sim-Racing/lovely-track-data)
  (corner names credited upstream to [racingcircuits.info](https://racingcircuits.info))
- Geometry + named-corner coordinates: © OpenStreetMap contributors, ODbL
- Curated layers: this repo (see ATTRIBUTION.md)
