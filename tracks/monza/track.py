from lib.dsl import Track, osm

t = Track(
    "monza",
    "Autodromo Nazionale Monza",
    aka=["Monza", "Temple of Speed"],
    country="IT",
    series=["wec", "elms", "f1"],
    location=dict(lat=45.619, lon=9.287, locality="Monza", region="Lombardy", timezone="Europe/Rome"),
    external_ids=dict(imsa_data="monza"),
    osm=osm([45.589, 9.257, 45.649, 9.317], relation=284565),
    lovely=dict(gp="lmu/autodromo-nazionale-monza.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=5793, direction="clockwise", lovely="gp")
lap.summary(
    "T4 and T5 directions are swapped (Roggia is right-left not left-right); T8-10 (Ascari) scales are too high (marked 5 but should be 3); T8 direction wrong (should be right not left)",
)
lap.corner(
    1,
    driver="First Chicane",
    official="Variante del Rettifilo",
    complex="Variante del Rettifilo",
    direction="right",
    scale=2,
)
lap.corner(
    2,
    driver="First Chicane",
    official="Variante del Rettifilo",
    complex="Variante del Rettifilo",
    direction="left",
    scale=2,
)
lap.corner(3, driver="Curva Grande", official="Curva Grande", direction="right", scale=5)
lap.corner(
    4,
    driver="Roggia",
    official="Variante della Roggia",
    complex="Variante della Roggia",
    direction="right",
    scale=2,
    error="direction should be right not left - this is a right-left chicane, T4 is the right-hander",
)
lap.corner(
    5,
    driver="Roggia",
    official="Variante della Roggia",
    complex="Variante della Roggia",
    direction="left",
    scale=2,
    error="direction should be left not right - T5 is the left exit of the chicane",
)
lap.corner(6, driver="Lesmo 1", official="Lesmo 1", direction="right", scale=3)
lap.corner(
    7,
    driver="Lesmo 2",
    official="Lesmo 2",
    direction="right",
    scale=3,
    error="scale should be 3 not 4 - Lesmo 2 is a medium-speed right-hander, similar severity to Lesmo 1",
)
lap.corner(
    8,
    driver="Ascari",
    official="Variante Ascari",
    complex="Variante Ascari",
    direction="right",
    scale=3,
    error="direction should be right not left, scale should be 3 not 5 - Ascari is a medium-speed right-left-left chicane, T8 is the right entry",
)
lap.corner(
    9,
    driver="Ascari",
    official="Variante Ascari",
    complex="Variante Ascari",
    direction="left",
    scale=3,
    error="scale should be 3 not 5 - this is the medium-speed left middle part of Ascari chicane",
)
lap.corner(
    10,
    driver="Ascari",
    official="Variante Ascari",
    complex="Variante Ascari",
    direction="left",
    scale=3,
    error="scale should be 3 not 5 - this is the left exit of Ascari chicane, still medium speed",
)
lap.corner(11, driver="Parabolica", official="Curva Parabolica", direction="right", scale=3)
