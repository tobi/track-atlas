import { LitElement, html, svg, nothing } from "lit";
import {
  COLORS,
  LMP2,
  MODELS,
  forces,
  interpolate,
  clamp,
  validateCar,
  type Car,
  type Run,
} from "./physics";
import { loadTrack, type Track } from "./track";
import { parseReference, metrics, type Reference } from "./reference";
const names = ["1 grip circle", "2 axles", "4 tyres"];
const fmt = (s: number) =>
  `${Math.floor(s / 60)}:${(s % 60).toFixed(3).padStart(6, "0")}`;
const signed = (v: number, d = 2) => (v >= 0 ? "+" : "") + v.toFixed(d);
class LapLab extends LitElement {
  static properties = {
    track: { state: true },
    runs: { state: true },
    car: { state: true },
    corner: { state: true },
    cursor: { state: true },
    playing: { state: true },
    rate: { state: true },
    refs: { state: true },
    refIndex: { state: true },
    error: { state: true },
    status: { state: true },
    busy: { state: true },
    whole: { state: true },
    offset: { state: true },
    revision: { state: true },
  };
  declare track: Track | undefined;
  declare runs: Run[];
  declare car: Car;
  declare corner: number;
  declare cursor: number;
  declare playing: boolean;
  declare rate: number;
  declare refs: Reference[];
  declare refIndex: number;
  declare error: string;
  declare status: string;
  declare busy: boolean;
  declare whole: boolean;
  declare offset: number;
  declare revision: number;
  constructor() {
    super();
    Object.assign(this, {
      runs: [],
      car: { ...LMP2 },
      corner: 7,
      cursor: 0,
      playing: false,
      rate: 0.5,
      refs: [],
      refIndex: 0,
      error: "",
      status: "Loading measured track…",
      busy: false,
      whole: false,
      offset: 0,
      revision: 0,
    });
  }
  worker = new Worker(
    (globalThis as any).__LAP_LAB_BOOT__?.worker ||
      new URL("./worker.js", import.meta.url),
    {
      type: (globalThis as any).__LAP_LAB_BOOT__?.worker ? "classic" : "module",
    },
  );
  requestId = 0;
  timer = 0;
  last = 0;
  animation = 0;
  solvedCar = { ...LMP2 };
  createRenderRoot() {
    this.textContent = "";
    return this;
  }
  async connectedCallback() {
    super.connectedCallback();
    this.worker.onmessage = ({ data }) => {
      if (data.id !== this.requestId) return;
      if (data.progress) {
        this.status = `Fitting training laps · pass ${data.progress.round}/7 · ${data.progress.rmse.toFixed(1)} km/h RMSE`;
        return;
      }
      this.busy = false;
      if (data.error) {
        this.error = data.error;
        this.status = "Solve failed";
        return;
      }
      this.runs = data.runs;
      this.solvedCar = data.car;
      if (data.fit) this.car = data.fit.car;
      this.status = data.fit
        ? `Fit complete · ${data.fit.evaluations} evaluations · training laps only`
        : "Ready · all forces within model limits";
      this.revision++;
    };
    this.worker.onerror = () => {
      this.error = "The simulation worker could not start. Reload the page.";
      this.busy = false;
    };
    try {
      const get = async (p: string) => {
        const r = await fetch(p);
        if (!r.ok) throw new Error(`Track download failed: ${r.status}`);
        return r.json();
      };
      const boot = (globalThis as any).__LAP_LAB_BOOT__;
      const [o, s] =
        boot?.geometry ||
        (await Promise.all([
          get("../geojson/road-atlanta_gp.geojson"),
          get("../geojson/road-atlanta_gp.surface.geojson"),
        ]));
      this.track = loadTrack(o, s);
      this.corner = this.track.corners.findIndex((c) => c.name === "T7");
      this.cursor = this.bounds()[0];
      if (boot?.reference) {
        this.refs = parseReference(JSON.stringify(boot.reference));
        if (boot.reference.car) {
          validateCar(boot.reference.car);
          this.car = boot.reference.car;
        }
        this.refIndex = this.refs.reduce(
          (best, r, i) =>
            r.split === "validation" &&
            (best < 0 || r.time_s.at(-1)! < this.refs[best].time_s.at(-1)!)
              ? i
              : best,
          -1,
        );
        if (this.refIndex < 0) this.refIndex = 0;
      }
      this.compute();
    } catch (e) {
      this.error = String(e);
      this.status = "Unable to load track";
    }
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this.worker.terminate();
    cancelAnimationFrame(this.animation);
    clearTimeout(this.timer);
  }
  compute(action = "solve") {
    if (!this.track) return;
    this.busy = true;
    this.error = "";
    this.status = action === "fit" ? "Fitting training laps…" : "Solving…";
    this.worker.postMessage({
      id: ++this.requestId,
      action,
      road: this.track.road,
      car: this.car,
      references: this.refs,
    });
  }
  change(k: keyof Car, value: number) {
    this.playing = false;
    this.busy = true;
    this.status = "Solving…";
    this.car = { ...this.car, [k]: value };
    clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.compute(), 90);
  }
  bounds(): [number, number] {
    if (!this.track) return [0, 1];
    const r = this.track.road;
    if (this.whole) return [0, r.trackLength];
    const c = this.track.corners[this.corner]?.station || 0;
    return [Math.max(0, c - 300), Math.min(r.trackLength, c + 350)];
  }
  ref() {
    return this.refs[this.refIndex];
  }
  at(run: Run, key: "v" | "t", s: number) {
    const r = this.track!.road;
    return interpolate(
      [...r.station, r.trackLength],
      key === "v" ? [...run.v, run.v[0]] : run.t,
      s,
    );
  }
  refAt(key: "speed_kmh" | "time_s", s: number) {
    const r = this.ref();
    return r ? interpolate(r.distance_m, r[key], s - this.offset) : 0;
  }
  localDelta(run: Run) {
    const [start] = this.bounds(),
      r = this.ref();
    return r
      ? this.at(run, "t", this.cursor) -
          this.at(run, "t", start) -
          (this.refAt("time_s", this.cursor) - this.refAt("time_s", start))
      : null;
  }
  index() {
    const r = this.track!.road;
    let i = 0;
    while (i + 1 < r.station.length && r.station[i + 1] < this.cursor) i++;
    return i;
  }
  selectCorner(value: number) {
    this.playing = false;
    this.corner = value;
    this.cursor = this.bounds()[0];
  }
  toggle() {
    cancelAnimationFrame(this.animation);
    this.playing = !this.playing;
    this.last = 0;
    if (this.playing) this.tick(0);
  }
  tick = (now: number) => {
    if (!this.playing || !this.track || !this.runs.length) return;
    if (this.last && now - this.last < 30) {
      this.animation = requestAnimationFrame(this.tick);
      return;
    }
    const dt = this.last ? Math.min(0.15, (now - this.last) / 1000) : 0;
    this.last = now;
    const [start, end] = this.bounds(),
      i = this.index(),
      r = this.track.road;
    const dStation =
      (i + 1 < r.station.length ? r.station[i + 1] : r.trackLength) -
      r.station[i];
    this.cursor +=
      (dt * this.rate * this.at(this.runs[2], "v", this.cursor) * dStation) /
      r.ds[i];
    if (this.cursor > end) this.cursor = start;
    this.animation = requestAnimationFrame(this.tick);
  };
  async importFile(file?: File) {
    if (!file) return;
    if (file.size > 20_000_000) {
      this.error = "Reference file must be under 20 MB.";
      return;
    }
    try {
      const text = await file.text(),
        refs = parseReference(text);
      let parsed: any;
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = null;
      }
      let car = this.car;
      if (parsed?.car) {
        validateCar(parsed.car);
        car = { ...parsed.car };
      }
      this.refs = refs;
      this.refIndex = Math.max(
        0,
        refs.findIndex((r) => r.split === "validation"),
      );
      this.car = car;
      this.offset = 0;
      this.error = "";
      this.compute();
    } catch (e) {
      this.error = String(e);
    }
  }
  download() {
    if (!this.track) return;
    const data = {
      schema: 1,
      track: "road-atlanta",
      car: this.solvedCar,
      assumptions:
        "Fixed atlas line; flat road; quasi-steady loads; equal rear torque; no transient yaw/slip. Effective parameters, not measured vehicle coefficients.",
      runs: this.runs,
      station_m: this.track.road.station,
      referenceMetrics: this.ref()
        ? this.runs.map((r) => ({
            model: r.model,
            ...metrics(this.track!.road, r, this.ref(), this.offset),
          }))
        : null,
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "road-atlanta-lmp2-simulation.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  grip(run: Run, m: number) {
    const i = this.index(),
      f = forces(
        this.solvedCar,
        run.model,
        run.v[i],
        this.track!.road.k[i],
        run.ax[i],
      ),
      color = COLORS[m],
      delta = this.localDelta(run);
    return html`<article class="grip">
      <h2 style=${`color:${color}`}>${names[m]}</h2>
      <svg
        viewBox="0 0 250 224"
        role="img"
        aria-label=${`${names[m]} force use`}
      >
        <defs>
          <marker
            id=${`arrow${m}`}
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M0 0L10 5L0 10z" fill="#253831" />
          </marker>
        </defs>
        <g opacity=".10" fill=${color}>
          <rect x="112" y="32" width="26" height="148" rx="10" />
          <rect x="96" y="60" width="9" height="24" rx="3" />
          <rect x="145" y="60" width="9" height="24" rx="3" />
          <rect x="96" y="142" width="9" height="24" rx="3" />
          <rect x="145" y="142" width="9" height="24" rx="3" />
        </g>
        ${f.patches.map((p) => {
          const radius = Math.sqrt(p.capacity / 45000) * 83,
            cx = 125 + p.x * 39,
            cy = 111 + p.y * 46,
            fill = radius * Math.sqrt(clamp(p.used, 0, 1));
          return svg`
        <circle cx=${cx} cy=${cy} r=${radius} fill=${color} fill-opacity=".07" stroke=${color} stroke-width="1.2"/>
        <circle cx=${cx} cy=${cy} r=${fill} fill=${color} fill-opacity=".34"/>
        ${p.used > 0.985 ? svg`<circle cx=${cx} cy=${cy} r=${radius} fill="none" stroke="#344b42" stroke-width="2.4"/>` : nothing}
        <line x1=${cx} y1=${cy} x2=${cx - (radius * p.fy) / p.capacity} y2=${cy - (radius * p.fx) / p.capacity} stroke="#253831" stroke-width="1.3" marker-end=${`url(#arrow${m})`}/>
        <text x=${cx} y=${cy + radius + 13} text-anchor="middle" font-size="10" fill="#697970">${Math.round(p.used * 100)}%</text>`;
        })}
      </svg>
      <div class="speed-readout number">
        ${(this.at(run, "v", this.cursor) * 3.6).toFixed(0)}
        <small>km/h</small>${delta !== null
          ? html`<span class="delta ${delta < 0 ? "fast" : "slow"}"
              >${signed(delta)} s</span
            >`
          : nothing}
      </div>
      <div class="lap-label">Lap ${fmt(run.lap)}</div>
    </article>`;
  }
  mapInset() {
    const r = this.track!.road,
      xmin = Math.min(...r.x),
      xmax = Math.max(...r.x),
      ymin = Math.min(...r.y),
      ymax = Math.max(...r.y),
      scale = Math.min(135 / (xmax - xmin), 77 / (ymax - ymin));
    const x = (v: number) => 70 + (v - xmin) * scale,
      y = (v: number) => 112 - (v - ymin) * scale;
    const [start, end] = this.bounds(),
      d = (indices: number[]) =>
        "M" + indices.map((i) => `${x(r.x[i])},${y(r.y[i])}`).join("L");
    const indices = r.s.map((_, i) => i),
      section = indices.filter(
        (i) => r.station[i] >= start && r.station[i] <= end,
      ),
      i = this.index();
    return svg`<path d=${d(indices) + "Z"} fill="none" stroke="#d8ddd5" stroke-width="2.5"/><path d=${d(section)} fill="none" stroke="#dc9564" stroke-width="3"/><circle cx=${x(r.x[i])} cy=${y(r.y[i])} r="3.5" fill="#344b42"/>`;
  }
  chart(delta = false) {
    const [start, end] = this.bounds(),
      W = 780,
      H = delta ? 150 : 355,
      left = 52,
      right = 760,
      top = delta ? 16 : 30,
      bottom = delta ? 115 : 309;
    const x = (s: number) =>
        left + ((s - start) / (end - start)) * (right - left),
      s = this.track!.road.station;
    const ref = this.ref(),
      anchor = this.whole ? 0 : this.track!.corners[this.corner].station;
    const arrays = this.runs.map((run) =>
      s
        .map((station, i) => ({
          s: station,
          v: delta
            ? run.t[i] -
              this.at(run, "t", start) -
              (this.refAt("time_s", station) - this.refAt("time_s", start))
            : run.v[i] * 3.6,
        }))
        .filter((p) => p.s >= start && p.s <= end),
    );
    const ys = arrays.flat().map((p) => p.v),
      max = delta ? Math.max(1, ...ys.map(Math.abs)) * 1.15 : 320,
      min = delta ? -max : 60;
    const y = (v: number) =>
      bottom - ((v - min) / (max - min)) * (bottom - top);
    const path = (points: { s: number; v: number }[]) =>
      "M" +
      points.map((p) => `${x(p.s).toFixed(2)},${y(p.v).toFixed(2)}`).join("L");
    const ticks = delta ? [-max / 2, 0, max / 2] : [100, 150, 200, 250, 300];
    const xticks = this.whole
      ? Array.from({ length: 5 }, (_, i) => i * 1000)
      : Array.from(
          { length: 8 },
          (_, i) => (Math.ceil((start - anchor) / 100) + i) * 100 + anchor,
        ).filter((v) => v >= start && v <= end);
    const refPoints = ref
      ? ref.distance_m
          .map((v, i) => ({ s: v + this.offset, v: ref.speed_kmh[i] }))
          .filter((p) => p.s >= start && p.s <= end)
      : [];
    return html`<div class="chart-box">
      <div class="chart-top">
        <span>${delta ? "Time difference" : "Speed"}</span
        ><span class="units"
          >${delta
            ? "relative to reference · reset at window entry"
            : "km/h · click to scrub"}</span
        >
      </div>
      <svg
        viewBox=${`0 0 ${W} ${H}`}
        role="img"
        aria-label=${delta
          ? "Model time difference against reference"
          : "Speed comparison by track distance"}
        @click=${(e: MouseEvent) => {
          const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
          this.cursor = clamp(
            start +
              ((((e.clientX - rect.left) * W) / rect.width - left) /
                (right - left)) *
                (end - start),
            start,
            end,
          );
        }}
      >
        <defs>
          <clipPath id=${delta ? "clipDelta" : "clipSpeed"}>
            <rect
              x=${left}
              y=${top}
              width=${right - left}
              height=${bottom - top}
            />
          </clipPath>
        </defs>
        ${ticks.map(
          (v) =>
            svg`<line x1=${left} x2=${right} y1=${y(v)} y2=${y(v)} stroke="#e6e9e1"/><text x="40" y=${y(v) + 4} text-anchor="end" fill="#8a948c" font-size="10">${delta ? v.toFixed(1) : v}</text>`,
        )}
        ${xticks.map(
          (v) =>
            svg`<line x1=${x(v)} x2=${x(v)} y1=${top} y2=${bottom} stroke="#eef0eb"/><text x=${x(v)} y=${bottom + 18} fill="#8a948c" font-size="10" text-anchor="middle">${Math.round(v - anchor)}</text>`,
        )}
        <g clip-path=${`url(#${delta ? "clipDelta" : "clipSpeed"})`}>
          ${!delta && ref
            ? svg`<path class="chart-line" d=${path(refPoints)} stroke="#7c847a" stroke-width="2.3"/>`
            : nothing}
          ${arrays.map(
            (pts, i) =>
              svg`<path class="chart-line" d=${path(pts)} stroke=${COLORS[i]}/>`,
          )}
        </g>
        ${!this.whole
          ? svg`<line x1=${x(anchor)} x2=${x(anchor)} y1="20" y2=${bottom} stroke="#bfc8bd" stroke-dasharray="3 4"/><text x=${x(anchor)} y="15" fill="#657268" font-size="10" text-anchor="middle">${this.track!.corners[this.corner].name}</text>`
          : nothing}
        <line
          x1=${x(this.cursor)}
          x2=${x(this.cursor)}
          y1=${top}
          y2=${bottom}
          stroke="#b6bfb5"
        />
        ${this.runs.map(
          (run, i) =>
            svg`<circle cx=${x(this.cursor)} cy=${y(delta ? this.localDelta(run) || 0 : this.at(run, "v", this.cursor) * 3.6)} r="4" fill=${COLORS[i]} stroke="#fffefb" stroke-width="1.5"/>`,
        )}
        ${!delta ? this.mapInset() : nothing}
        <text
          x="405"
          y=${H - 5}
          text-anchor="middle"
          font-size="10"
          fill="#8a948c"
        >
          ${this.whole
            ? "Distance from start / finish [m]"
            : "Distance from atlas corner anchor [m]"}
        </text>
      </svg>
    </div>`;
  }
  slider(
    key: keyof Car,
    label: string,
    min: number,
    max: number,
    step: number,
    scale = 1,
    unit = "",
  ) {
    return html`<label class="row" for=${key}
        >${label}<span class="val"
          >${(this.car[key] / scale).toFixed(
            step / scale < 0.1 ? 2 : step / scale < 1 ? 1 : 0,
          )}
          ${unit}</span
        ></label
      ><input
        id=${key}
        type="range"
        min=${min}
        max=${max}
        step=${step}
        .value=${String(this.car[key])}
        @input=${(e: Event) =>
          this.change(key, +(e.target as HTMLInputElement).value)}
      />`;
  }
  referencePanel() {
    const ref = this.ref(),
      m =
        ref && this.runs[2]
          ? metrics(this.track!.road, this.runs[2], ref, this.offset)
          : null;
    return html`<section class="panel">
      <h2>A lap to chase</h2>
      <label
        class="file"
        @dragover=${(e: DragEvent) => e.preventDefault()}
        @drop=${(e: DragEvent) => {
          e.preventDefault();
          this.importFile(e.dataTransfer?.files[0]);
        }}
        >＋ Load reference laps<input
          type="file"
          accept=".json,.csv"
          aria-label="Load reference laps"
          @change=${(e: Event) =>
            this.importFile((e.target as HTMLInputElement).files?.[0])}
      /></label>
      <p>JSON / CSV · stays in your browser</p>
      ${ref
        ? html`<label for="reference">Recorded lap</label
            ><select
              id="reference"
              .value=${String(this.refIndex)}
              @change=${(e: Event) => {
                this.refIndex = +(e.target as HTMLSelectElement).value;
                this.offset = 0;
              }}
            >
              ${this.refs.map(
                (r, i) =>
                  html`<option value=${i} ?selected=${i === this.refIndex}>
                    ${r.name} ·
                    ${fmt(r.time_s.at(-1)!)}${r.split ? " · " + r.split : ""}
                  </option>`,
              )}
            </select>
            ${m
              ? html`<div class="reference-stats">
                  <div>
                    <b>${m.r.toFixed(3)}</b
                    ><small>Speed correlation · 4 tyres</small>
                  </div>
                  <div>
                    <b>${m.rmse.toFixed(1)}</b><small>Speed RMSE · km/h</small>
                  </div>
                  <div>
                    <b>${signed(m.lapDelta)}</b
                    ><small>Lap error · seconds</small>
                  </div>
                  <div>
                    <b>${m.mae.toFixed(1)}</b><small>Speed MAE · km/h</small>
                  </div>
                </div>`
              : nothing}
            <p>
              ${ref.gps_p95_m
                ? `GPS-to-midline p95: ${ref.gps_p95_m.toFixed(0)} m. Corner positions are approximate.`
                : ""}
            </p>
            <div class="fitrow">
              <button
                class="secondary"
                ?disabled=${this.busy ||
                !this.refs.some((r) => r.split === "training")}
                @click=${() => this.compute("fit")}
              >
                Fit training laps</button
              ><button
                class="secondary"
                @click=${() => {
                  this.refs = [];
                  this.offset = 0;
                }}
              >
                Clear
              </button>
            </div>
            <details>
              <summary>Distance alignment</summary>
              <p>
                Shift the reference station only. No speed or lap-time scaling.
                Report comparisons at zero shift unless a documented alignment
                correction is needed.
              </p>
              <label
                >Offset: ${this.offset} m<input
                  aria-label="Reference station offset"
                  type="range"
                  min="-50"
                  max="50"
                  step="1"
                  .value=${String(this.offset)}
                  @input=${(e: Event) =>
                    (this.offset = +(e.target as HTMLInputElement).value)}
              /></label>
            </details> `
        : html`<p class="empty-reference">
              Bring a recorded Road Atlanta lap to compare apex speed, braking
              and corner exit. There’s no fabricated reference trace.
            </p>
            <details>
              <summary>File format</summary>
              <p>
                CSV columns: <code>distance_m,speed_kmh,time_s</code>. One
                complete lap from start/finish; metres, km/h, seconds. JSON:
                <code
                  >{name, track:"road-atlanta", distance_m:[], speed_kmh:[],
                  time_s:[]}</code
                >. A JSON array loads multiple laps. Mark calibration laps
                <code>split:"training"</code> and held-out laps
                <code>split:"validation"</code>.
              </p>
            </details>`}
    </section>`;
  }
  cornerTable() {
    if (!this.ref()) return nothing;
    const r = this.track!.road,
      ref = this.ref(),
      run = this.runs[2];
    return html`<details class="methods corner-table">
      <summary>Corner checks · four-tyre model versus reference</summary>
      <p>
        Minimum speed and window time within ±100 m of each atlas anchor.
        Adjacent windows can overlap. Not official timing sectors.
      </p>
      <table>
        <thead>
          <tr>
            <th>Corner</th>
            <th>Reference min</th>
            <th>Model min</th>
            <th>Speed error</th>
            <th>Window Δt</th>
          </tr>
        </thead>
        <tbody>
          ${this.track!.corners.map((c) => {
            const a = Math.max(0, c.station - 100),
              b = Math.min(r.trackLength, c.station + 100),
              indices = r.station
                .map((_, i) => i)
                .filter((i) => r.station[i] >= a && r.station[i] <= b),
              refIndices = ref.distance_m
                .map((_, i) => i)
                .filter(
                  (i) =>
                    ref.distance_m[i] + this.offset >= a &&
                    ref.distance_m[i] + this.offset <= b,
                );
            if (!indices.length || !refIndices.length) return nothing;
            const mv = Math.min(...indices.map((i) => run.v[i] * 3.6)),
              rv = Math.min(...refIndices.map((i) => ref.speed_kmh[i])),
              dt =
                this.at(run, "t", b) -
                this.at(run, "t", a) -
                (this.refAt("time_s", b) - this.refAt("time_s", a));
            return html`<tr>
              <td>${c.name}</td>
              <td>${rv.toFixed(0)} km/h</td>
              <td>${mv.toFixed(0)} km/h</td>
              <td>${signed(mv - rv, 0)} km/h</td>
              <td>${signed(dt)} s</td>
            </tr>`;
          })}
        </tbody>
      </table>
    </details>`;
  }
  render() {
    const ready = !!this.track && this.runs.length === 3,
      [start, end] = this.bounds();
    return html`<header>
        <a class="brand" href="../"
          ><svg viewBox="0 0 32 32">
            <rect width="32" height="32" rx="8" fill="#234a39" />
            <path
              d="M8 23C6 11 16 5 23 10S16 18 18 23 9 27 8 23"
              fill="none"
              stroke="#d7e9c9"
              stroke-width="2"
            /></svg
          >Track Atlas
          <span style="font-weight:400;color:#8b958c">/ Lap Lab</span></a
        >
        <nav>
          <a href="../#/road-atlanta">Explore the track ↗</a
          ><span class="tag">Experimental</span>
        </nav>
      </header>
      ${this.error
        ? html`<div class="layout">
            <div class="error" role="alert">${this.error}</div>
          </div>`
        : nothing}
      <main class="layout">
        <section class="paper">
          <div class="mast">
            <div class="eyebrow">One track · one car · three models</div>
            <h1>
              ROAD ATLANTA
              ${!this.whole && this.track
                ? " / " + this.track.corners[this.corner].name
                : ""}
            </h1>
            <p class="sub">
              LMP2 · same settings, same racing
              line${this.ref()
                ? ` · reference ${fmt(this.ref().time_s.at(-1)!)}`
                : ""}
            </p>
          </div>
          ${ready
            ? html`<div class="grip-grid">
                  ${this.runs.map((r, i) => this.grip(r, i))}
                </div>
                <p class="legend-note">
                  Circle area = available force · fill = force used · dark ring
                  = at the limit · arrow = tyre force
                </p>
                ${this.chart()}
                <div class="trace-legend">
                  ${names.map(
                    (n, i) =>
                      html`<span
                        ><i
                          class="swatch"
                          style=${`background:${COLORS[i]}`}
                        ></i
                        >${n}</span
                      >`,
                  )}${this.ref()
                    ? html`<span
                        ><i class="swatch" style="background:#7c847a"></i
                        >Recorded lap</span
                      >`
                    : nothing}
                </div>
                ${this.ref() ? this.chart(true) : nothing}
                <div class="transport">
                  <input
                    class="scrub"
                    type="range"
                    aria-label="Lap position"
                    min=${start}
                    max=${end}
                    step="any"
                    .value=${String(this.cursor)}
                    @input=${(e: Event) => {
                      this.playing = false;
                      this.cursor = +(e.target as HTMLInputElement).value;
                    }}
                  />
                  <div class="transport-row">
                    <button class="play" @click=${() => this.toggle()}>
                      ${this.playing ? "Ⅱ Pause" : "▶ Play"}</button
                    ><select
                      class="secondary"
                      aria-label="Playback speed"
                      .value=${String(this.rate)}
                      @change=${(e: Event) =>
                        (this.rate = +(e.target as HTMLSelectElement).value)}
                    >
                      <option value="0.25">¼ speed</option>
                      <option value="0.5">½ speed</option>
                      <option value="1">1× speed</option>
                      <option value="4">4× speed</option>
                    </select>
                    <div class="toggle">
                      <button
                        class="secondary ${!this.whole ? "on" : ""}"
                        @click=${() => {
                          this.whole = false;
                          this.cursor = this.bounds()[0];
                        }}
                      >
                        Corner</button
                      ><button
                        class="secondary ${this.whole ? "on" : ""}"
                        @click=${() => {
                          this.whole = true;
                          this.cursor = 0;
                        }}
                      >
                        Full lap
                      </button>
                    </div>
                    <span class="station"
                      >${Math.round(this.cursor)} m /
                      ${Math.round(this.track!.road.trackLength)} m</span
                    >
                  </div>
                </div>`
            : html`<div class="loading">${this.status}</div>`}
        </section>
        <aside class="sidebar">
          <section class="panel">
            <h2>Pick your corner</h2>
            <label for="corner">Road Atlanta</label
            ><select
              id="corner"
              .value=${String(this.corner)}
              @change=${(e: Event) =>
                this.selectCorner(+(e.target as HTMLSelectElement).value)}
            >
              ${this.track?.corners.map(
                (c, i) =>
                  html`<option value=${i} ?selected=${i === this.corner}>
                    ${c.name}
                  </option>`,
              )}
            </select>
            <div class="status" role="status">${this.status}</div>
            <p>
              Measured edges · 61.4% seen on both sides. Flat-road model;
              elevation and banking are not included.
            </p>
          </section>
          <section class="panel">
            <button
              class="reset"
              @click=${() => {
                this.car = { ...LMP2 };
                this.compute();
              }}
            >
              Reset
            </button>
            <h2>Find the balance</h2>
            ${this.slider("mu", "Tyre grip", 1.1, 2.3, 0.025)}${this.slider(
              "clA",
              "Downforce · ClA",
              1.5,
              7,
              0.1,
              1,
              "m²",
            )}${this.slider(
              "power",
              "Wheel power",
              250000,
              450000,
              5000,
              1000,
              "kW",
            )}${this.slider("cdA", "Drag · CdA", 0.7, 2, 0.025, 1, "m²")}
            <details>
              <summary>Weight, tyres & load transfer</summary>
              ${this.slider(
                "mass",
                "Operating mass",
                930,
                1200,
                5,
                1,
                "kg",
              )}${this.slider(
                "exponent",
                "Tyre load exponent",
                0.75,
                1,
                0.01,
              )}${this.slider(
                "height",
                "CG height",
                0.15,
                0.5,
                0.01,
                1,
                "m",
              )}${this.slider(
                "brakeFront",
                "Front brake share",
                0.4,
                0.7,
                0.01,
              )}
              <p>
                Axle and aero front share 45%; roll load-transfer share 45%.
                Rear drive torque split equally. Exponent 1 disables load
                sensitivity.
              </p>
            </details>
            <p class="help">
              Exploratory coefficients, not a measured ORECA setup.
            </p>
            <button
              class="secondary"
              ?disabled=${!ready || this.busy}
              @click=${() => this.download()}
            >
              Export simulation ↓
            </button>
          </section>
          ${this.referencePanel()}
        </aside>
        ${ready ? this.cornerTable() : nothing}
        <details class="methods">
          <summary>What this model can tell you</summary>
          <div class="cols">
            <div>
              <p>
                <b>Three views of the same car.</b> The point model has one grip
                budget. The axle model adds longitudinal transfer, tyre load
                sensitivity, rear-only drive and brake balance. Four tyres add
                lateral load transfer and equal rear drive torque. Lateral
                forces satisfy quasi-steady axle yaw balance.
              </p>
              <p>
                This is a fixed-path quasi-steady comparison, not a full
                transient two-track simulator. There are no yaw/slip states,
                bumps, kerbs, suspension or thermal dynamics. Four circles show
                modelled loads, not measured tyre forces.
              </p>
            </div>
            <div>
              <p>
                <b>Geometry and uncertainty.</b> The line is the atlas’s
                precomputed minimum-curvature GT3 line, reused for all three
                models. It is not an LMP2 time-optimal path. Curvature is
                smoothed over 4 m. Road Atlanta has interpolated edge spans and
                1.06 m stated absolute CE95.
              </p>
              <p>
                Mass 1000 kg and 400 kW wheel power are initial operating
                assumptions. ORECA’s
                <a
                  href="https://www.oreca.com/wp-content/uploads/2025/06/Media-Kit-24h-of-Le-Mans-25.pdf"
                  target="_blank"
                  rel="noopener"
                  >2025 technical sheet</a
                >
                supplies the 3.005 m wheelbase and approximate track width.
                Fitting adjusts four effective parameters against training speed
                profiles; it does not identify the actual aero map or tyre law.
                High correlation can coexist with substantial speed and time
                errors.
              </p>
            </div>
          </div>
          <p>
            Inspired by
            <a
              href="https://x.com/m_lubieniecki/status/2107081419101016159"
              target="_blank"
              rel="noopener"
              >Marek Lubieniecki’s model comparison</a
            >. Independently implemented in TypeScript; not a reproduction of
            his solver or results.
          </p>
        </details>
      </main>
      <footer>
        Track Atlas · geometry © contributors, ODbL · browser-only computation
        · no reference lap uploads
      </footer>`;
  }
}
customElements.define("lap-lab", LapLab);
