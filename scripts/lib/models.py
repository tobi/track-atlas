"""Pydantic models for a track-atlas track.json — the single source of truth.

The atlas is layout-first: a physical track/facility has one or more racing
layouts, and every spatial annotation belongs to a layout. Layout annotations
come in two shapes:

  * point_layers: discrete lap locations (corner apexes, start/finish, pit in/out,
    marshal posts, timing loops)
  * range_layers: lap intervals (timing sectors, IMSA microsectors, corner
    phases, complexes, slow zones)

These models define the schema: `scripts/build_schema.py` emits
`schema/track.schema.json` from them, and `scripts/verify.py` validates every
track against them.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import (
    BaseModel, ConfigDict, Field, StringConstraints,
    field_validator, model_validator,
)

from .naming import DEFAULT_LAYER, MANDATORY_LAYERS

# --- scalar / constrained types ----------------------------------------------
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
LayerCode = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]
LayerId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]
ItemId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]*$")]
LonLat = Annotated[
    list[float],
    Field(min_length=2, max_length=2,
          description="[longitude, latitude] in GeoJSON axis order (WGS84)."),
]
Fraction = Annotated[float, Field(ge=0.0, le=1.0,
                                  description="Lap fraction in [0,1].")]


class Strict(BaseModel):
    """Base: reject unknown keys so typos surface instead of silently passing."""
    model_config = ConfigDict(extra="forbid")


# --- leaf objects ------------------------------------------------------------
class Location(Strict):
    lat: float
    lon: float
    locality: Optional[str] = None
    region: Optional[str] = None
    timezone: Optional[str] = None


class LabelLayer(Strict):
    """Registry entry describing one label/name layer for clients."""
    label: Optional[str] = Field(None, description="Human-readable layer name for UI.")
    description: Optional[str] = None


class Geometry(Strict):
    centerline: str = Field(description="Path (relative to track dir) to the layout's GeoJSON centerline/layer file.")
    surface: Optional[str] = Field(
        None, description="Path (relative to the track's raw dir) to the layout's surface GeoJSON: edges, "
                          "midline, surface polygon, pit lane, crossing lines and apexes (docs/GEOMETRY.md).")
    crs: str = "EPSG:4326"
    basis: Literal["centerline", "midline"] = Field(
        "centerline", description="What `centerline` is and what every lap fraction is measured along: "
                                  "'midline' = the measured surface midline (docs/GEOMETRY.md), "
                                  "'centerline' = the OSM-derived line (unmeasured layouts).")


# --- surface geometry (docs/GEOMETRY.md) ---------------------------------------
LineAcross = Annotated[
    list[LonLat],
    Field(min_length=2, max_length=2,
          description="A 2-point line across the track: [point on the left edge, point on the right edge], "
                      "left/right in the driving direction."),
]


class Quality(Strict):
    """Provenance and estimated positional accuracy of one geometric feature."""
    source: str = Field(
        pattern=r"^[a-z0-9][a-z0-9-]*$",
        description="What the position was measured from: an imagery source id (naip, ct-2023, indiana-2025, "
                    "... see layout.surface.sources.imagery), osm (OpenStreetMap trace), survey (a surveyed "
                    "dataset), or derived (computed from other features).")
    accuracy_m: float = Field(ge=0, description="Estimated absolute horizontal accuracy in metres (95%), in the "
                                                "atlas frame (layout.surface.position): the measurement's position "
                                                "CE95 combined with this feature's relative accuracy.")
    relative_accuracy_m: Optional[float] = Field(
        None, ge=0, description="Estimated accuracy relative to the rest of this layout's geometry, in metres "
                                "(what matters for widths, lines and apexes against the edges).")
    measured: bool = Field(description="True when the feature rests on edges actually seen in the imagery; "
                                       "false when it was bridged across an unseen span (shadow, bridge, "
                                       "run-off) or taken from a trace.")
    date: Optional[str] = Field(None, description="Acquisition date of the source (ISO date).")
    note: Optional[str] = None


class Crossing(Strict):
    """A line across the track at one lap position (edge to edge)."""
    marker: Fraction
    line: LineAcross
    width_m: float = Field(ge=0, description="Track width along the line.")
    quality: Quality


class Apex(Strict):
    """The geometric apex: the point of greatest curvature on the inside edge."""
    marker: Fraction
    location: LonLat
    edge: Literal["left", "right"] = Field(description="The inside edge the apex lies on.")
    quality: Quality


class Placement(Strict):
    """How a corner's entry/apex/exit were placed on the measured surface."""
    basis: Literal["curvature", "none"] = Field(
        description="curvature: matched to a curvature peak of the measured midline; none: no peak near the "
                    "legacy marker, so the corner has no entry/apex/exit.")
    shape: Optional[Literal["corner", "kink"]] = Field(None, description="kink when the peak radius exceeds 250 m.")
    direction: Optional[Literal["left", "right"]] = Field(None, description="Turning direction measured from the geometry.")
    declared_direction: Optional[Literal["left", "right"]] = Field(
        None, description="Present only when the curated direction disagrees with the measured one.")
    radius_m: Optional[float] = Field(None, description="Minimum radius of the midline (8 m smoothing).")
    marker_offset_m: Optional[float] = Field(None, description="Curvature peak minus the legacy marker, in metres along the lap.")
    note: Optional[str] = None


