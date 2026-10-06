from lib.dsl import Track, osm

t = Track(
    "suzuka",
    "Suzuka International Racing Course",
    aka=["Suzuka"],
    country="JP",
    series=["f1"],
    location=dict(lat=34.8431, lon=136.541, locality="Suzuka, Mie", region="Mie", timezone="Asia/Tokyo"),
    osm=osm([34.8131, 136.511, 34.8731, 136.571], relation=284570),
    lovely=dict(gp="f12025/suzuka.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=5807, direction="clockwise", lovely="gp")
lap.summary(
    "Corners 8, 9, and 10 have incorrect directions (all marked right, should be left); corner 15 (130R) severity should be 5 not 4",
)
lap.corner(1, driver="Turn 1", official="First Corner", direction="right", scale=3)
lap.corner(2, driver="Turn 2", official="Second Corner", direction="right", scale=4)
lap.corner(
    3,
    driver="S Curves",
    official="S Curves",
    complex="S Curves",
    direction="left",
    scale=3,
)
lap.corner(
    4,
    driver="S Curves",
    official="S Curves",
    complex="S Curves",
    direction="right",
    scale=3,
)
lap.corner(
    5,
    driver="S Curves",
    official="S Curves",
    complex="S Curves",
    direction="left",
    scale=3,
)
lap.corner(
    6,
    driver="S Curves",
    official="S Curves",
    complex="S Curves",
    direction="right",
    scale=4,
)
lap.corner(7, driver="Dunlop", official="Dunlop Curve", direction="left", scale=4)
lap.corner(
    8,
    driver="Degner 1",
    official="Degner Curve 1",
    complex="Degner",
    direction="left",
    scale=3,
    error="corner 8 direction should be left not right",
)
lap.corner(
    9,
    driver="Degner 2",
    official="Degner Curve 2",
    complex="Degner",
    direction="left",
    scale=2,
    error="corner 9 direction should be left not right",
)
lap.corner(
    10,
    driver="Turn 10",
    official="Turn 10",
    direction="left",
    scale=4,
    error="corner 10 direction should be left not right",
)
lap.corner(11, driver="Hairpin", official="Hairpin", direction="left", scale=1)
lap.corner(12, driver="Turn 12", official="Turn 12", direction="right", scale=5)
lap.corner(
    13,
    driver="Spoon",
    official="Spoon Curve",
    complex="Spoon",
    direction="left",
    scale=3,
)
lap.corner(
    14,
    driver="Spoon",
    official="Spoon Curve",
    complex="Spoon",
    direction="left",
    scale=3,
)
lap.corner(
    15,
    driver="130R",
    official="130R",
    direction="left",
    scale=5,
    error="corner 15 scale should be 5 not 4 - this is one of F1's fastest corners",
)
lap.corner(
    16,
    driver="Casio Triangle",
    official="Casio Triangle",
    complex="Casio Triangle",
    direction="right",
    scale=2,
)
lap.corner(
    17,
    driver="Casio Triangle",
    official="Casio Triangle",
    complex="Casio Triangle",
    direction="left",
    scale=2,
)
lap.corner(18, driver="Chicane", official="Chicane", direction="right", scale=3)
