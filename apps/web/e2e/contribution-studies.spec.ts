/* Use case: Verifies genuine period and mapped-file comparisons in the study UI.
What it does: Creates exact results through the API-backed form, inspects records,
shares and pins immutable evidence, downloads files and checks narrow layouts. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { expect, test, type Page } from "@playwright/test";

const api = "http://127.0.0.1:8001";
type Source = { did: string; uid: string; root: string };

async function seed(page: Page, token: string, wid: string, name: string, csv: string, amount: string, quantity: string): Promise<Source> {
  const headers = { Authorization: `Bearer ${token}` };
  const created = await page.request.post(`${api}/workspaces/${wid}/datasets`, { headers, data: { name } });
  expect(created.status()).toBe(201);
  const did = (await created.json()).id;
  const uploaded = await page.request.post(`${api}/workspaces/${wid}/datasets/${did}/uploads?filename=${name}.csv`, { headers: { ...headers, "Content-Type": "text/csv" }, data: Buffer.from(csv) });
  expect(uploaded.status()).toBe(201);
  const uid = (await uploaded.json()).id;
  const root = `/workspaces/${wid}/datasets/${did}/uploads/${uid}`;
  const current = await (await page.request.get(api + root + "/understanding", { headers })).json();
  const confirmed = await page.request.post(api + root + "/understanding", { headers, data: {
    revision_id: current.revision_id, expected_version: current.version, state: "confirmed",
    definition: { ...current.definition, grain: "record", domain: "sales", columns: current.definition.columns.map((column: { name: string }) => ({ ...column,
      role: [amount, quantity].includes(column.name) ? "metric" : "dimension",
      meaning: `Recorded ${column.name}`, unit: column.name === amount ? "currency" : column.name === quantity ? "items" : "",
      currency: column.name === amount ? "USD" : "",
    })) },
  } });
  expect(confirmed.status()).toBe(201);
  return { did, uid, root };
}

async function prepare(page: Page, period: boolean) {
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `contribution-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  const headers = { Authorization: `Bearer ${token}` };
  const workspace = await page.request.post(api + "/workspaces", { headers, data: { name: "Fictional sales", seat_limit: 3 } });
  expect(workspace.status()).toBe(201);
  const wid = (await workspace.json()).id;
  const baseline = await seed(page, token, wid, "baseline", period
    ? "date,product,revenue,quantity\n2026-01-01,A,100,10\n2026-01-02,B,200,10\n2026-01-03,D,30,1\n2026-02-01,A,240,20\n2026-02-02,B,125,5\n2026-02-03,C,80,2\n"
    : "product,revenue,quantity\nA,100,10\nB,200,10\nD,30,1\n", "revenue", "quantity");
  const other = period ? baseline : await seed(page, token, wid, "comparison", "item,sales,units\nA,240,20\nB,125,5\nC,80,2\n", "sales", "units");
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByLabel("Current workspace")).toHaveValue(wid);
  await page.getByLabel("Dataset", { exact: true }).selectOption(baseline.did);
  await page.getByLabel("Profile upload").selectOption(baseline.uid);
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Studies & dashboards", exact: true }).click();
  const library = page.getByRole("region", { name: "Studies and dashboards", exact: true });
  await library.getByLabel("Study name (optional)").fill("Observed sales change");
  await library.getByText("Explain a change", { exact: true }).click();
  return { wid, headers, baseline, other, library };
}

async function choose(page: Page, label: string, value: string) {
  await page.getByRole("combobox", { name: label, exact: true }).click();
  await page.getByRole("option", { name: value, exact: true }).click();
}

for (const mode of ["period", "dataset"] as const) {
  test(`${mode} contribution study uses exact source evidence and remains interactive`, async ({ page }) => {
    test.setTimeout(150_000);
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", event => { if (event.text().includes("same key")) errors.push(event.text()); });
    const { wid, headers, baseline, other, library } = await prepare(page, mode === "period");
    await library.getByLabel("Also separate volume, product mix and revenue per unit").check();
    await choose(page, "Baseline amount", "revenue");
    await choose(page, "Baseline category", "product");
    await choose(page, "Baseline quantity", "quantity");
    if (mode === "period") {
      await choose(page, "Comparison date field", "date");
      await library.getByLabel("Baseline start", { exact: true }).fill("2026-01-01");
      await library.getByLabel("Baseline end", { exact: true }).fill("2026-01-31");
      await library.getByLabel("Comparison start", { exact: true }).fill("2026-02-01");
      await library.getByLabel("Comparison end", { exact: true }).fill("2026-02-28");
    } else {
      await choose(page, "Compare populations", "Two file snapshots");
      await choose(page, "Comparison dataset", "comparison");
      await page.getByRole("combobox", { name: "Comparison snapshot", exact: true }).click();
      await page.getByRole("option", { name: /comparison.csv/ }).click();
      await choose(page, "Comparison amount", "sales");
      await choose(page, "Comparison category", "item");
      await choose(page, "Comparison quantity", "units");
    }
    const calculate = library.getByRole("button", { name: "Calculate & save comparison", exact: true });
    await expect(calculate).toBeDisabled();
    await library.getByLabel("These amounts can be added across rows", { exact: false }).check();
    let failHistory = mode === "period";
    let creations = 0;
    page.on("request", request => { if (request.method() === "POST" && request.url().endsWith(baseline.root + "/studies")) creations += 1; });
    await page.route(`${api}/workspaces/${wid}/datasets/${baseline.did}/studies`, route => failHistory ? route.fulfill({ status: 503, json: { error: { message: "Synthetic history read failure" } } }) : route.continue());
    const response = page.waitForResponse(value => value.url().endsWith(baseline.root + "/studies") && value.status() === 201);
    await calculate.click();
    const saved = await (await response).json();
    expect(saved.contribution.net_change.display).toBe("115");
    expect(saved.version.evidence.sources.map((source: { dataset_id: string }) => source.dataset_id)).toEqual([baseline.did, other.did]);
    const result = library.getByRole("article", { name: "Study result: Observed sales change", exact: true });
    await expect(result.getByLabel("Recorded comparison totals")).toContainText("330");
    await expect(result.getByLabel("Recorded comparison totals")).toContainText("445");
    await expect(result.getByLabel("Recorded comparison totals")).toContainText("115");
    if (mode === "period") {
      await expect(library.getByRole("alert")).toContainText("Your study was saved");
      await expect(calculate).toBeDisabled();
      failHistory = false;
      await library.getByRole("button", { name: "Reload saved study list", exact: true }).click();
      await expect(library.getByRole("status")).toContainText("Saved study list reloaded");
      expect(creations).toBe(1);
    }
    await result.getByText("Volume, mix and revenue per unit", { exact: true }).click();
    await expect(result).toContainText("75/1");
    await expect(result).toContainText("-75/1");
    await expect(result).toContainText("65/1");
    await result.getByText("Inspect supporting records", { exact: true }).click();
    await choose(page, "Supporting category", "A");
    await expect(result.getByRole("cell", { name: "240", exact: true })).toBeVisible();
    await result.getByText("Download result", { exact: true }).click();
    await result.getByLabel("File type").selectOption("xlsx");
    const downloaded = page.waitForEvent("download");
    await result.getByRole("button", { name: "Download Excel", exact: true }).click();
    const download = await downloaded;
    expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
    expect(readFileSync((await download.path())!).subarray(0, 2).toString()).toBe("PK");
    await library.getByLabel("Dashboard name", { exact: true }).fill("Recorded changes");
    await library.getByRole("button", { name: "Create study dashboard", exact: true }).click();
    await library.getByRole("button", { name: "Pin this result", exact: true }).click();
    await library.getByRole("button", { name: "Share study with workspace", exact: true }).click();
    await library.getByRole("button", { name: "Share dashboard", exact: true }).click();
    await library.getByRole("button", { name: "Open version 1", exact: true }).click();
    await expect(result.getByLabel("Recorded comparison totals")).toContainText("115");
    const reopened = await page.request.get(`${api}/workspaces/${wid}/study-versions/${saved.version.id}`, { headers });
    expect((await reopened.json()).contribution).toEqual(saved.contribution);
    const output = process.env.PLAYWRIGHT_JSON_OUTPUT_NAME ? join(dirname(process.env.PLAYWRIGHT_JSON_OUTPUT_NAME), "captures", "contributions") : "../../data/verification/2026-10-17/two-phase/contributions-browser";
    mkdirSync(output, { recursive: true });
    await page.emulateMedia({ reducedMotion: "reduce" });
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      await result.scrollIntoViewIfNeeded();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      await result.screenshot({ path: join(output, `${mode}-${width}.png`) });
    }
    expect(errors).toEqual([]);
  });
}
