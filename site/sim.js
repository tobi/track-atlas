/* Track Atlas — Three.js mini driving sim.
 *
 * Drives a car around a track's real centerline (from the layout GeoJSON). The
 * speed profile is a quasi-static lap solver: per-point cornering limit from
 * curvature (v = sqrt(a_lat / kappa)), then a braking pass (back) and a traction
 * pass (forward) bounded by the car class's decel/accel. The track surface is
 * coloured by what the car is doing there — red = braking, green = on throttle,
 * amber = at the cornering limit. Cameras: chase (behind) or isometric.
 *
 * Exposes window.TrackSim with load(gj), setClass, setCamera, toggle.
 */
const TrackSim = (function () {
  // m/s and m/s^2. Distinct feel per class: a Hypercar brakes/grips/accelerates
  // far harder than a 1936 BMW 328.
  const CLASSES = {
    lmph:   { label: "LMPh",    color: 0xff3b30, vmax: 90, alat: 34, abrake: 46, aaccel: 17, len: 4.9, wid: 2.0 },
    gt3:    { label: "GT3",     color: 0x3aa0ff, vmax: 78, alat: 27, abrake: 36, aaccel: 12, len: 4.6, wid: 2.0 },
    bmw328: { label: "BMW 328", color: 0xf5c542, vmax: 42, alat: 12, abrake: 11, aaccel: 4.5, len: 3.9, wid: 1.55 },
  };
  const C_BRAKE = 0xff3b30, C_THROTTLE = 0x35c759, C_CORNER = 0xffd60a;
  const HALF_W = 6;          // track half-width, metres
  const TIME = 1.0;          // sim time scale

  let host, renderer, scene, camera, car, ground, overview = null;
  let pts = [], tang = [], cum = [], speed = [], total = 0;
  let pos = 0, idx = 0, playing = true, camMode = "iso", cls = "gt3";
  let raf = null, last = 0, trackMesh = null;

  function dispose() {
    if (raf) cancelAnimationFrame(raf), raf = null;
    if (renderer) { renderer.dispose(); renderer.domElement.remove(); }
    renderer = scene = camera = car = ground = trackMesh = null;
    pts = []; tang = []; cum = []; speed = []; total = 0; pos = 0; idx = 0;
  }

  // GeoJSON lon/lat loop -> centred local metres on the XZ plane.
  function project(coords) {
    if (coords.length > 1 && coords[0][0] === coords[coords.length - 1][0]
        && coords[0][1] === coords[coords.length - 1][1]) coords = coords.slice(0, -1);
    const lat0 = coords.reduce((s, c) => s + c[1], 0) / coords.length;
    const R = 111320, k = Math.cos(lat0 * Math.PI / 180);
    const lon0 = coords.reduce((s, c) => s + c[0], 0) / coords.length;
    return coords.map((c) => [(c[0] - lon0) * k * R, (c[1] - lat0) * R]);
  }

  // Resample the loop to ~N evenly spaced points via a closed Catmull-Rom curve.
  function resample(xz, N) {
    const v = xz.map((p) => new THREE.Vector3(p[0], 0, p[1]));
    const curve = new THREE.CatmullRomCurve3(v, true, "catmullrom", 0.5);
    const p = curve.getSpacedPoints(N);  // N+1 points; last ≈ first on a closed curve
    p.pop();
    return p;
  }

  function buildProfile() {
    const N = pts.length;
    const ds = [];
    for (let i = 0; i < N; i++) ds[i] = pts[i].distanceTo(pts[(i + 1) % N]);
    cum = [0];
    for (let i = 0; i < N; i++) cum[i + 1] = cum[i] + ds[i];
    total = cum[N];

    // whole-track isometric framing (static overview)
    let mnx = Infinity, mxx = -Infinity, mnz = Infinity, mxz = -Infinity;
    pts.forEach((p) => { mnx = Math.min(mnx, p.x); mxx = Math.max(mxx, p.x); mnz = Math.min(mnz, p.z); mxz = Math.max(mxz, p.z); });
    const cx = (mnx + mxx) / 2, cz = (mnz + mxz) / 2, span = Math.max(mxx - mnx, mxz - mnz) || 200;
    overview = { pos: new THREE.Vector3(cx + span * 0.6, span * 0.85, cz + span * 0.6),
                 target: new THREE.Vector3(cx, 0, cz) };

    tang = [];
    for (let i = 0; i < N; i++) {
      const a = pts[(i - 1 + N) % N], b = pts[(i + 1) % N];
      tang[i] = new THREE.Vector3().subVectors(b, a).setY(0).normalize();
    }

    const k = CLASSES[cls];
    // cornering-limit target speed from curvature
    speed = [];
    for (let i = 0; i < N; i++) {
      const a = pts[(i - 1 + N) % N], b = pts[i], c = pts[(i + 1) % N];
      const t1 = new THREE.Vector3().subVectors(b, a).setY(0);
      const t2 = new THREE.Vector3().subVectors(c, b).setY(0);
      const ang = t1.angleTo(t2);
      const seg = (t1.length() + t2.length()) / 2 || 1;
      const kappa = ang / seg;                 // 1/radius
      speed[i] = kappa > 1e-4 ? Math.min(k.vmax, Math.sqrt(k.alat / kappa)) : k.vmax;
    }
    // braking pass (backwards, cyclic) then traction pass (forwards), few sweeps
    for (let s = 0; s < 3; s++)
      for (let i = N - 1; i >= 0; i--) {
        const j = (i + 1) % N;
        speed[i] = Math.min(speed[i], Math.sqrt(speed[j] * speed[j] + 2 * k.abrake * ds[i]));
      }
    for (let s = 0; s < 3; s++)
      for (let i = 0; i < N; i++) {
        const j = (i - 1 + N) % N;
        speed[i] = Math.min(speed[i], Math.sqrt(speed[j] * speed[j] + 2 * k.aaccel * ds[j]));
      }
  }

  function stateColor(i) {
    const d = speed[(i + 1) % speed.length] - speed[i];
    if (d < -0.4) return C_BRAKE;
    if (d > 0.4) return C_THROTTLE;
    return C_CORNER;
  }

  function buildTrack() {
    const N = pts.length;
    const positions = [], colors = [];
    const col = new THREE.Color();
    for (let i = 0; i < N; i++) {
      const j = (i + 1) % N;
      const ni = new THREE.Vector3(-tang[i].z, 0, tang[i].x);
      const nj = new THREE.Vector3(-tang[j].z, 0, tang[j].x);
      const li = new THREE.Vector3().copy(pts[i]).addScaledVector(ni, HALF_W);
      const ri = new THREE.Vector3().copy(pts[i]).addScaledVector(ni, -HALF_W);
      const lj = new THREE.Vector3().copy(pts[j]).addScaledVector(nj, HALF_W);
      const rj = new THREE.Vector3().copy(pts[j]).addScaledVector(nj, -HALF_W);
      // two triangles li,ri,lj  +  ri,rj,lj
      [li, ri, lj, ri, rj, lj].forEach((p) => positions.push(p.x, 0.02, p.z));
      col.setHex(stateColor(i));
      for (let v = 0; v < 6; v++) colors.push(col.r, col.g, col.b);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    trackMesh = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide }));
    scene.add(trackMesh);

    // bright centre racing line
    const lineG = new THREE.BufferGeometry().setFromPoints(
      pts.concat([pts[0]]).map((p) => new THREE.Vector3(p.x, 0.06, p.z)));
    scene.add(new THREE.Line(lineG, new THREE.LineBasicMaterial({ color: 0xffffff, opacity: 0.5, transparent: true })));
  }

  function buildCar() {
    const k = CLASSES[cls];
    car = new THREE.Group();
    const body = new THREE.Mesh(new THREE.BoxGeometry(k.wid, 0.6, k.len),
      new THREE.MeshStandardMaterial({ color: k.color, metalness: 0.4, roughness: 0.4 }));
    body.position.y = 0.5;
    const cabin = new THREE.Mesh(new THREE.BoxGeometry(k.wid * 0.7, 0.5, k.len * 0.4),
      new THREE.MeshStandardMaterial({ color: 0x111417 }));
    cabin.position.set(0, 0.95, -k.len * 0.05);
    car.add(body, cabin);
    scene.add(car);
  }

  function sample(distM) {
    const N = pts.length;
    let d = ((distM % total) + total) % total;
    while (cum[idx + 1] < d) idx = (idx + 1) % N;
    while (cum[idx] > d) idx = (idx - 1 + N) % N;
    const seg = cum[idx + 1] - cum[idx] || 1;
    const f = (d - cum[idx]) / seg;
    const a = pts[idx], b = pts[(idx + 1) % N];
    return {
      p: new THREE.Vector3().lerpVectors(a, b, f),
      t: tang[idx], v: speed[idx] + (speed[(idx + 1) % N] - speed[idx]) * f, i: idx,
    };
  }

  function placeCamera(s) {
    const up = new THREE.Vector3(0, 1, 0);
    if (camMode === "iso" && overview) {
      camera.position.copy(overview.pos);   // static framing of the whole track
      camera.lookAt(overview.target);
    } else {
      const behind = new THREE.Vector3().copy(s.p).addScaledVector(s.t, -15).add(new THREE.Vector3(0, 6.5, 0));
      camera.position.lerp(behind, 0.18);
      camera.lookAt(s.p.x + s.t.x * 8, 1.5, s.p.z + s.t.z * 8);
    }
  }

  function frame(t) {
    raf = requestAnimationFrame(frame);
    const dt = Math.min(0.05, (t - last) / 1000 || 0); last = t;
    const s = sample(pos);
    if (playing) pos += s.v * dt * TIME;
    car.position.copy(s.p);
    car.lookAt(s.p.x + s.t.x, 0, s.p.z + s.t.z);
    placeCamera(s);
    renderer.render(scene, camera);
    const hud = document.getElementById("simHud");
    if (hud) hud.textContent = `${CLASSES[cls].label} · ${Math.round(s.v * 3.6)} km/h`;
  }

  function resize() {
    if (!renderer || !host) return;
    const w = host.clientWidth, h = host.clientHeight || 460;
    renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix();
  }

  function load(gj) {
    if (typeof THREE === "undefined") return;
    host = document.getElementById("sim");
    if (!host) return;
    const outline = (gj.features || []).find((f) => f.properties && f.properties.role === "outline");
    if (!outline) { host.innerHTML = "<p class='muted' style='padding:14px'>No geometry to drive.</p>"; return; }
    dispose();

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0c12);
    camera = new THREE.PerspectiveCamera(55, 1, 0.5, 20000);
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    host.innerHTML = ""; host.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.75));
    const dir = new THREE.DirectionalLight(0xffffff, 0.9); dir.position.set(1, 2, 1); scene.add(dir);

    const xz = project(outline.geometry.coordinates);
    const target = Math.max(120, Math.min(700, Math.round(xz.length)));
    pts = resample(xz, target);
    buildProfile();

    ground = new THREE.Mesh(new THREE.PlaneGeometry(8000, 8000),
      new THREE.MeshStandardMaterial({ color: 0x10151b }));
    ground.rotation.x = -Math.PI / 2; ground.position.y = -0.05; scene.add(ground);

    buildTrack();
    buildCar();
    pos = 0; idx = 0; last = performance.now();
    resize();
    raf = requestAnimationFrame(frame);
  }

  function setClass(name) {
    if (!CLASSES[name] || !scene) { cls = name; return; }
    cls = name;
    if (car) { scene.remove(car); }
    buildProfile();
    if (trackMesh) { scene.remove(trackMesh); }
    // rebuild coloured surface + car for the new class
    const old = scene.children.filter((o) => o.type === "Line"); old.forEach((o) => scene.remove(o));
    buildTrack(); buildCar();
    syncButtons();
  }
  function setCamera(mode) { camMode = mode; syncButtons(); }
  function toggle() { playing = !playing; syncButtons(); }

  function syncButtons() {
    document.querySelectorAll("[data-sim-cls]").forEach((b) =>
      b.classList.toggle("on", b.dataset.simCls === cls));
    document.querySelectorAll("[data-sim-cam]").forEach((b) =>
      b.classList.toggle("on", b.dataset.simCam === camMode));
    const p = document.getElementById("simPlay"); if (p) p.textContent = playing ? "⏸ pause" : "▶ play";
  }

  window.addEventListener("resize", resize);
  return { load, setClass, setCamera, toggle, dispose, syncButtons, get cls() { return cls; }, get cam() { return camMode; } };
})();
window.TrackSim = TrackSim;
