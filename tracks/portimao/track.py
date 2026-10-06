from lib.dsl import Track, osm

t = Track(
    "portimao",
    "Autodromo Internacional do Algarve",
    aka=["Portimao"],
    country="PT",
    series=["wec", "elms"],
    location=dict(
        lat=37.2304,
        lon=-8.6279,
        locality="Portimao",
        region="Algarve",
        timezone="Europe/Lisbon",
    ),
    external_ids=dict(imsa_data="portimao"),
    osm=osm([37.2004, -8.6579, 37.2604, -8.5979], relation=7509968),
    lovely=dict(gp="lmu/algarve-international-circuit.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=4653, direction="clockwise", lovely="gp")
lap.summary(None)
lap.corner(1, driver="Turn 1", official="Curva 1", direction="right", scale=4)
lap.corner(2, official="Curva 2", direction="right", scale=6)
lap.corner(3, driver="Lagos", official="Curva Lagos", direction="right", scale=1)
lap.corner(4, official="Curva 4", direction="left", scale=4)
lap.corner(5, driver="Torre VIP", official="Curva Torre VIP", direction="left", scale=1)
lap.corner(6, official="Curva 6", direction="left", scale=6)
lap.corner(7, official="Curva 7", direction="right", scale=5)
lap.corner(8, driver="Samsung", official="Curva Samsung", direction="right", scale=2)
lap.corner(9, driver="Craig Jones", official="Curva Craig Jones", direction="left", scale=5)
lap.corner(10, driver="Portimão", official="Curva Portimão", direction="right", scale=6)
lap.corner(11, official="Curva 11", direction="right", scale=3)
lap.corner(12, official="Curva 12", direction="left", scale=5)
lap.corner(13, official="Curva 13", direction="left", scale=1)
lap.corner(14, driver="Sagres", official="Curva Sagres", direction="right", scale=2)
lap.corner(15, driver="Galp", official="Curva Galp", direction="right", scale=5)
