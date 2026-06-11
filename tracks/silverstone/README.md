# Silverstone Circuit — Grand Prix layout

**Status: excellent.** All 18 corners named and pinned to real OSM coordinates.

- **Layout:** `gp` — Grand Prix Circuit (Arena), 5.891 km, clockwise.
- **Country:** GB · **Centroid:** 52.0733, -1.0147 · **Wikidata:** Q180969

## Data state

| field | state |
|-------|-------|
| corners (names) | ✅ 18/18 named (numbered + official + colloquial) |
| corner coordinates | ✅ 18/18 from OSM named ways |
| pit entry/exit | ✅ from Lovely |
| sectors | ✅ |
| outline geometry | 🟡 corner-trace; clean OSM relation available for a full centerline |

## Notes

- Cleanest possible case: single OSM area, every corner name resolves.
- Lovely repeats names across multi-apex complexes (Maggotts×2, Becketts×2,
  Vale×2) and gives **no turn numbers** — numbers are synthesized, repeats are
  grouped via `overrides.json` `complex`.
- British circuits mostly use the colloquial name officially, so `official` and
  `colloquial` largely coincide here.

## Complexes

- **Abbey / Farm** (T1–2) · **Village / The Loop / Aintree** (T3–5) ·
  **Maggotts / Becketts / Chapel** (T10–14) · **Vale** (T16–17)

## Regenerate

```bash
python scripts/import.py silverstone
python scripts/generate.py silverstone
```
