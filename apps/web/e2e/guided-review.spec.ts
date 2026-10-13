/* Use case: Verifies the recovered teammate onboarding against real governed APIs.
What it does: Covers optional review, private notes, explicit drafts and incomplete/error cases. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
const api = "http://127.0.0.1:8001";
function account() {
  const email = `guided-${randomUUID()}@example.test`;
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", email], { cwd: "../..", encoding: "utf8" }).trim();
  return { email, token, headers: { Authorization: `Bearer ${token}` } };
}
async function signIn(page: Page, person: ReturnType<typeof account>, query = "") {
  await page.goto(`/workspace${query}`);
  await page.getByLabel("Session token").fill(person.token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
  await page.waitForLoadState("networkidle");
}
async function upload(page: Page, content = "city,amount,cost\nKarachi,0.10,0.05\nLahore,0.20,0.15\n") {
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "guided.csv", mimeType: "text/csv", buffer: Buffer.from(content) });
  const response = page.waitForResponse(r => r.url().includes("/uploads?filename=") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  const r = await response; expect(r.status()).toBe(201); const stored = await r.json();
  const root = `/workspaces/${stored.workspace_id}/datasets/${stored.dataset_id}/uploads/${stored.id}`;
  const panel = page.getByRole("region", { name: "Guided data review", exact: true });
  await expect(panel.getByRole("button", { name: "Skip for now", exact: true })).toBeVisible();
  return { root, stored, panel };
}
async function corrections(page: Page, panel: ReturnType<Page["getByRole"]>) {
  await panel.getByRole("button", { name: "No, let me explain", exact: true }).click();
  await panel.getByRole("combobox", { name: "What does one row represent?", exact: true }).selectOption("record");
  await panel.getByRole("button", { name: "Use this answer and continue", exact: true }).click();
  await panel.getByRole("button", { name: "No, let me explain", exact: true }).click();
  await panel.getByLabel("Unit, if you know it", { exact: true }).fill("PKR");
  await panel.getByLabel("Column meaning for the shared draft", { exact: true }).fill("Declared measure description");
  await panel.getByLabel("Personal data note (optional)", { exact: true }).fill("Private reviewer explanation only");
  await panel.getByRole("button", { name: "Use this answer and continue", exact: true }).click();
  await panel.getByRole("button", { name: "Skip this question", exact: false }).click();
  await panel.getByRole("button", { name: "Skip this question", exact: false }).click();
  await expect(panel.getByRole("heading", { name: "Review your answers before saving", exact: true })).toBeVisible();
}

test("guided review can be skipped without replacing first-upload insights or shared definitions", async ({ page }) => {
  const person = account(); await signIn(page, person); const { root, panel } = await upload(page);
  const before = await (await page.request.get(api + root + "/understanding", { headers: person.headers })).json();
  await expect(page.locator(".discoveryValue").first()).toBeVisible();
  await panel.getByRole("button", { name: "Skip for now", exact: true }).click();
  await expect(panel).toHaveCount(0);
  const after = await (await page.request.get(api + root + "/understanding", { headers: person.headers })).json();
  expect(after).toEqual(before);
  await page.getByRole("button", { name: "Review this upload step by step", exact: true }).click();
  await expect(panel.getByRole("button", { name: "Skip for now", exact: true })).toBeVisible();
});

test("private notes and shared drafts save separately without silently confirming a dataset", async ({ page }) => {
  const person = account(); await signIn(page, person); const { root, stored, panel } = await upload(page);
  const before = await (await page.request.get(api + root + "/understanding", { headers: person.headers })).json();
  await corrections(page, panel);
  await expect(panel.getByRole("checkbox", { name: "Share my notes", exact: false })).not.toBeChecked();
  await panel.getByRole("button", { name: "Save my data notes", exact: true }).click();
  await expect(panel).toContainText("Notes saved privately");
  expect(await (await page.request.get(api + root + "/understanding", { headers: person.headers })).json()).toEqual(before);
  await panel.getByRole("button", { name: "Save draft meanings", exact: true }).click();
  await expect(panel).toContainText("Shared corrections saved as a draft");
  const saved = await (await page.request.get(api + root + "/understanding", { headers: person.headers })).json();
  expect(saved.state).toBe("needs_review"); expect(saved.definition.grain).toBe("record");
  expect(saved.definition.columns.find((c: { name: string }) => c.name === "amount")).toMatchObject({ unit: "PKR", meaning: "Declared measure description" });
  expect(JSON.stringify(saved.definition)).not.toContain("Private reviewer explanation");
  expect(saved.definition.metrics).toEqual(before.definition.metrics);
  const member = account(); const invited = await page.request.post(`${api}/workspaces/${stored.workspace_id}/invitations`, { headers: person.headers, data: { email: member.email, role: "member" } });
  expect(invited.status()).toBe(201);
  expect((await page.request.post(`${api}/workspaces/${stored.workspace_id}/invitations/${(await invited.json()).id}/accept`, { headers: member.headers })).status()).toBe(200);
  const documents = await page.request.get(`${api}/workspaces/${stored.workspace_id}/datasets/${stored.dataset_id}/documents`, { headers: member.headers });
  expect(await documents.json()).toEqual([]);
  for (const width of [1440, 390, 320]) { await page.setViewportSize({ width, height: 900 }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true); }
  await panel.getByRole("button", { name: "Review and confirm full meanings", exact: true }).click();
  await expect(page.getByRole("region", { name: "Data understanding", exact: true })).toBeVisible();
});

test("wide-schema focused review never auto-confirms the unreviewed columns", async ({ page }) => {
  const person = account(); await signIn(page, person);
  const headers = Array.from({ length: 12 }, (_, i) => `measure_${i}`);
  const { root, panel } = await upload(page, headers.join(",") + "\n" + headers.map((_, i) => i + 1).join(",") + "\n" + headers.map((_, i) => i + 2).join(",") + "\n");
  for (let i = 0; i < 11; i += 1) await panel.getByRole("button", { name: "Yes, that's right", exact: true }).click();
  await expect(panel).toContainText("at most 10 of 12 columns");
  await expect(panel.getByRole("button", { name: "Save draft meanings", exact: true })).toBeDisabled();
  const current = await (await page.request.get(api + root + "/understanding", { headers: person.headers })).json();
  expect(current.state).toBe("inferred"); expect(current.version).toBe(0); expect(current.definition.columns).toHaveLength(12);
});

test("a conflicting draft save cannot claim success or discard an already saved private note", async ({ page }) => {
  const person = account(); await signIn(page, person); const { root, panel } = await upload(page); await corrections(page, panel);
  await panel.getByRole("button", { name: "Save my data notes", exact: true }).click(); await expect(panel).toContainText("Notes saved privately");
  const current = await (await page.request.get(api + root + "/understanding", { headers: person.headers })).json();
  const changed = await page.request.post(api + root + "/understanding", { headers: person.headers, data: { revision_id: current.revision_id, expected_version: current.version, state: "needs_review", definition: { ...current.definition, description: "Another explicit edit" } } }); expect(changed.status()).toBe(201);
  await panel.getByRole("button", { name: "Save draft meanings", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("Draft save did not confirm success");
  await expect(panel).not.toContainText("Shared corrections saved as a draft");
  await expect(panel.getByRole("button", { name: "Save my data notes", exact: true })).toBeDisabled();
  const saved = await (await page.request.get(api + root + "/understanding", { headers: person.headers })).json(); expect(saved.definition.description).toBe("Another explicit edit");
});

test("an ordinary member can save a private interpretation but cannot change shared meanings", async ({ page }) => {
  const owner = account(); await signIn(page, owner); const { root, stored } = await upload(page);
  const before = await (await page.request.get(api + root + "/understanding", { headers: owner.headers })).json();
  const member = account(); const invitation = await page.request.post(`${api}/workspaces/${stored.workspace_id}/invitations`, { headers: owner.headers, data: { email: member.email, role: "member" } });
  expect(invitation.status()).toBe(201); expect((await page.request.post(`${api}/workspaces/${stored.workspace_id}/invitations/${(await invitation.json()).id}/accept`, { headers: member.headers })).status()).toBe(200);
  const otherPage = await page.context().newPage(); await signIn(otherPage, member, `?workspace=${stored.workspace_id}`);
  await otherPage.getByRole("button", { name: "Review this upload step by step", exact: true }).click();
  const panel = otherPage.getByRole("region", { name: "Guided data review", exact: true });
  await panel.getByRole("button", { name: "Skip this question", exact: false }).click();
  await panel.getByRole("button", { name: "No, let me explain", exact: true }).click();
  await expect(panel.getByLabel("Column meaning for the shared draft", { exact: true })).toHaveCount(0);
  await panel.getByLabel("Personal data note (optional)", { exact: true }).fill("Member-private interpretation");
  await panel.getByRole("button", { name: "Use this answer and continue", exact: true }).click();
  await panel.getByRole("button", { name: "Skip this question", exact: false }).click();
  await panel.getByRole("button", { name: "Skip this question", exact: false }).click();
  await expect(panel.getByRole("button", { name: "Save draft meanings", exact: true })).toBeDisabled();
  await panel.getByRole("button", { name: "Save my data notes", exact: true }).click(); await expect(panel).toContainText("Notes saved privately");
  expect(await (await page.request.get(api + root + "/understanding", { headers: owner.headers })).json()).toEqual(before);
  expect(await (await page.request.get(`${api}/workspaces/${stored.workspace_id}/datasets/${stored.dataset_id}/documents`, { headers: owner.headers })).json()).toEqual([]);
  await otherPage.close();
});

test("sharing a review note is explicit and still does not confirm business meanings", async ({ page }) => {
  const owner = account(); await signIn(page, owner); const { root, stored, panel } = await upload(page);
  const before = await (await page.request.get(api + root + "/understanding", { headers: owner.headers })).json(); await corrections(page, panel);
  await panel.getByRole("checkbox", { name: "Share my notes", exact: false }).check();
  await panel.getByRole("button", { name: "Save my data notes", exact: true }).click(); await expect(panel).toContainText("explicitly shared");
  const documents = await (await page.request.get(`${api}/workspaces/${stored.workspace_id}/datasets/${stored.dataset_id}/documents`, { headers: owner.headers })).json();
  expect(documents).toHaveLength(1); expect(documents[0].shared).toBe(true);
  expect(await (await page.request.get(api + root + "/understanding", { headers: owner.headers })).json()).toEqual(before);
});
