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
  await page.route("**/data-brief", async route => {
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

async function upload(page: Page, person: ReturnType<typeof account>) {
  await page.getByLabel("CSV or Excel file").setInputFiles(file);
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
  await expect(panel).toBeVisible();
  await expect(page.locator("#chat-question")).toBeHidden();
  await page.getByRole("button", { name: "Overview", exact: true }).first().click();
  await expect(page.getByRole("region", { name: "Guided data review", exact: true })).toHaveCount(0);
  await panel.getByRole("button", { name: "Yes, that's right", exact: true }).click();
  await panel.getByRole("button", { name: "Yes, that's right", exact: true }).click();
  await expect(panel).toContainText("What currency is amt in?");
  await panel.getByLabel(/What does this column mean\?/).fill("Order value after discount");
  await panel.getByLabel("Unit, if you know it", { exact: true }).fill("PKR");
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
  await expect(page.locator("#chat-question")).toBeVisible();
  expect(await get(root + "/understanding")).toEqual(before);
  expect(await get(dataset + "/documents")).toEqual([]);
});

test("without a model reading the existing guided review still opens after upload", async ({ page }) => {
  const person = account();
  await signIn(page, person);
  await upload(page, person);
  await expect(page.getByRole("region", { name: "Guided data review", exact: true }).getByRole("button", { name: "Skip for now", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Data reading", exact: true })).toHaveCount(0);
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
  await page.getByRole("button", { name: "Check what ExecPlus understood about this data", exact: true }).click();
  await expect(panel.getByText("Question 1 of", { exact: false })).toBeVisible();
  await expect(page.locator("#chat-question")).toBeHidden();
});
