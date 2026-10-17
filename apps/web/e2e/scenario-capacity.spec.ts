/* Exercise explicit outcome limits and retained capacity comparisons through real local services. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { expect, test, type Page, type Locator } from "@playwright/test";
import { finishInitialReview } from "./workspace-helpers";

async function setup(page: Page, kind: "scenario" | "allocation") {
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `bounded-${kind}-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
  const headers = { Authorization: `Bearer ${token}` };
  const csv = kind === "scenario" ? "region,quantity,sales,cost,fixed\nNorth,2,10,6,3\nSouth,3,20,8,4\n" : "action,cost,benefit,hours\nA,0.03,0.07,0.2\nB,0.05,0.11,0.1\n";
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: `${kind}-limits.csv`, mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  const wid = await page.getByLabel("Current workspace").inputValue();
  const did = await page.getByLabel("Dataset", { exact: true }).inputValue();
  const uid = await page.getByLabel("Profile upload").inputValue();
  const root = `http://127.0.0.1:8001/workspaces/${wid}/datasets/${did}/uploads/${uid}`;
  const meaning = await (await page.request.get(`${root}/understanding`, { headers })).json();
  const saved = await page.request.post(`${root}/understanding`, { headers, data: { revision_id: meaning.revision_id, expected_version: meaning.version, state: "confirmed", definition: { ...meaning.definition, grain: "record", columns: meaning.definition.columns.map((column: { name: string }) => ["sales", "cost", "fixed", "benefit"].includes(column.name) ? { ...column, role: "metric", unit: "", currency: "USD" } : column.name === "quantity" || column.name === "hours" ? { ...column, role: "metric", unit: column.name === "quantity" ? "items" : "hours", currency: "" } : column) } } });
  expect(saved.status()).toBe(201);
  await page.getByRole("radio", { name: "Expert", exact: true }).check();
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Anomalies & decisions", exact: true }).click();
  return { root, headers, csv };
}

async function layouts(page: Page, result: Locator, name: string) {
  const path = "../../data/verification/2026-10-17/two-phase/scenario-capacity-browser";
  mkdirSync(path, { recursive: true });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    try {
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), { message: `${name} fits ${width}px` }).toBe(true);
    } catch (cause) {
      const overflow = await page.evaluate(() => [...document.querySelectorAll("body *")].flatMap(element => {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.right > innerWidth + 1 ? [{ tag: element.tagName, classes: element.className?.toString(), left: rect.left, right: rect.right, width: rect.width, overflow: getComputedStyle(element).overflowX, text: element.textContent?.slice(0, 100) }] : [];
      }));
      writeFileSync(`${path}/${name}-${width}-overflow.json`, JSON.stringify(overflow, null, 2));
      writeFileSync(`${path}/${name}-${width}-form-layout.json`, JSON.stringify(await page.locator("form, fieldset").evaluateAll(elements => elements.map(element => { const style = getComputedStyle(element); return { tag: element.tagName, classes: element.className, width: style.width, minWidth: style.minWidth, maxWidth: style.maxWidth, minInlineSize: style.minInlineSize, display: style.display, grid: style.gridTemplateColumns, text: element.textContent?.slice(0, 80) }; })), null, 2));
      await page.screenshot({ path: `${path}/${name}-${width}-failure.png` });
      throw cause;
    }
    await result.screenshot({ path: `${path}/${name}-${width}.png` });
  }
}

test("scenario limits use confirmed units, exact checks and immutable saved successors", async ({ page }) => {
  test.setTimeout(180_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const { root, headers, csv } = await setup(page, "scenario");
  await page.getByRole("combobox", { name: "Analysis method", exact: true }).selectOption("scenarios");
  await page.getByRole("combobox", { name: "Scenario approach", exact: true }).selectOption("source");
  const panel = page.getByRole("region", { name: "Source-derived scenarios", exact: true });
  await panel.getByLabel("Comparison name", { exact: true }).fill("Conservative and optimistic limits");
  for (const [label, column] of [["Quantity column", "quantity"], ["Price per unit column", "sales"], ["Variable cost per unit column", "cost"], ["Fixed cost allocated per row", "fixed"]]) await panel.getByRole("combobox", { name: label, exact: true }).selectOption(column);
  await panel.getByRole("checkbox", { name: "Each row contributes once", exact: false }).check();
  await panel.getByRole("button", { name: "Continue", exact: true }).click();
  await panel.getByLabel("Alternative name 1", { exact: true }).fill("Conservative");
  await panel.getByLabel("Price change 1 (%)", { exact: true }).fill("-10");
  await panel.getByRole("button", { name: "Add alternative", exact: true }).click();
  await panel.getByLabel("Alternative name 2", { exact: true }).fill("Optimistic");
  await panel.getByLabel("Price change 2 (%)", { exact: true }).fill("10");
  await panel.getByRole("button", { name: "Add outcome limit", exact: true }).click();
  await panel.getByLabel("Limit 1 value · USD", { exact: true }).fill("35");
  await panel.getByRole("button", { name: "Add outcome limit", exact: true }).click();
  const amount = panel.getByRole("combobox", { name: "Limit 2 amount", exact: true });
  await amount.focus();
  await page.keyboard.press("Enter");
  await page.getByRole("option", { name: "Quantity", exact: true }).click();
  await expect(panel.getByLabel("Limit 2 value · items", { exact: true })).toBeVisible();
  await panel.getByLabel("Limit 2 value · items", { exact: true }).fill("5");
  await panel.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(panel.getByRole("list", { name: "Review declared limits" })).toContainText("35 USD");
  await panel.getByRole("checkbox", { name: "I confirm these changes", exact: false }).check();
  const response = page.waitForResponse(value => value.url().endsWith("/decision-analysis/source-scenarios") && value.status() === 201);
  await panel.getByRole("button", { name: "Calculate and save source comparison", exact: true }).click();
  const body = await (await response).json();
  expect(body.run.method_version).toBe("source-unit-economics-constrained-v2");
  expect(body.run.result.alternatives.map((v: { constraints: { status: string }[] }) => v.constraints[0].status)).toEqual(["violated", "passed"]);
  const result = panel.getByRole("region", { name: "Saved source scenario result", exact: true });
  await expect(result.getByRole("region", { name: "Scenario limit checks", exact: true })).toContainText("37/1");
  await result.getByRole("button", { name: "Replay source comparison", exact: true }).click();
  await expect(panel).toContainText("All source rows and saved calculations were replayed");
  await result.getByText("Download result", { exact: true }).click();
  await result.getByRole("combobox", { name: "File type", exact: true }).selectOption("xlsx");
  const download = page.waitForEvent("download");
  await result.getByRole("button", { name: "Download Excel", exact: true }).click();
  expect(readFileSync((await (await download).path())!).subarray(0, 2).toString()).toBe("PK");
  await layouts(page, result, "scenario");
  await result.getByRole("button", { name: "Create source successor", exact: true }).click();
  await panel.getByRole("checkbox", { name: "Each row contributes once", exact: false }).check();
  await panel.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(panel.getByLabel("Limit 1 value · USD", { exact: true })).toHaveValue("35");
  await expect(panel.getByLabel("Limit 2 value · items", { exact: true })).toHaveValue("5");
  const reopened = await (await page.request.get(`${root.split("/uploads/")[0]}/decision-analysis/${body.run.id}`, { headers })).json();
  expect(reopened.run).toEqual(body.run);
  expect((await (await page.request.get(`${root}/content`, { headers })).body()).toString()).toBe(csv);
  expect(errors).toEqual([]);
});

test("capacity alternatives show exact outcomes, protected downloads and original-only review", async ({ page }) => {
  test.setTimeout(180_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const { root, headers, csv } = await setup(page, "allocation");
  await page.getByRole("combobox", { name: "Analysis method", exact: true }).selectOption("large-allocations");
  const panel = page.getByRole("region", { name: "Larger allocation", exact: true });
  await panel.getByLabel("Analysis name", { exact: true }).fill("Explicit budget alternatives");
  await panel.getByRole("combobox", { name: "Per-unit cost", exact: true }).selectOption("cost");
  await panel.getByRole("combobox", { name: "Per-unit benefit", exact: true }).selectOption("benefit");
  await panel.getByLabel("Available budget", { exact: false }).fill("0.11");
  await panel.getByLabel("Maximum units per action", { exact: true }).fill("2");
  await panel.getByRole("button", { name: "Add resource limit", exact: true }).click();
  await panel.getByRole("combobox", { name: "Resource 1", exact: true }).selectOption("hours");
  await panel.getByLabel("Resource 1 capacity", { exact: true }).fill("0.5");
  await panel.getByText("Compare alternative resource capacities", { exact: true }).click();
  await panel.getByRole("checkbox", { name: "Include capacity comparison", exact: true }).check();
  const chooser = panel.getByRole("combobox", { name: "Resource to compare", exact: true });
  await chooser.click();
  await page.getByRole("option", { name: "cost · USD", exact: true }).click();
  await panel.getByLabel("Alternative capacities · USD", { exact: false }).fill("0.03, 0.08, 0.11, 0.13, 0.16");
  await panel.getByRole("checkbox", { name: "I confirm each row", exact: false }).check();
  const response = page.waitForResponse(value => value.url().endsWith("/decision-analysis/large-allocations") && value.status() === 201);
  await panel.getByRole("button", { name: "Calculate and save privately", exact: true }).click();
  const body = await (await response).json();
  expect(body.run.method_version).toBe("cp-sat-capacity-sensitivity-v2");
  expect(body.run.result.capacity_sensitivity.variants).toHaveLength(5);
  const result = panel.getByRole("region", { name: "Saved larger allocation", exact: true });
  await expect(result.getByRole("region", { name: "Capacity comparison results", exact: true })).toContainText("Approval below applies only to the original model");
  await result.getByRole("button", { name: "Verify saved allocation evidence", exact: true }).click();
  await expect(panel).toContainText("The search was not rerun");
  await result.getByLabel("Reason for your review", { exact: true }).fill("Original 0.11 USD budget only.");
  await result.getByRole("button", { name: "Approve recommendation", exact: true }).click();
  await expect(result).toContainText("Approval is effective for this declared model");
  await result.getByText("Download result", { exact: true }).click();
  await result.getByRole("combobox", { name: "File type", exact: true }).selectOption("png");
  await result.getByRole("combobox", { name: "Chart", exact: true }).selectOption({ label: "Conditional benefit by declared capacity" });
  const download = page.waitForEvent("download");
  await result.getByRole("button", { name: "Download PNG", exact: true }).click();
  expect(readFileSync((await (await download).path())!).subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
  await layouts(page, result, "capacity");
  await page.getByRole("combobox", { name: "Analysis method", exact: true }).selectOption("allocations");
  await expect(page.getByRole("region", { name: "Private analysis history", exact: true })).not.toContainText("Explicit budget alternatives");
  const reopened = await (await page.request.get(`${root.split("/uploads/")[0]}/decision-analysis/${body.run.id}`, { headers })).json();
  expect(reopened.run).toEqual(body.run);
  expect(reopened.reviews).toHaveLength(1);
  expect((await (await page.request.get(`${root}/content`, { headers })).body()).toString()).toBe(csv);
  expect(errors).toEqual([]);
});
