from lib.dsl import Track, osm

t = Track(
    "spa-francorchamps",
    "Circuit de Spa-Francorchamps",
    aka=["Spa"],
    country="BE",
    series=["wec", "elms", "f1"],
    location=dict(
        lat=50.4357,
        lon=5.9695,
        locality="Stavelot",
        region="Wallonia",
        timezone="Europe/Brussels",
    ),
    external_ids=dict(imsa_data="spa-francorchamps"),
    osm=osm([50.4057, 5.9395, 50.4657, 5.9995], relation=284560),
    lovely=dict(gp="lmu/circuit-de-spa-francorchamps.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=7004, direction="clockwise", lovely="gp")
lap.summary(
    "Corner numbering/naming confusion in Fagnes-Stavelot-Campus section (T13-17); T16 direction wrong; T4 questionable as distinct corner; scale ratings too low for several fast corners",
)
lap.corner(
    3,
    driver="Eau Rouge",
    official="Eau Rouge",
    complex="Eau Rouge-Raidillon",
    direction="left",
    scale=5,
)
lap.corner(
    4,
    driver="Eau Rouge-Raidillon",
    complex="Eau Rouge-Raidillon",
    direction="right",
    scale=5,
    error="This kink is typically not called Turn 4 - it's the transition within Eau Rouge-Raidillon complex",
)
lap.corner(
    5,
    driver="Raidillon",
    official="Raidillon",
    complex="Eau Rouge-Raidillon",
    direction="left",
    scale=5,
)
lap.corner(
    7,
    driver="Les Combes",
    official="Les Combes",
    direction="right",
    scale=3,
    error="scale should be 3 not 4 - Les Combes is a medium-speed corner, not fast",
)
lap.corner(
    8,
    driver="Les Combes",
    official="Les Combes",
    direction="left",
    scale=3,
    error="scale should be 3 not 4 - second part of Les Combes switchback is medium speed",
)
lap.corner(9, driver="Malmedy", official="Malmedy", direction="right", scale=4)
lap.corner(11, driver="Rivage", official="Rivage", direction="left", scale=4)
lap.corner(
    13,
    driver="Les Fagnes",
    official="Les Fagnes",
    complex="Fagnes-Stavelot",
    direction="right",
    scale=5,
    error="scale should be 5 not 4 - Les Fagnes is a fast sweeper",
)
lap.corner(
    14,
    driver="Stavelot",
    official="Stavelot",
    complex="Fagnes-Stavelot",
    direction="left",
    scale=5,
    error="scale should be 5 not 4 - Stavelot is taken flat or near-flat in modern cars",
)
lap.corner(
    15,
    driver="Paul Frère",
    official="Paul Frère",
    direction="right",
    scale=3,
    error="commonly called Paul Frère not Campus - Campus was the old name before 2022 rename",
)
lap.corner(
    16,
    driver="Campus",
    official="Campus",
    direction="left",
    scale=3,
    error="direction should be left not right, and scale should be 3 not 4 - this is the left-hander after Paul Frère; also Stavelot label appears misplaced",
)
lap.corner(
    17,
    driver="Stavelot",
    official="Stavelot",
    direction="left",
    scale=1,
    error="This appears to be the actual Stavelot corner (tight left hairpin), not corner 16",
)
lap.corner(
    19,
    driver="Bus Stop Chicane",
    official="Chicane",
    complex="Bus Stop",
    direction="right",
    scale=1,
)
lap.corner(
    20,
    driver="Bus Stop Chicane",
    official="Chicane",
    complex="Bus Stop",
    direction="left",
    scale=1,
)
