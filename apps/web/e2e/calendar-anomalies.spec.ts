/* Use case: Verifies explicit seasonal and two-window checks against real source evidence.
What it does: Exercises save/reload recovery, immutable replay, review, export and accessible narrow chart layouts. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { finishInitialReview } from "./workspace-helpers";

const api = "http://127.0.0.1:8001";
for (const method of ["seasonal", "drift"] as const) test(`${method} calendar checks retain exact private periods, reviews and exports`, async ({ page }) => {
  test.setTimeout(180_000);
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `calendar-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  const headers = { Authorization: `Bearer ${token}` };
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error" && /same key|unique.*key/i.test(message.text())) errors.push(message.text()); });
  const csv = "day,region,amount\n" + Array.from({ length: 49 }, (_, index) => `${new Date(Date.UTC(2020, 0, 1 + index)).toISOString().slice(0, 10)},North,${10 + (index % 7) * 20 + (index === 28 ? 100 : 0)}`).join("\n") + "\n";
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "calendar-example.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  const wid = await page.getByLabel("Current workspace").inputValue();
  const did = await page.getByLabel("Dataset", { exact: true }).inputValue();
  const uid = await page.getByLabel("Profile upload").inputValue();
  const root = `${api}/workspaces/${wid}/datasets/${did}/uploads/${uid}`;
  const runsRoot = `${api}/workspaces/${wid}/datasets/${did}/decision-analysis`;
  const meaning = await (await page.request.get(`${root}/understanding`, { headers })).json();
  const savedMeaning = await page.request.post(`${root}/understanding`, { headers, data: { revision_id: meaning.revision_id, expected_version: meaning.version, state: "confirmed", definition: { ...meaning.definition, grain: "record", columns: meaning.definition.columns.map((column: { name: string }) => column.name === "amount" ? { ...column, unit: "", currency: "USD" } : column) } } });
  expect(savedMeaning.status()).toBe(201);
  const confirmed = await (await page.request.get(`${root}/understanding`, { headers })).json();
  await page.getByRole("radio", { name: "Expert", exact: true }).check();
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Anomalies & decisions", exact: true }).click();
  await page.getByRole("combobox", { name: "Analysis method", exact: true }).selectOption(method);
  const panel = page.getByRole("region", { name: "Calendar analysis", exact: true });
  await panel.getByLabel("Analysis name", { exact: true }).fill(`Explicit ${method}`);
  await panel.getByRole("combobox", { name: "Measure", exact: true }).selectOption("amount");
  await panel.getByRole("combobox", { name: "Date field", exact: true }).selectOption("day");
  await panel.getByLabel(method === "seasonal" ? "Coverage starts" : "Reference window starts", { exact: true }).fill("2020-01-01");
  await panel.getByLabel(method === "seasonal" ? "Coverage ends" : "Reference window ends", { exact: true }).fill(method === "seasonal" ? "2020-02-18" : "2020-01-14");
  if (method === "seasonal") await panel.getByLabel("Last training period", { exact: true }).fill("2020-01-28");
  else {
    await panel.getByLabel("Comparison window starts", { exact: true }).fill("2020-01-29");
    await panel.getByLabel("Comparison window ends", { exact: true }).fill("2020-02-11");
    await panel.getByLabel("Minimum cumulative share separation", { exact: false }).fill("0.05");
  }
  const confirmation = panel.getByRole("checkbox", { name: "I confirm these windows", exact: false });
  const calculate = panel.getByRole("button", { name: "Calculate and save privately", exact: true });
  await expect(calculate).toBeDisabled();
  await confirmation.check();
  await panel.getByLabel("Analysis name", { exact: true }).fill(`Explicit ${method} final`);
  await expect(confirmation).not.toBeChecked();
  await confirmation.check();
  let failSave = method === "seasonal";
  let failHistory = true;
  const routeName = method === "seasonal" ? "seasonal-anomalies" : "distribution-drift";
  await page.route(`**/decision-analysis/${routeName}`, route => failSave ? route.fulfill({ status: 503, json: { error: { message: "Temporary calendar save failure" } } }) : route.continue());
  await page.route(runsRoot, route => failHistory ? route.fulfill({ status: 503, json: { error: { message: "Temporary calendar history failure" } } }) : route.continue());
  if (failSave) {
    await calculate.click();
    await expect(panel.getByRole("alert")).toContainText("Temporary calendar save failure");
    await expect(calculate).toBeEnabled();
    failSave = false;
  }
  const responsePromise = page.waitForResponse(response => response.url().endsWith(`/decision-analysis/${routeName}`) && response.status() === 201);
  await calculate.click();
  const body = await (await responsePromise).json();
  if (method === "seasonal") expect(body.run.result.findings.map((item: { period: string }) => item.period)).toEqual(["2020-01-29", "2020-02-05"]);
  else {
    expect(body.run.result.maximum_cdf_separation).toMatchObject({ numerator: "1", denominator: "14", display_exact: false });
    expect(body.run.result.wasserstein_distance).toMatchObject({ numerator: "50", denominator: "7", display_exact: false });
    expect(body.run.result.review_flag).toBe(true);
  }
  await expect(panel.getByRole("alert")).toContainText("Your result is saved. History could not reload");
  await expect(calculate).toBeDisabled();
  failHistory = false;
  await panel.getByRole("button", { name: "Reload saved results", exact: true }).click();
  await expect(panel.getByRole("region", { name: "Saved calendar checks", exact: true })).toContainText(`Explicit ${method} final`);
  const result = panel.getByRole("region", { name: "Saved calendar result", exact: true });
  await result.getByRole("button", { name: "Replay original calendar evidence", exact: true }).click();
  await expect(panel).toContainText("The original result and every receipt were verified");
  if (method === "seasonal") {
    await result.getByRole("combobox", { name: "Values shown on the plot", exact: true }).selectOption("expected");
    await expect(result.locator('[data-visualization="Earlier-season comparison reference"]')).toContainText("of 21 returned rows");
    await expect(result).toContainText("Earlier training periods were not scored");
  }
  await result.getByLabel("Reason for your review", { exact: true }).fill("Fictional review: inspect source context before changing anything.");
  await result.getByRole("button", { name: "Save private review", exact: true }).click();
  await expect(panel).toContainText("Review saved. No source values or detection rules changed");
  await result.getByText("Download result", { exact: true }).click();
  await result.getByRole("combobox", { name: "File type", exact: true }).selectOption("xlsx");
  const downloadPromise = page.waitForEvent("download");
  await result.getByRole("button", { name: "Download Excel", exact: true }).click();
  const download = await downloadPromise;
  expect(readFileSync((await download.path())!).subarray(0, 2).toString()).toBe("PK");
  const output = "../../data/verification/2026-10-16/remaining-work/calendar-browser";
  mkdirSync(output, { recursive: true });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    try { await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true); }
    catch (cause) { writeFileSync(`${output}/${method}-overflow-${width}.json`, JSON.stringify(await page.evaluate(() => [...document.querySelectorAll("body *")].flatMap(element => { const r = element.getBoundingClientRect(); return r.width > 0 && r.right > innerWidth + 1 ? [{ tag: element.tagName, classes: String(element.className), right: r.right, width: r.width }] : []; })), null, 2)); throw cause; }
    await result.screenshot({ path: `${output}/${method}-${width}.png` });
    const chart = result.locator('[data-chart-renderer="apache-echarts"]').first();
    await expect(chart.locator("svg")).toBeVisible();
    await expect(chart.locator('svg path[d^="M1 0A1 1"]')).toHaveCount(method === "seasonal" ? 21 : 28);
    expect(await chart.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
    await chart.screenshot({ path: `${output}/${method}-plot-${width}.png` });
  }
  const reopened = await (await page.request.get(`${runsRoot}/${body.run.id}`, { headers })).json();
  expect(reopened.run).toEqual(body.run);
  expect(reopened.reviews).toHaveLength(1);
  await page.getByRole("combobox", { name: "Analysis method", exact: true }).selectOption("anomalies");
  await expect(page.getByRole("region", { name: "Private analysis history", exact: true })).not.toContainText(`Explicit ${method} final`);
  expect((await (await page.request.get(`${root}/content`, { headers })).body()).toString()).toBe(csv);
  expect(await (await page.request.get(`${root}/understanding`, { headers })).json()).toEqual(confirmed);
  expect(errors).toEqual([]);
});
