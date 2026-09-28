from lib.dsl import Track, osm

t = Track(
    "bahrain",
    "Bahrain International Circuit",
    aka=["Sakhir"],
    country="BH",
    series=["wec", "f1"],
    location=dict(
        lat=26.0326,
        lon=50.5106,
        locality="Sakhir",
        region="Southern Governorate",
        timezone="Asia/Bahrain",
    ),
    external_ids=dict(imsa_data="bahrain"),
    osm=osm([26.0026, 50.4806, 26.0626, 50.5406], relation=11987743),
    lovely=dict(gp="lmu/bahrain-international-circuit.json"),
)

# -- gp --------------------------------------------------------------------
lap = t.layout("gp", "Grand Prix Circuit", length_m=5412, direction="clockwise", lovely="gp")
lap.summary(
    "Turn 7 direction is wrong (should be left, not right); T6/T7/T8 corner coordinates appear shifted ~50-90m past their actual apexes; minor severity-scale adjustments on T1, T2, T11, T14",
)
lap.corner(
    1,
    number=1,
    official="Michael Schumacher Corner",
    direction="right",
    scale=2,
    error="scale 1 slightly overstated — T1 is a heavy-braking ~90° right, not a true hairpin; 2 is more accurate",
)
lap.corner(
    2,
    number=2,
    direction="left",
    scale=3,
    error="scale 4 too fast — T2 is a medium-speed left taken in sequence with T1/T3; 3 fits better",
)
lap.corner(
    6,
    number=6,
    direction="right",
    scale=5,
    error="corner coordinate appears ~60m late — the rightward bend apexes nearer [50.5159, 26.0330]; marker 0.36 likely closer to 0.35",
)
lap.corner(
    7,
    number=7,
    direction="left",
    scale=5,
    error="corner 7 direction should be left not right — centerline bearing swings counterclockwise (~278° to ~220°) through this section; coordinate also looks ~60m past the actual bend",
)
lap.corner(
    8,
    number=8,
    direction="right",
    scale=2,
    error="corner point [50.51309, 26.032017] sits ~50m north of the actual apex (~26.0315), on the corner exit; also scale 1 is slightly harsh — it's a tight right but not a full hairpin",
)
lap.corner(10, number=10, direction="left", scale=1)
lap.corner(
    11,
    number=11,
    direction="left",
    scale=3,
    error="scale 4 a touch fast — T11 is a long medium-speed left where the car is loaded for a long time; 3 fits better",
)
lap.corner(
    14,
    number=14,
    direction="right",
    scale=2,
    error="scale 3 too fast — T14 is a slow heavy-braking right onto the run to the final kink; 2 is more accurate",
)
