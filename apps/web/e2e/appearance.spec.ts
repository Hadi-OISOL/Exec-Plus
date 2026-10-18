/* Use case: Protects persisted accessible appearance without touching source data.
What it does: Verifies explicit choices, operating-system changes, reload and narrow layouts. */
import { expect, test } from "@playwright/test";

test("appearance follows system, persists explicit choice and stays keyboard accessible", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await page.goto("/workspace");
  const appearance = page.getByLabel("Appearance", { exact: true });
  await expect(appearance).toHaveValue("system");
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).colorScheme)).toBe("light dark");
  const systemDark = await page.locator(".workbench").evaluate(element => getComputedStyle(element).backgroundColor);
  await appearance.selectOption("light");
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).colorScheme)).toBe("light");
  const light = await page.locator(".workbench").evaluate(element => getComputedStyle(element).backgroundColor);
  expect(light).not.toBe(systemDark);
  await page.reload();
  await expect(appearance).toHaveValue("light");
  await appearance.focus();
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(appearance).toHaveValue("dark");
  await page.emulateMedia({ colorScheme: "light" });
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).colorScheme)).toBe("dark");
  await appearance.selectOption("system");
  await expect.poll(() => page.locator(".workbench").evaluate(element => getComputedStyle(element).backgroundColor)).toBe(light);
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(appearance).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
});
