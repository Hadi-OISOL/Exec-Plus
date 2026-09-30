/* Use case: Verifies deployed study persistence for the approved eight-user private demo.
What it does: Creates fictional receipts, then exercises concurrent browser studies and pins without logging secrets. */

import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { chromium, expect as baseExpect } from "@playwright/test";

const expect = baseExpect.configure({ timeout: 90_000 });
const [sessionsPath, outputPath] = process.argv.slice(2);
if (!sessionsPath || !outputPath)
  throw new Error("Pass private session and report paths");
const sessions = JSON.parse(await readFile(sessionsPath, "utf8"));
assert.equal(sessions.scope, "private-fictional-demo");
assert.equal(sessions.accounts.length, 8);
const post = (body) => ({ method: "POST", body: JSON.stringify(body) });
const browser = await chromium.launch({ headless: true });
let results;
try {
  results = await Promise.all(
    sessions.accounts.map(async (account, index) => {
      const started = performance.now();
      let stage = "fictional_source";
      const context = await browser.newContext();
      const page = await context.newPage();
      page.setDefaultTimeout(90_000);
      async function api(path, options = {}) {
        const response = await fetch(`http://localhost:18401${path}`, {
          signal: AbortSignal.timeout(90_000),
          ...options,
          headers: {
            Authorization: `Bearer ${account.token}`,
            "Content-Type": "application/json",
            ...options.headers,
          },
        });
        if (!response.ok) throw new Error(`API ${response.status}`);
        return response.status === 204 ? undefined : response.json();
      }
      try {
        const workspace = await api(
          "/workspaces",
          post({
            name: `Fictional study walkthrough ${index + 1}`,
            seat_limit: 3,
          }),
        );
        const dataset = await api(
          `/workspaces/${workspace.id}/datasets`,
          post({ name: "Fictional exact receipts" }),
        );
        const prefix = `/workspaces/${workspace.id}/datasets/${dataset.id}`;
        const upload = await api(
          `${prefix}/uploads?filename=fictional-study.csv`,
          {
            method: "POST",
            headers: { "Content-Type": "text/csv" },
            body: "city,amount\nKarachi,0.10\nLahore,0.20\n",
          },
        );
        const root = `${prefix}/uploads/${upload.id}`;
        const meaning = await api(`${root}/understanding`);
        meaning.definition.grain = "record";
        meaning.definition.domain = "sales";
        meaning.definition.columns.find(
          (column) => column.name === "amount",
        ).currency = "PKR";
        await api(
          `${root}/understanding`,
          post({
            revision_id: meaning.revision_id,
            expected_version: meaning.version,
            state: "confirmed",
            definition: meaning.definition,
          }),
        );
        stage = "sign_in";
        await page.goto("http://localhost:18400/workspace");
        await page.getByLabel("Session token").fill(account.token);
        await page
          .getByRole("button", { name: "Sign in", exact: true })
          .click();
        await expect(
          page.getByText(`Signed in as ${account.email}`),
        ).toBeVisible();
        await page.getByLabel("Current workspace").selectOption(workspace.id);
        await page
          .getByLabel("Dataset", { exact: true })
          .selectOption(dataset.id);
        await page
          .getByRole("navigation", { name: "Workspace navigation" })
          .getByRole("button", { name: "Studies & dashboards", exact: true })
          .click();
        const panel = page.getByRole("region", {
          name: "Studies and dashboards",
        });
        stage = "study_exact_result";
        await panel
          .getByLabel("Study name (optional)")
          .fill("Exact fictional receipts");
        await panel
          .locator(".studySuggestion")
          .filter({
            has: page.getByRole("heading", {
              name: "What is the sum of amount?",
              exact: true,
            }),
          })
          .getByRole("button", { name: "Run & save study" })
          .click();
        await expect(panel.locator(".studyValue")).toHaveText("0.300000000000");
        stage = "persistent_pin";
        await panel
          .getByLabel("Dashboard name", { exact: true })
          .fill("Fictional sales review");
        await panel
          .getByRole("button", { name: "Create study dashboard" })
          .click();
        await panel.getByRole("button", { name: "Pin this result" }).click();
        await expect(panel.getByRole("status")).toContainText("Result pinned");
        await panel
          .getByRole("button", {
            name: "Open dashboard Fictional sales review",
          })
          .click();
        await expect(
          page
            .getByRole("region", {
              name: "Pinned dashboard: Fictional sales review",
            })
            .locator(".studyValue"),
        ).toHaveText("0.300000000000");
        stage = "version_rerun";
        await panel
          .getByRole("button", { name: "Rerun on selected snapshot" })
          .click();
        await expect(
          panel.getByRole("button", { name: "Open version 2", exact: true }),
        ).toBeVisible();
        await panel
          .getByRole("button", { name: "Open version 1", exact: true })
          .click();
        await expect(panel.locator(".studyResult").first()).toContainText(
          "Version 1",
        );
        stage = "mobile";
        await page.setViewportSize({ width: 390, height: 844 });
        await page.emulateMedia({ reducedMotion: "reduce" });
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth + 1,
          ),
          true,
        );
        if (index === 0)
          await page.screenshot({
            path: outputPath.replace(/\.json$/, ".png"),
            fullPage: true,
          });
        return {
          user: index + 1,
          passed: true,
          stage: "complete",
          elapsed_ms: Math.round(performance.now() - started),
        };
      } catch (error) {
        return {
          user: index + 1,
          passed: false,
          stage,
          error: error?.name || "Error",
        };
      } finally {
        await context.close();
      }
    }),
  );
} finally {
  await browser.close();
}
const report = {
  scope: "private-fictional-demo",
  created_at: new Date().toISOString(),
  concurrent_browsers: 8,
  passed: results.filter((item) => item.passed).length,
  total: results.length,
  results,
};
await writeFile(outputPath, JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report));
process.exitCode = report.passed === report.total ? 0 : 1;
