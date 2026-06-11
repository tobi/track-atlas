# Attribution

This project combines data from multiple sources. Respect their licenses.

## OpenStreetMap
Geometry and named-corner coordinates are derived from OpenStreetMap data via
the Overpass API.

> © OpenStreetMap contributors, licensed under the
> [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/).

Any distributed geometry (the `layers/*.geojson` files and corner `location`
fields in `track.json`) is a Produced Work / derived database under ODbL and
must carry this attribution.

## Lovely-Sim-Racing/lovely-track-data
Ordered corner metadata (apex/sector/pit lap fractions, severity, direction) and
the colloquial corner-name base layer come from
[Lovely-Sim-Racing/lovely-track-data](https://github.com/Lovely-Sim-Racing/lovely-track-data).
Their corner/straight names are credited upstream to Racing Circuits. Follow the
upstream repository's terms for reuse.

## Curated overrides
`tracks/*/overrides.json` (official names + complex grouping) is hand-maintained
for this project and offered under the repository's MIT code license.
