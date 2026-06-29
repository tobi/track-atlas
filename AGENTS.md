# AGENTS.md — building track data

Working notes for anyone (human or agent) adding a track. The non-obvious paths
that actually get you to clean data, recorded so nobody re-discovers them.

## The one insight that makes this tractable

**OSM tags individual circuit segments with their corner names.** Query
`highway=raceway` ways in a track's bounding box and many come back named
("Tertre Rouge", "Mulsanne", "Maggotts", ...) with full geometry. That means
geometry AND named-corner coordinates arrive in a single Overpass pull — no
fragile "project the name onto the line by guessing lap distance" step. The
corner-name→coordinate join is solved at the source. This is the backbone of
`generate.py`.

## Source paths that work

### Generated layer inputs (timing sectors, microsectors, slow zones)
- Use the project skill at `skills/layer-tools/SKILL.md` before adding or
  changing generated point/range layers.
- Per-track generated layer inputs live in `tracks/<slug>/generation-config.json`.
  The config declares URLs/files, converter tool name, layout id, and all params.
- `scripts/generate.py <slug>` writes base `raw/track.json` and then applies the
  generation config. For config-only edits, use `uv run python scripts/build_layers.py <slug>`.
- Converter tools live in `scripts/layer_tools/` and must be pure stdin→stdout:
  the runner resolves every URL/path to `raw/layer-sources/<config-id>/` before
  invocation. Do not make tools fetch their own inputs or guess missing data.
- Range-layer fractions assume the GeoJSON centerline begins at marker `0.0` /
  start-finish. `generate.py` rotates generated centerlines to that origin; keep
  this invariant or every sector/microsector/slow-zone overlay will be offset.
- For corner discovery/apex QA, use `scripts/layer_tools/curvature_apexes.py`
  through `generation-config.json` or the read-only check `uv run python
  scripts/check_apexes.py <slug>`. It derives a smoothed `κ(s)` profile from the
  centerline and emits both apex candidate points and padded corner ranges;
  apex points and corner ranges are intentionally distinct concepts. Keep layer
  names cohesive: point layer `Corner Apexes`, per-corner range layer `Each
  Corner`, merged complete group layer `Corner Complexes`. Put apexes inside
  range items as `points: [{role: "apex", point_ref: "..."}]`, not by
  narrowing the range to the apex. `corner_complexes` is the corner list with
  adjacent named complexes merged, but solo high-speed corners/kinks (scale 5/6)
  are omitted to avoid UI clutter. Multi-apex complexes such as Porsche Curves
  stay grouped even if their members are fast. `verify.py`, `suggest_phases.py`,
  and `annotate.py` also consume these candidates for QA.
### Corner curation workflow
- Start every cleanup pass with:
  `uv run python scripts/check_corner_curation.py <slug>` and
  `uv run python scripts/check_apexes.py <slug>`.
- Treat OSM named ways as strong positional evidence, not an automatic rename.
  Use the way's lap fraction and distance-to-outline to decide which turn it
  names; many OSM ways are facility/infrastructure noise.
- Put durable fixes in `tracks/<slug>/overrides.json`, never by editing
  `raw/track.json` directly. Regenerate after each curation pass.
- Prefer `official` for circuit/OSM names and `driver` for what crews say on
  radio. If drivers just say the number, clear `driver` so display falls back to
  `numbered`.
- For pit entry/exit, use the actual pit-lane geometry when OSM provides it:
  project the pit-lane endpoints to the lap centerline. Do not leave speculative
  series-specific fractions in `source.json`.
- After curation run: `uv run python scripts/generate.py <slug>` and
  `uv run python scripts/verify.py <slug>`, then refresh `tracks.jsonl`/site
  artifacts if the local preview is open.

- Known good sources:
  - IMSA / Al Kamel noticeboard `Timing 3 Sector Map.pdf` and
    `Timing All Sections Map.pdf` for timing sectors + microsectors.
  - HH Timing IMSA docs for loop-pair crosschecks:
    `https://help.hhtiming.com/series-specific-info/imsa/`.
  - HH Timing Le Mans docs / `.cha` configs for WEC slow-zone loop pairs:
    `https://help.hhtiming.com/series-specific-info/lm24/`.

