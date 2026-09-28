from lib.dsl import Track, osm

t = Track(
    "circuit-de-la-sarthe",
    "Circuit de la Sarthe",
    aka=["La Sarthe", "Circuit des 24 Heures du Mans", "Le Mans"],
    country="FR",
    series=["wec"],
    location=dict(
        lat=47.95,
        lon=0.2247,
        locality="Le Mans",
        region="Pays de la Loire",
        timezone="Europe/Paris",
    ),
    wikidata="Q270760",
    external_ids=dict(imsa_data="le-mans"),
    osm=osm([47.9, 0.15, 47.98, 0.28], relation=2126739),
    lovely={"24h": "lmu/circuit-de-la-sarthe.json"},
)
t.note(
    "Curated naming layers Lovely/OSM lack. official = circuit/ACO naming, colloquial = what drivers say. complex groups multi-corner sections. Keyed by layout id -> corners -> corner number.",
)

# -- 24h -------------------------------------------------------------------
lap = t.layout(
    "24h",
    "Circuit des 24 Heures",
    aka=["Grand Prix Endurance Circuit"],
    length_m=13626,
    direction="clockwise",
    active_years="2018-",
    lovely="24h",
)
lap.summary(
    "Directions all verified correct against geometry; main issues: T1 coordinate duplicated from T2, T20 coordinate/marker duplicated from T19, chicane partner corners (T3, T5, T19, T21) were previously left unnamed and outside their complexes, the two Mulsanne chicanes must remain separate despite both being on the Hunaudières/Mulsanne straight, and Mulsanne Corner severity was overrated at 2 instead of 1.",
)
lap.corner(
    1,
    driver="Dunlop Curve",
    official="Courbe Dunlop",
    direction="right",
    scale=5,
    error="location is identical to corner 2 (0.210987, 47.956831) — Dunlop Curve apex should be earlier, near ~0.2095, 47.9558; marker 0.05 looks right but the coordinate was copied from the chicane",
)
lap.corner(
    2,
    driver="Dunlop Chicane",
    official="Chicane Dunlop",
    complex="Dunlop Chicane",
    direction="left",
    scale=4,
)
lap.corner(
    4,
    driver="Esses de la Forêt",
    official="Esses de la Forêt",
    complex="Esses de la Forêt",
    direction="left",
    scale=4,
    error="T4 carries the Esses name but complex was null — T4 and T5 together are the Esses de la Forêt",
)
lap.corner(6, driver="Tertre Rouge", official="Virage du Tertre Rouge")
lap.corner(
    7,
    driver="First Chicane",
    official="Chicane Daytona",
    direction="right",
    scale=2,
    error="Do not group with the second chicane as 'Mulsanne Straight Chicanes' — the two chicanes are ~2 km apart and drivers call them first chicane / second chicane. This right-left chicane is currently represented by a single apex.",
)
lap.corner(
    8,
    driver="Second Chicane",
    official="Chicane Michelin",
    direction="left",
    scale=2,
    error="Do not group with the first chicane as 'Mulsanne Straight Chicanes' — this left-right chicane is currently represented by a single apex.",
)
lap.corner(
    9,
    driver="Mulsanne",
    official="Virage de Mulsanne",
    direction="right",
    scale=1,
    error="scale 2 is too generous — Mulsanne Corner is the slowest point on the lap (~1st/2nd gear, ~100° tightening right), should be scale 1",
)
lap.corner(
    11,
    driver="Indianapolis",
    official="Virage d'Indianapolis",
    complex="Indianapolis",
    direction="left",
    scale=3,
    error="scale 4 slightly high — the left at Indianapolis is a 2nd/3rd-gear banked left, scale 3 fits better; complex should pair with T10",
)
lap.corner(
    12,
    driver="Arnage",
    official="Virage d'Arnage",
    direction="right",
    scale=2,
    error="scale 3 too high — Arnage is a slow 1st/2nd-gear right-hander, scale 2",
)
lap.corner(
    14,
    driver="Porsche Curves",
    official="Virage Porsche",
    complex="Porsche Curves",
    direction="right",
    scale=5,
)
lap.corner(
    15,
    driver="Porsche Curves",
    official="Virage du Pont",
    complex="Porsche Curves",
    direction="left",
    scale=5,
)
lap.corner(
    16,
    driver="Karting",
    official="Virage du Karting",
    complex="Porsche Curves",
    direction="right",
    scale=4,
    error="scale 5 slightly high — Karting is the tightening right where the Porsche Curves slow down, scale 4 fits better",
)
lap.corner(
    17,
    driver="Corvette",
    official="Virage Corvette",
    complex="Porsche Curves",
    direction="left",
    scale=4,
    error="official name should be 'Virage Corvette', not 'Virage du Corvette'; scale 4 rather than 5 — it's the slowest part of the Porsche Curves sequence",
)
lap.corner(
    18,
    driver="Ford Chicane",
    official="Chicane Ford",
    complex="Ford Chicanes",
    direction="left",
    scale=3,
    error="scale 4 slightly high — first Ford chicane is a 2nd/3rd-gear flick, scale 3",
)
lap.corner(
    20,
    driver="Ford Chicane",
    official="Chicane du Raccordement",
    complex="Ford Chicanes",
    direction="left",
    scale=3,
    error="marker 0.98 duplicates T19's marker and the coordinate (0.20753, 47.948222) is essentially identical to T19's (0.207512, 47.948214) — second Ford chicane apex should be further north, near ~0.2078, 47.9489",
)
lap.corner(
    3,
    driver="Dunlop Chicane",
    official="Chicane Dunlop",
    complex="Dunlop Chicane",
    direction="right",
    scale=4,
    error="T3 is the second element of the Dunlop Chicane but was left unnamed and unassigned to the complex",
)
lap.corner(
    5,
    driver="Esses de la Forêt",
    official="Esses de la Forêt",
    complex="Esses de la Forêt",
    direction="right",
    scale=4,
    error="second element of the Esses left unnamed",
)
lap.corner(
    10,
    driver="Indianapolis",
    official="Virage d'Indianapolis",
    complex="Indianapolis",
    direction="right",
    scale=5,
    error="T10 is the fast right entry kink of Indianapolis — it should be named and grouped with T11, not left as an anonymous corner",
)
lap.corner(
    19,
    driver="Ford Chicane",
    official="Chicane Ford",
    complex="Ford Chicanes",
    direction="right",
    scale=3,
    error="T19 is the exit of the first Ford chicane — should be named and assigned to the Ford Chicanes complex, not left anonymous",
)
lap.corner(
    21,
    driver="Ford Chicane",
    official="Virage du Raccordement",
    complex="Ford Chicanes",
    direction="right",
    scale=3,
    error="T21 is the final right of the second Ford chicane (the Raccordement) — should be named and assigned to the Ford Chicanes complex",
)
lap.layer(
    "wec_lm24_slow_zones_2026",
    "hhtiming_cha_microsectors",
    dict(
        cha=dict(
            url="https://s3.us-west-2.amazonaws.com/downloads.hhtiming.com/Championship+Configurations/WEC_LM24_SZ_Cloud.cha",
            filename="wec-lm24-slow-zones-cloud.cha",
        ),
    ),
    dict(
        resource="cha",
        layer_id="slow_zones",
        kind="slow_zones",
        label="WEC Slow Zones",
        series=["wec"],
        coverage="partition",
        source="HH Timing WEC LM24 slow-zone championship configuration",
        items=[
            dict(id="sz1", label="SZ1", driver="SZ1", official="Dunlop", start=0.0, end=0.1),
            dict(
                id="sz2",
                label="SZ2",
                driver="SZ2",
                official="Tertre Rouge",
                start=0.1,
                end=0.16,
            ),
            dict(
                id="sz3",
                label="SZ3",
                driver="SZ3",
                official="Hunaudières (1st chicane)",
                start=0.16,
                end=0.31,
            ),
            dict(
                id="sz4",
                label="SZ4",
                driver="SZ4",
                official="Hunaudières (2nd chicane)",
                start=0.31,
                end=0.46,
            ),
            dict(
                id="sz5",
                label="SZ5",
                driver="SZ5",
                official="Mulsanne corner",
                start=0.46,
                end=0.58,
            ),
            dict(
                id="sz6",
                label="SZ6",
                driver="SZ6",
                official="Indianapolis",
                start=0.58,
                end=0.71,
            ),
            dict(id="sz7", label="SZ7", driver="SZ7", official="Arnage", start=0.71, end=0.78),
            dict(
                id="sz8",
                label="SZ8",
                driver="SZ8",
                official="Porsche Curves",
                start=0.78,
                end=0.93,
            ),
            dict(
                id="sz9",
                label="SZ9",
                driver="SZ9",
                official="Ford Chicanes",
                start=0.93,
                end=1.0,
            ),
        ],
    ),
)
