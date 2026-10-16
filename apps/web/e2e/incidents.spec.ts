/* Use case: Verifies real staff-only operational alerts in the browser.
What it does: Waits for durable failure collection, acknowledges and resolves incidents, checks responsive layouts and clears privileged content after revocation. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";

test("internal alerts collect durable failures and honor staff review and revocation", async ({ page }) => {
  test.setTimeout(140_000);
  page.setDefaultTimeout(20_000);
  const email = `incident-${randomUUID()}@example.test`;
  const command = (args: string[]) => execFileSync("python3", args, { cwd: "../..", encoding: "utf8" }).trim();
  const token = command(["-m", "execplus.manage", "provision-user", "--email", email]);
  command(["-m", "execplus.manage", "grant-staff", "--email", email, "--role", "admin"]);
  const headers = { Authorization: `Bearer ${token}` };
  const actor = await (await page.request.get("http://127.0.0.1:8001/auth/me", { headers })).json();
  const created = await page.request.post("http://127.0.0.1:8001/workspaces", { headers, data: { name: "Incident browser fixture", seat_limit: 3 } });
  expect(created.ok()).toBe(true);
  const wid = (await created.json()).id;
  command(["-c", "import sys;from uuid import UUID,uuid4;from datetime import datetime,timezone;from sqlalchemy import create_engine,insert;from execplus.config import Settings;from execplus.infrastructure.persistence import schema as s;engine=create_engine(Settings().database_url);c=engine.begin();conn=c.__enter__();conn.execute(insert(s.audit_events).values(id=uuid4(),workspace_id=UUID(sys.argv[1]),actor_id=UUID(sys.argv[2]),action='refresh.activation_failed',resource_type='refresh_candidate',resource_id=uuid4(),created_at=datetime.now(timezone.utc)));c.__exit__(None,None,None);engine.dispose()", wid, actor.id]);
  await expect.poll(async () => (await (await page.request.get("http://127.0.0.1:8001/admin/incidents", { headers })).json()).incidents.some((value: { code: string }) => value.code === "refresh_failed"), { timeout: 45_000, intervals: [500, 1000] }).toBe(true);
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Admin console", exact: true }).click();
  await page.getByRole("button", { name: "Service alerts", exact: true }).click();
  const panel = page.getByRole("region", { name: "Internal service alerts", exact: true });
  const card = panel.getByRole("article", { name: "A staged refresh could not activate", exact: true });
  await expect(card).toBeVisible();
  await expect(panel.getByText("Collector is running", { exact: true })).toBeVisible();
  const acknowledgement = page.waitForResponse(response => response.url().includes("/admin/incidents/") && response.request().method() === "PATCH");
  await card.getByRole("button", { name: "Acknowledge", exact: true }).click();
  const acknowledged = await acknowledgement;
  expect(acknowledged.request().headers()["content-type"]).toBe("application/json");
  expect(acknowledged.ok()).toBe(true);
  await expect(card.getByText("acknowledged", { exact: true })).toBeVisible();
  const directory = "../../data/verification/2026-10-16/remaining-work/incidents-browser";
  mkdirSync(directory, { recursive: true });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await panel.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await panel.screenshot({ path: `${directory}/alerts-${width}.png`, animations: "disabled" });
    const button = await card.getByRole("button", { name: "Mark resolved", exact: true }).boundingBox();
    expect(button!.height).toBeGreaterThanOrEqual(44);
  }
  await card.getByRole("button", { name: "Mark resolved", exact: true }).click();
  await expect(card).toHaveCount(0);
  await panel.getByRole("combobox", { name: "Show incidents", exact: true }).selectOption("resolved");
  await expect(card).toBeVisible();
  await expect(card.getByText("resolved", { exact: true })).toBeVisible();
  command(["-m", "execplus.manage", "revoke-staff", "--email", email]);
  await panel.getByRole("button", { name: "Refresh alerts", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("staff admin access");
  await expect(card).toHaveCount(0);
  expect(errors).toEqual([]);
});
