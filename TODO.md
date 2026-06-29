# TODO

Running checklist of requested work. Keep updated; don't drop anything.

## DONE: Three.js driving sim on the detail page
- [x] site/sim.js: drives the real centerline; quasi-static speed solver (curvature -> cornering limit, brake pass, traction pass)
- [x] 3 car classes (GT3 / LMPh / BMW 328) with distinct grip/brake/accel/top-speed; chase + isometric cameras
- [x] track surface coloured by state: red brake / amber corner / green throttle; HUD shows class + km/h
- [x] verified in headless Chromium (iso shows whole coloured loop; chase shows surface ahead)

## DONE: tracks.jsonl + phases-in-data + site move
- [x] Corner phases promoted into track.json (corner.start/marker/end) via lib/phases.py; schema updated; rendered in the site corner table + geojson properties
- [x] Pipeline generates `tracks.jsonl` at repo root (build_jsonl.py, one track per line); linked prominently from README + the website
- [x] Moved the web app into `site/` (paths rebased to ../); README browse link updated
- [x] Every track README embeds `![](raw/render/<slug>.png)`; repo README has a Sebring example at the top and states tracks.jsonl is the point
- [x] suggest_phases.py is now a preview/tuning tool (phases live in the data)

## In progress: corner-naming model redesign
Base identifier + arbitrary sparse name layers; `official` mandatory layer;
display = default-layer ?? numbered (no fall-through); Sebring "Sunset Bend"
shows as "Turn 17". Scale stays int 1-6 + canonical labels. Complex = contiguous
run of corners (verified). `colloquial` layer renamed to `driver`.

- [x] Rewrite `schema/track.schema.json` (name_layers registry, corner.code, open names, name_default)
- [x] `scripts/lib/naming.py` — shared conventions (scale labels, layer registry, resolution)
- [x] `scripts/lib/lovely.py` — emit `code`, `driver` layer
- [x] `scripts/generate.py` — registry, code, junk-strip, override deletion semantics
- [x] `scripts/verify.py` — code uniqueness, complex contiguity, layer-reference checks *(superseded by Pydantic rewrite below)*
- [x] `scripts/render.py` — two-step resolution + named detection
- [x] Migrate all 36 `overrides.json` (`colloquial` -> `driver`)
- [x] Regenerate all 39 tracks; validate against schema (all pass)
- [x] Sebring worked example: promoted "Sunset Bend" to `official`, cleared `driver`, render shows "Turn 17"
- [x] `driver` defaults to `official` when no distinct nickname (drivers use official name unless cleared)
- [x] `name_default` self-heals to a populated layer; number-only tracks default to `numbered`
- [x] Re-render all 39 tracks; verify --all green (0 errors, 39/39 clear)
- [ ] `app.js` — name-layer picker / dynamic columns, scale labels, driver rename in edit dialog
- [ ] Update `README.md` + `AGENTS.md` for the new naming model

## DONE: verification rewritten in Pydantic
Models in `scripts/lib/models.py` are the source of truth; `scripts/build_schema.py`
emits `schema/track.schema.json` from them; `verify.py` validates via the models
(structure/naming invariants) + keeps geometry/alignment/render checks.
- [x] Pydantic models for the full track schema (carries the naming model)
- [x] Emit JSON Schema from models (`scripts/build_schema.py`)
- [x] Reimplement verify on models; uv project (`pyproject.toml`), pydantic dep
- [x] Removed jsonschema + requirements.txt; structural checks de-duplicated into models

## Curation backlog (verify warns, doesn't fail)
- [x] Added repeatable curation workflow: `scripts/check_corner_curation.py`, `scripts/check_apexes.py`, and AGENTS playbook.
- [x] Sebring high-confidence cleanup from OSM positional evidence: Tower/Fangio/Cunningham/Bishop/Gendebien/Sunset fixed; speculative IMSA pit markers replaced with projected pit-lane endpoints.
- [x] Corner layer cohesion applied repo-wide: `Corner Apexes`, `Each Corner`, `Corner Complexes`; solo scale-5/6 corners omitted from complexes.
- [ ] Number-only tracks need real corner names if any exist: jeddah, miami, shanghai, losail, indianapolis.
- [ ] Run manual curation passes from `check_corner_curation.py --all` output; do not blindly apply OSM names because many are facility/layout noise.
- [x] Barcelona geometry/start-origin fixed: relation included old/connector geometry, generator now chooses the cleaner stitched lap and Barcelona pins start/finish explicitly. Remaining signal is only T6, a scale-6 kink near Würth.

## DONE: poster size
- [x] PNG compression in render.py (supersample -> downscale 1.5x -> octree palette + optimize): 23MB -> 4.1MB
- [x] Render quality: reserved title band so track never sits under the title; wider label spacing + footer clamp
- [x] Site poster switched to SVG (980KB total, crisp); PNG kept as `poster_png` raster fallback

## DONE: corner-phase suggester script
- [x] `scripts/suggest_phases.py`: severity-scaled start/apex/exit lap fractions,
      neighbour overlap resolved, complex members meet exactly; writes
      `tracks/<slug>/phases.suggested.json` (review artifact) + prints a table. Ran --all.

## DONE: docs + hygiene
- [x] README + AGENTS updated (naming model, name_layers, scale labels, uv workflow, new scripts)
- [x] Removed committed `.goutputstream` temp leak from the working tree/index
- [x] uv project; `.venv` gitignored; jsonschema fully removed

## DONE: build layout (everything generated -> raw/)
- [x] All generated files moved under `tracks/<slug>/raw/` (track.json, layers, render, phases, downloads)
- [x] Inputs stay at track root (source.json, overrides.json, README.md, optional scripts/)
- [x] generate/render/verify/build_index/suggest_phases + app.js + config helpers updated to raw/ paths
- [x] `tracks/index.json` is the pulled-together artifact

## DONE: website browse layouts + naming layers
- [x] Layout `<select>` (browse every configuration) + name-layer `<select>` (browse every naming layer)

## DONE: git history rewrite
- [x] git-filter-repo stripped old tracks/<slug>/render/ blobs + .goutputstream from all history; force-pushed. .git 70M -> 5.6M.

## DONE: committed + pushed everything to origin/main

## DONE: layout-variant model (separate full layouts per series)
- [x] Capability: per-layout `pit` override + `series` field in source.json; `"*"` shared-overrides key so variants share corner curation
- [x] Sebring: two layouts (`wec`, `imsa`) sharing geometry, different pit; site browses both
- [x] Sebring IMSA pit values corrected from OSM pit-lane endpoints projected to the lap centerline (0.9675/0.0608).
- note: only Sebring races both IMSA+WEC; other multi-series tracks (f1/wec/elms) use one shared layout, so no variants added

## Not actionable without input/data
- [ ] Number-only tracks (jeddah, miami, shanghai, losail, indianapolis) — genuinely have no corner names; need real-world naming, not code
- [ ] Single-corner "complex" warnings (silverstone Abbey/Farm; laguna-seca Corkscrew; Esses) — judgment calls: are these really complexes, or just named corners? Left for human review. (Maggotts-Becketts-Chapel separator typo: FIXED)
