import { describe, test, expect } from "bun:test";
import { LMP2, MODELS, forces, solve, type Road } from "../../site/sim/physics";
import { loadTrack } from "../../site/sim/track";
import { parseReference, metrics } from "../../site/sim/reference";
import { calibrate } from "../../site/sim/calibrate";
const outline = await Bun.file(
  new URL("../../tracks/road-atlanta/raw/layers/gp.geojson", import.meta.url),
).json();
const surface = await Bun.file(
  new URL(
    "../../tracks/road-atlanta/raw/layers/gp.surface.geojson",
    import.meta.url,
  ),
).json();
function circle(radius = 100, n = 200): Road {
  const length = 2 * Math.PI * radius,
    ds = length / n,
    s = Array.from({ length: n }, (_, i) => i * ds);
  return {
    s,
    station: s,
    x: s.map((v) => radius * Math.cos(v / radius)),
    y: s.map((v) => radius * Math.sin(v / radius)),
    k: Array(n).fill(1 / radius),
    ds: Array(n).fill(ds),
    length,
    trackLength: length,
  };
}
describe("physical limits", () => {
  test("flat circle agrees with analytical friction limit", () => {
    const r = circle(),
      c = { ...LMP2, clA: 0, cdA: 0.1 };
    const run = solve(r, c, "circle"),
      expected = Math.sqrt(c.mu * 9.81 * 100);
    expect(run.v[0]).toBeCloseTo(expected, 2);
    expect(run.lap).toBeCloseTo(r.length / run.v[0], 6);
  });
  test("force balance and longitudinal transfer conserve vertical load", () => {
    const c = LMP2,
      v = 50,
      k = 0.002,
      ax = 3,
      f = forces(c, "wheels", v, k, ax),
      sum = (key: "fx" | "fy" | "fz") =>
        f.patches.reduce((s, p) => s + p[key], 0);
    expect(sum("fz")).toBeCloseTo(c.mass * 9.81 + 0.6 * c.clA * v * v, 7);
    expect(sum("fx")).toBeCloseTo(c.mass * ax + 0.6 * c.cdA * v * v, 7);
    expect(sum("fy")).toBeCloseTo(c.mass * v * v * k, 7);
    const front = f.patches.slice(0, 2).reduce((s, p) => s + p.fz, 0);
    expect(front).toBeLessThan(
      c.mass * 9.81 * c.front + 0.6 * c.clA * v * v * c.aeroFront,
    );
  });
  test("no lateral transfer: wheel and axle utilization agree", () => {
    for (const ax of [-5, 0, 4]) {
      expect(forces(LMP2, "wheels", 40, 0, ax).utilization).toBeCloseTo(
        forces(LMP2, "axles", 40, 0, ax).utilization,
        10,
      );
    }
  });
  test("load sensitivity loses total grip under lateral transfer", () => {
    const w = forces(LMP2, "wheels", 40, 0.008, 0),
      a = forces(LMP2, "axles", 40, 0.008, 0);
    expect(w.patches.reduce((s, p) => s + p.capacity, 0)).toBeLessThan(
      a.patches.reduce((s, p) => s + p.capacity, 0),
    );
  });
  test("invalid settings and impossible road values are rejected", () => {
    expect(() => solve(circle(), { ...LMP2, mass: NaN }, "wheels")).toThrow();
    expect(() => solve({ ...circle(), ds: [0] }, LMP2, "circle")).toThrow();
  });
});
describe("Road Atlanta", () => {
  const track = loadTrack(outline, surface);
  test("all three laps satisfy every edge, including start/finish", () => {
    for (const model of MODELS) {
      const r = solve(track.road, LMP2, model);
      expect(r.residual).toBeLessThan(1e-6);
      for (let i = 0; i < r.v.length; i++) {
        const j = (i + 1) % r.v.length,
          k =
            Math.abs(track.road.k[i]) > Math.abs(track.road.k[j])
              ? track.road.k[i]
              : track.road.k[j];
        const f = forces(LMP2, model, Math.max(r.v[i], r.v[j]), k, r.ax[i]);
        expect(f.utilization).toBeLessThan(1.000001);
        expect(f.powerRatio).toBeLessThan(1.000001);
        expect(f.patches.every((p) => p.fz >= 0)).toBe(true);
      }
      expect(r.lap).toBeGreaterThan(50);
      expect(r.lap).toBeLessThan(100);
    }
  });
  test("higher grip and power do not make the point model slower", () => {
    const base = solve(track.road, LMP2, "circle");
    expect(solve(track.road, { ...LMP2, mu: 1.9 }, "circle").lap).toBeLessThan(
      base.lap,
    );
    expect(
      solve(track.road, { ...LMP2, power: 440000 }, "circle").lap,
    ).toBeLessThan(base.lap);
  });
  test("refining 3 m to 1.5 m changes lap time by under 1%", () => {
    const fine = loadTrack(outline, surface, 1.5);
    for (const m of MODELS) {
      const a = solve(track.road, LMP2, m),
        b = solve(fine.road, LMP2, m);
      expect(Math.abs(a.lap - b.lap) / b.lap).toBeLessThan(0.01);
    }
  });
});
test("reference import rejects nonfinite data and reverse time", () => {
  const ref = {
    name: "Test",
    track: "road-atlanta",
    distance_m: Array.from({ length: 21 }, (_, i) => i * 200),
    speed_kmh: Array(21).fill(200),
    time_s: Array.from({ length: 21 }, (_, i) => i * 3.6),
  };
  expect(parseReference(JSON.stringify(ref))).toHaveLength(1);
  expect(() =>
    parseReference(
      JSON.stringify({ ...ref, time_s: [...ref.time_s].reverse() }),
    ),
  ).toThrow();
  expect(() =>
    parseReference(JSON.stringify({ ...ref, speed_kmh: Array(21).fill(null) })),
  ).toThrow();
});
test("calibration ignores all held-out lap values", () => {
  const road = circle(650, 80),
    run = solve(road, LMP2, "wheels"),
    ref = {
      name: "Synthetic training",
      track: "road-atlanta" as const,
      split: "training",
      distance_m: [...road.station, road.trackLength],
      speed_kmh: [...run.v, run.v[0]].map((x) => x * 3.6),
      time_s: run.t,
    };
  const a = calibrate(road, LMP2, [ref]),
    b = calibrate(road, LMP2, [
      ref,
      {
        ...ref,
        split: "validation",
        speed_kmh: ref.speed_kmh.map((v) => v * 0.5),
      },
    ]);
  expect(a.car).toEqual(b.car);
  expect(a.trainingRmse).toBeLessThan(1e-7);
  expect(metrics(road, run, ref).rmse).toBeLessThan(1e-7);
});
