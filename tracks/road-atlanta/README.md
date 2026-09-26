# Michelin Raceway Road Atlanta

![road-atlanta poster](raw/render/road-atlanta.png)

- **Layout**: Full Course (4088 m, clockwise)
- **Series**: imsa
- **Corners**: 14 (14 named); OSM name-match 1/14, 0 placed by centerline lap-fraction
- **Geometry**: stitched from `highway=raceway` ways in the bbox (no OSM route relation found)
- **Corner metadata**: Lovely-Sim-Racing `iracing/roadatlanta-full.json`

## Surface

- Edges measured from USDA NAIP (2023-10-22, 0.6 m): width median 12.5 m
  (p05 11.9, p95 17.2), edges seen on 73% (left) / 77% (right) of the lap,
  relative precision 0.25 m, absolute accuracy 4 m CE95 (NAIP contract).
- Largest bridged (unseen) spans: left edge 0.363-0.401 (after T6), right
  edge 0.539-0.585 (back straight) and 0.789-0.822 (approach to T10A); the
  rest are short gaps (shadow, kerbs, pit merges). All are listed in
  `unseen_spans`.
- Corner directions corrected from the measured curvature (the lap is
  clockwise): T1, T3, T10B and T12 were marked left, T2 right.
- Corner list re-curated onto the measured peaks (see Curation notes).

## Curation notes

Evidence: NAIP-measured midline curvature (`raw/surface-gp.json`), the stitched
OSM centerline and its named ways, Lovely `iracing/roadatlanta-full.json`
ranges. Lovely lists 1, 2, 3, 4, The Esses, 5, 6, 7, 8, 9, 10A, 10B, 11, 12
(14 items); the old override had renumbered them 1..12 plus a plain "Turn 10",
so every name after T4 was one off, and markers sat 14-127 m from their peaks.
Now every corner sits within 0.2 m of its measured peak except T9 (below).

| # | code | dir | marker | measured peak | was |
|---|---|---|---|---|---|
| 1 | 1 | R | 0.0858 | R53, -62 deg | marker 66 m off |
| 2 | 2 | L | 0.1713 | R125, +34 deg | |
| 3 | 3 | R | 0.1856 | R34, -60 deg | marker 77 m off |
| 4 | 4 | L | 0.2209 | R101, +58 deg | marker 43 m off |
| 5 | Esses | R | 0.2559 | R76, -24 deg; OSM "The Esses" way 0.248-0.338 | labelled Turn 5 |
| 6 | 5 | L | 0.3323 | R44.5, +70 deg | labelled Turn 6, marker 85 m off |
| 7 | 6 | R | 0.4718 | R56, -90 deg | labelled Turn 7, was an unnamed peak |
| 8 | 7 | R | 0.5092 | R23, -100 deg | labelled Turn 8, declared left, no peak |
| 9 | 8 | L | 0.5638 | R355, +6.6 deg (back-straight kink; centerline R442) | labelled Turn 9, marker 127 m off |
| 10 | 9 | R | 0.7213 | R187, -7 deg (kink; centerline R476) | labelled Turn 10, no peak |
| 11 | 10A | L | 0.8420 | R24, +64.5 deg | complex "Turn 10" |
| 12 | 10B | R | 0.8617 | R35, -79 deg | complex "Turn 10" |
| 13 | 11 | R | 0.8985 | R48.5, -35 deg | marker 106 m off |
| 14 | 12 | R | 0.9574 | R78, -30 deg | marker 90 m off |

Left as warnings, on purpose:

- T8 and T9 are flat back-straight kinks (under 10 deg of heading). The
  centerline apex check finds no apex there (R > 400 m), so verify reports
  them as "may be on straights" (by item number: T9, T10). That is what
  they are.
- T9's measured placement lands on the R87 wiggle at 0.6994 (offset -90 m),
  not on the R187 kink at 0.7213 where the marker is. That wiggle is an edge
  artefact: it pairs with an equal L88 wiggle at 0.7045, the left edge is seen
  on only 30% of it, and the centerline there is straight (R20000). The
  matcher's cost prefers the tighter peak by 0.025 and a marker move cannot
  change that (the two costs move together). The marker is right; the
  measured entry/apex/exit for T9 are not trustworthy.
- The code "Esses" makes the numbered label "Turn Esses". Lovely has no number
  for it and the circuit numbers the next left as 5, so there is no honest
  numeric code.

## Known gaps

- No OSM route/circuit relation; outline quality depends on bbox way coverage.
