# Indianapolis Motor Speedway

![indianapolis poster](raw/render/indianapolis.png)

- **Layout**: Road Course (3925 m, clockwise)
- **Series**: imsa
- **Corners**: 14 (14 named); OSM name-match 0/14, 0 placed by centerline lap-fraction
- **Geometry**: OSM relation [20573734](https://www.openstreetmap.org/relation/20573734) centerline
- **Corner metadata**: Lovely-Sim-Racing `iracing/indianapolis-2022-road.json`

## Curation notes

Evidence: measured midline curvature (`raw/surface-gp.json`), the OSM raceway
ways (pit exit, "Alternate Corner 1"). Two unnamed peaks before T1 are
reviewed in `overrides.json` `gp.surface_review`:

- L42 at 0.1493: artefact. The OSM centerline is straight there (R7700) and
  the left edge is seen on only 10% of it, at the OSM pit-exit merge
  (0.105-0.164).
- R36 at 0.1555: the turn-in lobe of T1, 49 m before its R17 apex (the
  centerline bends there too, R71).

Corner directions are still unset (the Lovely iracing source has none); the
measured direction is in each corner's `placement.direction`.

## Known gaps

- Official corner names not yet layered in (colloquial layer from Lovely only).
