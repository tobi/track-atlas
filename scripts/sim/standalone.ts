/** A portable preview; optional reference data stay in the explicitly chosen
 * output file. Never run this with private laps into site/. */
import { resolve } from "node:path";
import { mkdir } from "node:fs/promises";
const root = resolve(import.meta.dir, "../.."),
  output = resolve(process.argv[2] || ".private/lap-lab.html"),
  referencePath = process.argv[3];
if (referencePath && output.startsWith(resolve(root, "site") + "/"))
  throw new Error(
    "Private preview must be written outside the published site directory",
  );
const geometry = await Promise.all(
  ["gp.geojson", "gp.surface.geojson"].map((f) =>
    Bun.file(`${root}/tracks/road-atlanta/raw/layers/${f}`).json(),
  ),
);
const reference = referencePath ? await Bun.file(referencePath).json() : null;
const worker = await Bun.file(`${root}/site/sim/dist/worker.js`).text(),
  app = await Bun.file(`${root}/site/sim/dist/app.js`).text(),
  css = await Bun.file(`${root}/site/sim/style.css`).text();
const safe = (s: string) => s.replaceAll("</script", "<\\/script");
const boot = `globalThis.__LAP_LAB_BOOT__=${safe(JSON.stringify({ geometry, reference }))};globalThis.__LAP_LAB_BOOT__.worker=URL.createObjectURL(new Blob([${safe(JSON.stringify(worker))}],{type:'text/javascript'}));`;
const html = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Road Atlanta · LMP2 Lap Lab${reference ? " · private reference laps" : ""}</title><style>${css}</style><body><lap-lab></lap-lab><script>${boot}</script><script type="module">${safe(app)}</script></body></html>`;
await mkdir(resolve(output, ".."), { recursive: true });
await Bun.write(output, html);
console.log(output, html.length, "bytes");
