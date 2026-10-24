/* Use case: Proves local plan controls through real owner/admin screens.
What it does: Checks a native Demo allowance, UI-assigned limits, upload denial, a price-free upgrade and safe refresh failure. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { finishInitialReview, navigateTo } from "./workspace-helpers";

const api = "http://127.0.0.1:8001";

test("local allowances enforce backend limits and administrator changes appear for the owner", async ({ page, request }) => {
  test.setTimeout(100_000);
  const email = `plans-${randomUUID()}@example.test`;
  const name = `Synthetic allowances ${randomUUID()}`;
  const password = "synthetic allowance passphrase 27";
  expect((await page.request.post(`${api}/auth/register`, { data: { email, password, display_name: "Synthetic operator", workspace_name: name } })).status()).toBe(202);
  const checkedAccount = await (await request.post(`${api}/auth/login`, { data: { email, password } })).json();
  execFileSync("python3", ["-m", "execplus.manage", "grant-staff", "--email", email, "--role", "admin", "--account-id", checkedAccount.user.id, "--identity-checked"], { cwd: "../..", encoding: "utf8" });
  await page.goto("/workspace");
  const login = page.getByRole("region", { name: "Local account access", exact: true });
  await login.getByLabel("Account email", { exact: true }).fill(email);
  await login.getByLabel("Account password", { exact: true }).fill(password);
  const signed = page.waitForResponse(response => response.url().endsWith("/auth/login") && response.request().method() === "POST");
  await login.getByRole("button", { name: "Sign in with password", exact: true }).click();
  const auth = await (await signed).json();
  const headers = { Authorization: `Bearer ${auth.token}` };
  await expect(page.getByText(`Signed in as ${email}`, { exact: true })).toBeVisible();
  const wid = await page.getByRole("combobox", { name: "Current workspace", exact: true }).inputValue();
  const navigate = async (label: string) => navigateTo(page, label);
  await navigate("Usage & retention");
  await page.getByRole("button", { name: "Workspace allowances", exact: true }).click();
  const summary = page.getByRole("region", { name: "Workspace allowances", exact: true });
  await expect(summary).toContainText("demo · Active");
  await expect(summary).toContainText("4 remaining");
  const catalog = await (await page.request.get(`${api}/plans`, { headers })).json();
  const limited = `browser-${randomUUID().slice(0, 12)}`;
  expect((await page.request.put(`${api}/admin/plans/${limited}`, { headers, data: { expected_version: 0, name: "Synthetic paused uploads", limits: { ...catalog.find((item: { key: string }) => item.key === "demo").limits, datasets: 0 } } })).status()).toBe(200);
  async function assign(label: string) {
    await navigate("Admin console");
    await page.getByLabel("Find a workspace", { exact: true }).fill(wid);
    await page.getByRole("button", { name: "Search workspaces", exact: true }).click();
    await page.getByRole("button", { name, exact: true }).click();
    const details = page.getByRole("region", { name: "Admin workspace details", exact: true });
    await details.getByText("Local workspace allowances", { exact: true }).click();
    const panel = details.getByRole("region", { name: "Assign local allowance", exact: true });
    await expect(panel.getByRole("combobox", { name: "Local plan", exact: true })).toBeEnabled();
    await panel.getByRole("combobox", { name: "Local plan", exact: true }).click();
    await page.getByRole("option", { name: label, exact: true }).click();
    await panel.getByRole("button", { name: "Assign local allowance", exact: true }).click();
    await expect(panel.getByRole("status")).toContainText("No payment or subscription was created");
  }
  await assign("Synthetic paused uploads");
  await navigate("Data library");
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "synthetic-plan-sales.csv", mimeType: "text/csv", buffer: Buffer.from("date,category,revenue,cost\n2026-01-01,A,10.10,5.05\n2026-01-02,B,20.20,8.10\n") });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(page.getByText("This workspace has reached its local allowance. Saved answers, dashboards, earlier results and receipt replays still open; new work of this kind waits until the allowance is reviewed. Ask an administrator to review it.", { exact: true })).toBeVisible();
  expect((await page.request.get(`${api}/workspaces/${wid}/datasets`, { headers })).status()).toBe(200);
  expect(await (await page.request.get(`${api}/workspaces/${wid}/datasets`, { headers })).json()).toEqual([]);
  await assign("Starter");
  await navigate("Data library");
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "synthetic-plan-sales.csv", mimeType: "text/csv", buffer: Buffer.from("date,category,revenue,cost\n2026-01-01,A,10.10,5.05\n2026-01-02,B,20.20,8.10\n") });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await navigate("Usage & retention");
  await page.getByRole("button", { name: "Workspace allowances", exact: true }).click();
  await expect(summary).toContainText("starter · Active");
  const reported = await (await page.request.get(`${api}/workspaces/${wid}/plan`, { headers })).json();
  expect(reported.allowances.datasets).toMatchObject({ used: 1, limit: 50, remaining: 49 });
  await expect(summary).toContainText("49 remaining");
  mkdirSync("../../data/verification/2026-10-17/two-phase/plans-ui", { recursive: true });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await summary.screenshot({ path: `../../data/verification/2026-10-17/two-phase/plans-ui/allowances-${width}.png` });
  }
  await page.route(`**/workspaces/${wid}/usage`, route => route.fulfill({ status: 403, json: { error: { code: "forbidden", message: "Allowance access removed." } } }));
  await summary.getByRole("button", { name: "Refresh allowances", exact: true }).click();
  await expect(summary.getByRole("alert")).toContainText("Allowance access removed");
  await expect(summary.getByText("49 remaining", { exact: true })).toHaveCount(0);
});
