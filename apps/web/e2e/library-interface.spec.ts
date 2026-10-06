/* Use case: Verifies the redesigned saved-answer and dashboard libraries with real evidence.
What it does: Exercises metadata-only search, layout choices, exact replay, stale-result removal and immutable study pins. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const api = "http://127.0.0.1:8001";

function session() {
  return execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `library-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
}

async function start(page: Page, token: string, csv: string) {
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({ name: "library-evidence.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(page.getByLabel("Profile upload")).toHaveValue(/.+/);
  return `/workspaces/${await page.getByLabel("Current workspace").inputValue()}/datasets/${await page.getByLabel("Dataset", { exact: true }).inputValue()}/uploads/${await page.getByLabel("Profile upload").inputValue()}`;
}

async function navigate(page: Page, name: string) {
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name, exact: true }).click();
}

async function mobile(page: Page) {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    const layout = await page.evaluate(() => ({
      width: innerWidth,
      scroll: document.documentElement.scrollWidth,
      overflowing: Array.from(document.querySelectorAll("main *")).filter((node) => !node.closest("aside") && node.getBoundingClientRect().right > innerWidth + 1).slice(0, 18).map((node) => ({ tag: node.tagName, className: String(node.className), right: node.getBoundingClientRect().right, width: node.getBoundingClientRect().width, clientWidth: node.clientWidth, scrollWidth: node.scrollWidth })),
      containers: Array.from(document.querySelectorAll("main, .workbenchBody, .workbenchContent, [aria-label='Saved work'], [aria-label^='Saved result:'], [data-library-layout], [role='region']")).map((node) => ({ tag: node.tagName, className: String(node.className), width: node.getBoundingClientRect().width, clientWidth: node.clientWidth, scrollWidth: node.scrollWidth })),
      outside: [document.documentElement, document.body, ...Array.from(document.body.children)].map((node) => ({ tag: node.tagName, className: String(node.className), width: node.getBoundingClientRect().width, right: node.getBoundingClientRect().right, clientWidth: node.clientWidth, scrollWidth: node.scrollWidth, position: getComputedStyle(node).position, overflow: getComputedStyle(node).overflow, shadow: node.shadowRoot ? Array.from(node.shadowRoot.querySelectorAll("*")).filter((child) => child.getBoundingClientRect().right > innerWidth + 1).slice(0, 8).map((child) => ({ tag: child.tagName, className: String(child.className), right: child.getBoundingClientRect().right, width: child.getBoundingClientRect().width, display: getComputedStyle(child).display, visibility: getComputedStyle(child).visibility })) : [] })),
    }));
    await page.screenshot({ path: `../../data/interface-reference/library-mobile-${width}.png`, fullPage: true });
    expect(layout.scroll, JSON.stringify(layout)).toBeLessThanOrEqual(width + 1);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
}

test("saved-answer library filters metadata, preserves exact replay and clears an unavailable result", async ({ page }) => {
  const token = session();
  const root = await start(page, token, "city,amount\nNorth,9007199254740993.10\nSouth,-0.20\n");
  const headers = { Authorization: `Bearer ${token}` };
  const query = await page.request.post(`${api}${root}/query`, { headers, data: { metric: "amount", aggregation: "sum", group_by: ["city"] } });
  expect(query.ok()).toBe(true);
  const evidence = await query.json();
  const savedIds: string[] = [];
  for (const [name, shared] of [["Branch evidence", false], ["Shared branch evidence", true]] as const) {
    const saved = await page.request.post(`${api}${root}/saved-items`, { headers, data: { name, shared, kind: "analysis", payload: { query_id: evidence.lineage.query_id } } });
    expect(saved.status()).toBe(201);
    savedIds.push((await saved.json()).id);
  }
  const guide = await page.request.post(`${api}${root}/saved-items`, { headers, data: { name: "Understand this file", kind: "question", payload: { question: "Help me understand my data" } } });
  expect(guide.status()).toBe(201);
  let replays = 0;
  page.on("request", (request) => {
    if (/\/saved-items\/[^/]+\/run$/.test(new URL(request.url()).pathname)) replays += 1;
  });
  await navigate(page, "Saved work");
  const library = page.getByRole("region", { name: "Saved work", exact: true });
  const cards = library.getByLabel("Saved items", { exact: true });
  await expect(cards.locator("article")).toHaveCount(3);
  await library.getByLabel("Search saved work", { exact: true }).fill("branch");
  await library.getByLabel("Visibility for saved work").selectOption("private");
  await expect(cards.locator("article")).toHaveCount(1);
  await library.getByRole("button", { name: "saved work list view", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(cards).toHaveAttribute("data-library-layout", "list");
  expect(replays).toBe(0);
  await library.getByRole("button", { name: "Open Branch evidence", exact: true }).click();
  const result = library.getByRole("region", { name: "Saved result: Branch evidence", exact: true });
  await expect(result).toBeVisible();
  await expect(result.getByRole("columnheader", { name: "Sum of amount", exact: true })).toBeVisible();
  await expect(result.getByRole("cell", { name: "9007199254740993.100000000000", exact: true })).toBeVisible();
  await expect(result.getByRole("cell", { name: "-0.200000000000", exact: true })).toBeVisible();
  await expect(result).toContainText(evidence.lineage.query_id);
  await expect(result.locator("pre")).toContainText('"__value"');
  expect(replays).toBe(1);
  await library.getByLabel("Search saved work", { exact: true }).fill("no-such-answer");
  await expect(library).toContainText("No saved work matches these filters");
  await library.getByLabel("Search saved work", { exact: true }).fill("");
  await mobile(page);
  const removed = await page.request.delete(`${api}${root.split("/datasets/")[0]}/saved-items/${savedIds[0]}`, { headers });
  expect(removed.status()).toBe(204);
  await library.getByRole("button", { name: "Open Branch evidence", exact: true }).click();
  await expect(library.getByRole("alert")).toBeVisible();
  await expect(result).toHaveCount(0);
  await library.getByRole("button", { name: "Questions", exact: true }).click();
  await library.getByRole("button", { name: "Open Understand this file", exact: true }).click();
  const explanation = library.getByRole("region", { name: "Saved result: Understand this file", exact: true });
  await expect(explanation).toContainText("Response for the selected revision");
  await expect(explanation).toContainText("Definition status:");
  await expect(explanation.getByText("Verified saved result and lineage", { exact: true })).toHaveCount(0);
  await explanation.getByText("Source & interpretation", { exact: true }).click();
  await expect(explanation).toContainText("Source revision:");
});

test("study and dashboard galleries filter real saved versions and retain pinned evidence", async ({ page }) => {
  await start(page, session(), "date,city,amount\n2024-01-01,North,0.10\n2024-01-03,South,0.20\n");
  await page.locator("summary").filter({ hasText: "Review & refine data understanding" }).click();
  const meaning = page.getByRole("region", { name: "Data understanding", exact: true });
  await meaning.getByLabel("One row represents").selectOption("record");
  await meaning.getByLabel("Column to review").selectOption("amount");
  await meaning.getByLabel("Currency code").fill("PKR");
  await meaning.getByRole("button", { name: "Confirm business definitions" }).click();
  await expect(meaning.getByText("confirmed", { exact: true })).toBeVisible();
  await navigate(page, "Studies & dashboards");
  const library = page.getByRole("region", { name: "Studies and dashboards", exact: true });
  await library.getByLabel("Study name (optional)").fill("Regional totals");
  await library.locator(".studySuggestion").filter({ has: page.getByRole("heading", { name: "What is the sum of amount?", exact: true }) }).getByRole("button", { name: "Run & save study" }).click();
  await expect(library.locator(".studyValue")).toHaveText("0.300000000000");
  await library.getByLabel("Dashboard name", { exact: true }).fill("Leadership review");
  await library.getByRole("button", { name: "Create study dashboard" }).click();
  await library.getByRole("button", { name: "Pin this result" }).click();
  await expect(library.getByRole("status")).toContainText("Result pinned");
  await library.getByLabel("Dashboard name", { exact: true }).fill("New investigation");
  await library.getByRole("button", { name: "Create study dashboard" }).click();
  const boardCards = library.getByLabel("Dashboard cards", { exact: true });
  await expect(boardCards.locator("article")).toHaveCount(2);
  await library.getByLabel("Search dashboards", { exact: true }).fill("leadership");
  await expect(boardCards.locator("article")).toHaveCount(1);
  await library.getByRole("button", { name: "dashboards list view", exact: true }).click();
  await expect(boardCards).toHaveAttribute("data-library-layout", "list");
  await library.getByRole("button", { name: "Open dashboard Leadership review", exact: true }).click();
  const board = library.getByRole("region", { name: "Pinned dashboard: Leadership review" });
  await expect(board.locator(".studyValue")).toHaveText("0.300000000000");
  await expect(board).toContainText("does not silently rerun");
  await library.getByLabel("Search saved studies", { exact: true }).fill("no match");
  await expect(library).toContainText("No saved studies match these filters.");
  await library.getByLabel("Search saved studies", { exact: true }).fill("regional");
  await library.getByRole("button", { name: "Share study with workspace" }).click();
  await library.getByRole("button", { name: "Share dashboard", exact: true }).click();
  await library.getByLabel("Visibility for dashboards").selectOption("private");
  await expect(library).toContainText("No dashboards match these filters.");
  await library.getByLabel("Visibility for dashboards").selectOption("shared");
  await expect(boardCards.locator("article")).toHaveCount(1);
  await library.getByRole("button", { name: "Open dashboard Leadership review", exact: true }).click();
  await expect(board.locator(".studyValue")).toHaveText("0.300000000000");
  await library.getByLabel("Study name (optional)").fill("Observed branch amounts");
  await library.locator(".studySuggestion").filter({ has: page.getByRole("heading", { name: "How does amount vary by date?", exact: true }) }).getByRole("button", { name: "Run & save study" }).click();
  const observations = library.getByRole("article", { name: "Study result: Observed branch amounts", exact: true });
  await expect(observations).toContainText("Observed date points; no inferred values between dates.");
  await expect(observations.locator("svg circle")).toHaveCount(2);
  await expect(observations.locator("svg polyline")).toHaveCount(0);
  await mobile(page);
});
