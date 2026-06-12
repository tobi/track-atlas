# track-atlas

Clean, source-agnostic metadata for racing circuits: corner names (numbered /
official / colloquial), corner coordinates, start/finish + pit markers, sector
splits, a real-geometry GeoJSON layer per layout, and a generated poster per
track.

The goal is the dataset that doesn't exist yet: **one place where a corner has
both its official name *and* what drivers actually call it, pinned to a real
coordinate, with a track outline that matches.** Eventually: every track in the
world.

Browse it: **https://tobi.github.io/track-atlas/** (search, inspect on a map,
propose edits via GitHub deep links).

## Directory structure

```
track-atlas/
├── schema/track.schema.json     # the contract every track.json validates against
├── scripts/
│   ├── import.py                # global: fetch raw source artifacts -> tracks/<slug>/raw/
│   ├── generate.py              # global: raw/ -> clean track.json + layers/*.geojson
│   ├── render.py                # global: track.json -> render/<slug>.svg + .png poster
│   ├── verify.py                # completeness + misalignment checks (CI gate)
│   └── lib/                     # shared source adapters (lovely, osm, sources, config)
├── index.html / app.js          # GitHub Pages static browser (served from repo root)
└── tracks/
    ├── index.json               # GENERATED catalog of all tracks (for the site)
    └── <slug>/
        ├── source.json          # INPUT: declares where this track's data comes from
        ├── overrides.json       # INPUT: curated naming layers sources don't carry (optional)
        ├── raw/                 # GENERATED: raw downloads, committed as artifacts
        ├── track.json           # GENERATED: clean metadata (validates against schema)
        ├── layers/<id>.geojson  # GENERATED: outline + corners + start/finish + pit points
        ├── render/<slug>.png    # GENERATED: poster (plus .svg)
        ├── scripts/             # per-track import.py / generate.py overrides (optional)
        └── README.md            # state of this track's data
```

**INPUT files are hand-edited; GENERATED files are never hand-edited** — they
are rebuilt by the pipeline. The flow:

```
source.json ──import.py──> raw/ ──generate.py──> track.json + layers/*.geojson
overrides.json ────────────────────────┘              │
                                        render.py ──> render/<slug>.{svg,png}
                                        verify.py ──> PASS/FAIL
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
| `name_default` | enum | | Which naming layer to display: `colloquial` (default) \| `official` \| `numbered`. Resolution order: default → colloquial → official → numbered |
| `corners` | corner[] | | Ordered corner list (see below) |
| `straights` | straight[] | | `{name, aka?, start?, end?}` as lap fractions |
| `sectors` | object[] | | `{name, marker}` — sector boundary lap fractions |
| `pit` | object | | `{entry, exit}` lap fractions of pit entry/exit |
| `marshal_posts` | point_ref[] | | optional |
| `access_points` | point_ref[] | | optional |

### Corner

| field | type | req | description |
|---|---|---|---|
| `number` | int | ✓ | Sequential 1..N around the lap, no gaps |
| `names` | object | ✓ | Parallel naming layers — see below |
| `names.numbered` | string | ✓ | Always present (`"Turn 6"`) |
| `names.official` | string | | Circuit/governing-body name (`"Virage du Tertre Rouge"`) |
| `names.colloquial` | string | | What drivers say (`"Tertre Rouge"`) — usually the best label |
| `complex` | string | | Multi-corner section this turn belongs to (`"Porsche Curves"`). Only for sections drivers say as one word — adjacent-but-distinct corners are NOT a complex |
| `direction` | enum | | `left` \| `right` |
| `scale` | int 1–6 | | Severity: 1 = hairpin … 6 = barely a kink |
| `marker` | number | | Lap fraction [0,1] at the apex, from the start/finish line |
| `start` / `end` | number | | Lap fractions where the corner begins/ends |
| `location` | [lon,lat] | | Apex coordinate |
| `location_source` | enum | | `osm-way` (matched a named OSM way — default when absent), `centerline` (projected onto the centerline by lap fraction), `manual` |

### Naming model

Corner names are **parallel layers, not aliases**. `numbered` always exists
(every bend gets `Turn N`, even unnamed kinks). `official` and `colloquial` are
present only when known. Consumers resolve a display name via the layout's
`name_default`, falling back colloquial → official → numbered.

## layers/<id>.geojson spec

A `FeatureCollection` per layout. Every feature carries a `role` property:

| role | geometry | properties |
|---|---|---|
| `outline` | LineString (closed: first == last point) | `layout` — the real centerline from the OSM route relation, every chicane preserved |
| `start_finish` | Point | `name`, `marker` (0.0) |
| `pit_entry` / `pit_exit` | Point | `marker` |
| `corner` | Point (one per located corner) | `number`, `display` (resolved name), `names` (all layers), `complex`, `direction`, `scale` |

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
   python scripts/import.py <slug>      # network: fills raw/
   python scripts/generate.py <slug>    # offline: track.json + layers/
   python scripts/render.py <slug>      # poster
   python scripts/verify.py <slug>      # must PASS
   ```
   Watch the `corners matched to OSM geometry: N/M` line from generate.
5. **Curate** what the sources got wrong in `tracks/<slug>/overrides.json`
   (keyed by layout id, then corner number — layers in official/colloquial
   names, `complex` grouping, direction/scale fixes):
   ```jsonc
   {"24h": {"corners": {
     "14": {"official": "Virage Porsche", "colloquial": "Porsche Curves",
            "complex": "Porsche Curves"}
   }}}
   ```
   Re-run generate + render + verify after edits.
6. Write a short `tracks/<slug>/README.md` (data state, known gaps, sources)
   and commit everything **including `raw/`** (reproducibility artifacts).

A track only needs its own `scripts/import.py` / `scripts/generate.py` when it
deviates from the standard pipeline.

## Verifying

```
python scripts/verify.py            # all tracks
python scripts/verify.py <slug>     # one
python scripts/verify.py --strict   # warnings fail too
```

Checks per track: schema validity, required files, sequential corner numbers,
every corner located, closed outline, **traced length vs declared length_m**
(warn >3%, fail >10%), **every corner within 60 m of the outline**, corner
lap-order vs geometric order along the centerline, start/finish + pit markers
present and on track, geojson ↔ track.json coordinate agreement, and render
freshness. Exit code is CI-friendly.

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
