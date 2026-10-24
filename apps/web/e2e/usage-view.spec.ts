/* Use case: Proves the owner Usage view, limit notices and staff usage ranking through real screens.
What it does: Uploads a file, lowers the dataset allowance to the current count, then checks exact counts, the reached notice and the admin ranking. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { finishInitialReview, navigateTo } from "./workspace-helpers";

const api = "http://127.0.0.1:8001";

test("owners see exact usage, daily history and limit notices; staff see the workspace ranked", async ({ page, request }) => {
  test.setTimeout(100_000);
  const email = `usage-${randomUUID()}@example.test`;
  const name = `Synthetic usage ${randomUUID()}`;
  const password = "synthetic usage passphrase 31";
  expect((await page.request.post(`${api}/auth/register`, { data: { email, password, display_name: "Synthetic owner", workspace_name: name } })).status()).toBe(202);
  const account = await (await request.post(`${api}/auth/login`, { data: { email, password } })).json();
  execFileSync("python3", ["-m", "execplus.manage", "grant-staff", "--email", email, "--role", "admin", "--account-id", account.user.id, "--identity-checked"], { cwd: "../..", encoding: "utf8" });
  await page.goto("/workspace");
  const login = page.getByRole("region", { name: "Local account access", exact: true });
  await login.getByLabel("Account email", { exact: true }).fill(email);
  await login.getByLabel("Account password", { exact: true }).fill(password);
  const signed = page.waitForResponse(response => response.url().endsWith("/auth/login") && response.request().method() === "POST");
  await login.getByRole("button", { name: "Sign in with password", exact: true }).click();
  const headers = { Authorization: `Bearer ${(await (await signed).json()).token}` };
  await expect(page.getByText(`Signed in as ${email}`, { exact: true })).toBeVisible();
  const wid = await page.getByRole("combobox", { name: "Current workspace", exact: true }).inputValue();

  await navigateTo(page, "Data library");
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "synthetic-usage.csv", mimeType: "text/csv", buffer: Buffer.from("date,category,revenue\n2026-01-01,A,10.10\n2026-01-02,B,20.20\n") });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);

  const catalog = await (await page.request.get(`${api}/plans`, { headers })).json();
  const key = `usage-${randomUUID().slice(0, 12)}`;
  expect((await page.request.put(`${api}/admin/plans/${key}`, { headers, data: { expected_version: 0, name: "Synthetic one dataset", limits: { ...catalog.find((item: { key: string }) => item.key === "demo").limits, datasets: 1 } } })).status()).toBe(200);
  const current = await (await page.request.get(`${api}/admin/workspaces/${wid}/plan`, { headers })).json();
  const start = new Date(Date.now() - 1000);
  expect((await page.request.put(`${api}/admin/workspaces/${wid}/plan`, { headers, data: { expected_version: current.version, plan_key: key, starts_at: start.toISOString(), ends_at: new Date(start.getTime() + 30 * 86400000).toISOString() } })).status()).toBe(200);

  await navigateTo(page, "Data library");
  const banner = page.getByRole("complementary", { name: "Workspace allowance notice", exact: true });
  await expect(banner).toContainText("An allowance has been reached");
  await expect(banner).toContainText("This workspace has reached its datasets allowance (1 of 1 used).");
  await expect(banner).toContainText("Saved answers, dashboards, earlier results and receipt replays still open");

  await navigateTo(page, "Usage & retention");
  await page.getByRole("button", { name: "Workspace allowances", exact: true }).click();
  const summary = page.getByRole("region", { name: "Workspace allowances", exact: true });
  await expect(summary).toContainText(`${key} · Active`);
  await expect(summary.getByText("Datasets · Limit reached", { exact: true })).toBeVisible();
  const usage = await (await page.request.get(`${api}/workspaces/${wid}/usage`, { headers })).json();
  expect(usage.allowances.datasets).toMatchObject({ used: 1, limit: 1, remaining: 0, state: "reached" });
  const today = new Date().toISOString().slice(0, 10);
  const table = summary.getByRole("table", { name: "Daily usage history", exact: true });
  await expect(table.getByRole("row")).toHaveCount(31);
  const todayRow = table.getByRole("row", { name: new RegExp(`^${today}`) });
  const uploads = usage.daily.rows.find((row: { day: string; kind: string }) => row.day === today && row.kind === "uploads");
  expect(uploads.count).toBe(1);
  const counted = (kind: string) => String(usage.daily.rows.find((row: { day: string; kind: string }) => row.day === today && row.kind === kind)?.count ?? 0);
  await expect(todayRow.getByRole("cell")).toHaveText(usage.daily.kinds.map(counted));

  await navigateTo(page, "Admin console");
  await page.getByRole("button", { name: "Usage by workspace", exact: true }).click();
  const ranking = page.getByRole("region", { name: "Workspace usage ranking", exact: true });
  await expect(ranking.getByRole("row", { name: new RegExp(name) })).toContainText(key);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
});
