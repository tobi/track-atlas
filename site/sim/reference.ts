import { interpolate, type Road, type Run } from "./physics";
export interface Reference {
  name: string;
  source?: string;
  track: "road-atlanta";
  distance_m: number[];
  speed_kmh: number[];
  time_s: number[];
  brake?: number[];
  throttle?: number[];
  gps_p95_m?: number;
  split?: string;
}
export interface Metrics {
  r: number;
  rmse: number;
  mae: number;
  bias: number;
  lapDelta: number;
  referenceLap: number;
}
export function parseReference(text: string): Reference[] {
  let parsed: any;
  try {
    parsed = JSON.parse(text);
  } catch {
    const rows = text
      .trim()
      .split(/\r?\n/)
      .map((l) => l.split(",").map((x) => x.trim()));
    const keys = rows.shift() || [];
    const index = (k: string) => keys.indexOf(k);
    if (["distance_m", "speed_kmh", "time_s"].some((k) => index(k) < 0))
      throw new Error(
        "Use JSON or CSV with distance_m,speed_kmh,time_s columns.",
      );
    parsed = {
      name: "Imported lap",
      track: "road-atlanta",
      ...Object.fromEntries(
        ["distance_m", "speed_kmh", "time_s"].map((k) => [
          k,
          rows.map((r) => Number(r[index(k)])),
        ]),
      ),
    };
  }
  const refs = Array.isArray(parsed) ? parsed : parsed.laps || [parsed];
  if (!refs.length || refs.length > 200)
    throw new Error("Load between 1 and 200 laps.");
  for (const r of refs) {
    const n = r.distance_m?.length;
    if (r.track !== "road-atlanta")
      throw new Error("Reference must identify track: road-atlanta.");
    if (
      typeof r.name !== "string" ||
      !n ||
      n < 20 ||
      n > 100000 ||
      ["distance_m", "speed_kmh", "time_s"].some(
        (k) =>
          !Array.isArray(r[k]) ||
          r[k].length !== n ||
          r[k].some((x: any) => typeof x !== "number" || !Number.isFinite(x)),
      )
    )
      throw new Error(
        "Reference arrays must contain equally sized finite numeric samples.",
      );
    if (
      Math.abs(r.distance_m[0]) > 2 ||
      r.distance_m[n - 1] < 3800 ||
      r.distance_m[n - 1] > 4300 ||
      r.time_s[0] !== 0 ||
      r.time_s[n - 1] < 40 ||
      r.time_s[n - 1] > 300 ||
      r.speed_kmh.some((v: number) => v < 1 || v > 400)
    )
      throw new Error(
        "Expected one complete Road Atlanta lap, starting at distance/time zero.",
      );
    for (let i = 1; i < n; i++)
      if (
        r.distance_m[i] <= r.distance_m[i - 1] ||
        r.time_s[i] <= r.time_s[i - 1]
      )
        throw new Error("Reference distance and time must increase strictly.");
    for (const k of ["brake", "throttle"])
      if (
        r[k] &&
        (!Array.isArray(r[k]) ||
          r[k].length !== n ||
          r[k].some((x: any) => !Number.isFinite(x)))
      )
        throw new Error(`Invalid ${k} samples`);
  }
  return refs;
}
export function metrics(
  road: Road,
  run: Run,
  ref: Reference,
  offset = 0,
): Metrics {
  const s = [...road.station, road.trackLength],
    v = [...run.v, run.v[0]].map((x) => x * 3.6);
  const xs: number[] = [],
    ys: number[] = [];
  for (let i = 0; i < ref.distance_m.length - 1; i++) {
    const d = ref.distance_m[i] + offset;
    if (d < 0 || d > road.trackLength) continue;
    xs.push(interpolate(s, v, d));
    ys.push(ref.speed_kmh[i]);
  }
  const mean = (a: number[]) => a.reduce((a, b) => a + b, 0) / a.length;
  const mx = mean(xs),
    my = mean(ys),
    err = xs.map((x, i) => x - ys[i]);
  let cov = 0,
    vx = 0,
    vy = 0;
  xs.forEach((x, i) => {
    cov += (x - mx) * (ys[i] - my);
    vx += (x - mx) ** 2;
    vy += (ys[i] - my) ** 2;
  });
  return {
    r: cov / Math.sqrt(vx * vy || 1),
    rmse: Math.sqrt(mean(err.map((x) => x * x))),
    mae: mean(err.map(Math.abs)),
    bias: mean(err),
    lapDelta: run.lap - ref.time_s.at(-1)!,
    referenceLap: ref.time_s.at(-1)!,
  };
}
