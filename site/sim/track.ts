import { mod, interpolate, type Road } from "./physics";
export type XY = [number, number];
export interface Track {
  road: Road;
  edges: XY[][];
  outline: XY[];
  corners: { name: string; station: number }[];
  seen: number;
  ce95: number;
}
const distance = (a: XY, b: XY) => Math.hypot(a[0] - b[0], a[1] - b[1]);
export function metricFrame(lon: number, lat: number) {
  const phi = (lat * Math.PI) / 180,
    w = Math.sqrt(1 - 0.00669437999014 * Math.sin(phi) ** 2);
  const sx = ((Math.PI / 180) * 6378137 * Math.cos(phi)) / w,
    sy = ((Math.PI / 180) * 6378137 * (1 - 0.00669437999014)) / w ** 3;
  return (p: number[]): XY => [(p[0] - lon) * sx, (p[1] - lat) * sy];
}
export function openRing(p: XY[]): XY[] {
  return distance(p[0], p[p.length - 1]) < 0.05 ? p.slice(0, -1) : p;
}
export function cumulative(p: XY[]): number[] {
  const s = [0];
  for (let i = 0; i < p.length; i++)
    s.push(s[i] + distance(p[i], p[(i + 1) % p.length]));
  return s;
}
export function project(
  p: XY,
  line: XY[],
  cum = cumulative(line),
): { s: number; error: number } {
  let best = Infinity,
    s = 0;
  for (let i = 0; i < line.length; i++) {
    const a = line[i],
      b = line[(i + 1) % line.length],
      dx = b[0] - a[0],
      dy = b[1] - a[1];
    const u = Math.max(
      0,
      Math.min(
        1,
        ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy || 1),
      ),
    );
    const error = Math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy);
    if (error < best) {
      best = error;
      s = cum[i] + u * (cum[i + 1] - cum[i]);
    }
  }
  return { s, error: best };
}
export function smooth(a: number[], sigma: number) {
  const radius = Math.ceil(sigma * 3),
    out: number[] = [];
  for (let i = 0; i < a.length; i++) {
    let v = 0,
      w = 0;
    for (let j = -radius; j <= radius; j++) {
      const ww = Math.exp(-0.5 * (j / sigma) ** 2);
      v += ww * a[mod(i + j, a.length)];
      w += ww;
    }
    out.push(v / w);
  }
  return out;
}
export function loadTrack(outlineGeo: any, surfaceGeo: any, step = 3): Track {
  const features = surfaceGeo.features;
  const coords = outlineGeo.features.find(
    (f: any) => f.properties.role === "outline",
  ).geometry.coordinates;
  const frame = metricFrame(coords[0][0], coords[0][1]);
  const outline = openRing(coords.map(frame)),
    sc = cumulative(outline),
    trackLength = sc[sc.length - 1];
  const raw = openRing(
    features
      .find((f: any) => f.properties.role === "racing_line")
      .geometry.coordinates.map(frame),
  );
  // Rotate the stored line to the geometric start/finish rather than assuming
  // the exported racing line happens to start at the lap origin.
  const cut = project(outline[0], raw),
    rc = cumulative(raw),
    length = rc[rc.length - 1];
  const n = Math.round(length / step),
    ds = length / n,
    s = Array.from({ length: n }, (_, i) => i * ds);
  const rx = [...raw.map((p) => p[0]), raw[0][0]],
    ry = [...raw.map((p) => p[1]), raw[0][1]];
  const x = s.map((v) => interpolate(rc, rx, mod(v + cut.s, length))),
    y = s.map((v) => interpolate(rc, ry, mod(v + cut.s, length)));
  // Curvature only is smoothed; path coordinates remain inside their original corridor.
  const heading = x.map((_, i) =>
    Math.atan2(
      y[(i + 1) % n] - y[mod(i - 1, n)],
      x[(i + 1) % n] - x[mod(i - 1, n)],
    ),
  );
  const k = smooth(
    heading.map(
      (_, i) =>
        Math.atan2(
          Math.sin(heading[(i + 1) % n] - heading[mod(i - 1, n)]),
          Math.cos(heading[(i + 1) % n] - heading[mod(i - 1, n)]),
        ) /
        (2 * ds),
    ),
    4 / ds,
  );
  const station = x.map((v, i) => project([v, y[i]], outline, sc).s);
  station[0] = 0;
  for (let i = 1; i < n; i++)
    if (station[i] < station[i - 1]) {
      if (station[i - 1] - station[i] > trackLength / 2)
        station[i] += trackLength;
      else station[i] = station[i - 1] + 1e-6;
    }
  if (station[n - 1] >= trackLength)
    throw new Error("Racing line station mapping wraps unexpectedly");
  const cornerFeatures = outlineGeo.features.filter(
    (f: any) =>
      f.geometry.type === "Point" &&
      (f.properties.layer === "corners" || f.properties.number != null),
  );
  const corners = cornerFeatures.map((f: any) => ({
    name:
      f.properties.code === "Esses"
        ? "Esses"
        : "T" + (f.properties.code || f.properties.number),
    station: project(frame(f.geometry.coordinates), outline, sc).s,
  }));
  return {
    road: { x, y, k, s, station, ds: Array(n).fill(ds), length, trackLength },
    outline,
    edges: features
      .filter((f: any) =>
        ["edge_left", "edge_right"].includes(f.properties.role),
      )
      .map((f: any) => f.geometry.coordinates.map(frame)),
    corners: corners.sort((a: any, b: any) => a.station - b.station),
    seen: 0.614,
    ce95: 1.06,
  };
}
