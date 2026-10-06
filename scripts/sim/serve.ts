import { resolve, sep } from "node:path";
const root = resolve(import.meta.dir, "../../site"),
  port = Number(process.env.PORT || 4173);
const server = Bun.serve({
  hostname: "127.0.0.1",
  port,
  async fetch(req) {
    let pathname: string;
    try {
      pathname = decodeURIComponent(new URL(req.url).pathname);
    } catch {
      return new Response("Bad path", { status: 400 });
    }
    const path = resolve(
      root,
      "." + pathname + (pathname.endsWith("/") ? "index.html" : ""),
    );
    if (!path.startsWith(root + sep))
      return new Response("Not found", { status: 404 });
    const file = Bun.file(path);
    if (!(await file.exists()))
      return new Response("Not found", { status: 404 });
    return new Response(file);
  },
});
console.log(`Lap Lab: ${server.url}sim/`);
