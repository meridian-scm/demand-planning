import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against the full stack — frontend, backend, and a real
 * Postgres database — brought up via `docker compose up`. They are NOT
 * responsible for starting that stack (see the repo README for the exact
 * command); this config just points at wherever it's already running.
 */
export default defineConfig({
  testDir: "./tests",
  globalSetup: "./global-setup.ts",
  fullyParallel: false, // tests share one seeded database; run sequentially
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ["list"],
    ["junit", { outputFile: "reports/junit.xml" }],
    ["html", { outputFolder: "reports/html", open: "never" }],
  ],
  timeout: 30_000,
  expect: { timeout: 8_000 },
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
