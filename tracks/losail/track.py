from lib.dsl import Track, osm

t = Track(
    "losail",
    "Lusail International Circuit",
    aka=["Losail", "Qatar"],
    country="QA",
    series=["wec", "f1"],
    location=dict(lat=25.4873, lon=51.4525, locality="Lusail", region="Al Daayen", timezone="Asia/Qatar"),
    external_ids=dict(imsa_data="losail"),
    osm=osm([25.4573, 51.4225, 25.5173, 51.4825]),
    lovely=dict(gp="lmu/lusail-international-circuit.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=5419, direction="clockwise", lovely="gp")
lap.summary(None)
lap.corner(1, official="Turn 1", direction="right", scale=1)
lap.corner(2, official="Turn 2", direction="left", scale=2)
lap.corner(3, official="Turn 3", direction="right", scale=5)
lap.corner(4, official="Turn 4", direction="right", scale=3)
lap.corner(5, official="Turn 5", direction="right", scale=3)
lap.corner(6, official="Turn 6", direction="left", scale=1)
lap.corner(7, official="Turn 7", direction="right", scale=2)
lap.corner(8, official="Turn 8", direction="left", scale=6)
lap.corner(9, official="Turn 9", direction="right", scale=4)
lap.corner(10, official="Turn 10", direction="left", scale=2)
lap.corner(11, official="Turn 11", direction="left", scale=6)
lap.corner(12, official="Turn 12", direction="right", scale=5)
lap.corner(13, official="Turn 13", direction="right", scale=5)
lap.corner(14, official="Turn 14", direction="right", scale=4)
lap.corner(15, official="Turn 15", direction="left", scale=4)
lap.corner(16, official="Turn 16", direction="right", scale=2)