class PointItem(Strict):
    """A discrete annotation on a layout lap coordinate.

    The corners layer uses number/code/direction/scale/labels. Layout control
    points such as start_finish, pit_entry and pit_exit usually use label,
    marker and location.
    """
    id: ItemId
    label: Optional[str] = None
    marker: Optional[Fraction] = None
    location: Optional[LonLat] = None
    location_source: Optional[Literal["osm-way", "centerline", "midline", "manual"]] = None
    labels: dict[LayerCode, str] = Field(default_factory=dict)
    number: Optional[int] = None
    code: Optional[str] = None
    direction: Optional[Literal["left", "right"]] = None
    line: Optional[Crossing] = Field(None, description="Layout points (start/finish, pit entry/exit): the line across the track at the marker.")
    entry: Optional[Crossing] = Field(None, description="Corners: the geometric turn-in line (curvature onset).")
    apex: Optional[Apex] = Field(None, description="Corners: the geometric apex on the inside edge.")
    exit: Optional[Crossing] = Field(None, description="Corners: the geometric track-out line (curvature release).")
    placement: Optional[Placement] = None
    scale: Optional[int] = Field(None, ge=1, le=6,
                                description="Severity 1-6: 1=Hairpin, 2=Slow, 3=Medium, 4=Fast, 5=Very fast, 6=Kink.")


class PointLayer(Strict):
    id: LayerId
    kind: LayerId
    label: str
    description: Optional[str] = None
    series: list[str] = []
    items: list[PointItem] = []

    @model_validator(mode="after")
    def _unique_items(self) -> "PointLayer":
        ids = [i.id for i in self.items]
        dupes = {x for x in ids if ids.count(x) > 1}
        if dupes:
            raise ValueError(f"point layer '{self.id}' duplicate item ids: {sorted(dupes)}")
        if self.kind == "corners":
            nums = [i.number for i in self.items]
            if any(n is None for n in nums):
                raise ValueError("corners point layer items must have number")
            nums_int = [int(n) for n in nums if n is not None]
            if sorted(nums_int) != list(range(1, len(nums_int) + 1)):
                raise ValueError(f"corner numbers not sequential 1..{len(nums_int)}: {sorted(nums_int)}")
            codes = [i.code for i in self.items]
            if any(c in (None, "") for c in codes):
                raise ValueError("corners point layer items must have code")
            dup_codes = {x for x in codes if codes.count(x) > 1}
            if dup_codes:
                raise ValueError(f"duplicate corner codes: {sorted(dup_codes)}")
            missing_numbered = [i.id for i in self.items if "numbered" not in i.labels]
            if missing_numbered:
                raise ValueError(f"corner items missing numbered label: {missing_numbered}")
        return self


class RangePoint(Strict):
    """A point that lives inside a range item.

    Use this when a range has meaningful internal landmarks: the apex inside a
    corner range, timing-loop lines inside a sector, a speed trap inside a slow
    zone. `point_ref` links to a point item when one exists; `marker`/`location`
    let generated tools embed a lightweight point directly in the range.
    """
    id: ItemId
    role: LayerId = Field(description="Semantic role inside the range, e.g. apex, entry_loop, exit_loop, speed_trap.")
    label: Optional[str] = None
    marker: Optional[Fraction] = None
    location: Optional[LonLat] = None
    point_ref: Optional[ItemId] = Field(None, description="Point-layer item this nested range point references, when available.")


