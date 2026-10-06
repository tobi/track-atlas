/** Local-only adapter for the already-audited Road Atlanta NPZ extracts.
 * No private data paths or telemetry are compiled into the public app. */
import { unzipSync } from "fflate";
import { readFile, mkdir, stat } from "node:fs/promises";
import { resolve } from "node:path";
import { createHash } from "node:crypto";
import {
  loadTrack,
  cumulative,
  metricFrame,
  openRing,
  project,
  type XY,
} from "../../site/sim/track";
import { LMP2, MODELS, solve, interpolate } from "../../site/sim/physics";
import {
  metrics,
  type Reference,
  parseReference,
} from "../../site/sim/reference";
import { calibrate } from "../../site/sim/calibrate";
const base = process.argv[2],
  out = resolve(process.argv[3] || ".private");
if (!base)
  throw new Error(
    "Usage: bun scripts/sim/correlate.ts <existing-analysis-directory> [output-directory]",
  );
await mkdir(out, { recursive: true });
function npz(bytes: Uint8Array) {
  const files = unzipSync(bytes),
    arrays: Record<string, number[]> = {};
  for (const [name, bytes] of Object.entries(files)) {
    if (!name.endsWith(".npy")) continue;
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength),
      major = bytes[6];
    const len = major === 1 ? view.getUint16(8, true) : view.getUint32(8, true),
      start = major === 1 ? 10 : 12;
    const header = new TextDecoder().decode(bytes.slice(start, start + len));
    if (!header.includes("'<f8'") || header.includes("True"))
      throw new Error("Expected little-endian float64 NPY");
    const data: number[] = [];
    for (let i = start + len; i + 8 <= bytes.length; i += 8)
      data.push(view.getFloat64(i, true));
    arrays[name.slice(0, -4)] = data;
  }
  return arrays;
}
const root = resolve(import.meta.dir, "../..");
const track = loadTrack(
  await Bun.file(`${root}/tracks/road-atlanta/raw/layers/gp.geojson`).json(),
  await Bun.file(
    `${root}/tracks/road-atlanta/raw/layers/gp.surface.geojson`,
  ).json(),
);
const all = await Bun.file(`${base}/analyzed-laps.json`).json();
const selected = all.filter(
  (r: any) => r.year === 2026 && ["FP1", "FP2"].includes(r.session),
);
const training = new Set(
  selected
    .filter((r: any) => r.session === "FP1")
    .sort((a: any, b: any) => a.duration_s - b.duration_s)
    .slice(0, 3)
    .map((r: any) => r.trace_file),
);
const geometry = await Bun.file(`${base}/geometry.json`).json();
const coords = geometry.centerline as XY[],
  origin = [-83.8135175, 34.1500048];
const oldScale = [111320 * Math.cos((origin[1] * Math.PI) / 180), 111320];
const old = openRing(
  coords.map((p) => [
    (p[0] - origin[0]) * oldScale[0],
    (p[1] - origin[1]) * oldScale[1],
  ]),
);
const oldCum = cumulative(old),
  oldLength = oldCum.at(-1)!;
const sf = geometry.points.find((p: any) => p.id === "start_finish").location;
const oldS0 = project(
  [(sf[0] - origin[0]) * oldScale[0], (sf[1] - origin[1]) * oldScale[1]],
  old,
  oldCum,
).s;
const newFrame = metricFrame(coords[0][0], coords[0][1]);
const ox = [...old.map((p) => p[0]), old[0][0]],
  oy = [...old.map((p) => p[1]), old[0][1]];
function remap(s: number) {
  const oldS = (s + oldS0) % oldLength,
    x = interpolate(oldCum, ox, oldS),
    y = interpolate(oldCum, oy, oldS);
  return project(
    newFrame([origin[0] + x / oldScale[0], origin[1] + y / oldScale[1]]),
    track.outline,
  ).s;
}
const refs: Reference[] = [];
const provenance = [];
for (const row of selected) {
  const bytes = await readFile(`${base}/${row.trace_file}`),
    a = npz(bytes),
    n = a.distance_m.length;
  const station = a.distance_m.map(remap);
  station[0] = 0;
  station[n - 1] = track.road.trackLength;
  for (let i = 1; i < n; i++)
    if (station[i] <= station[i - 1]) throw new Error("Invalid remapping");
  const ref: Reference = {
    name: `2026 ${row.session} ${row.label} · ${row.trace_file.replace(".npz", "")}`,
    source: row.path,
    track: "road-atlanta",
    split: training.has(row.trace_file)
      ? "training"
      : row.session === "FP2"
        ? "validation"
        : "unused",
    gps_p95_m: row.gps_p95_distance_m,
    distance_m: station,
    speed_kmh: a.speed_kmh,
    time_s: a.time_s,
    brake: a.brake,
    throttle: a.throttle_normalized,
  };
  refs.push(ref);
  provenance.push({
    trace: row.trace_file,
    sha256: createHash("sha256").update(bytes).digest("hex"),
    source: row.path,
    sourceLap: row.label,
    nativeDuration: row.native_duration_s,
    commonDuration: row.duration_s,
    canOffset: row.can_time_offset_s,
    gpsP95: row.gps_p95_distance_m,
    split: ref.split,
  });
}
parseReference(JSON.stringify(refs));
const fit = calibrate(track.road, LMP2, refs, (p) => console.log("fit", p));
const runs = MODELS.map((m) => solve(track.road, fit.car, m));
const comparisons = refs.map((ref) => ({
  name: ref.name,
  source: ref.source,
  split: ref.split,
  gpsP95: ref.gps_p95_m,
  metrics: runs.map((run) => ({
    model: run.model,
    ...metrics(track.road, run, ref),
  })),
}));
const baseline = MODELS.map((m) => solve(track.road, LMP2, m));
const results = {
  track: "road-atlanta",
  geometryLength: track.road.trackLength,
  lineLength: track.road.length,
  selection:
    "Three fastest GPS-qualified 2026 FP1 laps for training. All five GPS-qualified FP2 laps held out. No parameter tuning uses FP2.",
  alignment:
    "GPS projected onto atlas; remapped from archived equirectangular station frame into current metric frame; no speed or time scaling, no fitted station offset.",
  fit,
  provenance,
  baseline: baseline.map((r) => ({ model: r.model, lap: r.lap })),
  runs: runs.map((r) => ({
    model: r.model,
    lap: r.lap,
    residual: r.residual,
    iterations: r.iterations,
  })),
  comparisons,
};
await Bun.write(`${out}/correlation.json`, JSON.stringify(results, null, 2));
await Bun.write(
  `${out}/reference-laps.json`,
  JSON.stringify({ schema: 1, car: fit.car, laps: refs }),
);
console.log(
  JSON.stringify(
    {
      fit,
      baseline: results.baseline,
      runs: results.runs,
      validation: comparisons.filter((r) => r.split === "validation"),
    },
    null,
    2,
  ),
);
