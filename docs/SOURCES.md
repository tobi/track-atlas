# Open geometry sources: what each really gives

The atlas is ODbL. A source is usable only if its licence allows derived
geometry to be published under ODbL (public domain, CC0, CC BY with
attribution, or "no restrictions"). Commercial basemaps (Esri, Google, Bing,
Mapbox satellite) may be viewed but **never traced**. Accuracies are the
producer's own statements; "specification" means a design target, "tested" a
checkpoint report. CE95 = 2.4477 x per-axis RMSE (circular, equal axes).

US producers deliver in **NAD83(2011)**. 3DEP lidar reaches us still in
NAD83(2011) (EPT labels it WGS 84 by the identity step); the imagery services
already converted it to WGS 84 (`WGS84-service`). `lib/datum.py` moves the
position reference to the atlas frame (WGS 84 (G2139) ~ ITRF2014, epoch
2026.0); the NAD83 step is 0.9-1.6 m and was silently ignored before.

## Imagery (traces the edges): `lib/imagery.SOURCES`

| id | coverage | GSD | bands | licence | stated accuracy |
|---|---|---|---|---|---|
| `naip` | conterminous US, every 2-3 years | 0.6 m (served 0.5) | RGB + NIR | public domain | **4 m CE95 contract** (6 m before 2016); not tested per acquisition |
| `ct-2023` | Connecticut (Lime Rock) | 7.6 cm (served 0.25) | RGB + NIR | no restrictions (CT ECO) | **tested**: RMSEx 0.072, RMSEy 0.060 m on 179 checkpoints, 0.16 m CE95 |
| `indiana-2025` | Indiana (Indianapolis) | 7.6 cm | RGB + NIR | CC0 1.0 | specification ASPRS 15 cm class, 0.37 m CE95; no test report found |
| `txgio-2021-caparea` | Austin area (COTA) | 15 cm | RGB + CIR | CC0 1.0 | not stated |
| `fdep-2020` | Florida counties | 15 cm | RGB + NIR | public record, no restrictions stated | specification 1 ft RMSE per axis, 0.75 m CE95 |
| `fdep-2021` | Florida counties | 15 cm | RGB only | as above | as above |

Served frame, measured by registration onto NAD83(2011) lidar: `naip`
(all ten venues), `ct-2023` and `txgio-2021-caparea` are transformed to WGS 84
(`WGS84-service`); `indiana-2025` is identity-labelled NAD83(2011). `fdep-2021`
(RGB only, Volusia) is the reference on its specification at Daytona (it wins
the selection: sharper, and it sees the outside wall that NAIP misses); its
weak pseudo-NIR registration puts it 0.86 m from where the lidar puts it, but
positioned NAIP agrees with it to 0.09 m (median). `fdep-2020` does not cover
Volusia; at Sebring it loses to NAIP (edges seen on 26 % of the lap on both
sides) and `fdep-2021` does not cover Highlands.

Which source a track uses is chosen by `measure_surface.py` (see
docs/GEOMETRY.md, auto selection) and recorded in `layout.surface.selection`.

Only `ct-2023` has a tested accuracy better than the lidar references; it
can be the reference itself. The others are sharper than NAIP (better edge
tracing) but their position is still established by lidar registration.

## Lidar (absolute reference): USGS 3DEP, `lib/lidar.PROJECTS`

Public domain, served as Entwine Point Tiles on `s3://usgs-lidar-public`
(discovery: hobuinc/usgs-lidar `resources.geojson`). Ground/road returns at
2-20 pts/m2: too sparse to trace an edge sharply, but positioned by GNSS/IMU and
ground control. Most project metadata do **not** state a tested horizontal
accuracy (USGS Lidar Base Specification only requires reporting it since
2014 and many vendors leave it blank); 1.0 m CE95 is then assumed and flagged.

| venue | survey (reference first) | stated horizontal accuracy |
|---|---|---|
| Road Atlanta | GA_Statewide_B3_2018; ARRA-GA_LakeLanier_2010 | not stated; not stated |
| Daytona | FL_Peninsular_Volusia_2018 | 0.5 m (statistic unspecified, taken as radial RMSE) = 0.87 m CE95 |
| Sebring | FL_Peninsular_FDEM_Highlands_2018 | ASPRS 41 cm class = 1.0 m CE95 (design) |
| Long Beach | CA_LosAngeles_1_B23; USGS_LPC_CA_LosAngeles_2016 | not stated |
| Laguna Seca | CA_FEMA_Z4_B1_2018; ARRA-CA_CentralCoast-Z4_2010 | not stated |
| Watkins Glen | NY_FingerLakes_1_2020; NY_FEMA_R2_Seneca_2012 | not stated |
| Lime Rock | CT_Statewide_B7_2016 | 1.0 m RMSE per axis (design) = 2.45 m CE95 |
| VIR | VA_South_Central_B2_2017 | not found |
| Indianapolis | IN_Central_MarionCo_2016; IN_MarionCo_2011 | 0.6 m RMSE per axis (spec) = 1.47 m CE95 |
| COTA | TX_Central_B1_2017 | tested RMSEx 0.189, RMSEy 0.186 m = 0.46 m CE95 |

