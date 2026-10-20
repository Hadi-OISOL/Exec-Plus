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
  await expect(home.or(skip)).toBeVisible({ timeout: 60_000 });
  if (await skip.isVisible()) await skip.click();
  await expect(home).toBeVisible();
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
