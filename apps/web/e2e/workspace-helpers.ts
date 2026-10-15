/* Use case: Drives the focused workspace journey in real browser tests.
What it does: Explicitly leaves optional reading and opens the requested working view. */

import { expect } from "@playwright/test";
import type { Page } from "@playwright/test";

export async function finishInitialReview(page: Page) {
  const home = page.getByRole("region", { name: "Analytics home", exact: true });
  const skip = page.getByRole("button", { name: "Skip for now", exact: true }).first();
  await expect(home.or(skip)).toBeVisible();
  if (await skip.isVisible()) await skip.click();
  await expect(home).toBeVisible();
}

export async function openFindings(page: Page) {
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Overview", exact: true }).click();
  const findings = page.locator(".overviewFindings");
  if (!(await findings.getAttribute("open"))) {
    if (!(await findings.evaluate(element => (element as HTMLDetailsElement).open))) await findings.locator(":scope > summary").click();
  }
}

export async function openConversation(page: Page) {
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Ask ExecPlus", exact: true }).click();
  await expect(page.getByLabel("Your question", { exact: true })).toBeVisible();
}
