/* Use case: Proves native account and private guide journeys through the actual UI.
What it does: Exercises signup, resume, source profiling, password rotation and explicit invitation proof with synthetic users. */

import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { finishInitialReview, navigateTo } from "./workspace-helpers";

const api = "http://127.0.0.1:8001";
const password = "synthetic browser passphrase 27";
const replacement = "replacement browser passphrase 49";

async function nativeLogin(page: Page, email: string, secret = password) {
  await page.goto("/workspace");
  const access = page.getByRole("region", { name: "Local account access", exact: true });
  await access.getByLabel("Account email", { exact: true }).fill(email);
  await access.getByLabel("Account password", { exact: true }).fill(secret);
  const result = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/auth/login"));
  await access.getByRole("button", { name: "Sign in with password", exact: true }).click();
  const body = await (await result).json();
  await expect(page.getByText(`Signed in as ${email}`, { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeEnabled();
  return { token: body.token as string, userId: body.user.id as string, headers: { Authorization: `Bearer ${body.token}` } };
}
async function navigate(page: Page, name: string) {
  await navigateTo(page, name);
}
async function register(page: Page, email: string) {
  const response = await page.request.post(`${api}/auth/register`, { data: { email, password, display_name: "Synthetic account", workspace_name: "Synthetic local workspace" } });
  expect(response.status()).toBe(202);
}

test("native signup creates a private workspace and the guide resumes without claiming skipped work", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const email = `native-browser-${randomUUID()}@example.test`;
  await page.goto("/workspace");
  await expect(page.getByLabel("Session token", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
  const access = page.getByRole("region", { name: "Local account access", exact: true });
  await access.getByRole("button", { name: "New account", exact: true }).click();
  await access.getByLabel("Account email", { exact: true }).fill(email);
  await access.getByLabel("Your name", { exact: true }).fill("Synthetic owner");
  await access.getByLabel("Workspace name", { exact: true }).fill("Synthetic browser workspace");
  await access.getByLabel("Account password", { exact: true }).fill(password);
  await access.getByLabel("Confirm account password", { exact: true }).fill(password);
  const signedIn = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/auth/login"));
  await access.getByRole("button", { name: "Create local account", exact: true }).click();
  const created = await (await signedIn).json();
  const session = { token: created.token as string, userId: created.user.id as string, headers: { Authorization: `Bearer ${created.token}` } };
  await expect(page.getByText(`Signed in as ${email}`, { exact: true })).toBeVisible();
  await expect(page.getByText("Your private workspace is ready", { exact: false })).toBeVisible();
  await page.reload();
  await expect(page.getByText(`Signed in as ${email}`, { exact: true })).toBeVisible();
  expect((await page.context().cookies(api)).find(cookie => cookie.name === "execplus_session")).toMatchObject({ httpOnly: true, sameSite: "Lax" });
  const wid = await page.getByRole("combobox", { name: "Current workspace", exact: true }).inputValue();
  const guidePath = `${api}/workspaces/${wid}/onboarding-progress`;
  const guide = page.locator("details").filter({ has: page.locator("summary").filter({ hasText: "Your setup guide" }) }).first();
  await expect(guide).toHaveAttribute("open", "");
  await guide.getByRole("button", { name: "Skip this step", exact: true }).click();
  await expect(guide.getByRole("heading", { level: 3 })).toHaveText("Check the data profile");
  await guide.getByRole("button", { name: "Pause guide", exact: true }).click();
  await expect(guide).not.toHaveAttribute("open", "");
  let state = await (await page.request.get(guidePath, { headers: session.headers })).json();
  expect(state).toMatchObject({ paused: true, active_step: "quality", skipped_steps: ["data"] });
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.reload();
  await expect(page.getByRole("region", { name: "Local account access", exact: true })).toBeVisible();
  const resumed = await nativeLogin(page, email);
  await expect(guide.locator("summary")).toContainText("paused");
  await expect(guide).not.toHaveAttribute("open", "");
  await guide.locator("summary").click();
  await guide.getByRole("button", { name: "Resume guide", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "synthetic-native-sales.csv", mimeType: "text/csv", buffer: Buffer.from("date,category,revenue,cost\n2026-01-01,A,100.10,60.05\n2026-01-02,B,120.20,70.10\n2026-01-03,A,140.30,80.15\n") });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await navigate(page, "Data library");
  if (await guide.getAttribute("open") === null) await guide.locator("summary").click();
  await guide.getByRole("button", { name: "Refresh recorded progress", exact: true }).click();
  state = await (await page.request.get(guidePath, { headers: resumed.headers })).json();
  expect(state.steps.find((step: { id: string }) => step.id === "quality").observed).toBe(true);
  expect(state.steps.find((step: { id: string }) => step.id === "recommendations").observed).toBe(false);
  await expect(guide.getByRole("button", { name: "Finish guide", exact: true })).toBeDisabled();
  const unfinished = state.steps.filter((step: { observed: boolean; skipped: boolean }) => !step.observed && !step.skipped);
  for (const step of unfinished) {
    if (state.active_step !== step.id) {
      await guide.getByRole("combobox", { name: "Setup step", exact: true }).click();
      const changed = page.waitForResponse(response => response.url() === guidePath && response.request().method() === "PUT");
      await page.getByRole("option", { name: step.label, exact: true }).click();
      const response = await changed;
      expect(response.status()).toBe(200);
      state = await response.json();
    }
    const skipped = page.waitForResponse(response => response.url() === guidePath && response.request().method() === "PUT");
    await guide.getByRole("button", { name: "Skip this step", exact: true }).click();
    const response = await skipped;
    expect(response.status()).toBe(200);
    state = await response.json();
  }
  const finished = page.waitForResponse(response => response.url() === guidePath && response.request().method() === "PUT");
  await guide.getByRole("button", { name: "Finish guide", exact: true }).click();
  state = await (await finished).json();
  expect(state.finished).toBe(true);
  expect(state.steps.find((step: { id: string }) => step.id === "recommendations")).toMatchObject({ observed: false, skipped: true });
  await expect(guide.locator("summary")).toContainText("finished");
  await expect(guide).not.toHaveAttribute("open", "");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  const completed = await nativeLogin(page, email);
  await expect(guide.locator("summary")).toContainText("finished");
  await expect(guide).not.toHaveAttribute("open", "");
  await guide.locator("summary").click();
  await expect(guide.getByRole("button", { name: "Resume guide", exact: true })).toBeVisible();
  state = await (await page.request.get(guidePath, { headers: completed.headers })).json();
  expect(state.finished).toBe(true);
  expect(state.steps.find((step: { id: string }) => step.id === "recommendations")).toMatchObject({ observed: false, skipped: true });
  expect(await page.evaluate(() => Object.keys(localStorage).filter(key => /password|token|session/i.test(key)))).toEqual([]);
  mkdirSync("../../data/verification/2026-10-17/two-phase/accounts-ui", { recursive: true });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.screenshot({ path: `../../data/verification/2026-10-17/two-phase/accounts-ui/guide-${width}.png`, fullPage: true });
  }
  expect(errors).toEqual([]);
});

test("password rotation and account disable revoke access from the real account controls", async ({ page }) => {
  const email = `security-browser-${randomUUID()}@example.test`;
  await register(page, email);
  const session = await nativeLogin(page, email);
  await navigate(page, "Team & settings");
  const security = page.getByRole("region", { name: "Your account settings", exact: true });
  await expect(security).toContainText(session.userId);
  await security.getByText("Change your password", { exact: true }).click();
  await security.getByLabel("Current password", { exact: true }).fill(password);
  await security.getByLabel("New password", { exact: true }).fill(replacement);
  await security.getByLabel("Confirm new password", { exact: true }).fill(replacement);
  await security.getByRole("button", { name: "Change password", exact: true }).click();
  await expect(security.getByRole("status")).toContainText("Password changed");
  expect((await page.request.get(`${api}/auth/me`, { headers: session.headers })).status()).toBe(401);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  const next = await nativeLogin(page, email, replacement);
  await navigate(page, "Team & settings");
  await security.getByText("Disable your account", { exact: true }).click();
  await security.getByLabel("Password to disable account", { exact: true }).fill(replacement);
  await security.getByRole("checkbox", { name: /I understand that I will be signed out/ }).check();
  await security.getByRole("button", { name: "Disable my account", exact: true }).click();
  await expect(page.getByLabel("Session token", { exact: true })).toBeVisible();
  expect((await page.request.get(`${api}/auth/me`, { headers: next.headers })).status()).toBe(401);
});

test("a native teammate joins only after the manager explicitly checks their account ID", async ({ page, browser }) => {
  const ownerEmail = `manager-browser-${randomUUID()}@example.test`;
  const memberEmail = `teammate-browser-${randomUUID()}@example.test`;
  await register(page, ownerEmail); await register(page, memberEmail);
  const owner = await nativeLogin(page, ownerEmail);
  const wid = await page.getByRole("combobox", { name: "Current workspace", exact: true }).inputValue();
  await navigate(page, "Team & settings");
  await page.getByLabel("Teammate email", { exact: true }).fill(memberEmail);
  await page.getByRole("button", { name: "Create invitation", exact: true }).click();
  const second = await browser.newPage({ baseURL: "http://127.0.0.1:3001" });
  try {
    const member = await nativeLogin(second, memberEmail);
    const checked = page.locator("li").filter({ hasText: memberEmail }).filter({ has: page.getByRole("button", { name: `Copy link for ${memberEmail}`, exact: true }) }).first();
    await checked.getByText(`Check the local account for ${memberEmail}`, { exact: true }).click();
    await checked.getByLabel("Invited account ID", { exact: true }).fill(member.userId);
    await checked.getByRole("checkbox", { name: /I checked this exact account ID/ }).check();
    const approved = page.waitForResponse(response => response.url().endsWith("/identity-approval") && response.request().method() === "POST");
    await checked.getByRole("button", { name: `Approve account for ${memberEmail}`, exact: true }).click();
    const approval = await approved;
    expect(approval.status()).toBe(204);
    const invitationId = new URL(approval.url()).pathname.split("/").at(-2)!;
    await navigate(second, "Team & settings");
    await second.getByLabel("Invitation link", { exact: true }).fill(`http://127.0.0.1:3001/workspace?workspace=${wid}&invitation=${invitationId}`);
    await second.getByRole("button", { name: "Accept invitation", exact: true }).click();
    await expect(second.getByRole("combobox", { name: "Current workspace", exact: true })).toHaveValue(wid);
    const guide = second.locator("details").filter({ has: second.locator("summary").filter({ hasText: "Your setup guide" }) }).first();
    await expect(guide.getByRole("heading", { level: 3 })).toBeVisible();
    await guide.getByRole("button", { name: "Next setup step", exact: true }).click();
    await expect(guide.getByRole("heading", { level: 3 })).toHaveText("Check the data profile");
    const removed = await page.request.delete(`${api}/workspaces/${wid}/members/${member.userId}`, { headers: owner.headers });
    expect(removed.status()).toBe(204);
    await guide.getByRole("button", { name: "Refresh recorded progress", exact: true }).click();
    await expect(guide.getByRole("alert")).toBeVisible();
    await expect(guide.getByRole("heading", { level: 3 })).toHaveCount(0);
    await expect(guide.getByRole("button", { name: "Reload setup guide", exact: true })).toBeVisible();
  } finally { await second.close(); }
});
