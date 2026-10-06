from lib.dsl import Track, osm

t = Track(
    "mexico-city",
    "Autodromo Hermanos Rodriguez",
    aka=["Mexico City"],
    country="MX",
    series=["f1"],
    location=dict(
        lat=19.4042,
        lon=-99.0907,
        locality="Mexico City",
        region="CDMX",
        timezone="America/Mexico_City",
    ),
    osm=osm([19.3742, -99.1207, 19.4342, -99.0607], relation=16251935),
    lovely=dict(gp="f12025/mexico.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=4304, direction="clockwise", lovely="gp")
lap.summary(None)
lap.corner(
    1,
    driver="Esses",
    official="Esses Moisés Solana",
    complex="Esses",
    direction="right",
    scale=2,
)
lap.corner(
    2,
    driver="Esses",
    official="Esses Moisés Solana",
    complex="Esses",
    direction="left",
    scale=3,
)
lap.corner(
    3,
    driver="Esses",
    official="Esses Moisés Solana",
    complex="Esses",
    direction="right",
    scale=3,
)
lap.corner(4, driver="Ese del Lago", official="Ese del Lago", direction="left", scale=2)
lap.corner(5, driver="Ese del Lago", official="Ese del Lago", direction="right", scale=2)
lap.corner(6, driver="Horquilla", official="Horquilla", direction="right", scale=1)
lap.corner(
    7,
    driver="Esses del Bosque",
    official="Esses del Bosque",
    complex="Esses del Bosque",
    direction="left",
    scale=3,
)
lap.corner(
    8,
    driver="Esses del Bosque",
    official="Esses del Bosque",
    complex="Esses del Bosque",
    direction="right",
    scale=5,
)
lap.corner(
    9,
    driver="Esses del Bosque",
    official="Esses del Bosque",
    complex="Esses del Bosque",
    direction="left",
    scale=4,
)
lap.corner(10, driver="Turn 10", direction="right", scale=5)
lap.corner(11, driver="Turn 11", direction="left", scale=5)
lap.corner(12, driver="Turn 12", direction="right", scale=3)
lap.corner(13, driver="Foro Sol", official="Foro Sol", direction="left", scale=1)
lap.corner(14, driver="Turn 14", direction="right", scale=2)
lap.corner(15, driver="Turn 15", direction="left", scale=6)
lap.corner(16, driver="Turn 16", direction="right", scale=2)
lap.corner(17, driver="Peraltada", official="Peraltada", direction="right", scale=5)
