import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

// The API serves the built SPA; tests/e2e/start_server.py prepares a throwaway database,
// fixture content and an admin, then listens on this port.
const PORT = Number(process.env.E2E_PORT ?? 8100);
const BASE_URL = `http://127.0.0.1:${PORT}`;

const repo = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
const venvPython = [".venv/Scripts/python.exe", ".venv/bin/python"]
  .map((p) => resolve(repo, p))
  .find((p) => existsSync(p));
const python = process.env.E2E_PYTHON ?? venvPython ?? "python";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  // One SQLite database behind one API process: run the tests one after the other.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: BASE_URL,
    locale: "en-GB",
    // The PWA service worker would cache pages between tests.
    serviceWorkers: "block",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `"${python}" tests/e2e/start_server.py`,
    cwd: repo,
    url: `${BASE_URL}/api/health`,
    timeout: 300_000,
    reuseExistingServer: !process.env.CI,
    env: { E2E_PORT: String(PORT) },
  },
});
