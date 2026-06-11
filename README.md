# track-atlas

Clean, source-agnostic metadata for racing circuits: corner names (numbered /
official / colloquial), corner coordinates, GPS location, pit + sector markers,
and a GeoJSON layer per track that ties named corners to real geography.

The goal is the dataset that doesn't exist yet: **one place where a corner has
both its official name *and* what drivers actually call it, pinned to a real
coordinate, with a track outline that matches.**

## Layout

```
track-atlas/
├── schema/track.schema.json     # the contract every track.json validates against
├── scripts/
│   ├── import.py                # global: fetch raw source artifacts -> tracks/<slug>/raw/
│   ├── generate.py              # global: raw/ -> clean track.json + layers/*.geojson
│   └── lib/                     # shared source adapters (lovely, osm, sources, config)
└── tracks/
    └── <slug>/
        ├── source.json          # declares where this track's data comes from
        ├── overrides.json       # curated naming layers sources don't carry (optional)
        ├── track.json           # GENERATED clean metadata
        ├── raw/                 # GENERATED raw downloads, kept as artifacts
        ├── layers/<id>.geojson  # GENERATED geometry + named corner points
        ├── scripts/             # per-track import.py / generate.py overrides (optional)
        └── README.md            # state of this track's data
```

A track only needs its own `scripts/import.py` or `scripts/generate.py` when it
deviates from the standard pipeline. Easy tracks just drop a `source.json` and
the global scripts handle everything.

## The naming model

Corner names are **parallel layers**, not one field with aliases:

| layer        | always present | example (Le Mans T6) |
|--------------|----------------|----------------------|
| `numbered`   | yes            | `Turn 6`             |
| `official`   | when known     | `Virage du Tertre Rouge` |
| `colloquial` | when known     | `Tertre Rouge`       |

- **Every corner that bends gets a `numbered` name** — even unnamed kinks.
- A single name often spans several numbered corners (a *complex*): Le Mans
  turns 14–17 are all "Porsche Curves"; Silverstone 10–13 are
  "Maggotts/Becketts". That grouping lives in the `complex` field.
- Each layout sets `name_default` (usually `colloquial` — what drivers say is
  usually the best label). Consumers resolve a display name via that default,
  falling back `colloquial → official → numbered`.

## Data sources

| source | provides | notes |
|--------|----------|-------|
| [Lovely-Sim-Racing/lovely-track-data](https://github.com/Lovely-Sim-Racing/lovely-track-data) | ordered corners, apex/sector/pit as lap fractions, colloquial names | base layer, ingested wholesale |
| [OpenStreetMap](https://www.openstreetmap.org) (Overpass) | geometry + **named corner coordinates** | OSM tags individual `highway=raceway` segments with corner names → corner-name-to-coordinate join solved at the source |
| `overrides.json` | curated official names + complex grouping | hand-maintained where sources are thin |

See `AGENTS.md` for hard-won source paths and per-track gotchas.

## Usage

```bash
# fetch raw artifacts for a track (or --all)
python scripts/import.py circuit-de-la-sarthe

# build clean track.json + geojson from raw/ (no network)
python scripts/generate.py circuit-de-la-sarthe

# validate
python -c "import json,jsonschema,glob; s=json.load(open('schema/track.schema.json')); [jsonschema.validate(json.load(open(f)),s) for f in glob.glob('tracks/*/track.json')]"
```

`import.py` touches the network and writes `raw/`. `generate.py` is a pure
transform over `raw/` — re-runnable, deterministic, offline.

## Status

| track | corners | geo-matched | outline | state |
|-------|---------|-------------|---------|-------|
| Circuit de la Sarthe (Le Mans 24h) | 21 | 14/21 | corner-trace | good; Mulsanne straight not in OSM as raceway |
| Silverstone GP | 18 | 18/18 | corner-trace | excellent; clean single relation |

Outlines are currently a corner-trace (named-corner points ordered by lap
fraction). A precise stitched centerline from OSM ways is the next step — see
each track README.

## License

Code: MIT. Data: OSM-derived geometry is **ODbL**; Lovely-derived corner
metadata follows its upstream terms. See `ATTRIBUTION.md`.
