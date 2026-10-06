from lib.dsl import Track, osm

t = Track(
    "watkins-glen",
    "Watkins Glen International",
    aka=["The Glen"],
    country="US",
    series=["imsa"],
    location=dict(
        lat=42.3369,
        lon=-76.9272,
        locality="Watkins Glen, New York",
        region="New York",
        timezone="America/New_York",
    ),
    external_ids=dict(imsa_data="watkins-glen"),
    osm=osm([42.3069, -76.9572, 42.3669, -76.8972], relation=4872324),
    lovely=dict(gp="iracing/watkinsglen-2021-fullcourse.json"),
)
t.surface()

# -- gp --------------------------------------------------------------------
lap = t.layout(
    "gp",
    "Full Course (Boot)",
    length_m=5435,
    direction="clockwise",
    lovely="gp",
    centerline="relation",
)
lap.summary(
    "iRacing/Lovely source collapses the Esses into one turn; this replacement expands Watkins Glen to the driver/common 11-turn full-course numbering.",
)
lap.corners([
    dict(
        number=1,
        driver="The 90",
        official="The Ninety",
        marker=0.066,
        direction="right",
        scale=2,
    ),
    dict(
        number=2,
        driver="Esses",
        official="The Esses",
        marker=0.1686,
        match_osm=False,
        direction="left",
        scale=4,
        complex="Esses",
    ),
    dict(
        number=3,
        driver="Esses",
        official="The Esses",
        marker=0.2066,
        match_osm=False,
        direction="right",
        scale=4,
        complex="Esses",
    ),
    dict(
        number=4,
        driver="Bus Stop",
        official="Inner Loop",
        marker=0.3507,
        direction="right",
        scale=2,
    ),
    dict(
        number=5,
        driver="Carousel",
        official="Outer Loop",
        marker=0.428,
        direction="right",
        scale=3,
    ),
    dict(
        number=6,
        driver="Chute",
        official="The Chute",
        marker=0.515,
        direction="left",
        scale=4,
    ),
    dict(
        number=7,
        driver="Toe",
        official="Toe of the Boot",
        marker=0.6085,
        direction="right",
        scale=2,
    ),
    dict(
        number=8,
        driver="Heel",
        official="Heel of the Boot",
        marker=0.7315,
        direction="right",
        scale=3,
    ),
    dict(number=9, driver="Turn 9", official="Turn 9", marker=0.8005, direction="left", scale=2),
    dict(
        number=10,
        driver="Turn 10",
        official="Turn 10",
        marker=0.8695,
        direction="left",
        scale=2,
    ),
    dict(
        number=11,
        driver="Turn 11",
        official="Turn 11",
        marker=0.9228,
        direction="right",
        scale=4,
    ),
])
lap.unnamed(
    0.1177,
    "right",
    "artefact",
    "38 m lobe in a stretch where both edges are bridged (seen 0.3/0.2); OSM centerline R204 here",
)
lap.unnamed(
    0.3603,
    "left",
    "part_of_corner",
    "T4 Inner Loop (Bus Stop) chicane R-L-L-R, OSM Inner Loop way 0.3482-0.3924: second element",
)
lap.unnamed(0.3749, "left", "part_of_corner", "T4 Inner Loop chicane: third element")
lap.unnamed(0.3848, "right", "part_of_corner", "T4 Inner Loop chicane: exit right")
lap.unnamed(
    0.409,
    "right",
    "part_of_corner",
    "T5 Outer Loop first apex, OSM Outer Loop way 0.3924-0.4588",
)
lap.unnamed(0.4438, "right", "part_of_corner", "T5 Outer Loop late apex")
lap.unnamed(
    0.5199,
    "left",
    "part_of_corner",
    "second apex of T6 The Chute, OSM way 0.4970-0.5390",
)
lap.unnamed(
    0.7553,
    "right",
    "artefact",
    "23 m, -11 deg lobe with neither edge seen, right after the T8 Heel apex",
)
lap.unnamed(
    0.9621,
    "left",
    "artefact",
    "+-20 deg L/R pair on the front straight where the pit lane rejoins (OSM pit way 0.9509-0.9725); left edge unseen, OSM centerline straight (R10000)",
)
lap.unnamed(0.9663, "right", "artefact", "other half of the pit-merge pair")
lap.layer(
    "imsa_timing_sectors_2026",
    "imsa_timing_pdf",
    dict(
        pdf=dict(
            url="https://imsa.results.alkamelcloud.com/Results_NoticeBoard/26-2026/14_Watkins%20Glen%20International/03_Timing%203%20Sector%20Map.pdf",
            filename="imsa-2026-timing-3-sector-map.pdf",
        ),
    ),
    dict(
        resource="pdf",
        layer_id="timing_sectors",
        kind="timing_sectors",
        label="Timing Sectors",
        series=["imsa"],
        coverage="partition",
        count=3,
        item_prefix="s",
        item_label_prefix="S",
        source="IMSA / Al Kamel Timing 3 Sector Map",
        segment_refs=[["FL", "i1"], ["i1", "i2"], ["i2", "FL"]],
    ),
)
lap.layer(
    "imsa_microsectors_2026",
    "imsa_timing_pdf",
    dict(
        pdf=dict(
            url="https://imsa.results.alkamelcloud.com/Results_NoticeBoard/26-2026/14_Watkins%20Glen%20International/03_Timing%20All%20Sections%20Map.pdf",
            filename="imsa-2026-timing-all-sections-map.pdf",
        ),
    ),
    dict(
        resource="pdf",
        layer_id="imsa_microsectors",
        kind="microsectors",
        label="IMSA Microsectors",
        series=["imsa"],
        coverage="partition",
        count=11,
        item_prefix="ms",
        item_label_prefix="MS",
        source="IMSA / Al Kamel Timing All Sections Map",
        segment_refs=[
            ["T1", "T2"],
            ["T2", "T3"],
            ["T3", "T4"],
            ["T4", "T5"],
            ["T5", "T6"],
            ["T6", "T7"],
            ["T7", "T8"],
            ["T8", "T9"],
            ["T9", "TA"],
            ["TA", "TB"],
            ["TB", "T1"],
        ],
    ),
)
