/** SI throughout. A fixed-path, flat-road, quasi-steady model comparison.
 * Four contact patches include load transfer and equal rear drive torque,
 * but not transient yaw, slip, suspension, banking or energy deployment. */
export type Model = "circle" | "axles" | "wheels";
export const MODELS: Model[] = ["circle", "axles", "wheels"];
export const COLORS = ["#e68141", "#22a88a", "#438ed1"];
export interface Car {
  mass: number;
  power: number;
  mu: number;
  clA: number;
  cdA: number;
  front: number;
  aeroFront: number;
  wheelbase: number;
  height: number;
  track: number;
  rollFront: number;
  brakeFront: number;
  exponent: number;
}
// Chassis dimensions from ORECA's 2025 media kit. Mass includes an assumed
// operating allowance. Power/aero/tyres/balance are exploratory, not team data.
export const LMP2: Car = {
  mass: 1000,
  power: 400000,
  mu: 1.65,
  clA: 4.5,
  cdA: 1.15,
  front: 0.45,
  aeroFront: 0.45,
  wheelbase: 3.005,
  height: 0.3,
  track: 1.555,
  rollFront: 0.45,
  brakeFront: 0.57,
  exponent: 0.9,
};
export interface Patch {
  x: number;
  y: number;
  fx: number;
  fy: number;
  fz: number;
  capacity: number;
  used: number;
}
export interface Forces {
  patches: Patch[];
  utilization: number;
  powerRatio: number;
  valid: boolean;
}
export interface Road {
  x: number[];
  y: number[];
  s: number[];
  station: number[];
  k: number[];
  ds: number[];
  length: number;
  trackLength: number;
}
export interface Run {
  model: Model;
  v: number[];
  t: number[];
  ax: number[];
  lap: number;
  iterations: number;
  residual: number;
}
const G = 9.81,
  RHO = 1.2,
  FREF = 2500;
export const clamp = (x: number, a: number, b: number) =>
  Math.max(a, Math.min(b, x));
export const mod = (x: number, n: number) => ((x % n) + n) % n;

export function forces(
  car: Car,
  model: Model,
  v: number,
  k: number,
  ax: number,
): Forces {
  const down = 0.5 * RHO * car.clA * v * v,
    drag = 0.5 * RHO * car.cdA * v * v;
  const fy = car.mass * v * v * k,
    fx = car.mass * ax + drag,
    total = car.mass * G + down;
  const tyre = (fz: number) =>
    car.mu * FREF * (Math.max(0, fz) / FREF) ** car.exponent;
  const patches: Patch[] = [];
  const add = (
    x: number,
    y: number,
    fx: number,
    fy: number,
    fz: number,
    capacity: number,
  ) =>
    patches.push({
      x,
      y,
      fx,
      fy,
      fz,
      capacity,
      used: Math.hypot(fx, fy) / Math.max(capacity, 1e-9),
    });
  if (model === "circle") add(0, 0, fx, fy, total, car.mu * total);
  else {
    const frontLoad =
      car.mass * G * car.front +
      down * car.aeroFront -
      (car.mass * ax * car.height) / car.wheelbase;
    const loads = [frontLoad, total - frontLoad];
    // Zero quasi-steady yaw moment: Fy_front/Fy_total = b/L = front fraction.
    const lateral = [fy * car.front, fy * (1 - car.front)];
    const longitudinal =
      fx >= 0 ? [0, fx] : [fx * car.brakeFront, fx * (1 - car.brakeFront)];
    for (let a = 0; a < 2; a++) {
      if (model === "axles")
        add(
          0,
          a === 0 ? -1 : 1,
          longitudinal[a],
          lateral[a],
          loads[a],
          2 * tyre(loads[a] / 2),
        );
      else {
        const transfer =
          (fy * car.height * (a === 0 ? car.rollFront : 1 - car.rollFront)) /
          car.track;
        const z = [loads[a] / 2 - transfer, loads[a] / 2 + transfer];
        const cap = z.map(tyre),
          sum = cap[0] + cap[1];
        for (let side = 0; side < 2; side++)
          add(
            side === 0 ? -1 : 1,
            a === 0 ? -1 : 1,
            longitudinal[a] / 2,
            (lateral[a] * cap[side]) / Math.max(sum, 1e-9),
            z[side],
            cap[side],
          );
      }
    }
  }
  const utilization = Math.max(...patches.map((p) => p.used));
  const powerRatio = (Math.max(0, fx) * v) / car.power;
  const valid =
    patches.every((p) => p.fz >= 0) &&
    utilization <= 1 + 1e-8 &&
    powerRatio <= 1 + 1e-8;
  return { patches, utilization, powerRatio, valid };
}

