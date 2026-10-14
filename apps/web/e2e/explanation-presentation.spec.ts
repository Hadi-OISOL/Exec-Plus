/* Use case: Exercises meaning-first answer presentation in a real private conversation.
What it does: Uses an explicit response-text fixture to check card hierarchy, safe text, keyboard access and narrow layouts. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

test("structured explanation cards preserve text and accessible context at three widths", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `explanation-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "observations.csv", mimeType: "text/csv", buffer: Buffer.from("region,amount\nNorth,0.10\nSouth,0.20\nNorth,0.30\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(page.getByRole("region", { name: "Analytics home", exact: true })).toBeVisible();
  const fixture = [
    "What this data is about\nRecorded observations across regions.",
    "How the fields fit together\nregion groups the records; amount describes each reading.",
    "Useful things to explore\nCompare amount across region.",
    "One thing to clarify\nWhat unit is amount measured in?",
    "What I can do now\nExplore recorded readings. Future changes need observation dates.",
    'Context used\nSaved description and column names. Literal source text: <script>alert("unsafe")</script>.',
  ].join("\n\n");
  await page.route(/\/jobs\/[^/]+\/result$/, async route => {
    const response = await route.fetch();
    const result = await response.json();
    expect(result.answer.guidance).toBeTruthy();
    await route.fulfill({ json: { ...result, answer: { ...result.answer, message: fixture } } });
  });
  await page.getByRole("button", { name: "Understand this data", exact: true }).click();
  const cards = page.locator(".datasetGuidance");
  await expect(cards.getByRole("heading", { name: "What this data is about", exact: true })).toBeVisible();
  await expect.poll(async () => {
    const heading = await cards.getByRole("heading", { name: "What this data is about", exact: true }).boundingBox();
    const log = await page.getByRole("log", { name: "Conversation", exact: true }).boundingBox();
    return Boolean(heading && log && heading.y >= log.y && heading.y + heading.height <= log.y + log.height);
  }).toBe(true);
  await expect(cards.getByRole("heading", { name: "One thing to clarify", exact: true })).toBeVisible();
  await expect(cards.locator("script")).toHaveCount(0);
  const context = cards.locator(".explanationContext");
  await expect(context).not.toHaveAttribute("open", "");
  await context.locator("summary").focus();
  await page.keyboard.press("Enter");
  await expect(context).toHaveAttribute("open", "");
  await expect(context).toContainText('<script>alert("unsafe")</script>');
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(cards.getByRole("heading", { name: "How the fields fit together", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await cards.getByRole("heading", { name: "What this data is about", exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: `../../data/verification/2026-10-14/meaning-first/explanation-${width}.png`, fullPage: true });
  }
  let release: () => void = () => {};
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route(/\/threads\/[^/]+\/jobs$/, async route => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch();
    await held;
    await route.fulfill({ response });
  });
  try {
    await page.getByLabel("Your question", { exact: true }).fill("What does region mean?");
    await page.getByLabel("Your question", { exact: true }).press("Enter");
    await expect(page.locator(".userMessage").last()).toContainText("What does region mean?");
    await expect.poll(() => page.getByRole("log", { name: "Conversation", exact: true }).evaluate(log => log.scrollHeight - log.clientHeight - log.scrollTop)).toBeLessThan(3);
  } finally {
    release();
  }
  await expect(cards).toHaveCount(2);
  expect(errors).toEqual([]);
});
