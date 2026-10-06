# Lap Lab

Road Atlanta, an exploratory ORECA 07 / LMP2 parameter set, and three levels
of force allocation. Inspired by [Marek Lubieniecki's comparison](https://x.com/m_lubieniecki/status/2107081419101016159).
The UI follows its three force displays, synchronized speed traces and corner
distance view. The physics is independently implemented, not a reconstruction
of the author's solver.

## Run and ship

Use Bun 1.3.14 (also pinned in CI):

```sh
bun install --frozen-lockfile
bun run build:sim
bun run serve:sim
```

Open `http://127.0.0.1:4173/sim/`. All paths work under a GitHub Pages project
prefix. `build:sim` copies the committed Road Atlanta GeoJSON and bundles Lit,
the TypeScript app and the solver worker into `site/sim/dist/`. Existing
Python data generation is unchanged; the simulator/build/calibration code is
TypeScript. No service, telemetry upload, WebAssembly or server computation
is required. Fonts are optional external assets with local fallbacks.

The existing Pages workflow assembles the atlas, runs the simulator checks and
builds the bundles. The atlas navigation links to `sim/`.

## Models and units

Physics uses metres, seconds, kilograms, newtons and watts. Display speed is
km/h. All models use the same settings and fixed racing line.

- **Grip circle:** total normal force `mg + 0.5 rho ClA v²`, capacity `mu Fz`.
  Longitudinal tyre force includes drag; power limits positive wheel force.
- **Two axles:** longitudinal load transfer `m ax h / wheelbase`, separate
  axle grip budgets, rear-only drive and specified brake balance. Lateral
  force splits according to the static CG geometry to satisfy quasi-steady
  axle yaw balance. Each axle capacity is the sum of two equally loaded tyres.
- **Four tyres:** additionally splits lateral load transfer between axles
  with a fixed roll-load share. Normal loads differ left/right. Lateral force
  allocation within each axle is proportional to available tyre grip;
  drive and brake forces split equally left/right. This models equal rear
  drive torque, not an active or locking differential. Negative wheel loads
  are infeasible.

The load-sensitive law is `mu Fref (Fz/Fref)^q`, with `Fref = 2500 N` per tyre
and the same reference in both axle and four-tyre models. `q = 1` removes
load sensitivity. Grip circles are isotropic; no slip-based Pacejka or
transient yaw state is claimed. Forces are expressed in the vehicle frame.
Aerodynamic pitch moments and the height at which drag acts are omitted.

Circle area represents capacity on a common force scale. Filled area is
capacity multiplied by utilization. Arrow components represent the actual
computed longitudinal/lateral forces. A dark ring appears above 98.5%
utilization. Display forces use the settings of the last completed solve,
even while new slider settings are being computed.

## Geometry and solver

`track.ts` uses the existing exported minimum-curvature GT3 racing line. It
rotates that line to the atlas start/finish, resamples at approximately 3 m,
computes signed curvature, and Gaussian-smooths curvature with 4 m sigma.
It preserves the path coordinates. This is not a new LMP2 line optimizer.
Line distance and atlas station are kept separate; time integrates along
line distance, while plots and reference alignment use atlas station.

`physics.ts` finds a steady-speed cap for each segment, then monotonically
reduces squared speeds with repeated forward/backward sweeps on the closed
lap. Each segment checks its larger endpoint speed and curvature and its
constant longitudinal acceleration `Delta(v²)/(2 ds)`. This is conservative;
all final edges, including the start/finish edge, must satisfy tyre and power
constraints. Unconverged or infeasible results throw rather than displaying
a plausible lap time. The solver is deterministic and runs in a worker.

The model has **no road elevation, banking, kerbs, bumps, suspension, tyre
temperature, fuel burn, gear shifts or time-dependent tyre slip/yaw**. Road
Atlanta's geometry includes unseen/interpolated edges: both edges were
directly observed on 61.4% of the lap. Absolute CE95 is 1.06 m; that number
does not describe relative curvature error or telemetry accuracy.

The [ORECA 2025 media kit](https://www.oreca.com/wp-content/uploads/2025/06/Media-Kit-24h-of-Le-Mans-25.pdf)
supports the 3.005 m wheelbase and approximate 1.555 m track width. The
1000 kg operating mass, 400 kW wheel power, aero, tyre and balance defaults
are assumptions, not team setup measurements. Effective calibration
parameters must not be presented as a measured engine or aerodynamic map.

## Reference laps

CSV requires `distance_m,speed_kmh,time_s` with strictly increasing distance
and time, time starting at zero and one complete Road Atlanta lap. JSON:

```json
{
  "name": "Reference lap",
  "track": "road-atlanta",
  "split": "validation",
  "distance_m": [],
  "speed_kmh": [],
  "time_s": []
}
```

Arrays must contain at least 20 numeric samples. Metres refer to atlas
station from its start/finish, not integrated speed or racing-line length.
One JSON array loads multiple laps. A bundle can contain `{car, laps}`;
`car` must provide every field in the `Car` interface. Optional fields:
`source`, `gps_p95_m`, `brake`, `throttle`. Brake units are not interpreted as
absolute pressure. The file picker parses locally and sends data only to
the local Web Worker. References are neither fetched remotely nor uploaded.

The UI reports Pearson speed correlation, speed RMSE/MAE and signed lap-time
error. Samples are compared at reference stations; there is no automatic
phase shift, time warp, speed scale or lap-time normalization. A manual
station offset is exposed but defaults to zero and does not change lap time.
Corner time deltas reset at the selected window's entry. Full-lap delta
starts at the line. Corner minimum-speed checks use ±100 m windows and may
overlap; they are not official timing sectors.

**Fit training laps** runs 57 bounded coordinate-search evaluations against
mean speed RMSE across only references labelled `split: "training"`. It
adjusts mu, ClA, wheel power and CdA in the four-tyre model. The resulting
settings are applied unchanged to all three models. Validation laps are not
consulted. It is a small local search, not a global parameter-identification
procedure. Fuel, traffic, driver inputs and changing conditions can explain
differences between laps. A smaller total-lap error alone does not establish
better physics.

## Reproduce the private archive comparison

`correlate.ts` reads the pre-existing, audited Road Atlanta analysis directory
(`analyzed-laps.json`, `geometry.json`, `lap-*.npz`) without modifying it.
NPZ is decoded in TypeScript. It selects the three fastest GPS-qualified
2026 FP1 laps for fitting and holds out all five GPS-qualified FP2 laps.
Remaining FP1 laps are marked unused. Original measured speed and elapsed
time are preserved. Station positions are remapped geometrically from the
extraction's reference frame to this solver's atlas frame.

```sh
bun scripts/sim/correlate.ts /path/to/existing/analysis .private
bun scripts/sim/standalone.ts .private/lap-lab.html .private/reference-laps.json
```

Outputs record source lap IDs, input hashes, common/native lap times, GPS
quality, train/validation roles, exact effective parameters, and per-lap
metrics. This adapter reuses measured signal extracts; it does not decode
the original MP4/VBO media again. The source scripts and metadata should be
retained alongside them. `.private/` is ignored, outside the Pages artifact.
Never copy private laps into `site/` or commit them. `standalone.ts` refuses
private-reference output inside `site/` and can make a public preview by
omitting its reference argument.

## Verification

```sh
bun run check:sim
bun run test:sim
bunx playwright install chromium
bun run test:browser
```

Physics checks cover analytical constant-radius grip, force conservation,
load transfer, symmetric axle/wheel limits, load sensitivity, closed-lap
edge feasibility, monotonic grip/power behaviour, 3 m vs 1.5 m convergence
and calibration isolation from held-out samples. Browser checks cover
playback, corner selection, parameter recomputation, local import/metrics,
malformed input handling and mobile scrubbing. Synthetic references exist
only inside tests and are never shown as measured data in the public tool.
