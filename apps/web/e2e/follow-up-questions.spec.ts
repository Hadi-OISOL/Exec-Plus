/* Use case: Proves the follow-up questions after an upload are asked, saved privately and change what comes next.
What it does: Uploads a fictional sales file, answers the questions on the "Your data is ready" card, checks the saved focus receipt, the suggested question led by the chosen group and the dashboard rebuilt around the chosen time view, at desktop and phone width. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { finishInitialReview } from "./workspace-helpers";

const sales = "order_date,region,product,amount\n" + Array.from({ length: 60 }, (_, index) =>
  `2025-${String(1 + (index % 9)).padStart(2, "0")}-${String(1 + (index % 27)).padStart(2, "0")},${["North", "South", "East"][index % 3]},P${index % 4},${(index * 7.25).toFixed(2)}`).join("\n") + "\n";

test("follow-up answers after upload lead the suggestions and rebuild the dashboard", async ({ page }) => {
  test.setTimeout(240_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `follow-up-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "fictional-sales.csv", mimeType: "text/csv", buffer: Buffer.from(sales) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Overview", exact: true }).click();
  const board = page.getByRole("region", { name: "Your dashboard", exact: true });
  await expect(board.locator("[data-tile]").first()).toBeVisible({ timeout: 90_000 });
  const before = await board.getAttribute("data-version");
  const ask = page.getByRole("region", { name: "A few questions about this file" });
  await expect(ask).toBeVisible({ timeout: 60_000 });
  await ask.getByRole("group", { name: "Which number matters most to you?" }).getByRole("button", { name: "amount", exact: true }).click();
  await ask.getByRole("group", { name: "Which group do you want to compare?" }).getByRole("button", { name: "product", exact: true }).click();
  const time = ask.getByRole("group", { name: "How do you want to follow it over time?" }).getByRole("button", { name: "Week by week", exact: true });
  await time.click();
  await expect(time).toHaveAttribute("aria-pressed", "true");
  await ask.getByRole("textbox", { name: "What decision should this data help with?" }).fill("Plan stock for spring");
  await ask.getByRole("button", { name: "Save my answers", exact: true }).click();
  const focus = page.getByRole("region", { name: "Your focus for this file" });
  await expect(focus).toContainText("Week by week", { timeout: 30_000 });
  await expect(focus).toContainText("Plan stock for spring");
  const questions = page.getByRole("region", { name: "Questions you could ask" });
  await expect(questions.getByRole("button").first()).toHaveAttribute("title", "Which product has the highest total amount?", { timeout: 30_000 });
  await expect(board).not.toHaveAttribute("data-version", before ?? "", { timeout: 90_000 });
  await expect(board.locator('[data-tile="volume:order_date:week"]')).toBeVisible({ timeout: 90_000 });
  await expect(board).toContainText("Tiles follow your answers");
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(focus).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await focus.screenshot({ path: test.info().outputPath(`follow-up-${width}.png`) });
  }
  expect(errors).toEqual([]);
});