class RangeItem(Strict):
    """A lap interval annotation."""
    id: ItemId
    label: Optional[str] = None
    start: Fraction
    end: Fraction
    labels: dict[LayerCode, str] = Field(default_factory=dict)
    anchor: Optional[ItemId] = Field(None, description="Primary point item this range is derived from, e.g. a corner apex id.")
    members: list[ItemId] = Field(default=[], description="Point items contained in this range, e.g. corners in a complex.")
    points: list[RangePoint] = Field(default=[], description="Ordered point landmarks inside this range, e.g. the apex inside a corner range.")
    entry_ref: Optional[str] = Field(None, description="Upstream timing loop / line where the range starts, when known.")
    exit_ref: Optional[str] = Field(None, description="Upstream timing loop / line where the range ends, when known.")
    length_m: Optional[float] = Field(None, description="Official/source length of this range in metres, when known.")
    start_line: Optional[Crossing] = Field(None, description="The line across the track at `start`.")
    end_line: Optional[Crossing] = Field(None, description="The line across the track at `end`.")
    entry: Optional[Crossing] = Field(None, description="Complexes: the geometric entry line of the first member corner.")
    exit: Optional[Crossing] = Field(None, description="Complexes: the geometric exit line of the last member corner.")

    @model_validator(mode="after")
    def _nested_points_inside_range(self) -> "RangeItem":
        for p in self.points:
            if p.marker is not None and not (self.start <= p.marker <= self.end):
                raise ValueError(f"range point '{p.id}' marker {p.marker} outside range {self.start}→{self.end}")
        return self


class RangeLayer(Strict):
    id: LayerId
    kind: LayerId
    label: str
    description: Optional[str] = None
    series: list[str] = []
    coverage: Optional[Literal["partition", "partial", "overlap"]] = None
    generated: bool = False
    provenance: Optional[dict[str, Any]] = None
    items: list[RangeItem] = []

    @model_validator(mode="after")
    def _range_invariants(self) -> "RangeLayer":
        ids = [i.id for i in self.items]
        dupes = {x for x in ids if ids.count(x) > 1}
        if dupes:
            raise ValueError(f"range layer '{self.id}' duplicate item ids: {sorted(dupes)}")
        for item in self.items:
            if not item.start < item.end:
                raise ValueError(f"range '{item.id}' start {item.start} must be < end {item.end}")
        if self.coverage == "partition" and self.items:
            ordered = sorted(self.items, key=lambda i: i.start)
            if abs(ordered[0].start - 0.0) > 1e-6 or abs(ordered[-1].end - 1.0) > 1e-6:
                raise ValueError(f"partition layer '{self.id}' must cover 0.0→1.0")
            for a, b in zip(ordered, ordered[1:]):
                if abs(a.end - b.start) > 1e-6:
                    raise ValueError(f"partition layer '{self.id}' has gap/overlap between {a.id} and {b.id}")
        return self


# --- layout ------------------------------------------------------------------
class Percentiles(Strict):
    p05: float
    median: float
    p95: float


class SeenFraction(Strict):
    left: float = Field(ge=0, le=1)
    right: float = Field(ge=0, le=1)
    both: float = Field(ge=0, le=1)


class UnnamedCorner(Strict):
    marker: Fraction
    direction: Literal["left", "right"]
    radius_m: float


class PositionReference(Strict):
    kind: Literal["lidar", "imagery"]
    name: str
    ce95_m: float
    basis: str
    stated: bool = Field(description="False when the reference's accuracy is an assumption (not stated by its producer).")


class Position(Strict):
    """Absolute positioning of a surface measurement (lib/position.py)."""
    frame: str = Field(description="Coordinate frame of every published coordinate: WGS 84 (G2139) ~ ITRF2014.")
    epoch: float = Field(description="Coordinate epoch (decimal year); plate motion moves ground a few cm/yr in this frame.")
    source_frame: str = Field(description="Frame of the position reference, stepped to `frame`: NAD83(2011) for 3DEP lidar, WGS84-service for imagery served in Web Mercator.")
    imagery_frame: Optional[str] = Field(None, description="Frame the imagery was served in.")
    imagery_frame_basis: Optional[str] = Field(None, description="How the imagery's frame was established (inferred from lidar, or catalog default).")
    datum_shift_m: dict[str, float] = Field(description="east/north metres added for source_frame -> frame.")
    registration_shift_m: dict[str, float] = Field(description="east/north metres added to move the imagery onto the reference.")
    applied_shift_m: dict[str, float] = Field(description="Sum of the two, as applied to the traced geometry.")
    reference: PositionReference
    budget_ce95_m: dict[str, float] = Field(description="95% horizontal error budget: reference, registration, datum, total.")
    imagery_stated_ce95_m: Optional[float] = None
    registration_model: str = Field(description="How the registration term of the budget was derived.")
    checks: list[dict[str, Any]] = Field(default=[], description="Registration against every lidar survey and their mutual agreement.")