export function validateCar(c: Car) {
  for (const key of Object.keys(LMP2)) {
    const v = c[key as keyof Car];
    if (typeof v !== "number" || !Number.isFinite(v))
      throw new Error(`Invalid ${key}`);
  }
  if (
    c.mass < 300 ||
    c.mass > 3000 ||
    c.power < 10000 ||
    c.power > 1500000 ||
    c.mu < 0.3 ||
    c.mu > 4 ||
    c.cdA < 0.1 ||
    c.cdA > 5 ||
    c.clA < 0 ||
    c.clA > 15 ||
    c.height < 0 ||
    c.height > 1 ||
    c.wheelbase < 1 ||
    c.track < 1 ||
    c.exponent < 0.6 ||
    c.exponent > 1 ||
    [c.front, c.aeroFront, c.rollFront, c.brakeFront].some(
      (x) => x < 0.15 || x > 0.85,
    )
  )
    throw new Error("Car settings outside supported range");
}

/** Monotone relaxation of squared speeds on a CLOSED graph. Each edge is
 * constrained at its maximum speed and curvature: conservative at 2–4 m.
 * Repeated forward/backward sweeps recheck all constraints after braking. */
export function solve(road: Road, car: Car, model: Model): Run {
  validateCar(car);
  const n = road.k.length;
  if (
    n < 3 ||
    road.ds.length !== n ||
    road.ds.some((d) => !Number.isFinite(d) || d <= 0) ||
    road.k.some((k) => !Number.isFinite(k))
  )
    throw new Error("Invalid road");
  const edgeK = road.k.map((k, i) =>
    Math.abs(k) > Math.abs(road.k[(i + 1) % n]) ? k : road.k[(i + 1) % n],
  );
  const caps = edgeK.map((k) => {
    let lo = 0.1,
      hi = 110;
    for (let j = 0; j < 32; j++) {
      const mid = (lo + hi) / 2;
      if (forces(car, model, mid, k, 0).valid) lo = mid;
      else hi = mid;
    }
    return lo * lo;
  });
  const u = caps.map((v, i) => Math.min(v, caps[mod(i - 1, n)]));
  const feasible = (i: number, a: number, b: number) =>
    forces(
      car,
      model,
      Math.sqrt(Math.max(a, b)),
      edgeK[i],
      (b - a) / (2 * road.ds[i]),
    ).valid;
  let iterations = 0;
  for (; iterations < 100; iterations++) {
    let change = 0;
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n;
      if (u[j] <= u[i] || feasible(i, u[i], u[j])) continue;
      let lo = u[i],
        hi = u[j];
      for (let k = 0; k < 28; k++) {
        const mid = (lo + hi) / 2;
        if (feasible(i, u[i], mid)) lo = mid;
        else hi = mid;
      }
      change = Math.max(change, u[j] - lo);
      u[j] = lo;
    }
    for (let i = n - 1; i >= 0; i--) {
      const j = (i + 1) % n;
      if (u[i] <= u[j] || feasible(i, u[i], u[j])) continue;
      let lo = u[j],
        hi = u[i];
      for (let k = 0; k < 28; k++) {
        const mid = (lo + hi) / 2;
        if (feasible(i, mid, u[j])) lo = mid;
        else hi = mid;
      }
      change = Math.max(change, u[i] - lo);
      u[i] = lo;
    }
    if (change < 1e-7) break;
  }
  const v = u.map(Math.sqrt),
    t = [0],
    ax: number[] = [];
  let residual = 0;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    ax.push((u[j] - u[i]) / (2 * road.ds[i]));
    t.push(t[i] + (2 * road.ds[i]) / (v[i] + v[j]));
    const f = forces(car, model, Math.max(v[i], v[j]), edgeK[i], ax[i]);
    residual = Math.max(
      residual,
      f.utilization - 1,
      f.powerRatio - 1,
      ...f.patches.map((p) => -p.fz / (car.mass * G)),
    );
  }
  if (!Number.isFinite(t[n]) || iterations === 100 || residual > 1e-5)
    throw new Error(`Solver did not converge (residual ${residual})`);
  return { model, v, t, ax, lap: t[n], iterations: iterations + 1, residual };
}

export function interpolate(xs: number[], ys: number[], x: number): number {
  if (x <= xs[0]) return ys[0];
  if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
  let a = 0,
    b = xs.length - 1;
  while (b - a > 1) {
    const m = (a + b) >> 1;
    if (xs[m] <= x) a = m;
    else b = m;
  }
  return ys[a] + ((ys[b] - ys[a]) * (x - xs[a])) / (xs[b] - xs[a]);
}
