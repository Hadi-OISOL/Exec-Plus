/* Use case: Verifies the inventory reorder planner in a real browser.
What it does: Reaches the planner from the chat reorder answer, saves a budget-limited plan and checks the shown quantities, replay and narrow layout. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { finishInitialReview, openConversation } from "./workspace-helpers";

const api = "http://127.0.0.1:8001";
const demand: Record<string, number[]> = {
  A: [5, 7, 6, 0, 8, 5, 6, 7, 4, 6, 5, 9, 6, 5],
  B: [1, 0, 2, 1, 0, 0, 3, 1, 1, 0, 2, 1, 0, 1],
  C: [12, 10, 11, 14, 9, 13, 12, 10, 11, 12, 15, 9, 10, 12],
};
const fixed: Record<string, string> = { A: "20,30,4,2.50", B: "3,5,10,7", C: "80,40,3,1.25" };
const csv = "day,item,sold,on_hand,reorder_point,lead_days,unit_cost\n" + Object.entries(demand).flatMap(([item, values]) => values.map((value, day) => `2026-01-${String(day + 1).padStart(2, "0")},${item},${value},${fixed[item]}\n`)).join("");

test("the chat reorder answer opens a budget-limited reorder plan with exact saved quantities", async ({ page }) => {
  test.setTimeout(180_000);
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `reorder-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  const auth = { Authorization: `Bearer ${token}` };
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "stock-history.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  const wid = await page.getByLabel("Current workspace").inputValue();
  const did = await page.getByLabel("Dataset", { exact: true }).inputValue();
  const uid = await page.getByLabel("Profile upload").inputValue();
  const root = `${api}/workspaces/${wid}/datasets/${did}/uploads/${uid}`;
  const current = await (await page.request.get(`${root}/understanding`, { headers: auth })).json();
  const units: Record<string, { unit: string; currency: string }> = { sold: { unit: "units", currency: "" }, on_hand: { unit: "units", currency: "" }, reorder_point: { unit: "units", currency: "" }, lead_days: { unit: "days", currency: "" }, unit_cost: { unit: "", currency: "USD" } };
  const saved = await page.request.post(`${root}/understanding`, { headers: auth, data: {
    revision_id: current.revision_id, expected_version: current.version, state: "confirmed",
    definition: { ...current.definition, grain: "record", columns: current.definition.columns.map((column: { name: string }) => units[column.name] ? { ...column, role: "metric", ...units[column.name] } : column) },
  } });
  expect(saved.status()).toBe(201);
  await openConversation(page);
  const chat = page.getByRole("region", { name: "Ask a question", exact: true });
  await chat.getByLabel("Your question", { exact: true }).fill("What should I reorder first?");
  await chat.getByRole("button", { name: "Ask", exact: true }).click();
  const turn = chat.locator(".conversationTurn").last();
  await expect(turn).toContainText("Rule used: items whose on_hand is below their reorder_point", { timeout: 60_000 });
  await turn.getByRole("button", { name: "Plan reorder quantities", exact: true }).click();
  const panel = page.getByRole("region", { name: "Inventory reorder plan", exact: true });
  await expect(panel).toBeVisible();
  await panel.getByRole("combobox", { name: "History date", exact: true }).selectOption("day");
  await panel.getByRole("combobox", { name: "Demand quantity", exact: true }).selectOption("sold");
  await panel.getByRole("combobox", { name: "Stock on hand from", exact: true }).selectOption("on_hand");
  await panel.getByRole("combobox", { name: "Reorder point from", exact: true }).selectOption("reorder_point");
  await panel.getByRole("combobox", { name: "Lead time (days) from", exact: true }).selectOption("lead_days");
  await panel.getByRole("combobox", { name: "Unit cost from", exact: true }).selectOption("unit_cost");
  await panel.getByLabel("Budget · optional", { exact: true }).fill("60");
  await panel.getByRole("checkbox", { name: "I confirm the history", exact: false }).check();
  const responsePromise = page.waitForResponse(response => response.url().endsWith("/decision-analysis/inventory-reorders") && response.status() === 201);
  await panel.getByRole("button", { name: "Plan reorder quantities", exact: true }).click();
  const result = await (await responsePromise).json();
  expect(result.run.result.funding).toBe("budget_limited");
  expect(Number(result.run.result.cost)).toBeLessThanOrEqual(60);
  const table = panel.getByRole("region", { name: "Reorder quantities table", exact: true });
  const rows = table.locator("tbody tr");
  await expect(rows).toHaveCount(3);
  for (const [index, row] of result.run.result.allocations.entries()) {
    await expect(rows.nth(index)).toContainText(row.candidate);
    await expect(rows.nth(index).locator("td").nth(9)).toHaveText(String(row.quantity));
    await expect(rows.nth(index).locator("td").nth(7)).toHaveText(row.target_level);
  }
  expect(result.run.result.allocations[0].candidate).toBe("B");
  await expect(panel).toContainText("favouring items with fewer days of cover");
  const replay = page.waitForResponse(response => response.url().endsWith(`/decision-analysis/${result.run.id}`) && response.status() === 200);
  await panel.getByRole("button", { name: "Replay original evidence", exact: true }).click();
  expect((await (await replay).json()).run).toEqual(result.run);
  await page.setViewportSize({ width: 320, height: 900 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  expect(errors).toEqual([]);
});
