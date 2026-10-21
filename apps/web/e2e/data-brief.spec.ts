/* Use case: Verifies the data reading that opens after an upload, against real governed APIs.
What it does: Covers saved meaning, private notes, a skip that changes nothing and the existing review fallback. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const api = "http://127.0.0.1:8001";
const file = { name: "orders.csv", mimeType: "text/csv", buffer: Buffer.from("order_id,amt,st\n1,10.50,P\n2,20.00,R\n3,5.25,P\n") };

function account() {
  const email = `brief-${randomUUID()}@example.test`;
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", email], { cwd: "../..", encoding: "utf8" }).trim();
  return { token, headers: { Authorization: `Bearer ${token}` } };
}

async function signIn(page: Page, person: ReturnType<typeof account>) {
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(person.token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
  await page.waitForLoadState("networkidle");
}

async function modelReading(page: Page) {
  await page.route("**/data-brief*", async route => {
    const real = await (await route.fetch()).json();
    const meanings: Record<string, { meaning: string; question?: string }> = {
      order_id: { meaning: "Order number" },
      amt: { meaning: "Order amount", question: "What currency is amt in?" },
      st: { meaning: "State", question: "Does st mean state?" },
    };
    const columns = real.columns
      .map((column: { name: string }) => ({
        ...column,
        meaning: meanings[column.name].meaning,
        uncertain: Boolean(meanings[column.name].question),
        question: meanings[column.name].question ?? "",
      }))
      .sort((a: { uncertain: boolean }, b: { uncertain: boolean }) => Number(b.uncertain) - Number(a.uncertain));
    await route.fulfill({ json: { ...real, source: "model", model_route: "test:canned", notice: "", summary: "Customer orders with an amount and a status code.", columns, questions: [] } });
  });
}

async function readingLeadsOverview(page: Page, panel: ReturnType<Page["getByRole"]>) {
  const home = page.getByRole("region", { name: "Analytics home", exact: true });
  await expect(home).toBeVisible();
  expect((await panel.boundingBox())!.y).toBeLessThan((await home.boundingBox())!.y);
}

