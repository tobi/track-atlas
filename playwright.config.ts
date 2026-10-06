import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests/sim",
  testMatch: "*.spec.ts",
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:4173",
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    },
  },
  webServer: {
    command: "bun run build:sim && bun run serve:sim",
    url: "http://127.0.0.1:4173/sim/",
    reuseExistingServer: !process.env.CI,
  },
});
