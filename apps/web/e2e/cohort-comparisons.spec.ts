/* Use case: Verifies a selected group comparison through the private conversation UI.
What it does: Checks actual calculated values, saved reopening, next-question actions,
missing-value labels and three responsive layouts using fictional agricultural rows. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { openLatestChat } from "./workspace-helpers";

const api = "http://127.0.0.1:8001";
const question = 'Compare records where "Crop_Growth_Stage" equals "Harvest" with other records';

async function prepare(page: Page, numeric: boolean) {
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `cohort-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  const headers = { Authorization: `Bearer ${token}` };
  const workspace = await page.request.post(`${api}/workspaces`, { headers, data: { name: "Fictional field observations", seat_limit: 3 } });
  expect(workspace.status()).toBe(201);
  const wid = (await workspace.json()).id;
  const dataset = await page.request.post(`${api}/workspaces/${wid}/datasets`, { headers, data: { name: "Fictional crop groups" } });
  expect(dataset.status()).toBe(201);
  const did = (await dataset.json()).id;
  let csv = "id,Crop_Growth_Stage,Crop_Type,Rainfall_mm,Temperature_C,Previous_Irrigation_mm\n";
  for (let i = 0; i < 60; i++) {
    const harvest = i < 20, seedling = i >= 20 && i < 30;
    const stage = harvest ? "Harvest" : seedling ? "Seedling" : "Growing";
    const crop = harvest ? i < 15 ? "Rice" : "Wheat" : i < 25 || (i >= 30 && i < 35) ? "Rice" : "Wheat";
    csv += `${i + 1},${stage},${crop},${(harvest ? 20 : seedling ? 10 : 30) + i % 5},${20 + i % 5},${harvest ? i < 4 ? "5" : "" : "6"}\n`;
  }
  csv += "61,,Rice,999,999,999\n";
  const uploaded = await page.request.post(`${api}/workspaces/${wid}/datasets/${did}/uploads?filename=fictional-crop-groups.csv`, { headers: { ...headers, "Content-Type": "text/csv" }, data: Buffer.from(csv) });
  expect(uploaded.status()).toBe(201);
  const uid = (await uploaded.json()).id;
  const root = `/workspaces/${wid}/datasets/${did}/uploads/${uid}`;
  const current = await (await page.request.get(api + root + "/understanding", { headers })).json();
  const units: Record<string, string> = { Rainfall_mm: "mm", Temperature_C: "C", Previous_Irrigation_mm: "mm" };
  const confirmed = await page.request.post(api + root + "/understanding", { headers, data: {
    revision_id: current.revision_id, expected_version: current.version, state: "confirmed",
    definition: { ...current.definition, grain: "record", domain: "other", description: "Fictional observations, not a treatment experiment.", columns: current.definition.columns.map((column: { name: string }) => ({ ...column,
      role: column.name === "id" ? "identifier" : Object.hasOwn(units, column.name) ? "metric" : "dimension",
      meaning: `Recorded ${column.name}`, unit: numeric ? units[column.name] ?? "" : "", currency: "",
    })) },
  } });
  expect(confirmed.status()).toBe(201);
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByLabel("Current workspace")).toHaveValue(wid);
  await page.getByLabel("Dataset", { exact: true }).selectOption(did);
  await page.getByLabel("Profile upload").selectOption(uid);
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Ask Syntelio", exact: true }).click();
  return { headers, root };
}

async function askComparison(page: Page) {
  const response = page.waitForResponse(value => /\/jobs\/[^/]+\/result$/.test(value.url()) && value.request().method() === "GET");
  await page.getByLabel("Your question", { exact: true }).fill(question);
  await page.getByLabel("Your question", { exact: true }).press("Enter");
  const body = await (await response).json();
  expect(body.answer?.patterns?.version).toBe("cohort-comparison-v1");
  return body;
}

for (const numeric of [true, false]) {
  test(`selected cohort ${numeric ? "measures" : "category-only evidence"} stays grounded and reopens at three widths`, async ({ page }) => {
    test.setTimeout(180_000);
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    const { headers, root } = await prepare(page, numeric);
    const originalMeaning = await (await page.request.get(api + root + "/understanding", { headers })).json();
    const saved = await askComparison(page);
    const computed = saved.answer.patterns;
    expect(computed.coverage).toMatchObject({ source_rows: 61, filtered_rows: 61, target_rows: 20, other_rows: 40, missing_target_rows: 1 });
    const result = page.getByRole("region", { name: "Selected group comparison", exact: true });
    await expect(result).toContainText("all other nonmissing values of Crop_Growth_Stage");
    await expect(result).toContainText("do not explain why a difference happened");
    await expect(result.getByRole("region", { name: "Category mix comparison", exact: true })).toContainText("Crop_Type");
    if (numeric) {
      const rainfall = computed.numeric.find((item: { column: string }) => item.column === "Rainfall_mm");
      expect(Number(rainfall.target_mean)).toBe(22); expect(Number(rainfall.other_mean)).toBe(27); expect(Number(rainfall.difference)).toBe(-5);
      const rainCard = result.getByRole("article", { name: "Comparison of Rainfall_mm", exact: true });
      await expect(rainCard).toContainText(`${rainfall.difference} mm`);
      await expect(rainCard.getByRole("table")).toContainText(rainfall.target_mean);
      const equal = computed.numeric.find((item: { column: string }) => item.column === "Temperature_C");
      expect(Number(equal.difference)).toBe(0);
      await expect(result.getByRole("article", { name: "Comparison of Temperature_C", exact: true })).toContainText(`${equal.difference} C`);
      const sparse = result.getByRole("article", { name: "Comparison of Previous_Irrigation_mm", exact: true });
      await expect(sparse).toContainText("not enough comparable values");
      await expect(sparse.getByRole("table")).toBeVisible();
      await expect(sparse.locator(".patternBarChart")).toHaveCount(0);
    } else {
      expect(computed.status).toBe("insufficient_data");
      await expect(result).toContainText("not enough usable data for a supported numerical comparison");
      await expect(result.getByRole("heading", { name: "What we can compare for Harvest", exact: true })).toBeVisible();
      await expect(result.getByRole("region", { name: "Category counts for Crop_Type", exact: true })).toBeVisible();
    }
    await page.emulateMedia({ reducedMotion: "reduce" });
    const output = process.env.PLAYWRIGHT_JSON_OUTPUT_NAME ? join(dirname(process.env.PLAYWRIGHT_JSON_OUTPUT_NAME), "captures", "cohorts") : "../../data/verification/2026-10-17/two-phase/cohort-browser";
    mkdirSync(output, { recursive: true });
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      await result.locator(".patternOverview").scrollIntoViewIfNeeded();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      expect(await result.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
      if (numeric) await expect(result.locator(".patternFinding").first()).toHaveCSS("animation-name", "none");
      await page.screenshot({ path: join(output, `${numeric ? "measures" : "categories"}-overview-${width}.png`) });
      if (numeric) {
        const rain = result.getByRole("article", { name: "Comparison of Rainfall_mm", exact: true });
        await rain.getByRole("table").scrollIntoViewIfNeeded();
        await expect(rain.getByRole("table")).toBeVisible();
        await page.screenshot({ path: join(output, `measures-values-${width}.png`) });
      }
      const categories = result.getByRole("region", { name: "Category counts for Crop_Type", exact: true });
      await categories.scrollIntoViewIfNeeded();
      await expect(categories.getByRole("table")).toBeVisible();
      await page.screenshot({ path: join(output, `${numeric ? "measures" : "categories"}-mix-${width}.png`) });
      if (width <= 390) {
        await categories.focus();
        await page.keyboard.press("ArrowRight");
        await expect.poll(() => categories.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
      }
    }
    await result.getByText("Scope, method and source evidence", { exact: true }).click();
    await expect(result).toContainText(saved.answer.pattern_evidence.query_id);
    if (!numeric) await expect(result).toContainText("Fields left out");
    await result.getByText("Scope, method and source evidence", { exact: true }).click();
    await page.getByRole("button", { name: "New chat", exact: true }).click();
    const reopenedResponse = page.waitForResponse(value => value.url().endsWith(`/turns/${saved.turn.id}/answer`));
    await openLatestChat(page);
    expect((await (await reopenedResponse).json()).patterns).toEqual(computed);
    await expect(result).toContainText("Harvest");
    if (numeric) {
      const followup = computed.suggestions[0];
      expect(followup).toBe('Show records where "Crop_Growth_Stage" equals "Harvest"');
      let release: () => void = () => {}, dispatched: () => void = () => {};
      const held = new Promise<void>(resolve => { release = resolve; });
      const started = new Promise<void>(resolve => { dispatched = resolve; });
      await page.route(/\/threads\/[^/]+\/jobs$/, async route => {
        if (route.request().method() !== "POST") return route.continue();
        expect(route.request().postDataJSON().question).toBe(followup);
        dispatched(); await held; await route.continue();
      });
      const buttons = result.getByRole("group", { name: "Ask about this comparison", exact: true });
      const answerResponse = page.waitForResponse(value => /\/jobs\/[^/]+\/result$/.test(value.url()));
      try {
        await buttons.getByRole("button", { name: followup, exact: true }).click();
        await started;
        await expect(buttons.getByRole("button", { name: followup, exact: true })).toBeDisabled();
      } finally { release(); }
      const followupBody = await (await answerResponse).json();
      expect(followupBody.answer?.rows).toHaveLength(20);
      const stageIndex = followupBody.answer.columns.indexOf("Crop_Growth_Stage");
      expect(stageIndex).toBeGreaterThanOrEqual(0);
      expect(followupBody.answer.rows.every((row: string[]) => row[stageIndex] === "Harvest")).toBe(true);
    }
    expect(await (await page.request.get(api + root + "/understanding", { headers })).json()).toEqual(originalMeaning);
    expect(errors).toEqual([]);
  });
}
