/* Use case: Configures real-service browser acceptance tests.
What it does: Starts isolated API and web processes with the runner's temporary database and bucket. */

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  use: {
    baseURL: "http://127.0.0.1:3001",
    trace: "off",
    launchOptions: { args: ["--host-resolver-rules=MAP execplus.test 127.0.0.1"] },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "python3 -m uvicorn execplus.main:app --host 127.0.0.1 --port 8001 --no-access-log",
      cwd: "../..",
      url: "http://127.0.0.1:8001/health/ready",
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3001",
      env: { EXECPLUS_WEB_DEV_HOSTS: "execplus.test" },
      url: "http://127.0.0.1:3001",
      reuseExistingServer: false,
    },
  ],
});