async function upload(page: Page, person: ReturnType<typeof account>, source = file) {
  await page.getByLabel("CSV or Excel file").setInputFiles(source);
  const created = page.waitForResponse(r => r.url().includes("/uploads?filename=") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  expect((await created).status()).toBe(201);
  const get = async (path: string) => (await page.request.get(api + path, { headers: person.headers })).json();
  const [workspace] = await get("/workspaces");
  const [dataset] = await get(`/workspaces/${workspace.id}/datasets`);
  const [item] = await get(`/workspaces/${workspace.id}/datasets/${dataset.id}/uploads`);
  const base = `/workspaces/${workspace.id}/datasets/${dataset.id}`;
  return { get, dataset: base, root: `${base}/uploads/${item.id}` };
}

test("a model reading opens at the top after upload and saves confirmed meaning and private notes", async ({ page }) => {
  const person = account();
  await modelReading(page);
  await signIn(page, person);
  const { get, dataset, root } = await upload(page, person);
  const panel = page.getByRole("region", { name: "Data reading", exact: true });
  await expect(panel.getByText("Question 1 of", { exact: false })).toBeVisible();
  expect((await panel.boundingBox())!.y).toBeLessThan(500);
  await expect(page.locator("#chat-question")).toBeHidden();
  await page.getByRole("button", { name: "Ask ExecPlus", exact: true }).first().click();
  await expect(page.locator("#chat-question")).toBeVisible();
  await page.getByRole("button", { name: "Overview", exact: true }).first().click();
  await expect(panel).toBeVisible();
  await expect(page.getByRole("region", { name: "Guided data review", exact: true })).toHaveCount(0);
  await panel.getByRole("button", { name: "Yes, that's right", exact: true }).click();
  await panel.getByRole("button", { name: "Yes, that's right", exact: true }).click();
  await expect(panel).toContainText('What unit does "amt" use?');
  await panel.getByLabel(/What does this column mean\?/).fill("Order value after discount");
  await panel.getByLabel("Unit of measurement (required)", { exact: true }).fill("PKR");
  await panel.getByRole("button", { name: "Use my answer", exact: true }).click();
  await expect(panel).toContainText("Does st mean state?");
  await panel.getByLabel(/What does this column mean\?/).fill("Order status: P paid, R refunded");
  await panel.getByRole("button", { name: "Use my answer", exact: true }).click();
  await panel.getByRole("button", { name: "Yes, that's right", exact: true }).click();
  await expect(panel.getByRole("heading", { name: "Review before saving", exact: true })).toBeVisible();
  await expect(panel.getByRole("checkbox", { name: "Share my notes", exact: false })).not.toBeChecked();
  await panel.getByRole("button", { name: "Save as context for this data", exact: true }).click();
  await expect(panel).toContainText("This reading is now context for answers about this data");
  await expect(panel).toContainText("2 notes added");
  const saved = await get(root + "/understanding");
  expect(saved.state).toBe("confirmed");
  expect(saved.definition.description).toBe("Customer orders with an amount and a status code.");
  const column = (name: string) => saved.definition.columns.find((item: { name: string }) => item.name === name);
  expect(column("amt")).toMatchObject({ unit: "PKR", meaning: "Order value after discount" });
  expect(column("st").meaning).toBe("Order status: P paid, R refunded");
  const documents = await get(dataset + "/documents");
  expect(documents).toHaveLength(1);
  expect(documents[0].shared).toBe(false);
  await panel.getByRole("button", { name: "Continue to my insights", exact: true }).click();
  await expect(panel).toHaveCount(0);
});

test("skipping the data reading changes no shared meaning and stores no notes", async ({ page }) => {
  const person = account();
  await modelReading(page);
  await signIn(page, person);
  const { get, dataset, root } = await upload(page, person);
  const panel = page.getByRole("region", { name: "Data reading", exact: true });
  await expect(panel.getByText("Question 1 of", { exact: false })).toBeVisible();
  const before = await get(root + "/understanding");
  await panel.getByRole("button", { name: "Skip for now", exact: true }).click();
  await expect(panel).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Analytics home", exact: true })).toBeVisible();
  await expect(page.locator("#chat-question")).toBeHidden();
  expect(await get(root + "/understanding")).toEqual(before);
  expect(await get(dataset + "/documents")).toEqual([]);
});

test("without a model reading the overview stays open with a way to review meaning", async ({ page }) => {
  const person = account();
  await signIn(page, person);
  await upload(page, person);
  await expect(page.getByRole("region", { name: "First findings from your file", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Check what ExecPlus understood", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Data reading", exact: true })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Guided data review", exact: true })).toHaveCount(0);
});

test("a skipped data reading can be reopened from the Prepare data panel", async ({ page }) => {
  const person = account();
  await modelReading(page);
  await signIn(page, person);
  await upload(page, person);
  const panel = page.getByRole("region", { name: "Data reading", exact: true });
  await expect(panel.getByText("Question 1 of", { exact: false })).toBeVisible();
  await panel.getByRole("button", { name: "Skip for now", exact: true }).click();
  await expect(panel).toHaveCount(0);
  await page.getByRole("button", { name: "Prepare data", exact: true }).first().click();
  await page.getByRole("button", { name: "Review data meaning", exact: true }).click();
  await expect(panel.getByText("Question 1 of", { exact: false })).toBeVisible();
  await expect(page.locator("#chat-question")).toBeHidden();
});

for (const partial of [false, true]) {
  test(`wide reading ${partial ? "retains skipped fields as a draft" : "saves every reviewed column and explains forecast limits"}`, async ({ page }) => {
    test.setTimeout(180000);
    const person = account();
    const names = Array.from({ length: 20 }, (_, index) => `measure_${index}`);
    await page.route("**/data-brief*", async route => {
      const real = await (await route.fetch()).json();
      if (real.already_confirmed || real.review_mode === "missing") return route.fulfill({ json: real });
      await route.fulfill({ json: { ...real, source: "model", model_route: "test:canned", summary: "Reviewed fictional field observations.", grain: "record", questions: [], columns: real.columns.map((column: { name: string }) => ({ ...column, meaning: `Reviewed ${column.name}`, unit: "mm", uncertain: false, question: "" })) } });
    });
    await signIn(page, person);
    const { get, root } = await upload(page, person, { name: "wide-fields.csv", mimeType: "text/csv", buffer: Buffer.from(names.join(",") + "\n" + names.map((_, i) => i + 1).join(",") + "\n") });
    const reading = page.getByRole("region", { name: "Data reading", exact: true });
    await expect(reading).toContainText("Question 1 of 22");
    for (let i = 0; i < 22; i++) {
      await reading.getByRole("button", { name: partial && i === 21 ? "Skip this question →" : "Yes, that's right", exact: true }).click();
    }
    await reading.getByRole("button", { name: "Save as context for this data", exact: true }).click();
    await expect(reading.getByRole("button", { name: "Continue to my insights" })).toBeVisible();
    const saved = await get(root + "/understanding");
    expect(saved.state).toBe(partial ? "needs_review" : "confirmed");
    expect(saved.definition.columns[18].meaning).toBe("Reviewed measure_18");
    expect(saved.definition.columns[19].meaning).toBe(partial ? "" : "Reviewed measure_19");
    await reading.getByRole("button", { name: "Continue to my insights" }).click();
    if (partial) return;
    await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Forecasts", exact: true }).click();
    await expect(page.getByRole("heading", { name: "This file has no dates, so we can't forecast over time" })).toBeVisible();
    await expect(page.getByText("Your saved data meanings are in use.", { exact: false })).toBeVisible();
    await expect(page.getByRole("button", { name: "Review missing meanings or units" })).toHaveCount(0);
    await page.getByRole("button", { name: "Explore observed data", exact: true }).click();
    await page.getByRole("button", { name: "Check what ExecPlus understood", exact: true }).click();
    await expect(reading).toContainText("already confirmed");
    await reading.getByRole("button", { name: "Close", exact: true }).click();
    await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Ask ExecPlus", exact: true }).click();
    await page.locator("#chat-question").fill("Find anomalies in measure_19");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await page.getByRole("button", { name: "Scan for unusual values", exact: true }).click();
    const decisions = page.getByRole("region", { name: "Anomalies and decisions", exact: true });
    await expect(decisions.getByRole("region", { name: "Unusual values", exact: true })).toBeVisible();
    await decisions.getByText("Advanced options: choose one measure", { exact: false }).click();
    await expect(decisions.getByRole("combobox", { name: "Measure to inspect", exact: true })).toHaveValue("measure_19");
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Overview", exact: true }).click();
    const definition = saved.definition;
    definition.columns[19].unit = "";
    expect((await page.request.post(api + root + "/understanding", { headers: person.headers, data: { revision_id: saved.revision_id, expected_version: saved.version, state: "confirmed", definition } })).status()).toBe(201);
    await page.getByRole("button", { name: "Check what ExecPlus understood", exact: true }).click();
    await expect(reading).toContainText("Question 1 of 1");
    await expect(reading.getByRole("textbox", { name: "What does this column mean?", exact: true })).toHaveValue("Reviewed measure_19");
    await reading.getByLabel("Unit of measurement (required)", { exact: true }).fill("mm");
    await reading.getByRole("button", { name: "Use my answer", exact: true }).click();
    await reading.getByRole("button", { name: "Save as context for this data", exact: true }).click();
    await expect(reading.getByRole("button", { name: "Continue to my insights" })).toBeVisible();
    expect((await get(root + "/understanding")).questions).toEqual([]);
  });
}

test("focused reading keeps edits on Back, saves progress and retries only the failed save", async ({ page }) => {
  const person = account();
  await modelReading(page);
  await signIn(page, person);
  const { root, dataset, get } = await upload(page, person);
  const panel = page.getByRole("region", { name: "Data reading", exact: true });
  await expect(panel.getByText("Question 1 of", { exact: false })).toBeVisible();
  await readingLeadsOverview(page, panel);
  await expect(page.locator("#chat-question")).toBeHidden();
  await panel.getByRole("button", { name: "Yes, that's right", exact: true }).click();
  await panel.getByRole("button", { name: "Yes, that's right", exact: true }).click();
  await panel.getByRole("textbox", { name: "What does this column mean?", exact: true }).fill("Amount actually received after discount");
  await panel.getByLabel("Unit of measurement (required)", { exact: true }).fill("PKR");
  await panel.getByRole("button", { name: "Back", exact: false }).click();
  await panel.getByRole("button", { name: "Yes, that's right", exact: true }).click();
  await expect(panel.getByRole("textbox", { name: "What does this column mean?", exact: true })).toHaveValue("Amount actually received after discount");
  await expect(panel.getByLabel("Unit of measurement (required)", { exact: true })).toHaveValue("PKR");
  for (const width of [1440, 390, 320]) {
    const theme = width === 390 ? "dark" : "light";
    await page.getByLabel("Appearance", { exact: true }).selectOption(theme);
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await panel.screenshot({ path: `../../data/verification/2026-10-18/intelligence-upgrade/reading-${theme}-${width}.png` });
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(panel).toBeVisible();
  await panel.getByRole("button", { name: "Save my progress", exact: true }).click();
  await expect(panel).toContainText("3 of 5 questions answered");
  let notesAttempts = 0;
  await page.route("**/documents?name=data-reading-*", async route => {
    notesAttempts += 1;
    if (notesAttempts === 1) return route.fulfill({ status: 503, json: { error: { message: "Temporary notes failure" } } });
    return route.continue();
  });
  await panel.getByRole("button", { name: "Save as context for this data", exact: true }).click();
  await expect(panel.getByRole("heading", { name: "Some answers still need saving", exact: true })).toBeVisible();
  const first = await get(root + "/understanding");
  expect(first.state).toBe("needs_review");
  expect(first.definition.columns.find((item: { name: string }) => item.name === "amt")).toMatchObject({ unit: "PKR", meaning: "Amount actually received after discount" });
  await panel.getByRole("button", { name: "Retry saving", exact: true }).click();
  await expect(panel.getByRole("heading", { name: "Review save results", exact: true })).toBeVisible();
  expect((await get(root + "/understanding")).version).toBe(first.version);
  expect(await get(dataset + "/documents")).toHaveLength(1);
  expect(notesAttempts).toBe(2);
  await panel.getByRole("button", { name: "Continue to my insights", exact: true }).click();
  await expect(page.getByRole("region", { name: "Analytics home", exact: true })).toBeVisible();
  await expect(page.locator("#chat-question")).toBeHidden();
});

test("a rejected AI reading keeps a focused structural review with honest provenance", async ({ page }) => {
  const person = account();
  await page.route("**/data-brief*", async route => {
    const real = await (await route.fetch()).json();
    await route.fulfill({ json: { ...real, source: "profile", model_enabled: true, model_route: null, notice: "A model reading was unavailable.", questions: [] } });
  });
  await signIn(page, person);
  const { root, get } = await upload(page, person);
  const panel = page.getByRole("region", { name: "Data reading", exact: true });
  await expect(panel.getByText("Question 1 of", { exact: false })).toBeVisible();
  await expect(panel).toContainText("a new AI reading is unavailable");
  await expect(panel).toContainText("Based on the file’s structure and your saved definitions");
  await expect(panel).not.toContainText("Suggested by the language model");
  await expect(page.getByRole("region", { name: "Guided data review", exact: true })).toHaveCount(0);
  await readingLeadsOverview(page, panel);
  const before = await get(root + "/understanding");
  await panel.getByRole("button", { name: "Skip for now", exact: true }).click();
  expect(await get(root + "/understanding")).toEqual(before);
  await expect(page.getByRole("region", { name: "Analytics home", exact: true })).toBeVisible();
});
