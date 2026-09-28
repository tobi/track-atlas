"""The track definition language: `tracks/<slug>/track.py`.

Every track is one small Python file that says where its data comes from and
how it is curated:

    from lib.dsl import Track, osm

    t = Track("indianapolis", "Indianapolis Motor Speedway", country="US",
              location=dict(lat=39.795, lon=-86.235, locality="Speedway"),
              osm=osm(bbox=(39.78, -86.25, 39.81, -86.22)),
              lovely={"gp": "iracing/indianapolis-road.json"})
    t.surface()                                   # measure edges (docs/GEOMETRY.md)
    t.bridge("right", 0.100, 0.167, "pit exit merges without a painted line")

    gp = t.layout("gp", "Road Course", length_m=3925, direction="clockwise", lovely="gp")
    gp.corner(1, official="Turn 1", direction="right", scale=3)
    gp.unnamed(0.1515, "left", "artefact", "pit wall shadow")

A track file is plain data plus curation, in lap order and with comments where
the evidence lives. It compiles to the documents the pipeline has always read:
`source()` (the former source.json), `overrides()` (overrides.json) and
`generation()` (generation-config.json); lib/config.py loads them. Calls merge:
a later `corner(n, ...)` updates the fields of an earlier one, so tools may
append curation to the end of a file.
"""
from __future__ import annotations

import copy
from typing import Any

_TRACKS: list["Track"] = []


def osm(bbox, relation: int | None = None, **extra) -> dict:
    """OSM inputs: bbox (south, west, north, east) and optionally the circuit
    relation whose member ways form the centerline."""
    out: dict[str, Any] = {"bbox": list(bbox)}
    if relation is not None:
        out["relation"] = relation
    out.update(extra)
    return out


class Layout:
    """One layout (lap) of a track: its source entry and its curation."""

    def __init__(self, track: "Track", id: str, entry: dict | None):
        self.track, self.id, self.entry = track, id, entry
        self.ov: dict[str, Any] = {}

    # -- corners ---------------------------------------------------------------
    def corner(self, number: int | str, /, **fields) -> "Layout":
        """Curate corner `number` (the Lovely/OSM turn number): official,
        driver, complex, direction, scale, code, marker, error. `None` clears a
        field (e.g. driver=None so the display falls back to the number)."""
        c = self.ov.setdefault("corners", {}).setdefault(str(number), {})
        c.update(fields)
        return self

    def corners(self, items: list[dict]) -> "Layout":
        """Replace the upstream corner list outright (Lovely wrong or absent)."""
        self.ov["replace_corners"] = list(items)
        return self

    def summary(self, text: str) -> "Layout":
        """Curator's summary of what was wrong upstream and what was fixed."""
        self.ov["errors_summary"] = text
        return self

    # -- surface review ----------------------------------------------------------
    def unnamed(self, marker: float, direction: str, verdict: str, note: str) -> "Layout":
        """A reviewed curvature peak that is not an atlas corner (verdict:
        artefact, part_of_corner, unnumbered_bend)."""
        rv = self.ov.setdefault("surface_review", {})
        rv.setdefault("unnamed", []).append(
            {"marker": marker, "direction": direction, "verdict": verdict, "note": note})
        return self

    def unplaceable(self, number: int | str, note: str, /) -> "Layout":
        """A corner the measured geometry cannot place (a straight-line kink)."""
        rv = self.ov.setdefault("surface_review", {})
        rv.setdefault("corners", {})[str(number)] = note
        return self

    # -- generated layers ----------------------------------------------------------
    def layer(self, id: str, tool: str, resources: dict, params: dict, **extra) -> "Layout":
        """A generated point/range layer (skills/layer-tools/SKILL.md)."""
        self.track._layers.append({"id": id, "layout": self.id, "tool": tool,
                                   "resources": resources, "params": params, **extra})
        return self


