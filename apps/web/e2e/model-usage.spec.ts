/* Use case: Verifies owner AI usage against real accounting records.
What it does: Checks unknown and exact priced amounts, allowances, retry recovery, responsive layouts and revoked access. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";

const api = "http://127.0.0.1:8001";
const seed = `
import sys
from uuid import UUID,uuid4
from sqlalchemy import create_engine
from execplus.config import Settings
from execplus.application.services.usage_metering import UsageMeteringService
from execplus.infrastructure.persistence.usage_metering import SQLUsageUnitOfWork
from execplus.domain.usage_metering import UsageAttribution,TokenUsage
settings=Settings()
assert settings.environment=='test'
engine=create_engine(settings.database_url)
service=UsageMeteringService(SQLUsageUnitOfWork(engine))
scope=UsageAttribution(UUID(sys.argv[1]),UUID(sys.argv[2]),uuid4(),'conversation')
for usage in ([TokenUsage()] if sys.argv[3]=='unknown' else [TokenUsage(100,50,20),TokenUsage()]):
    attempt=service.reserve(scope,uuid4(),'browser-fixture','fictional-model')
    service.start(scope,attempt.id)
    service.finish(scope,attempt.id,'succeeded',usage)
engine.dispose()
`;

test("AI usage preserves unknown costs, exact amounts and owner boundaries", async ({ page }) => {
  test.setTimeout(100_000);
  page.setDefaultTimeout(20_000);
  const command = (args: string[]) => execFileSync("python3", args, { cwd: "../..", encoding: "utf8" }).trim();
  const email = `usage-${randomUUID()}@example.test`;
  const token = command(["-m", "execplus.manage", "provision-user", "--email", email]);
  command(["-m", "execplus.manage", "grant-staff", "--email", email, "--role", "admin"]);
  const headers = { Authorization: `Bearer ${token}` };
  const actor = await (await page.request.get(`${api}/auth/me`, { headers })).json();
  const created = await page.request.post(`${api}/workspaces`, { headers, data: { name: "AI usage fixture", seat_limit: 3 } });
  expect(created.ok()).toBe(true);
  const wid = (await created.json()).id;
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Usage & retention", exact: true }).click();
  await page.getByRole("group", { name: "Usage view" }).getByRole("button", { name: "AI usage", exact: true }).click();
  const panel = page.getByRole("region", { name: "AI usage", exact: true });
  await expect(panel.getByText("No AI attempts were recorded in this window.", { exact: false })).toBeVisible();
  command(["-c", seed, wid, actor.id, "unknown"]);
  await panel.getByRole("button", { name: "Refresh AI usage" }).click();
  await expect(panel.getByRole("heading", { name: "Unpriced requests", exact: true })).toBeVisible();
  const unpriced = panel.locator("section").filter({ has: page.getByRole("heading", { name: "Unpriced requests", exact: true }) }).last();
  await expect(unpriced.getByText("Unknown", { exact: true })).toBeVisible();
  const priced = await page.request.post(`${api}/admin/model-prices`, { headers, data: {
    id: randomUUID(), provider: "browser-fixture", model: "fictional-model", currency: "USD",
    input_per_million: "2.75", output_per_million: "8.125", cached_input_per_million: "0.125",
    evidence_ref: "fictional-browser-fixture", effective_at: new Date(Date.now() - 60_000).toISOString(),
  } });
  expect(priced.status()).toBe(201);
  const allowance = await page.request.put(`${api}/admin/workspaces/${wid}/model-allowance`, { headers, data: {
    expected_version: 0, plan_key: "fictional-browser-allowance",
    starts_at: new Date().toISOString(), ends_at: new Date(Date.now() + 86_400_000).toISOString(),
    max_attempts: 2, max_in_flight: 2, currency: "USD", spend_limit: "1", reservation_per_attempt: "0.1",
  } });
  expect(allowance.ok()).toBe(true);
  command(["-c", seed, wid, actor.id, "priced"]);
  await panel.getByRole("button", { name: "Refresh AI usage" }).click();
  await expect(panel.getByText("This workspace has used its request allowance.", { exact: true })).toBeVisible();
  const summary = await (await page.request.get(`${api}/workspaces/${wid}/model-usage`, { headers })).json();
  const cost = summary.costs.find((value: { currency: string | null }) => value.currency === "USD");
  expect(Number(cost.known_cost)).toBe(0.00062875);
  expect(Number(cost.held_exposure)).toBe(0.1);
  const costPanel = panel.getByRole("region", { name: "Recorded model costs", exact: true });
  await expect(costPanel.getByText(`${cost.known_cost} USD`, { exact: true })).toBeVisible();
  await expect(costPanel.getByText(`${cost.held_exposure} USD`, { exact: true })).toBeVisible();
  await panel.getByText("Reported tokens and counting details", { exact: true }).click();
  await expect(panel.getByText("Reported by 1 attempt", { exact: true })).toHaveCount(3);
  const directory = "../../data/verification/2026-10-16/remaining-work/model-usage-browser";
  mkdirSync(directory, { recursive: true });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await panel.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    const button = await panel.getByRole("button", { name: "Refresh AI usage" }).boundingBox();
    expect(button!.height).toBeGreaterThanOrEqual(44);
    await panel.screenshot({ path: `${directory}/usage-${width}.png`, animations: "disabled" });
  }
  let rejectRefresh = true;
  await page.route(`**/workspaces/${wid}/model-usage?*`, route => rejectRefresh
    ? route.fulfill({ status: 503, json: { error: { code: "temporary", message: "Usage is temporarily unavailable." } } })
    : route.continue());
  await panel.getByRole("button", { name: "Refresh AI usage" }).click();
  await expect(panel.getByRole("alert")).toContainText("temporarily unavailable");
  await expect(costPanel).toHaveCount(0);
  rejectRefresh = false;
  await panel.getByRole("button", { name: "Refresh AI usage" }).click();
  await expect(costPanel).toBeVisible();
  const period = page.waitForResponse(response => response.url().endsWith(`/workspaces/${wid}/model-usage?days=7`));
  await panel.getByRole("combobox", { name: "Reporting window", exact: true }).selectOption("7");
  expect((await period).ok()).toBe(true);
  command(["-c", "import sys;from uuid import UUID;from sqlalchemy import create_engine,delete;from execplus.config import Settings;from execplus.infrastructure.persistence import schema as s;settings=Settings();assert settings.environment=='test';engine=create_engine(settings.database_url);context=engine.begin();conn=context.__enter__();conn.execute(delete(s.memberships).where(s.memberships.c.workspace_id==UUID(sys.argv[1]),s.memberships.c.user_id==UUID(sys.argv[2])));context.__exit__(None,None,None);engine.dispose()", wid, actor.id]);
  await panel.getByRole("button", { name: "Refresh AI usage" }).click();
  await expect(panel.getByRole("alert")).toBeVisible();
  await expect(costPanel).toHaveCount(0);
  expect(errors).toEqual([]);
});
