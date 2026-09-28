from lib.dsl import Track, osm

t = Track(
    "fuji",
    "Fuji Speedway",
    aka=["Fuji"],
    country="JP",
    series=["wec"],
    location=dict(
        lat=35.3697,
        lon=138.9227,
        locality="Oyama, Shizuoka",
        region="Shizuoka",
        timezone="Asia/Tokyo",
    ),
    external_ids=dict(imsa_data="fuji"),
    osm=osm([35.3397, 138.8927, 35.3997, 138.9527]),
    lovely=dict(gp="lmu/fuji-speedway.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=4549, direction="clockwise", lovely="gp")
lap.summary(
    "Data is structurally sound; geometry confirms all directions. Minor severity adjustments: T3 Coca-Cola (5→4), T9 300R (6→5), T15 Netz (1→2). Turns 4-5 form the 100R complex, 10-11 the Dunlop chicane, and 14-15 the Netz double-left.",
)
lap.corner(1, driver="First Corner", official="TGR Corner", direction="right", scale=1)
lap.corner(2, direction="right", scale=6)
lap.corner(
    3,
    driver="Coca-Cola",
    official="Coca-Cola Corner",
    direction="left",
    scale=4,
    error="scale 5 slightly optimistic — Coca-Cola is a medium-fast left with notable steering input, scale 4 fits better",
)
lap.corner(4, driver="100R", official="100R", complex="100R", direction="right", scale=4)
lap.corner(5, driver="100R exit", official="100R", complex="100R", direction="right", scale=5)
lap.corner(6, driver="Hairpin", official="Hairpin Corner (75R)", direction="left", scale=1)
lap.corner(
    9,
    driver="300R",
    official="300R",
    direction="right",
    scale=5,
    error="scale 6 understates it — 300R is a genuine high-speed sweeper, scale 5 more appropriate",
)
lap.corner(
    10,
    driver="Dunlop",
    official="Dunlop Corner",
    complex="Dunlop Chicane",
    direction="right",
    scale=1,
)
lap.corner(11, complex="Dunlop Chicane", direction="left", scale=2)
lap.corner(13, driver="13th Corner", official="GR Supra Corner", direction="right", scale=3)
lap.corner(14, official="Netz Corner", complex="Netz", direction="left", scale=4)
lap.corner(
    15,
    driver="Netz",
    official="Netz Corner",
    complex="Netz",
    direction="left",
    scale=2,
    error="scale 1 slightly harsh — Netz is a tight-medium left, not a true hairpin; scale 2 fits",
)
lap.corner(16, driver="Panasonic", official="Panasonic Corner", direction="right", scale=1)
