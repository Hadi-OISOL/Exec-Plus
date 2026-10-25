/* Use case: Proves that each uploaded dataset gets its own automatic dashboard on the overview.
What it does: Uploads two different fictional files, compares their dashboard tiles, opens the
"Why this dashboard" disclosure, rebuilds a version and checks dark mode at phone width. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";
import { finishInitialReview } from "./workspace-helpers";

const sales = "order_date,region,product,amount\n" + Array.from({ length: 60 }, (_, index) =>
  `2025-${String(1 + (index % 9)).padStart(2, "0")}-${String(1 + (index % 27)).padStart(2, "0")},${["North", "South", "East"][index % 3]},P${index % 4},${(index * 7.25).toFixed(2)}`).join("\n") + "\n";
const survey = "respondent_id,age_group,department,satisfaction\n" + Array.from({ length: 40 }, (_, index) =>
  `R${index},${["18-24", "25-34", "35-44"][index % 3]},${["Sales", "Ops"][index % 2]},${1 + (index % 5)}`).join("\n") + "\n";

async function upload(page: Page, name: string, content: string) {
  await page.getByLabel("CSV or Excel file").setInputFiles({ name, mimeType: "text/csv", buffer: Buffer.from(content) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Overview", exact: true }).click();
  const board = page.getByRole("region", { name: "Your dashboard", exact: true });
  await expect(board.locator("[data-tile]").first()).toBeVisible({ timeout: 90_000 });
  return board;
}

async function tiles(board: ReturnType<Page["getByRole"]>) {
  return (await board.locator("[data-tile]").evaluateAll(nodes => nodes.map(node => node.getAttribute("data-tile")))).sort();
}

test("two different datasets get two different automatic dashboards", async ({ page }) => {
  test.setTimeout(240_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `auto-board-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const first = await upload(page, "fictional-sales.csv", sales);
  await expect(first).toContainText("Built for fictional-sales");
  await expect(first).toContainText("Confirm meanings for more");
  const salesTiles = await tiles(first);
  expect(salesTiles).toContain("volume:order_date:month");
  await expect(first).toHaveAttribute("data-version", "1");
  const firstId = await first.getAttribute("data-dashboard");
  await first.getByText("Why this dashboard", { exact: true }).click();
  await expect(first.locator("details[open]")).toContainText("receipt");
  await first.getByRole("button", { name: "Rebuild dashboard", exact: true }).click();
  await expect(first).toHaveAttribute("data-version", "2");
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Data library", exact: true }).click();
  const second = await upload(page, "fictional-survey.csv", survey);
  await expect(second).toContainText("Built for fictional-survey");
  const surveyTiles = await tiles(second);
  expect(surveyTiles).not.toEqual(salesTiles);
  expect(surveyTiles.some(id => id?.startsWith("volume:"))).toBe(false);
  expect(await second.getAttribute("data-dashboard")).not.toBe(firstId);
  await page.getByLabel("Appearance", { exact: true }).selectOption("dark");
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(second.locator("[data-tile]").first()).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await second.screenshot({ path: test.info().outputPath(`auto-dashboard-dark-${width}.png`) });
  }
  expect(errors).toEqual([]);
});
