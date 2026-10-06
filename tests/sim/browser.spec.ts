import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
test("loads three models, changes corners, plays and resolves parameter changes", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/sim/");
  await expect(page.locator(".grip")).toHaveCount(3);
  await expect(page.locator(".status")).toContainText("Ready");
  await expect(page.locator("#corner")).toHaveValue("7");
  await page.locator("#corner").selectOption("0");
  await expect(page.locator("h1")).toContainText("T1");
  const before = await page.locator(".speed-readout").first().textContent();
  await page.getByRole("button", { name: "▶ Play", exact: true }).click();
  await page.waitForTimeout(250);
  await page.getByRole("button", { name: "Ⅱ Pause", exact: true }).click();
  expect(await page.locator(".speed-readout").first().textContent()).not.toBe(
    before,
  );
  const lap = await page.locator(".lap-label").first().textContent();
  await page.locator("#mu").fill("1.8");
  await page.locator("#mu").dispatchEvent("input");
  await expect(page.locator(".lap-label").first()).not.toHaveText(lap!);
  await page.getByRole("button", { name: "Full lap", exact: true }).click();
  await expect(page.getByLabel("Lap position")).toHaveAttribute("min", "0");
  expect(errors).toEqual([]);
});
test("imports a local reference, computes metrics, rejects incomplete car settings", async ({
  page,
}) => {
  await page.goto("/sim/");
  await expect(page.locator(".grip")).toHaveCount(3);
  const ref = {
    name: "Synthetic test fixture",
    track: "road-atlanta",
    distance_m: Array.from({ length: 101 }, (_, i) => i * 40.84),
    speed_kmh: Array.from(
      { length: 101 },
      (_, i) => 190 + 20 * Math.sin(i / 10),
    ),
    time_s: Array.from({ length: 101 }, (_, i) => i * 0.77),
  };
  const requests: string[] = [];
  page.on("request", (r) => requests.push(r.url()));
  await page
    .getByLabel("Load reference laps")
    .setInputFiles({
      name: "synthetic.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(ref)),
    });
  await expect(page.locator("#reference")).toBeVisible();
  await expect(page.locator(".reference-stats b")).toHaveCount(4);
  await expect(page.locator(".trace-legend")).toContainText("Recorded lap");
  expect(requests.filter((u) => !u.includes("fonts."))).toEqual([]);
  await page
    .getByLabel("Load reference laps")
    .setInputFiles({
      name: "bad.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify({ car: {}, laps: [ref] })),
    });
  await expect(page.getByRole("alert")).toContainText("Invalid mass");
});
test("mobile layout fits the viewport and supports scrubbing", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/sim/");
  await expect(page.locator(".grip")).toHaveCount(3);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.getByLabel("Lap position").fill("2080");
  await page.getByLabel("Lap position").dispatchEvent("input");
  await expect(page.locator(".station")).toContainText("2080");
});
test("portable preview runs inside an opaque sandboxed iframe", async ({
  page,
}) => {
  execFileSync("bun", [
    "scripts/sim/standalone.ts",
    ".private/test-standalone.html",
  ]);
  await page.setContent(
    '<iframe sandbox="allow-scripts" style="width:1100px;height:900px"></iframe>',
  );
  await page.locator("iframe").evaluate(
    (el, content) => {
      (el as HTMLIFrameElement).srcdoc = content;
    },
    readFileSync(".private/test-standalone.html", "utf8"),
  );
  await expect(page.frameLocator("iframe").locator(".grip")).toHaveCount(3);
  await expect(page.frameLocator("iframe").locator(".status")).toContainText(
    "Ready",
  );
});
