/* Use case: Verifies the first-run get-to-know-you flow for a new native account in a real browser.
What it does: Registers an account, answers three questions, skips the rest, confirms the workspace
opens, that reopening does not repeat the flow, and that "Redo the questions" works. */
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

const api = "http://127.0.0.1:8001";
const password = "synthetic onboarding passphrase 41";

test("a new account meets the questionnaire once, can skip the rest and redo it later", async ({ page, request }) => {
  test.setTimeout(120_000);
  const email = `onboard-${randomUUID()}@example.test`;
  expect((await request.post(`${api}/auth/register`, { data: { email, password, display_name: "Synthetic newcomer", workspace_name: `Onboarding ${randomUUID()}` } })).status()).toBe(202);
  const account = await (await request.post(`${api}/auth/login`, { data: { email, password } })).json();
  const headers = { Authorization: `Bearer ${account.token}` };
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));

  await page.goto("/workspace");
  await page.getByLabel("Session token", { exact: true }).fill(account.token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const flow = page.getByRole("main", { name: "Getting to know you", exact: true });
  await expect(flow).toBeVisible();
  await expect(flow.getByRole("heading", { level: 1 })).toContainText("let's get to know you");
  await expect(page.getByText("Signed in as", { exact: false })).toHaveCount(0);
  await flow.getByRole("button", { name: "Let's start", exact: true }).click();
  await expect(flow.getByText("Question 1 of 18", { exact: true })).toBeVisible();
  await flow.getByRole("textbox").fill("Hadi");
  await flow.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(flow.getByText("Question 2 of 18", { exact: true })).toBeVisible();
  await flow.getByRole("radio", { name: "Analyst", exact: true }).click();
  await flow.getByRole("button", { name: "Continue", exact: true }).click();
  await flow.getByRole("button", { name: "Back", exact: true }).click();
  await expect(flow.getByRole("radio", { name: "Analyst", exact: true })).toHaveAttribute("aria-checked", "true");
  await flow.getByRole("button", { name: "Continue", exact: true }).click();
  await flow.getByRole("button", { name: "Skip this question", exact: true }).click();
  await expect(flow.getByText("Question 4 of 18", { exact: true })).toBeVisible();
  await flow.getByRole("button", { name: "Continue", exact: true }).click();
  await flow.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(flow.getByText("Question 6 of 18", { exact: true })).toBeVisible();
  await flow.getByRole("checkbox", { name: "Track KPIs", exact: true }).click();
  await flow.getByRole("checkbox", { name: "Forecast", exact: true }).click();
  await flow.getByRole("button", { name: "Skip for now", exact: true }).click();

  await expect(page.getByText(`Signed in as ${email}`, { exact: true })).toBeVisible();
  const saved = await (await request.get(`${api}/me/profile`, { headers })).json();
  expect(saved).toMatchObject({ status: "skipped", version: 1, preferred_name: "Hadi", answers: { role: "Analyst", goals: ["Track KPIs", "Forecast"] } });

  await page.goto("/workspace");
  await page.getByLabel("Session token", { exact: true }).fill(account.token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText(`Signed in as ${email}`, { exact: true })).toBeVisible();
  await expect(flow).toHaveCount(0);

  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Team & settings", exact: true }).click();
  await page.getByRole("button", { name: "Answer the questions", exact: true }).click();
  await expect(flow).toBeVisible();
  await flow.getByRole("button", { name: "Let's start", exact: true }).click();
  await expect(flow.getByRole("textbox")).toHaveValue("Hadi");
  for (let index = 0; index < 18; index += 1) {
    const finish = flow.getByRole("button", { name: "Finish", exact: true });
    if (await finish.isVisible()) { await finish.click(); break; }
    await flow.getByRole("button", { name: "Continue", exact: true }).click();
  }
  await expect(flow.getByRole("heading", { level: 1 })).toContainText("Thanks, Hadi!");
  await flow.getByRole("button", { name: "Continue to workspace", exact: true }).click();
  await expect(page.getByText(`Signed in as ${email}`, { exact: true })).toBeVisible();
  const redone = await (await request.get(`${api}/me/profile`, { headers })).json();
  expect(redone).toMatchObject({ status: "completed", version: 2, preferred_name: "Hadi", answers: { role: "Analyst" } });
  expect(errors).toEqual([]);
});
