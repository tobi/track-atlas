from lib.dsl import Track, osm

t = Track(
    "sebring",
    "Sebring International Raceway",
    aka=["Sebring"],
    country="US",
    series=["imsa", "wec"],
    location=dict(
        lat=27.4547,
        lon=-81.3483,
        locality="Sebring, Florida",
        region="Florida",
        timezone="America/New_York",
    ),
    external_ids=dict(imsa_data="sebring"),
    osm=osm([27.4247, -81.3783, 27.4847, -81.3183], relation=7003292),
    lovely=dict(gp="lmu/sebring-international-raceway.json"),
)
t.surface()

# -- every layout ------------------------------------------------------------
every = t.every_layout
every.summary(
    "Corrected Sebring names by lap-position against OSM named ways: Tower Turn is T13, Fangio is T8, Cunningham is T10, Bishop Bend is T14, Gendebien is T15, and Sunset Bend is T17. Removed unsupported Tower/Workbench/Coca-Cola-style labels from the wrong turns.",
)
every.corner(
    1,
    driver=None,
    official="Turn 1",
    direction="left",
    scale=3,
    error="Do not label T1 as Tower Turn; OSM and lap position put Tower Turn at T13.",
)
every.corner(2, driver=None, official="Turn 2", direction="right", scale=6)
every.corner(3, driver=None, official="Turn 3", direction="left", scale=4)
every.corner(4, driver=None, official="Turn 4", direction="right", scale=5)
every.corner(
    5,
    driver=None,
    official="Turn 5",
    direction="left",
    scale=2,
    error="Do not label as Warehouse without a source; no corresponding named OSM way is present.",
)
every.corner(
    6,
    driver="Big Bend",
    official="Gurney Bend",
    direction="right",
    scale=5,
    error="OSM names the way at this lap position Gurney Bend; keep Big Bend as driver/common label.",
)
every.corner(7, driver="Hairpin", official="Hairpin", direction="right", scale=1)
every.corner(
    8,
    driver="Fangio",
    official="Fangio",
    direction="right",
    scale=6,
    error="Bishop Bend is near T14, not T8.",
)
every.corner(
    9,
    driver=None,
    official="Turn 9",
    direction="left",
    scale=6,
    error="Cunningham is near T10, not T9.",
)
every.corner(10, driver="Cunningham", official="Cunningham Corner", direction="right", scale=3)
every.corner(11, driver="Collier", official="Collier Curve", direction="left", scale=4)
every.corner(12, driver=None, official="Turn 12", direction="right", scale=5)
every.corner(13, driver="Tower Turn", official="Tower Turn", direction="right", scale=4)
every.corner(14, driver="Bishop Bend", official="Bishop Bend", direction="left", scale=4)
every.corner(
    15,
    driver="Gendebien",
    official="Gendebien Bend",
    direction="right",
    scale=4,
    error="Do not label as Coca-Cola; OSM names this section Gendebien Bend.",
)
every.corner(16, driver="Le Mans", official="Le Mans Curve", direction="right", scale=4)
every.corner(17, driver="Sunset Bend", official="Sunset Bend", direction="right", scale=4)
every.unnamed(
    0.095,
    "left",
    "part_of_corner",
    "second lobe of T1 (L79, +26 deg) 70 m after its apex; both edges seen on <10% of it",
)
every.unnamed(
    0.0994,
    "right",
    "artefact",
    "R69, -14 deg where the OSM centerline bends left (R205); right edge unseen",
)
every.unnamed(
    0.3473,
    "left",
    "part_of_corner",
    "Hairpin (T7) exit wiggle, L44 +32 deg, inside the OSM Hairpin way 0.3298-0.3642; the centerline stays right here",
)
every.unnamed(
    0.3579,
    "right",
    "part_of_corner",
    "Hairpin (T7) exit, R76 -37 deg, inside the OSM Hairpin way 0.3298-0.3642",
)
every.unnamed(
    0.4889,
    "left",
    "part_of_corner",
    "first lobe of Collier (T11, a left), L52 +30 deg between the Cunningham and Collier ways; centerline L61",
)
every.unnamed(
    0.5169,
    "left",
    "part_of_corner",
    "Collier (T11) second lobe, L75 +15 deg, inside the OSM Collier Curve way 0.5003-0.5171",
)
every.unnamed(
    0.6564,
    "left",
    "unnumbered_bend",
    "L70, +25.5 deg between Bishop Bend (T14) and Gendebien (T15); real (centerline L81) but unnumbered on the 17-turn circuit",
)
every.unnamed(
    0.704,
    "left",
    "part_of_corner",
    "Gendebien (T15) exit, L66 +31 deg, at the end of the OSM Gendebien Bend way 0.6824-0.7054",
)
every.unnamed(
    0.8962,
    "right",
    "part_of_corner",
    "Sunset Bend (T17) first apex, R59 -41 deg; OSM Sunset Bend way 0.8912-0.9578",
)
every.unnamed(
    0.9145,
    "right",
    "part_of_corner",
    "Sunset Bend (T17) second apex, R47 -37 deg; the marked apex is R46 at 0.9251",
)
every.unnamed(
    0.9368,
    "right",
    "part_of_corner",
    "Sunset Bend (T17) exit apex, R61 -32.5 deg; OSM Sunset Bend way",
)

# -- wec -------------------------------------------------------------------
wec = t.layout(
    "wec",
    "International Circuit",
    length_m=5954,
    direction="clockwise",
    lovely="gp",
    centerline="relation",
    series=["wec"],
    pit=dict(entry=0.9675, exit=0.0608),
)

# -- imsa ------------------------------------------------------------------
imsa = t.layout(
    "imsa",
    "International Circuit",
    length_m=5954,
    direction="clockwise",
    lovely="gp",
    centerline="relation",
    series=["imsa"],
    pit=dict(entry=0.9675, exit=0.0608),
)