Two independent surveys of the same place (different years, vendors, flights)
that register the imagery to the same shift bound each other's errors: that
agreement is recorded in `position.checks` as empirical support for an
assumed accuracy.

## France: IGN (Géoplateforme), integrated

Le Mans is measured from French open data (Licence Ouverte Etalab 2.0,
attribution "IGN"), delivered in RGF93 / Lambert-93 (EPSG:2154).

- **Imagery `ign-bdortho-2022`**: BD ORTHO 20 cm, RGB + IRC (false colour,
  NIR first), WMS `data.geopf.fr/wms-r` layers `ORTHOIMAGERY.ORTHOPHOTOS2022` /
  `ORTHOIMAGERY.ORTHOPHOTOS.IRC.2022`, requested in EPSG:3857 (the server
  reprojects; the frame is then measured against lidar). Sarthe (72) was flown
  in 2016, 2019, 2022 and 2025 (Géoportail now shows 2025, which the yearly
  WMS layer does not serve yet). Accuracy: IGN states it as an EMQ per
  département, in a table the product description (DC_BDORTHO_2-0, April 2025,
  section 5.2) lists as forthcoming: **not stated**. Tiles outside a campaign come
  back pure white and are skipped.
- **Lidar `IGN_LiDAR_HD`** (`lib/lidar_ign.py`): LiDAR HD classified point
  clouds, 1 km COPC tiles (index: WFS `IGNF_LIDAR-HD_METADONNEE:metadata`,
  Lambert-93 bbox), read by HTTP range requests for the corridor only (~30
  ground pts/m2 at Le Mans). **Specification** (DC_LiDAR_HD_1-0, rev. July 2026,
  section 2.3.1.4): planimetric REMQ (RMSE) at most 0.50 m, altimetric 0.10 m; taken as a
  radial RMSE = **0.87 m CE95**. The worked control example in the same document
  reaches 0.117 m, but it is not a per-block test.
- **Datum**: RGF93 is ETRS89 (v1 = ETRF93 at 1993.0, v2/v2b = ETRF2000 at
  2009.0/2019.0; the products do not say which, the v1/v2 difference is "a few cm").
  `lib/datum.py` steps ETRF2000 -> ITRF2014 at 2026.0 (0.92 m towards
  NE at Le Mans), with 4 cm (1 sigma) for the realisation.
- **Result**: BD ORTHO 2022 sits 0.67 m (E 0.21, N -0.64) from LiDAR HD, and
  the local shift varies by 0.4-0.5 m across the lap (a mosaic of flights), so
  the registration term dominates the budget: **1.44 m CE95**. A piecewise
  registration (per-section shifts) is the way under 1 m.

## Outside the US and France

Desk research only: nothing here has been fetched or tested by the pipeline,
and each licence must be re-read for the specific product before use.

| country | programme | GSD | licence | accuracy | status |
|---|---|---|---|---|---|
| Canada (Mosport) | Ontario OIPC / SWOOP / COOP | 16-20 cm | Open Government Licence - Ontario for some years; others restricted | ~0.5 m spec | not integrated; licence per year to check |
| UK (Silverstone) | Environment Agency lidar (DTM/intensity), Aerial Photography for Great Britain | 25 cm / 1 m lidar | OGL v3 (lidar); APGB is **not** open | lidar ~0.4 m | lidar usable as a reference, imagery source missing |
| Spain, Netherlands, Belgium, Germany (some Länder) | PNOA / PDOK / Geopunt / state DOPs | 20 cm | Etalab 2.0 / CC BY 4.0 / CC0 / dl-de-by-2.0 | 0.2-0.5 m tested (national specs) | usable; not integrated |

National European orthophoto programmes are both open and tested, often better
than 0.5 m: they would be imagery **and** reference in one.

## Not usable

- Esri World Imagery, Google, Bing, Mapbox satellite: terms forbid tracing.
- OSM `highway=raceway` geometry: open, but traced from mixed imagery with no
  stated accuracy (typically 2-10 m off at the venues checked): it only seeds
  the edge search.
- Owner telemetry / GPS logs: private data, never used for the atlas.
