/* Use case: Exercises "Build a prediction model" through the real UI and backend.
What it does: Builds a model, checks the honest verdict, leakage switches, exact reopening and narrow layouts. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { finishInitialReview } from "./workspace-helpers";

test("prediction model shows an honest verdict and reopens exactly", async ({ page }) => {
  test.setTimeout(180_000);
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `predict-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  const headers = { Authorization: `Bearer ${token}` }; const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const csv = "outcome,visits,channel,lead_id,spend\n" + Array.from({ length: 300 }, (_, i) => {
    const visits = (i * 7) % 21, channel = ["web", "phone", "partner"][i % 3], noise = ((i * 37) % 11) / 5 - 1;
    return `${(visits - 10) / 4 + (channel === "partner" ? 0.8 : 0) + noise > 1 ? "yes" : "no"},${visits},${channel},L${String(i).padStart(5, "0")},${100 + ((i * 13) % 30)}`;
  }).join("\n") + "\n";
  await page.goto("/workspace"); await page.getByLabel("Session token").fill(token); await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "leads.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click(); await finishInitialReview(page);
  const wid = await page.getByLabel("Current workspace").inputValue(), did = await page.getByLabel("Dataset", { exact: true }).inputValue(), uid = await page.getByLabel("Profile upload").inputValue();
  const root = `http://127.0.0.1:8001/workspaces/${wid}/datasets/${did}/uploads/${uid}`, runsRoot = `http://127.0.0.1:8001/workspaces/${wid}/datasets/${did}/decision-analysis`;
  const meaning = await (await page.request.get(`${root}/understanding`, { headers })).json();
  const confirmed = await page.request.post(`${root}/understanding`, { headers, data: { revision_id: meaning.revision_id, expected_version: meaning.version, state: "confirmed", definition: { ...meaning.definition, grain: "record", columns: meaning.definition.columns.map((c: { name: string; role: string }) => c.role === "metric" ? { ...c, unit: "units", currency: "" } : c) } } });
  expect(confirmed.status(), await confirmed.text()).toBe(201);
  await page.getByRole("radio", { name: "Expert", exact: true }).check();
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Anomalies & decisions", exact: true }).click();
  await page.getByRole("combobox", { name: "Analysis method", exact: true }).selectOption("prediction");
  const panel = page.getByRole("region", { name: "Build a prediction model", exact: true });
  await expect(panel.getByRole("checkbox", { name: /lead_id/ })).toBeDisabled();
  await panel.getByLabel("Model name", { exact: true }).fill("Who will convert?");
  const save = page.waitForResponse(r => r.url().endsWith("/prediction-models") && r.request().method() === "POST");
  await panel.getByRole("button", { name: "Build and test the model", exact: true }).click();
  const created = await save; expect(created.status()).toBe(201); const saved = await created.json();
  const result = panel.getByRole("region", { name: "Prediction model result", exact: true });
  await expect(result).toContainText(saved.run.result.verdict.text);
  await expect(result).toContainText("associated with, not a cause");
  await expect(result.getByRole("region", { name: "Scores on held-back rows" })).toContainText(saved.run.result.metrics.auc);
  for (const width of [1440, 390, 320]) { await page.setViewportSize({ width, height: 1000 }); await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true); }
  await panel.getByRole("button", { name: "Who will convert?", exact: true }).click();
  await expect(panel).toContainText("matches exactly");
  const opened = await (await page.request.get(`${runsRoot}/${saved.run.id}`, { headers })).json(); expect(opened.run).toEqual(saved.run);
  expect(errors).toEqual([]);
});
