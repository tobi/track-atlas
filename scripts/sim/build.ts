import { mkdir, copyFile } from "node:fs/promises";
import { resolve } from "node:path";
const root = resolve(import.meta.dir, "../..");
await mkdir(`${root}/site/geojson`, { recursive: true });
for (const suffix of ["gp.geojson", "gp.surface.geojson"])
  await copyFile(
    `${root}/tracks/road-atlanta/raw/layers/${suffix}`,
    `${root}/site/geojson/road-atlanta_${suffix}`,
  );
const result = await Bun.build({
  entrypoints: [`${root}/site/sim/app.ts`, `${root}/site/sim/worker.ts`],
  outdir: `${root}/site/sim/dist`,
  target: "browser",
  format: "esm",
  minify: true,
  sourcemap: "external",
  conditions: ["browser", "production"],
  define: { "process.env.NODE_ENV": '"production"' },
});
if (!result.success) {
  console.error(result.logs);
  process.exit(1);
}
console.log("Lap Lab built:", result.outputs.map((x) => x.path).join(", "));
