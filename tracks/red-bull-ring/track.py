from lib.dsl import Track, osm

t = Track(
    "red-bull-ring",
    "Red Bull Ring",
    aka=["Spielberg", "A1-Ring"],
    country="AT",
    series=["elms", "f1"],
    location=dict(
        lat=47.2185,
        lon=14.7588,
        locality="Spielberg",
        region="Styria",
        timezone="Europe/Vienna",
    ),
    external_ids=dict(imsa_data="red-bull-ring"),
    osm=osm([47.1885, 14.7288, 47.2485, 14.7888], relation=5309181),
    lovely=dict(gp="f12025/austria.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=4318, direction="clockwise", lovely="gp")
lap.summary(
    "T2 direction incorrect (should be right), T10 direction incorrect (should be left)",
)
lap.corner(1, driver="Turn 1", official="Niki Lauda Kurve", direction="right", scale=2)
lap.corner(
    2,
    driver="Remus Kurve",
    official="Remus Kurve",
    direction="right",
    scale=6,
    error="corner 2 direction should be right not left — the gentle right-hander before Remus hairpin",
)
lap.corner(3, driver="Remus", official="Remus", direction="right", scale=1)
lap.corner(4, driver="Schlossgold", official="Schlossgold", direction="right", scale=2)
lap.corner(5, driver="Turn 5", direction="right", scale=4)
lap.corner(6, driver="Rauch Kurve", official="Rauch Kurve", direction="left", scale=3)
lap.corner(7, driver="Würth Kurve", official="Würth Kurve", direction="left", scale=3)
lap.corner(8, driver="Turn 8", direction="right", scale=4)
lap.corner(9, driver="Rindt", official="Jochen-Rindt-Kurve", direction="right", scale=3)
lap.corner(
    10,
    driver="Mobilkurve",
    official="Red Bull Mobile Kurve",
    direction="left",
    scale=2,
    error="corner 10 direction should be left not right — final corner is a left-hander onto the main straight",
)