### Lovely-Sim-Racing/lovely-track-data
- Manifest: `https://raw.githubusercontent.com/Lovely-Sim-Racing/lovely-track-data/main/data/manifest.json`
- Per track: `.../main/data/{simId}/{trackId}.json` (the manifest gives the `path`).
- A circuit appears under **multiple sims** (lmu, iracing, f12025, acc...). They
  differ:
  - `lmu/circuit-de-la-sarthe.json` → has turn **numbers**, directions, scale, straights.
  - `f12025/silverstone.json` → **no turn numbers**, names repeat across complexes.
  - `iracing/*` → often names only, `direction: null`.
  - Pick the richest variant per track; `corners_from_lovely` synthesizes
    sequential numbers when the source omits them.
- Everything is **lap fractions [0,1]**: `turn.marker`=apex, `turn.scale`=1–6
  severity, `turn.direction`=0 left / 1 right. `pitentry`/`pitexit` same scale.

### OpenStreetMap / Overpass
- **Use a bbox `highway=raceway` query, not a relation lookup.** Big circuits
  rarely have one clean relation; the Sarthe has none usable (`wikidata=Q270760`
  is not on any OSM relation). Bbox of named ways is the reliable path.
- Overpass request shape that avoids `406 Not Acceptable`: POST/GET with the
  query as a urlencoded `data=` param **and a real User-Agent**. Raw
  `--data-binary @file.ql` without UA gets 406'd.
- Overpass returns an **HTML error page (not JSON)** when overloaded — detect
  `body[:1] not in {[,{}` and retry with backoff + endpoint rotation. See
  `lib/sources.overpass`. Expect to wait through 1–3 "busy" rounds.
- Nominatim is useful to sanity-check a circuit's centroid / osm_id, UA required:
  `https://nominatim.openstreetmap.org/search?q=<circuit>&format=json&extratags=1`

### GitHub (don't bother for full-circuit GeoJSON)
- Code search for `<track> extension:geojson` returns **administrative boundary
  noise** (`le-mans-cantons.geojson` etc.), not circuits. `f1-circuits` repos
  are F1-only (so Bugatti, not the 24h layout). OSM is the real path.
- GitHub **code search requires auth** — use `gh api search/code` (the
  unauthenticated REST endpoint 401s).

## Per-track gotchas

### circuit-de-la-sarthe (Le Mans 24h)
- The **Mulsanne straight (Ligne Droite des Hunaudières) is public road (D338)**,
  only partially tagged `highway=raceway`. Summing the raceway ways gives ~8.1 km
  vs the 13.6 km lap — the missing ~5.5 km is that public-road section. A precise
  full outline needs stitching in the D338 segments (tagged `highway=primary`,
  name "Route de Tours"/"D338"). Documented TODO, not faked.
- **Indianapolis (T11) is not named in OSM** — it's an unnamed segment between
  Mulsanne and Arnage. Keeps its lap-fraction marker; no coordinate yet.
- Lovely has a **typo: "Virage d'Arange"** → OSM "Virage d'Arnage". The fuzzy
  name-join (difflib cutoff 0.82) catches it; 0.85 was too tight (ratio 0.833).
- OSM uses accented names ("Esses de la Forêt", "Bœufs") — `normalize()` strips
  diacritics + connective words ("virage", "courbe", "de/du/des") before matching.

### silverstone (GP)
- Clean: single area, 18/18 corners geo-matched on first pass.
- Lovely repeats names across multi-apex complexes (Maggots×2, Becketts×2,
  Vale×2). Grouped via `overrides.json` `complex`. British circuits mostly use
  the driver name *as* the official name.

## Matching / normalization rules

- Join key = `normalize(driver or official)` against `normalize(osm_way_name)`.
- `normalize()` (in `lib/osm.py`): NFKD-strip accents, lowercase, drop
  {virage, courbe, chicane, esses, le/la/les/du/de/des/d/s, the}, strip
  non-alphanumerics. Tune here if a track mismatches.
- Infrastructure ways are filtered out by `NON_CORNER` regex (pit, circuit,
  ligne droite, safety car, porsche center, maison blanche, moto, ...).

## Adding a track — checklist

1. `mkdir -p tracks/<slug>/{raw,scripts,layers}`.
2. Write `tracks/<slug>/source.json` (slug, name, aka, country, wikidata,
   location centroid, `lovely` map, `osm.bbox`, layouts).
3. `python scripts/import.py <slug>` → fills `raw/`.
4. `python scripts/generate.py <slug>` → check the "matched N/M" line.
5. For unmatched / repeated / official names, add `tracks/<slug>/overrides.json`
   keyed by layout id → corner number, regenerate.
6. Validate against `schema/track.schema.json`. Update the track README.