class Surface(Strict):
    """Summary of the layout's measured surface (the geometry is in `geometry.surface`)."""
    file: str
    method: str = Field(description="Measurement method and version, e.g. edges/2.")
    measured_at: str
    lap_length_m: float = Field(description="Lap length along the measured midline.")
    width_m: Percentiles
    seen_fraction: SeenFraction = Field(description="Share of the lap where each edge was actually seen in the imagery.")
    unseen_spans: Optional[dict[str, list[list[float]]]] = Field(
        None, description="Per edge (left/right), the lap-fraction spans where the edge was not seen and is bridged.")
    relative_precision_m: float
    absolute_accuracy_ce95_m: float = Field(
        description="Absolute horizontal accuracy (95%) of the measured geometry in the atlas frame: reference, "
                    "registration and datum step combined (budget in `position`).")
    position: Optional[Position] = Field(
        None, description="How the absolute position was established: frame and epoch, the reference it was "
                          "registered to, the shifts applied, the error budget and independent checks.")
    selection: Optional[dict[str, Any]] = Field(
        None, description="Imagery sources tried for this measurement, their scores and which was chosen.")
    unnamed_corners: list[UnnamedCorner] = Field(
        default=[], description="Curvature peaks tighter than 80 m that no atlas corner claimed: candidates for curation.")
    sources: dict[str, Any] = Field(description="imagery (id, licence, tiles), reference (lidar surveys) and seed.")


class Layout(Strict):
    id: Slug
    name: str
    aka: list[str] = []
    series: list[str] = Field(default=[], description="Series that use THIS layout/configuration.")
    length_m: Optional[float] = Field(None, description="Lap length in metres.")
    direction: Optional[Literal["clockwise", "anticlockwise"]] = None
    active_years: Optional[str] = Field(None, description="Free-form, e.g. '2018-' or '1972,1979-1989'.")
    geometry: Geometry
    label_default: str = Field(
        DEFAULT_LAYER,
        description="Label layer code used as the default display name. Resolution is two steps: item.labels[label_default] if present, else item.labels.numbered.")
    point_layers: list[PointLayer] = []
    range_layers: list[RangeLayer] = []
    surface: Optional[Surface] = None

    @model_validator(mode="after")
    def _layer_ids_unique(self) -> "Layout":
        for attr in ("point_layers", "range_layers"):
            ids = [layer.id for layer in getattr(self, attr)]
            dupes = {x for x in ids if ids.count(x) > 1}
            if dupes:
                raise ValueError(f"layout '{self.id}' duplicate {attr} ids: {sorted(dupes)}")
        return self


# --- top level ---------------------------------------------------------------
class Provenance(BaseModel):
    model_config = ConfigDict(extra="allow")
    generated_at: Optional[str] = None
    sources: Optional[list[dict]] = None
    corner_match: Optional[dict] = None


class Track(Strict):
    slug: Slug
    name: str = Field(description="Official circuit/facility name.")
    aka: list[str] = []
    country: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 code.")
    location: Location
    wikidata: Optional[Annotated[str, StringConstraints(pattern=r"^Q[0-9]+$")]] = None
    series: list[str] = []
    external_ids: dict[str, str] = {}
    label_layers: dict[LayerCode, LabelLayer] = Field(
        description="Registry of label/name layers. Keys are label codes used by item.labels. 'numbered' and 'official' are mandatory; 'driver' is the usual default.")
    layouts: Annotated[list[Layout], Field(min_length=1)]
    provenance: Optional[Provenance] = None

    @field_validator("label_layers")
    @classmethod
    def _mandatory_layers(cls, v: dict) -> dict:
        missing = [m for m in MANDATORY_LAYERS if m not in v]
        if missing:
            raise ValueError(f"label_layers must declare mandatory layer(s): {missing}")
        return v

    @model_validator(mode="after")
    def _layer_references(self) -> "Track":
        declared = set(self.label_layers)
        for lo in self.layouts:
            if lo.label_default not in declared:
                raise ValueError(
                    f"layout '{lo.id}'.label_default '{lo.label_default}' is not a declared label layer {sorted(declared)}")
            point_ids = {item.id for layer in lo.point_layers for item in layer.items}
            for layer in lo.point_layers:
                for item in layer.items:
                    undeclared = set(item.labels) - declared
                    if undeclared:
                        raise ValueError(
                            f"layout '{lo.id}' point layer '{layer.id}' item '{item.id}' uses undeclared label layer(s) {sorted(undeclared)}")
            for layer in lo.range_layers:
                for item in layer.items:
                    undeclared = set(item.labels) - declared
                    if undeclared:
                        raise ValueError(
                            f"layout '{lo.id}' range layer '{layer.id}' item '{item.id}' uses undeclared label layer(s) {sorted(undeclared)}")
                    refs = ([item.anchor] if item.anchor else []) + item.members + [p.point_ref for p in item.points if p.point_ref]
                    missing = [ref for ref in refs if ref not in point_ids]
                    if missing:
                        raise ValueError(
                            f"layout '{lo.id}' range layer '{layer.id}' item '{item.id}' references missing point item(s) {missing}")
        return self
