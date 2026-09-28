from lib.dsl import Track, osm

t = Track(
    "mugello",
    "Autodromo Internazionale del Mugello",
    aka=["Mugello"],
    country="IT",
    series=["elms"],
    location=dict(
        lat=43.9918,
        lon=11.3698,
        locality="Scarperia e San Piero",
        region="Tuscany",
        timezone="Europe/Rome",
    ),
    external_ids=dict(imsa_data="mugello"),
    osm=osm([43.9618, 11.3398, 44.0218, 11.3998], relation=8487163),
    lovely=dict(gp="iracing/mugello-gp.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=5245, direction="clockwise", lovely="gp")
lap.summary(None)
lap.corner(1, driver="San Donato", official="San Donato", direction="right", scale=1)
lap.corner(2, driver="Luco", official="Luco", direction="left", scale=4)
lap.corner(3, driver="Poggio Secco", official="Poggio Secco", direction="left", scale=4)
lap.corner(4, driver="Materassi", official="Materassi", direction="right", scale=3)
lap.corner(
    5,
    driver="Borgo San Lorenzo",
    official="Borgo San Lorenzo",
    direction="left",
    scale=4,
)
lap.corner(6, driver="Casanova", official="Casanova-Savelli", direction="right", scale=5)
lap.corner(7, driver="Savelli", official="Casanova-Savelli", direction="left", scale=5)
lap.corner(
    8,
    driver="Arrabbiata 1",
    official="Arrabbiata 1",
    complex="Arrabbiata",
    direction="left",
    scale=3,
)
lap.corner(
    9,
    driver="Arrabbiata 2",
    official="Arrabbiata 2",
    complex="Arrabbiata",
    direction="right",
    scale=4,
)
lap.corner(10, driver="Scarperia", official="Scarperia", direction="left", scale=5)
lap.corner(11, driver="Palagio", official="Palagio", direction="left", scale=4)
lap.corner(12, driver="Correntaio", official="Correntaio", direction="right", scale=4)
lap.corner(
    13,
    driver="Biondetti 1",
    official="Biondetti 1",
    complex="Biondetti",
    direction="left",
    scale=3,
)
lap.corner(
    14,
    driver="Biondetti 2",
    official="Biondetti 2",
    complex="Biondetti",
    direction="left",
    scale=3,
)
lap.corner(15, driver="Bucine", official="Bucine", direction="right", scale=2)
