import { solve, type Car, type Road } from "./physics";
import { metrics, type Reference } from "./reference";
/** Small, deterministic bounded coordinate search. Fits effective parameters,
 * not identifiable physical tyre/aero measurements. No station-specific edits. */
export function calibrate(
  road: Road,
  initial: Car,
  references: Reference[],
  progress?: (x: any) => void,
) {
  const refs = references.filter((r) => r.split === "training");
  if (!refs.length)
    throw new Error(
      "No laps marked training. Validation laps must stay out of the fit.",
    );
  const bounds = {
    mu: [1.1, 2.3, 0.2],
    clA: [1.5, 7, 0.8],
    power: [250000, 450000, 40000],
    cdA: [0.7, 2, 0.2],
  } as const;
  const score = (c: Car) => {
    const run = solve(road, c, "wheels");
    return (
      refs.reduce((sum, r) => sum + metrics(road, run, r).rmse, 0) / refs.length
    );
  };
  let car = { ...initial },
    best = score(car),
    evaluations = 1;
  for (let round = 0; round < 7; round++) {
    const scale = 2 ** -Math.floor(round / 2);
    for (const [key, [lo, hi, step]] of Object.entries(bounds)) {
      const k = key as keyof typeof bounds;
      for (const direction of [-1, 1]) {
        const candidate = {
          ...car,
          [k]: Math.max(lo, Math.min(hi, car[k] + direction * step * scale)),
        };
        const s = score(candidate);
        evaluations++;
        if (s < best) {
          car = candidate;
          best = s;
        }
      }
    }
    progress?.({ round: round + 1, rmse: best });
  }
  return {
    car,
    trainingRmse: best,
    evaluations,
    method:
      "bounded coordinate search; four-tyre model; equal-lap mean speed RMSE; training laps only",
  };
}