class Track:
    def __init__(self, slug: str, name: str, *, country: str, location: dict, osm: dict,
                 aka=(), series=(), lovely: dict | None = None, **extra):
        self.slug = slug
        self.src: dict[str, Any] = {"slug": slug, "name": name, "aka": list(aka), "country": country,
                                    "series": list(series), "location": dict(location), "osm": osm}
        if lovely is not None:
            self.src["lovely"] = dict(lovely)
        self.src.update(extra)
        self.src["layouts"] = []
        self._layouts: dict[str, Layout] = {}
        self._every = Layout(self, "*", None)
        self._ov_extra: dict[str, Any] = {}
        self._layers: list[dict] = []
        _TRACKS.append(self)

    def layout(self, id: str, name: str, **fields) -> Layout:
        """Declare a layout: length_m, direction, lovely (key into the track's
        lovely map), start_finish, centerline, pit, aka, active_years, series."""
        entry = {"id": id, "name": name, **fields}
        self.src["layouts"].append(entry)
        lo = self._layouts[id] = Layout(self, id, entry)
        return lo

    def __getitem__(self, id: str) -> Layout:
        return self._every if id == "*" else self._layouts[id]

    @property
    def every_layout(self) -> Layout:
        """Curation shared by every layout (series variants on one geometry)."""
        return self._every

    def note(self, text: str) -> "Track":
        self._ov_extra["_comment"] = text
        return self

    # -- measured surface ------------------------------------------------------------
    def surface(self, **cfg) -> "Track":
        """Opt in to the measured surface; `imagery`/`lidar` pin a source."""
        self.src.setdefault("surface", {}).update(cfg)
        return self

    def bridge(self, side: str, start: float, end: float, note: str) -> "Track":
        """Treat the `side` edge between lap fractions start..end (on the OSM
        seed) as unseen: the imagery edge follows the wrong surface there."""
        s = self.src.setdefault("surface", {})
        s.setdefault("bridge", []).append({"side": side, "from": start, "to": end, "note": note})
        return self

    # -- compiled documents -------------------------------------------------------------
    def source(self) -> dict:
        return copy.deepcopy(self.src)

    def overrides(self) -> dict:
        out = copy.deepcopy(self._ov_extra)
        if self._every.ov:
            out["*"] = copy.deepcopy(self._every.ov)
        for lid, lo in self._layouts.items():
            if lo.ov:
                out[lid] = copy.deepcopy(lo.ov)
        return out

    def generation(self) -> dict | None:
        return {"layers": copy.deepcopy(self._layers)} if self._layers else None


def _lit(v) -> str:
    import json
    return json.dumps(v, ensure_ascii=False) if isinstance(v, str) else repr(v)


def append_curation(path, new: dict, header: str) -> int:
    """Append curation ({layout: {corners: {n: fields}, errors_summary}}) to a
    track.py as `t[layout].corner(...)` calls; later calls win per field."""
    lines = ["", f"# {header}"]
    for lid, block in new.items():
        for key, val in block.items():
            if key == "corners":
                for n, fields in val.items():
                    kw = ", ".join(f"{k}={_lit(v)}" for k, v in fields.items() if v is not None)
                    n = int(n) if str(n).isdigit() else _lit(n)
                    lines.append(f"t[{_lit(lid)}].corner({n}{', ' if kw else ''}{kw})")
            elif key == "errors_summary":
                lines.append(f"t[{_lit(lid)}].summary({_lit(val)})")
            else:
                raise ValueError(f"cannot append {key!r} curation")
    with open(path, "a") as f:
        f.write("\n".join(lines) + "\n")
    load(path)   # the file must still compile
    return len(lines) - 2


def load(path) -> Track:
    """Execute a track.py and return the Track it defines."""
    import runpy
    del _TRACKS[:]
    runpy.run_path(str(path), run_name="track")
    if len(_TRACKS) != 1:
        raise RuntimeError(f"{path}: expected exactly one Track, got {len(_TRACKS)}")
    return _TRACKS.pop()
