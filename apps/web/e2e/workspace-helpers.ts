/* Use case: Drives the focused workspace journey in real browser tests.
What it does: Leaves optional reading and verifies the requested working view is visible. */

import { expect } from "@playwright/test";
import type { Page } from "@playwright/test";

export async function selectAnalysisFocus(page: Page, value: "descriptive" | "predictive" | "prescriptive" | "all") {
  const label = { descriptive: "Descriptive", predictive: "Predictive", prescriptive: "Prescriptive", all: "All supported" }[value];
  await page.getByRole("combobox", { name: "Analysis focus", exact: true }).click();
  await page.getByRole("option", { name: new RegExp(`^${label} ·`) }).click();
}

export async function finishInitialReview(page: Page) {
  const home = page.getByRole("region", { name: "Analytics home", exact: true });
  const skip = page.getByRole("button", { name: "Skip for now", exact: true }).first();
  await expect(home.or(skip).first()).toBeVisible({ timeout: 60_000 });
  if (await skip.isVisible()) await skip.click();
  await expect(home).toBeVisible();
}

export async function openAnalysisAdvanced(page: Page) {
  await page.locator("label.analysisMethodSwitch").first().waitFor({ timeout: 30_000 });
  const advanced = page.locator("details.analysisAdvanced").first();
  if (await advanced.count() && !(await advanced.evaluate(element => (element as HTMLDetailsElement).open))) await advanced.locator(":scope > summary").click();
}

export async function showIndividualCalculations(page: Page) {
  const more = page.locator("details.legacyCalculations").first();
  await expect(more).toBeAttached({ timeout: 60_000 });
  if (!(await more.evaluate(element => (element as HTMLDetailsElement).open))) await more.locator(":scope > summary").click();
  await expect(more).toHaveJSProperty("open", true);
}

export async function openFindings(page: Page) {
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Overview", exact: true }).click();
  await expect(page.getByRole("region", { name: "First findings from your file", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Charts & dashboard controls", exact: true })).toBeVisible();
}

export async function openConversation(page: Page) {
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Ask ExecPlus", exact: true }).click();
  await expect(page.getByLabel("Your question", { exact: true })).toBeVisible();
}

export async function navigateTo(page: Page, name: string) {
  const nav = page.getByRole("navigation", { name: "Workspace navigation" });
  const more = nav.getByRole("button", { name: "More", exact: true });
  if (await more.getAttribute("aria-expanded") === "false") await more.click();
  await nav.getByRole("button", { name, exact: true }).click();
}
