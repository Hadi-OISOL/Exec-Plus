/* Use case: Exercises explicit agent setup, structured diagrams and private PDF downloads.
What it does: Checks saved preferences, upload-context ordering, real rendered maps, exact exports and immutable conversation reopening. */

import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { mkdirSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { finishInitialReview, openConversation } from "./workspace-helpers";

const api = "http://127.0.0.1:8001";
const evidence = "../../data/verification/2026-10-16/domain-agent-tools";

async function signIn(page: Page) {
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `agent-tools-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Upload file", exact: true })).toBeVisible();
  return { Authorization: `Bearer ${token}` };
}
async function upload(page: Page, name = "simple.csv", csv = "date,category,revenue,cost\n2026-01-01,A,100.10,60\n2026-01-02,B,120.20,70\n") {
  await page.getByLabel("CSV or Excel file").setInputFiles({ name, mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
}
async function source(page: Page) {
  const workspace = await page.getByLabel("Current workspace").inputValue();
  return { workspace, root: `/workspaces/${workspace}/datasets/${await page.getByLabel("Dataset", { exact: true }).inputValue()}/uploads/${await page.getByLabel("Profile upload").inputValue()}` };
}
async function capture(page: Page, name: string) {
  mkdirSync(evidence, { recursive: true });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    if (name === "diagram") await page.getByRole("region", { name: "Data organisation diagram", exact: true }).getByRole("heading", { name: "How this file is organised", exact: true }).scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.screenshot({ path: `${evidence}/${name}-${width}.png`, animations: "disabled", fullPage: true });
    await page.screenshot({ path: `${evidence}/${name}-viewport-${width}.png`, animations: "disabled" });
    if (name === "diagram") {
      const chart = page.locator('[data-diagram-renderer="apache-echarts-tree"]');
      await chart.scrollIntoViewIfNeeded();
      await chart.screenshot({ path: `${evidence}/diagram-chart-${width}.png`, animations: "disabled" });
    }
  }
}

test("quick private setup keeps drafts and writes only after explicit save", async ({ page }) => {
  const headers = await signIn(page);
  await upload(page);
  await finishInitialReview(page);
  const { workspace } = await source(page);
  const path = `${api}/workspaces/${workspace}/agent-memory`;
  const setup = page.getByRole("region", { name: "Quick private agent setup", exact: true });
  await setup.getByRole("button", { name: "Personalize my answers", exact: true }).click();
  await setup.getByLabel("Your perspective", { exact: false }).selectOption("I am learning about this data");
  await setup.getByRole("button", { name: "Continue", exact: true }).click();
  await setup.getByLabel("Your usual aim", { exact: false }).selectOption("Find patterns and unusual values");
  await setup.getByRole("button", { name: "Back", exact: true }).click();
  await expect(setup.getByLabel("Your perspective", { exact: false })).toHaveValue("I am learning about this data");
  await setup.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(setup.getByLabel("Your usual aim", { exact: false })).toHaveValue("Find patterns and unusual values");
  await setup.getByRole("button", { name: "Continue", exact: true }).click();
  await setup.getByRole("radio", { name: "Explain step by step", exact: true }).check();
  await setup.getByRole("button", { name: "Continue", exact: true }).click();
  expect((await (await page.request.get(path, { headers })).json()).version).toBe(0);
  await setup.scrollIntoViewIfNeeded();
  await capture(page, "setup-review");
  await setup.getByRole("button", { name: "Save my preferences", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Preferences saved" })).toBeVisible();
  expect(await (await page.request.get(path, { headers })).json()).toMatchObject({ version: 1, role: "I am learning about this data", focus: "Find patterns and unusual values", explanation_style: "step_by_step" });
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Data library", exact: true }).click();
  await upload(page, "another-file.csv");
  await finishInitialReview(page);
  await expect(setup).toHaveCount(0);
  await expect(page.getByRole("complementary", { name: "Private answer preferences", exact: true })).toContainText("saved preferences");
  expect((await (await page.request.get(path, { headers })).json()).version).toBe(1);
});

test("the first reading waits for entered upload context and a failed context save preserves the upload", async ({ page }) => {
  const headers = await signIn(page);
  let allowSave!: () => void;
  const gate = new Promise<void>(resolve => { allowSave = resolve; });
  let waiting = false;
  let readingRequests = 0;
  let readingGoal = "";
  await page.route("**/datasets/*/preferences", async route => { if (route.request().method() === "POST") { waiting = true; await gate; } await route.continue(); });
  await page.route("**/uploads/*/data-brief", async route => {
    readingRequests += 1;
    const meaning = await page.request.get(route.request().url().replace(/\/data-brief$/, "/understanding"), { headers });
    readingGoal = (await meaning.json()).preference.goal;
    await route.continue();
  });
  await page.getByLabel("What is this data about? (optional)").selectOption("sales");
  await page.getByLabel("What would you like to do first? (private, optional)").selectOption("Find patterns and unusual values");
  await upload(page);
  await expect.poll(() => waiting).toBe(true);
  await expect(page.getByRole("region", { name: "Add a data file", exact: true })).toBeVisible();
  expect(readingRequests).toBe(0);
  allowSave();
  await finishInitialReview(page);
  await expect.poll(() => readingRequests).toBeGreaterThan(0);
  await expect.poll(() => readingGoal).toBe("Find patterns and unusual values");
  await page.unroute("**/datasets/*/preferences");
  await page.route("**/datasets/*/preferences", route => route.request().method() === "POST" ? route.fulfill({ status: 503, json: { error: { message: "Temporary context save failure" } } }) : route.continue());
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Data library", exact: true }).click();
  await upload(page, "preserved-upload.csv");
  await finishInitialReview(page);
  await expect(page.getByLabel("Profile upload")).toContainText("preserved-upload.csv");
  await expect(page.getByRole("status").filter({ hasText: "File uploaded successfully" })).toContainText("optional context could not be saved");
  const active = await source(page);
  expect((await page.request.get(`${api}${active.root}/profile`, { headers })).ok()).toBe(true);
});

test("diagram requests render all declared fields and PDF actions reopen without automatic downloads", async ({ page }) => {
  test.setTimeout(120_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const headers = await signIn(page);
  const fields = ["date", "category", "revenue", "cost", ...Array.from({ length: 20 }, (_, index) => `measure_${index + 1}`)];
  await upload(page, "field-map.csv", `${fields.join(",")}\n2026-01-01,A,100.10,60,${Array.from({ length: 20 }, (_, index) => index + 1).join(",")}\n2026-01-02,B,120.20,70,${Array.from({ length: 20 }, (_, index) => index + 2).join(",")}\n`);
  await finishInitialReview(page);
  const active = await source(page);
  const meaning = await (await page.request.get(`${api}${active.root}/understanding`, { headers })).json();
  const definition = { ...meaning.definition, grain: "record", description: "Fictional daily records for the diagram test.", columns: meaning.definition.columns.map((column: { name: string; role: string }) => ({ ...column, meaning: `Saved meaning of ${column.name}`, unit: column.role === "metric" ? "USD" : "" })) };
  expect((await page.request.post(`${api}${active.root}/understanding`, { headers, data: { revision_id: meaning.revision_id, expected_version: meaning.version, state: "confirmed", definition } })).ok()).toBe(true);
  await openConversation(page);
  await page.getByLabel("Your question", { exact: true }).fill("Make a diagram of how our data converge");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const diagram = page.getByRole("region", { name: "Data organisation diagram", exact: true });
  await expect(diagram).toBeVisible();
  await expect(diagram.locator('[data-diagram-renderer="apache-echarts-tree"]')).toHaveAttribute("data-engine-ready", "true");
  await expect(diagram.locator("svg")).toBeVisible();
  await expect(diagram).toContainText("24 of 24 fields included");
  await expect(diagram).not.toContainText("This earlier map uses analysis groups");
  await expect.poll(() => diagram.getByRole("heading", { name: "How this file is organised", exact: true }).evaluate(heading => {
    const log = heading.closest(".conversationLog")!.getBoundingClientRect();
    const title = heading.getBoundingClientRect();
    return title.top >= log.top && title.bottom <= log.bottom;
  })).toBe(true);
  const inspector = diagram.getByRole("combobox", { name: "Inspect a field or group", exact: true });
  await expect(inspector).toBeVisible();
  await inspector.selectOption({ label: "measure_20" });
  await expect(diagram.getByLabel("Diagram item details", { exact: true })).toContainText("Saved meaning of measure_20");
  await expect(diagram.getByLabel("Diagram item details", { exact: true })).toContainText("Saved role");
  await expect(diagram).toContainText("21–22 of 22");
  await diagram.getByRole("button", { name: "Previous diagram fields", exact: true }).click();
  await expect(diagram).toContainText("11–20 of 22");
  await diagram.getByRole("button", { name: "Previous diagram fields", exact: true }).click();
  await diagram.scrollIntoViewIfNeeded();
  await capture(page, "diagram");
  expect(errors).toEqual([]);
  await expect(page.locator(".conversationTurn").last().getByText("Download result", { exact: true })).toBeVisible();
  await page.getByLabel("Your question", { exact: true }).fill("Make a PDF of every answer");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const unsupportedPdf = page.locator(".conversationTurn").filter({ hasText: "Whole-conversation and full-dataset reports are not available yet." });
  await expect(unsupportedPdf).toBeVisible();
  await expect(unsupportedPdf.getByRole("button", { name: "Load saved answer", exact: true })).toHaveCount(0);
  await page.getByLabel("Your question", { exact: true }).fill("Help me understand my data");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".conversationTurn").last().locator(".datasetGuidance")).toBeVisible();
  const firstTurn = page.locator(".conversationTurn").last();
  await firstTurn.getByText("Download result", { exact: true }).click();
  await page.route("**/export.pdf*", route => route.fulfill({ status: 503, json: { error: { message: "Temporary export failure. Please retry." } } }));
  await firstTurn.getByRole("button", { name: "Download PDF", exact: true }).click();
  await expect(firstTurn.getByRole("alert")).toContainText("Temporary export failure");
  await page.unroute("**/export.pdf*");
  const download = page.waitForEvent("download");
  await firstTurn.getByRole("button", { name: "Download PDF", exact: true }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^syntelio-answer-[0-9a-f-]+\.pdf$/);
  const bytes = await readFile((await file.path())!);
  expect(bytes.subarray(0, 5).toString()).toBe("%PDF-");
  await page.getByLabel("Your question", { exact: true }).fill("Make a PDF of this answer");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("region", { name: "Requested PDF report", exact: true })).toBeVisible();
  let automaticDownloads = 0;
  page.on("download", () => { automaticDownloads += 1; });
  await page.getByText("Private conversation history", { exact: true }).click();
  await page.getByRole("combobox", { name: "Saved conversation", exact: true }).selectOption({ index: 1 });
  await page.getByRole("button", { name: "Open conversation", exact: true }).click();
  const savedAnswers = page.getByRole("button", { name: "Load saved answer", exact: true });
  await expect(unsupportedPdf).toBeVisible();
  await expect(unsupportedPdf.getByRole("button", { name: "Load saved answer", exact: true })).toHaveCount(0);
  await page.route("**/turns/*/answer", route => route.fulfill({ status: 503, json: { error: { message: "Temporary saved evidence failure" } } }));
  await savedAnswers.first().click();
  await expect(page.getByRole("alert").filter({ hasText: "Temporary saved evidence failure" })).toBeVisible();
  await expect(savedAnswers.first()).toBeEnabled();
  await page.unroute("**/turns/*/answer");
  for (let remaining = await savedAnswers.count(); remaining > 0; remaining--) { await savedAnswers.first().click(); await expect(savedAnswers).toHaveCount(remaining - 1); }
  await expect(page.getByRole("region", { name: "Requested PDF report", exact: true })).toBeVisible();
  expect(automaticDownloads).toBe(0);
  await expect(diagram).toBeVisible();
  const threadId = await page.getByRole("combobox", { name: "Saved conversation", exact: true }).inputValue();
  const threadUrl = `${api}/workspaces/${active.workspace}/threads/${threadId}`;
  await page.route(threadUrl, async route => {
    const response = await route.fetch();
    const payload = await response.json();
    await route.fulfill({ response, json: { ...payload, turns: payload.turns.map((turn: { kind: string }) => ({ ...turn, kind: turn.kind === "ambiguous" ? "overview" : turn.kind })) } });
  });
  await page.getByRole("button", { name: "Open conversation", exact: true }).click();
  const nullAnswerButton = unsupportedPdf.getByRole("button", { name: "Load saved answer", exact: true });
  await expect(nullAnswerButton).toBeVisible();
  await nullAnswerButton.click();
  await expect(nullAnswerButton).toHaveCount(0);
  await expect(unsupportedPdf).toContainText("Whole-conversation and full-dataset reports are not available yet.");
  await page.unroute(threadUrl);
  expect(errors).toEqual([]);
});
