/* Use case: Protects the automatic overview and its explicit what-if handoff.
What it does: Uses synthetic source data, checks hidden internals and stale/error boundaries,
and verifies that an overview average remains the scenario's exact baseline. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { finishInitialReview, showIndividualCalculations } from "./workspace-helpers";

const api = "http://127.0.0.1:8001";

test("overview maps the file, keeps evidence optional, and carries an average into a declared what-if", async ({ page }) => {
  test.setTimeout(180_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `overview-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  const headers = { Authorization: `Bearer ${token}` };
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "fictional-moisture.csv", mimeType: "text/csv", buffer: Buffer.from("Crop_Type,Soil_Moisture\nWheat,10\nRice,20\nWheat,30\n") });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  const earlyOverview = page.getByRole("region", { name: "First reading of your data", exact: true });
  await expect(earlyOverview.getByRole("region", { name: "Data organisation diagram", exact: true })).toBeVisible();
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Ask Syntelio", exact: true }).click();
  await expect(page.getByLabel("Your question", { exact: true })).toBeVisible();
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Overview", exact: true }).click();
  await finishInitialReview(page);
  const root = `/workspaces/${await page.getByLabel("Current workspace").inputValue()}/datasets/${await page.getByLabel("Dataset", { exact: true }).inputValue()}/uploads/${await page.getByLabel("Profile upload").inputValue()}`;
  const source = await (await page.request.get(`${api}${root}/content`, { headers })).body();
  const overview = page.getByRole("region", { name: "First reading of your data", exact: true });
  await expect(overview.getByRole("button", { name: "Review data meaning", exact: true }).first()).toBeVisible();
  await expect(overview.getByRole("region", { name: "Data organisation diagram", exact: true })).toBeVisible();
  await expect(overview.getByRole("button", { name: /^What if Soil Moisture changes\?/ })).toHaveCount(0);
  const current = await (await page.request.get(`${api}${root}/understanding`, { headers })).json();
  expect((await page.request.post(`${api}${root}/understanding`, { headers, data: {
    revision_id: current.revision_id, expected_version: current.version, state: "confirmed",
    definition: { ...current.definition, grain: "record", columns: current.definition.columns.map((column: { name: string }) => column.name === "Soil_Moisture" ? { ...column, unit: "%", meaning: "Observed soil moisture" } : column) },
  } })).status()).toBe(201);
  const nav = page.getByRole("navigation", { name: "Workspace navigation" });
  await nav.getByRole("button", { name: "Ask Syntelio", exact: true }).click();
  const read = page.waitForResponse(response => response.url().endsWith(`${root}/discovery`) && response.status() === 200);
  await nav.getByRole("button", { name: "Overview", exact: true }).click();
  const briefing = await (await read).json();
  expect(briefing.scenario_metrics).toContainEqual({ metric: "Soil_Moisture", aggregation: "avg" });
  expect(briefing.diagram.nodes.filter((node: { kind: string }) => node.kind === "field").map((node: { label: string }) => node.label)).toEqual(expect.arrayContaining(["Soil_Moisture", "Crop_Type"]));
  for (const mode of ["Expert", "Simple"]) {
    await page.getByRole("radio", { name: mode, exact: true }).check();
    expect(await overview.locator("details[open]").count()).toBe(0);
  }
  await showIndividualCalculations(page);
  const evidence = overview.locator("details.findingEvidence").first();
  await evidence.locator(":scope > summary").focus();
  await page.keyboard.press("Enter");
  await expect(evidence).toHaveJSProperty("open", true);
  await page.keyboard.press("Enter");
  for (const theme of ["dark", "light"]) {
    await page.getByLabel("Appearance", { exact: true }).selectOption(theme);
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await expect(overview.getByRole("region", { name: "Data organisation diagram", exact: true })).toBeVisible();
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      const output = "../../data/verification/2026-10-19/proactive-overview/screenshots";
      mkdirSync(output, { recursive: true });
      await page.screenshot({ path: `${output}/overview-${theme}-${width}.png`, fullPage: true });
    }
  }
  await overview.getByRole("button", { name: /^What if Soil Moisture changes\?/ }).click();
  const scenario = page.getByRole("region", { name: "Scenario comparisons", exact: true });
  await expect(scenario.getByRole("combobox", { name: "Scenario measure", exact: true })).toHaveValue("Soil_Moisture");
  await expect(scenario.getByRole("combobox", { name: "Baseline calculation", exact: true })).toHaveValue("avg");
  const calculate = scenario.getByRole("button", { name: "Calculate and save comparison", exact: true });
  await expect(calculate).toBeDisabled();
  await scenario.getByLabel("Assumed value 1", { exact: true }).fill("25");
  await scenario.getByRole("checkbox", { name: "I confirm these are hypothetical", exact: false }).check();
  let posts = 0;
  page.on("request", request => { if (request.method() === "POST" && request.url().endsWith("/decision-analysis/scenarios")) posts += 1; });
  await page.route(`**${root.split("/uploads/")[0]}/decision-analysis`, route => route.fulfill({ status: 503, json: { error: { message: "History read temporarily unavailable" } } }));
  const saved = page.waitForResponse(response => response.url().endsWith("/decision-analysis/scenarios") && response.status() === 201);
  await calculate.click();
  const result = await (await saved).json();
  expect(Number(result.run.result.baseline)).toBe(20);
  expect(Number(result.run.result.alternatives[0].result)).toBe(25);
  expect(result.run.result.aggregation).toBe("avg");
  await expect(scenario.getByRole("region", { name: "Saved scenario result", exact: true })).toBeVisible();
  await expect(scenario.getByRole("alert")).toContainText("History read temporarily unavailable");
  await expect(calculate).toBeDisabled();
  expect(posts).toBe(1);
  expect(await (await page.request.get(`${api}${root}/content`, { headers })).body()).toEqual(source);
  expect(errors).toEqual([]);
});

test("switching sources abandons the previous briefing and failed reads stay empty until retry", async ({ page }) => {
  test.setTimeout(150_000);
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `overview-switch-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  const headers = { Authorization: `Bearer ${token}` };
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "first-source.csv", mimeType: "text/csv", buffer: Buffer.from("First_Category,first_measure\nAlpha,1\nBeta,2\n") });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  const first = await page.getByLabel("Profile upload").inputValue();
  const datasetRoot = `/workspaces/${await page.getByLabel("Current workspace").inputValue()}/datasets/${await page.getByLabel("Dataset", { exact: true }).inputValue()}`;
  const secondUpload = await page.request.post(`${api}${datasetRoot}/uploads?filename=second-source.csv`, { headers: { ...headers, "Content-Type": "text/csv" }, data: Buffer.from("Second_Category,second_measure\nGamma,30\nDelta,40\n") });
  expect(secondUpload.status()).toBe(201);
  const second = (await secondUpload.json()).id;
  await page.reload();
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const nav = page.getByRole("navigation", { name: "Workspace navigation" });
  await nav.getByRole("button", { name: "Overview", exact: true }).click();
  await page.getByLabel("Profile upload").selectOption(second);
  const overview = page.getByRole("region", { name: "First reading of your data", exact: true });
  await expect(overview).toContainText("second measure");
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  let observed!: () => void;
  const pending = new Promise<void>(resolve => { observed = resolve; });
  await page.route(`**${datasetRoot}/uploads/${first}/discovery`, async route => {
    const response = await route.fetch();
    observed();
    await Promise.race([held, new Promise(resolve => setTimeout(resolve, 20_000))]);
    await route.fulfill({ response }).catch(() => { /* The superseded request may already be cancelled. */ });
  });
  await page.getByLabel("Profile upload").selectOption(first);
  await Promise.race([pending, new Promise((_, reject) => setTimeout(() => reject(new Error("Old discovery request was not observed")), 15_000))]);
  await expect(overview).not.toContainText("second measure");
  await page.getByLabel("Profile upload").selectOption(second);
  await expect(overview).toContainText("second measure");
  release();
  await expect(overview).not.toContainText("first measure");
  let denied = true;
  await page.route(`**${datasetRoot}/uploads/${second}/discovery`, route => denied ? route.fulfill({ status: 403, json: { error: { code: "forbidden", message: "Briefing access denied for this test" } } }) : route.continue());
  await nav.getByRole("button", { name: "Ask Syntelio", exact: true }).click();
  await nav.getByRole("button", { name: "Overview", exact: true }).click();
  await expect(overview.getByRole("alert")).toContainText("Briefing access denied");
  await expect(overview.locator(".discoveryValue")).toHaveCount(0);
  await expect(overview.getByRole("region", { name: "Data organisation diagram", exact: true })).toHaveCount(0);
  denied = false;
  await overview.getByRole("button", { name: "Retry first reading", exact: true }).click();
  await expect(overview).toContainText("second measure");
  await expect(overview.getByRole("alert")).toHaveCount(0);
});
