/* Use case: Verifies the question-led analytics shell against real private workspace APIs.
What it does: Covers saved evidence navigation, accessible mobile search and preservation of a second question during active work. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const api = "http://127.0.0.1:8001";

async function start(page: Page) {
  const token = execFileSync("python3", [
    "-m", "execplus.manage", "provision-user", "--email",
    `analytics-home-${randomUUID()}@example.test`,
  ], { cwd: "../..", encoding: "utf8" }).trim();
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "regional-sales.csv", mimeType: "text/csv",
    buffer: Buffer.from("city,amount\nKarachi,0.10\nLahore,0.20\nKarachi,0.30\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(page.getByRole("region", { name: "Analytics home", exact: true })).toBeVisible();
  return {
    headers: { Authorization: `Bearer ${token}` },
    root: `/workspaces/${await page.getByLabel("Current workspace").inputValue()}/datasets/${await page.getByLabel("Dataset", { exact: true }).inputValue()}/uploads/${await page.getByLabel("Profile upload").inputValue()}`,
  };
}

async function navigate(page: Page, name: string) {
  await page.getByRole("navigation", { name: "Workspace navigation" })
    .getByRole("button", { name, exact: true }).click();
}

test("analytics home opens real saved evidence and mobile search preserves its selected source", async ({ page }) => {
  const { root, headers } = await start(page);
  const calculated = await page.request.post(`${api}${root}/query`, {
    headers, data: { metric: "amount", aggregation: "sum", group_by: ["city"] },
  });
  expect(calculated.ok()).toBe(true);
  const answer = await calculated.json();
  const saved = await page.request.post(`${api}${root}/saved-items`, {
    headers, data: { name: "Regional sales review", kind: "analysis", shared: false, payload: { query_id: answer.lineage.query_id } },
  });
  expect(saved.status()).toBe(201);
  await navigate(page, "Saved work");
  await navigate(page, "Overview");
  const home = page.getByRole("region", { name: "Analytics home", exact: true });
  await expect(home.getByRole("button", { name: /Regional sales review/ })).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: "../../data/interface-reference/execplus-home-desktop.png", fullPage: false });
  await home.getByRole("button", { name: /Regional sales review/ }).click();
  const result = page.getByRole("region", { name: "Saved result: Regional sales review", exact: true });
  await expect(result).toBeVisible();
  await expect(result).toContainText(answer.lineage.query_id);
  await expect(result.getByRole("cell", { name: "0.400000000000", exact: true })).toBeVisible();
  await expect(page.getByLabel("Profile upload")).toHaveValue(root.split("/").at(-1)!);
  await navigate(page, "Overview");
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("button", { name: "Search your data", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  await page.getByRole("button", { name: "Search your data", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: "Dataset dashboard", exact: true })).toBeVisible();
  await expect(page.getByLabel("Profile upload")).toHaveValue(root.split("/").at(-1)!);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: "../../data/interface-reference/execplus-search-mobile.png", fullPage: true });
});

test("a second home question becomes an explicit draft while the real first job finishes", async ({ page }) => {
  await start(page);
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  let submitted = 0;
  await page.route(/\/threads\/[^/]+\/jobs$/, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch();
    submitted += 1;
    if (submitted === 1) await held;
    await route.fulfill({ response });
  });
  try {
    await page.getByLabel("Ask about your data", { exact: true }).fill("Help me understand my data");
    await page.getByRole("button", { name: "Explore this question", exact: true }).click();
    await expect.poll(() => submitted).toBe(1);
    await expect(page.locator("main")).toHaveAttribute("data-section", "ask");
    await navigate(page, "Overview");
    await page.getByLabel("Ask about your data", { exact: true }).fill("What does city mean?");
    await page.getByRole("button", { name: "Explore this question", exact: true }).click();
    await expect(page.getByLabel("Your question")).toHaveValue("What does city mean?");
    await expect(page.getByText("Your next question is saved below. Send it when the current answer finishes.", { exact: true })).toBeVisible();
    expect(submitted).toBe(1);
    release();
    const chat = page.getByRole("region", { name: "Ask a question", exact: true });
    await expect(chat.locator(".datasetGuidance")).toContainText("3 rows and 2 columns");
    await expect(page.getByLabel("Your question")).toHaveValue("What does city mean?");
    await expect(chat.getByRole("button", { name: "Ask", exact: true })).toBeEnabled();
    await page.getByLabel("Your question").press("Enter");
    await expect.poll(() => submitted).toBe(2);
    await expect(chat.locator(".datasetGuidance")).toHaveCount(2);
    await expect(chat.locator(".datasetGuidance").last()).toContainText("city");
    await page.screenshot({ path: "../../data/interface-reference/execplus-conversation-desktop.png", fullPage: false });
    await navigate(page, "Overview");
    await navigate(page, "Ask ExecPlus");
    await expect(chat.locator(".datasetGuidance")).toHaveCount(2);
  } finally {
    release();
  }
});
