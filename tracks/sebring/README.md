# Sebring International Raceway

![sebring poster](raw/render/sebring.png)

- **Layouts**: two series-specific configurations of the International Circuit
  (5954 m, clockwise), sharing the same geometry and corners:
  - `wec` — pit entry/exit 0.9675 / 0.0608
  - `imsa` — pit entry/exit 0.9675 / 0.0608
- **Series**: imsa, wec
- **Corners**: 17; shared curation in the `"*"` block of `overrides.json`
- **Geometry**: OSM relation [7003292](https://www.openstreetmap.org/relation/7003292) centerline
- **Pit geometry**: pit-lane endpoints projected from the OSM `Pit Lane` way to
  the lap centerline.
- **Corner metadata**: Lovely-Sim-Racing `lmu/sebring-international-raceway.json`,
  corrected with OSM named-way positional evidence.

## Known gaps

- Several numbered Sebring turns intentionally remain number-only where we do
  not have a reliable driver/common name.
- If IMSA/WEC publish event-specific pit timing-loop fractions, those can become
  generated point layers; the current physical pit in/out points are geometry-derived.
