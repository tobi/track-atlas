from lib.dsl import Track, osm

t = Track(
    "barcelona",
    "Circuit de Barcelona-Catalunya",
    aka=["Catalunya", "Montmelo"],
    country="ES",
    series=["elms", "f1"],
    location=dict(
        lat=41.5687,
        lon=2.2567,
        locality="Montmelo",
        region="Catalonia",
        timezone="Europe/Madrid",
    ),
    external_ids=dict(imsa_data="barcelona-catalunya"),
    osm=osm([41.5387, 2.2267, 41.5987, 2.2867], relation=284540),
    lovely=dict(gp="f12025/catalunya.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout(
    "gp",
    "Grand Prix Circuit",
    length_m=4657,
    direction="clockwise",
    lovely="gp",
    start_finish=dict(marker=0.0, location=[2.262117, 41.571095]),
)
lap.summary(
    "Corner count (14) correctly reflects the post-2023 chicane-removal layout, but T14 is misnamed 'Catalunya' instead of New Holland; minor scale corrections at T1, T5, T9, T13, T14 and a dual-name cleanup at T7",
)
lap.corner(
    1,
    driver="Elf",
    official="Elf",
    direction="right",
    scale=3,
    error="scale 2 slightly understates it — T1 is a medium-speed right taken in 3rd/4th gear, scale 3 is more accurate",
)
lap.corner(3, driver="Renault", official="Renault", direction="right", scale=5)
lap.corner(4, driver="Repsol", official="Repsol", direction="right", scale=4)
lap.corner(
    5,
    driver="Seat",
    official="Seat",
    direction="left",
    scale=2,
    error="scale 1 overstates it — T5 is a slow downhill left but not a true hairpin, scale 2 fits better",
)
lap.corner(
    7,
    driver="Würth",
    official="Würth",
    direction="left",
    scale=2,
    error="colloquial field contains two names ('Würth, TV3') — should be a single name; 'Würth' is the established sponsor name for T7",
)
lap.corner(
    9,
    driver="Campsa",
    official="Campsa",
    direction="right",
    scale=4,
    error="scale 3 understates it — Campsa is a fast, blind, crested right-hander taken near flat, scale 4",
)
lap.corner(10, driver="La Caixa", official="La Caixa", direction="left", scale=1)
lap.corner(12, driver="Banc Sabadell", official="Banc de Sabadell", direction="right", scale=3)
lap.corner(
    13,
    driver="Europcar",
    official="Europcar",
    direction="right",
    scale=2,
    error="scale 3 slightly high — T13 is a slow right onto the run to the final corner, scale 2 fits better",
)
lap.corner(
    14,
    driver="New Holland",
    official="New Holland",
    direction="right",
    scale=4,
    error="colloquial 'Catalunya' is wrong — the final corner (former T16, renumbered T14 after the 2023 chicane removal) is named New Holland; it is also a fast right onto the main straight, scale 4 not 3",
)
