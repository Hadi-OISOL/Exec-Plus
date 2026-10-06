/* Use case: Proves the supported Week 1 user journey in a browser.
What it does: Uses real authentication, invitations, storage, and parser errors without mocking the API. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";

function token(email: string) {
  return execFileSync(
    "python3",
    ["-m", "execplus.manage", "provision-user", "--email", email],
    { cwd: "../..", encoding: "utf8" },
  ).trim();
}

test("first file needs no setup and opens sourced discoveries with useful conversation", async ({
  page,
}) => {
  test.setTimeout(150_000);
  const session = token(`first-reading-${randomUUID()}@example.test`);
  let legacySuggestionRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/suggested-questions"))
      legacySuggestionRequests += 1;
  });
  await signIn(page, session, false);
  await expect(
    page.getByRole("heading", {
      name: "Drop in a file. Find your first insight.",
    }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Workspace name", { exact: true }),
  ).not.toBeVisible();
  await expect(
    page.getByLabel("What is this data about? (optional)"),
  ).not.toBeVisible();
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "branch-performance.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("branch,revenue\nNorth,0.10\nSouth,0.20\nNorth,0.30\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(page.getByLabel("Current workspace")).toHaveValue(/.+/);
  await expect(
    page.getByLabel("Dataset", { exact: true }).locator("option:checked"),
  ).toHaveText("branch-performance");
  const discovery = page.getByRole("region", {
    name: "First reading of your data",
    exact: true,
  });
  await expect(discovery.locator(".discoveryValue")).toHaveText([
    "0.1",
    "0.3",
    "0.2",
  ]);
  await expect(discovery).toContainText("North has 2 rows");
  await page.screenshot({
    path: "../../data/vps-private/discovery-first-reading-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../../data/vps-private/discovery-first-reading-mobile.png",
    fullPage: true,
  });
  await discovery
    .getByRole("button", { name: "Ask about this file", exact: true })
    .click();
  await expect(page.getByLabel("Your question")).toBeFocused();
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(
    page.getByRole("region", { name: "Data understanding", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("region", { name: "Dataset dashboard" }),
  ).toHaveCount(0);
  await discovery
    .getByText("How this was calculated", { exact: true })
    .first()
    .click();
  await expect(discovery).toContainText("Query receipt:");
  await expect(discovery).toContainText("0.100000000000");
  await discovery.getByText("Source & interpretation", { exact: true }).click();
  await expect(discovery).toContainText("Source revision:");
  const chat = page.getByRole("region", {
    name: "Ask a question",
    exact: true,
  });
  await expect(chat).not.toContainText("Karachi");
  await chat
    .getByRole("button", { name: "Help me understand my data", exact: true })
    .click();
  await expect(chat.locator(".datasetGuidance")).toContainText(
    "3 rows and 2 columns",
  );
  const averageSubmitted = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/threads\/[^/]+\/jobs$/.test(new URL(response.url()).pathname),
  );
  const averageFinished = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      /\/jobs\/[^/]+\/result$/.test(new URL(response.url()).pathname),
    { timeout: 90_000 },
  );
  const averageStarted = Date.now();
  await discovery
    .getByRole("button", { name: "What is the average revenue?", exact: true })
    .first()
    .click();
  const submission = await averageSubmitted;
  const job = await submission.json();
  const completed = await (await averageFinished).json();
  const eventResponse = await page.request.get(
    `${new URL(submission.url()).origin}/workspaces/${job.workspace_id}/jobs/${job.id}/events?after=0`,
    { headers: { Authorization: `Bearer ${session}` } },
  );
  const activity = await eventResponse.json();
  const startedPlanning = activity.events.find(
    (event: { stage: string; status: string }) =>
      event.stage === "planning" && event.status === "started",
  );
  const finishedPlanning = activity.events.find(
    (event: { stage: string; status: string }) =>
      event.stage === "planning" && event.status === "completed",
  );
  console.info(
    "LIVE_QUERY_TIMING",
    JSON.stringify({
      case: "first_reading_average",
      elapsed_ms: Date.now() - averageStarted,
      planning_ms:
        startedPlanning && finishedPlanning
          ? Date.parse(finishedPlanning.created_at) -
            Date.parse(startedPlanning.created_at)
          : null,
      status: completed.turn.status,
    }),
  );
  expect(completed.turn.status).toBe("complete");
  await expect(chat.locator(".answerCard .kpiValue")).toHaveText("0.2", {
    timeout: 90_000,
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Ask ExecPlus", exact: true }).click();
  await page.getByLabel("Your question").scrollIntoViewIfNeeded();
  await expect(page.getByLabel("Your question")).toBeInViewport({ ratio: 1 });
  await navigate(page, "Overview");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await expect(
    discovery.locator(".discoveryBarTrack > span").first(),
  ).toHaveCSS("animation-name", "none");
  await page.screenshot({
    path: "../../data/vps-private/discovery-mobile-check.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "../../data/vps-private/discovery-desktop-check.png",
    fullPage: true,
  });
  await navigate(page, "Data library");
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "new-inventory.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("item,quantity\nPart,4\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(
    page.getByLabel("Dataset", { exact: true }).locator("option:checked"),
  ).toHaveText("new-inventory");
  await expect(
    page.getByLabel("Dataset", { exact: true }).locator("option"),
  ).toHaveCount(3);
  await expect(
    page.getByLabel("Profile upload").locator("option:checked"),
  ).toHaveText("new-inventory.csv");
  expect(legacySuggestionRequests).toBe(0);
});

test("superseded discoveries are cancelled and rapid file selection only reads the final source", async ({
  page,
}) => {
  await signIn(
    page,
    token(`discovery-switch-${randomUUID()}@example.test`),
    false,
  );
  const discovery = page.getByRole("region", {
    name: "First reading of your data",
    exact: true,
  });
  const dataset = page.getByLabel("Dataset", { exact: true });
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "earlier.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("amount\n0.10\n"),
  });
  const originalResponse = page.waitForResponse((response) =>
    response.url().endsWith("/discovery"),
  );
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  const originalUrl = (await originalResponse).url();
  await expect(discovery.locator(".discoveryValue")).toHaveText([
    "0.1",
    "0.1",
    "0.1",
  ]);
  const originalDataset = await dataset.inputValue();
  await navigate(page, "Data library");
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "current.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("amount\n0.90\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(discovery.locator(".discoveryValue")).toHaveText([
    "0.9",
    "0.9",
    "0.9",
  ]);
  const currentDataset = await dataset.inputValue();
  let release: () => void = () => {};
  let started: () => void = () => {};
  const hold = new Promise<void>((resolve) => {
    release = resolve;
  });
  const delayed = new Promise<void>((resolve) => {
    started = resolve;
  });
  let supersededRequests = 0;
  await page.route(originalUrl, async (route) => {
    supersededRequests += 1;
    const response = await route.fetch();
    started();
    await hold;
    await route.fulfill({ response }).catch(() => {});
  });
  try {
    await dataset.selectOption(originalDataset);
    await delayed;
    const aborted = page.waitForEvent(
      "requestfailed",
      (request) => request.url() === originalUrl,
    );
    await dataset.selectOption(currentDataset);
    release();
    await aborted;
    await expect(discovery.locator(".discoveryFilename")).toHaveText("current");
    await expect(discovery.locator(".discoveryValue")).toHaveText([
      "0.9",
      "0.9",
      "0.9",
    ]);
    await expect(discovery.getByRole("alert")).toHaveCount(0);
    await dataset.selectOption(originalDataset);
    await expect(dataset).toBeEnabled();
    await dataset.selectOption(currentDataset);
    await expect(discovery.locator(".discoveryValue")).toHaveText([
      "0.9",
      "0.9",
      "0.9",
    ]);
    expect(supersededRequests).toBe(1);
  } finally {
    release();
  }
});

test("automatic discoveries show leading categories and keep saved review gates visible", async ({
  page,
}) => {
  await signIn(
    page,
    token(`discovery-review-${randomUUID()}@example.test`),
    false,
  );
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "categories.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      `category,amount\n${["Alpha.00", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Zulu", "Zulu", "Zulu", "Zulu"].map((name) => `${name},1.00`).join("\n")}\n`,
    ),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  const discovery = page.getByRole("region", {
    name: "First reading of your data",
    exact: true,
  });
  await expect(discovery.locator(".discoveryBars li").first()).toContainText(
    "Zulu",
  );
  await expect(discovery.locator(".discoveryBars li")).toHaveCount(8);
  await expect(
    discovery.locator(".discoveryBarLabel").filter({ hasText: "Alpha.00" }),
  ).toHaveText("Alpha.00");
  await expect(discovery).toContainText("Top 8 of 10 groups shown");
  await expect(discovery.locator(".discoveryMetricNote")).toContainText(
    "inferred, not confirmed",
  );
  await reveal(page, "Review & refine data understanding");
  const meaning = page.getByRole("region", {
    name: "Data understanding",
    exact: true,
  });
  await meaning
    .getByRole("button", { name: "Save for review", exact: true })
    .click();
  await expect(discovery).toContainText("needs review before new calculations");
  await expect(discovery.locator(".discoveryValue")).toHaveCount(0);
  await reveal(page, "Review & refine data understanding");
  await discovery
    .getByRole("button", {
      name: "Review saved business definitions",
      exact: true,
    })
    .click();
  await expect(meaning.getByLabel("One row represents")).toBeVisible();
});

test("column meanings use dataset evidence and retain understandable follow-ups", async ({
  page,
}) => {
  const session = token(`guidance-${randomUUID()}@example.test`);
  await signIn(page, session);
  await page
    .getByLabel("Workspace name", { exact: true })
    .fill("Fictional ERP guidance");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await navigate(page, "Data library");
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "fictional-erp.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "item_code,item_description,category,attock_erp,attock_erp_value\nA1,Example item,Parts,2,5.25\nA2,Other item,Parts,3,8.75\n",
    ),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  const explanations = page.locator(".datasetGuidance");
  await page.getByLabel("Your question").fill("what is this attock erp means");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(explanations).toHaveCount(1);
  await expect(explanations.last()).toContainText(
    "Enterprise Resource Planning",
  );
  await expect(explanations.last()).toContainText("Tentative interpretation");
  await expect(page.locator(".assistantMessage .verifiedBadge")).toHaveCount(0);
  await page.getByLabel("Your question").fill("??");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(explanations).toHaveCount(2);
  await expect(explanations.last()).toContainText("In plain words: attock_erp");
  await explanations
    .last()
    .getByRole("button", {
      name: "What does attock_erp_value mean?",
      exact: true,
    })
    .click();
  await expect(explanations).toHaveCount(3);
  await expect(explanations.last()).toContainText(
    "attock_erp_value has no confirmed business definition",
  );
  await explanations
    .last()
    .getByRole("button", {
      name: "Help me understand this dataset",
      exact: true,
    })
    .click();
  await expect(explanations).toHaveCount(4);
  await expect(explanations.last()).toContainText("2 rows and 5 columns");
  await expect(explanations.last()).toContainText(
    "Repeated measure/value pairs",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await page.reload();
  await signIn(page, session);
  await page.getByText("Private conversation history", { exact: true }).click();
  await page.getByLabel("Saved conversation").selectOption({ index: 1 });
  await page
    .getByRole("button", { name: "Open conversation", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Load saved answer", exact: true })
    .first()
    .click();
  await expect(explanations.first()).toContainText(
    "Enterprise Resource Planning",
  );
  await explanations
    .first()
    .getByText("What this explanation is based on", { exact: true })
    .click();
  await expect(explanations.first()).toContainText("Source revision:");
});

test("combined data and document chat reopens private evidence after refresh", async ({
  page,
}) => {
  test.skip(
    process.env.EXECPLUS_BROWSER_LIVE_MODEL !== "1",
    "Requires an explicitly enabled live model with fictional data.",
  );
  test.setTimeout(150_000);
  const session = token(`combined-${randomUUID()}@example.test`);
  await signIn(page, session);
  await page
    .getByLabel("Workspace name", { exact: true })
    .fill("Fictional unified conversation");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await navigate(page, "Data library");
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "fictional.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("city,revenue\nKarachi,0.10\nLahore,0.20\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await reveal(page, "Charts & dashboard controls");
  await expect(
    page
      .getByRole("region", { name: "Dataset dashboard" })
      .locator(".kpiValue"),
  ).toHaveText("0.3");
  await navigate(page, "Documents");
  const knowledge = page.getByRole("region", { name: "Reference documents" });
  await knowledge
    .getByLabel("Reference document", { exact: true })
    .setInputFiles({
      name: "fictional-refund.md",
      mimeType: "text/markdown",
      buffer: Buffer.from(
        "# Fictional refund policy\nThe customer support lead approves standard refunds. The source's stated ceiling is 100 PKR.\n",
      ),
    });
  await knowledge
    .getByRole("button", { name: "Upload document", exact: true })
    .click();
  await expect(
    knowledge.getByText("Document stored.", { exact: true }),
  ).toBeVisible();
  await navigate(page, "Overview");
  await page
    .getByLabel("Your question")
    .fill(
      "What is total revenue, and who approves standard refunds according to the document?",
    );
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".answerCard .kpiValue")).toHaveText("0.3", {
    timeout: 90_000,
  });
  await expect(
    page.getByRole("region", { name: "Document evidence" }),
  ).toContainText("customer support lead");
  await page
    .getByRole("button", { name: "Open conversation citation" })
    .click();
  await expect(
    page.getByText("Verified conversation source passage", { exact: true }),
  ).toBeVisible();
  await page.getByText("How this answer was verified", { exact: true }).click();
  await expect(
    page
      .locator(".answerEvidence")
      .filter({
        has: page.getByText("How this answer was verified", { exact: true }),
      }),
  ).toContainText("Source revision:");
  await page.reload();
  await signIn(page, session);
  await page.getByText("Private conversation history", { exact: true }).click();
  await expect(
    page.getByLabel("Saved conversation").locator("option"),
  ).toHaveCount(2);
  await page.getByLabel("Saved conversation").selectOption({ index: 1 });
  await page
    .getByRole("button", { name: "Open conversation", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Load saved answer", exact: true })
    .click();
  await expect(page.locator(".answerCard .kpiValue")).toHaveText("0.3");
  await expect(
    page.getByRole("region", { name: "Document evidence" }),
  ).toContainText("customer support lead");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

async function signIn(page: Page, session: string, configureWorkspace = true) {
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(session);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Sign out", exact: true }),
  ).toBeEnabled();
  if (
    configureWorkspace &&
    !(await page.getByLabel("Current workspace").count())
  )
    await navigate(page, "Team & settings");
}

async function reveal(page: Page, name: string) {
  const summary = page.locator("summary").filter({ hasText: name });
  if (
    !(await summary.evaluate(
      (node) => (node.parentElement as HTMLDetailsElement).open,
    ))
  )
    await summary.click();
}

async function navigate(page: Page, name: string) {
  await page
    .getByRole("navigation", { name: "Workspace navigation" })
    .getByRole("button", { name, exact: true })
    .click();
}

test("adaptive studies retain versions and a private six-pin dashboard on mobile", async ({
  page,
}) => {
  const session = token(`studies-${randomUUID()}@example.test`);
  await signIn(page, session);
  await page.getByLabel("Workspace name", { exact: true }).fill("Studies team");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  const organizations = page.getByRole("region", {
    name: "Organization departments",
  });
  await organizations
    .getByLabel("Organization name", { exact: true })
    .fill("Fictional company");
  await organizations
    .getByRole("button", { name: "Create organization", exact: true })
    .click();
  await expect(organizations.getByRole("status")).toContainText(
    "Organization created",
  );
  await organizations.getByLabel("Department name").fill("Sales");
  await organizations
    .getByRole("button", { name: "Group current workspace" })
    .click();
  await expect(organizations.getByRole("status")).toContainText(
    "grouped as a department",
  );
  await navigate(page, "Data library");
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "study.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("city,amount\nKarachi,0.10\nLahore,0.20\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await reveal(page, "Review & refine data understanding");
  const meaning = page.getByRole("region", {
    name: "Data understanding",
    exact: true,
  });
  await meaning.getByLabel("One row represents").selectOption("record");
  await meaning.getByLabel("Column to review").selectOption("amount");
  await meaning.getByLabel("Currency code").fill("PKR");
  await meaning
    .getByRole("button", { name: "Confirm business definitions" })
    .click();
  await expect(meaning.getByText("confirmed", { exact: true })).toBeVisible();
  await navigate(page, "Studies & dashboards");
  const studies = page.getByRole("region", { name: "Studies and dashboards" });
  await expect(studies.locator(".studySuggestion")).not.toHaveCount(0);
  await studies
    .getByLabel("Study name (optional)")
    .fill("Exact revenue evidence");
  const suggestion = studies.locator(".studySuggestion").filter({
    has: page.getByRole("heading", {
      name: "What is the sum of amount?",
      exact: true,
    }),
  });
  await suggestion.getByRole("button", { name: "Run & save study" }).click();
  await expect(studies.locator(".studyValue")).toHaveText("0.300000000000");
  await studies
    .getByLabel("Dashboard name", { exact: true })
    .fill("Sales review");
  await studies.getByRole("button", { name: "Create study dashboard" }).click();
  await studies.getByRole("button", { name: "Pin this result" }).click();
  await expect(studies.getByRole("status")).toContainText("Result pinned");
  await studies
    .getByRole("button", { name: "Share dashboard", exact: true })
    .click();
  await expect(studies.getByRole("alert")).toContainText(
    "Share each study explicitly",
  );
  await studies
    .getByRole("button", { name: "Share study with workspace" })
    .click();
  await studies
    .getByRole("button", { name: "Share dashboard", exact: true })
    .click();
  await studies
    .getByRole("button", { name: "Open dashboard Sales review" })
    .click();
  const board = page.getByRole("region", {
    name: "Pinned dashboard: Sales review",
  });
  await expect(board.locator(".studyValue")).toHaveText("0.300000000000");
  await studies
    .getByRole("button", { name: "Rerun on selected snapshot" })
    .click();
  await expect(
    studies.getByRole("button", { name: "Open version 2", exact: true }),
  ).toBeVisible();
  await studies.getByText("Compare study versions", { exact: true }).click();
  await studies
    .getByLabel("Earlier version")
    .selectOption({ label: "Exact revenue evidence · v1" });
  await studies
    .getByLabel("Later version")
    .selectOption({ label: "Exact revenue evidence · v2" });
  await studies
    .getByRole("button", { name: "Compare evidence", exact: true })
    .click();
  await expect(studies.getByLabel("Study comparison")).toContainText(
    "Differences describe snapshots",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(
    studies.getByRole("heading", { name: "Studies & dashboards", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  await page.reload();
  await signIn(page, session);
  await navigate(page, "Studies & dashboards");
  await studies
    .getByRole("button", { name: "Open version 1", exact: true })
    .click();
  await expect(studies.locator(".studyValue")).toHaveText("0.300000000000");
  const dismiss = studies.getByRole("button", {
    name: "Dismiss What is the sum of amount?",
    exact: true,
  });
  await dismiss.focus();
  await page.keyboard.press("Enter");
  await expect(dismiss).toHaveCount(0);
  await studies
    .getByRole("button", { name: "Restore dismissed suggestions" })
    .click();
  await expect(dismiss).toBeVisible();
  await studies
    .getByRole("button", { name: "Clear all pins", exact: true })
    .click();
  await studies
    .getByRole("button", { name: "Open dashboard Sales review" })
    .click();
  await expect(board).toContainText("Run a study and pin a result here.");
});

test("create workspace, invite teammate, upload, reject malformed file, switch tenant", async ({
  page,
  context,
}) => {
  const suffix = randomUUID();
  const ownerEmail = `owner-${suffix}@example.test`;
  const memberEmail = `member-${suffix}@example.test`;
  await signIn(page, token(ownerEmail));
  await page.getByLabel("Workspace name", { exact: true }).fill("Finance team");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Team · Finance team" }),
  ).toBeVisible();
  await page.getByLabel("Teammate email").fill(memberEmail);
  await page
    .getByRole("button", { name: "Create invitation", exact: true })
    .click();
  await expect(page.locator('.notice[role="status"]')).toContainText("Invitation created");
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page
    .getByRole("button", { name: `Copy link for ${memberEmail}` })
    .click();
  await expect(page.locator('.notice[role="status"]')).toContainText(
    "Invitation link copied",
  );
  const invitation = await page.evaluate(() => navigator.clipboard.readText());
  await navigate(page, "Data library");
  await page
    .getByText("Create a named dataset manually", { exact: true })
    .click();
  await page.getByLabel("New dataset name").fill("Monthly sales");
  await page
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  await expect(page.locator('.notice[role="status"]')).toContainText("Dataset created");
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "sales.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("item,amount\nwidget,12\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(page.locator('.notice[role="status"]')).toContainText("uploaded successfully");
  await navigate(page, "Data library");
  await page.getByText(/Retained uploads in the selected dataset/).click();
  await expect(
    page.getByRole("cell", { name: "Validated and stored" }),
  ).toBeVisible();
  const catalog = page.getByRole("region", { name: "Find data by meaning" });
  await catalog.getByLabel("Search your catalog").fill("missingword");
  await catalog.getByRole("button", { name: "Find data", exact: true }).click();
  await expect(catalog).toContainText("No matching data found.");
  await catalog.getByLabel("Search your catalog").fill("Monthly sales");
  await catalog.getByRole("button", { name: "Find data", exact: true }).click();
  await expect(catalog).toContainText("Meaning: inferred");
  await catalog
    .getByRole("button", { name: "Open Monthly sales", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "First reading of your data" }),
  ).toBeVisible();
  await navigate(page, "Data library");
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "bad.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("a,b\n1,2,3\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(
    page.getByRole("alert", { name: "Request error" }),
  ).toContainText("consistent columns");
  await expect(
    page.getByRole("cell", { name: "bad.csv", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await signIn(page, token(memberEmail));
  await page.getByLabel("Invitation link").fill(invitation);
  await page
    .getByRole("button", { name: "Accept invitation", exact: true })
    .click();
  await expect(page.locator('.notice[role="status"]')).toContainText("Invitation accepted");
  await expect(
    page.getByRole("button", { name: "Create invitation", exact: true }),
  ).toHaveCount(0);
  await page
    .getByLabel("Dataset", { exact: true })
    .selectOption({ label: "Monthly sales" });
  await navigate(page, "Data library");
  await reveal(page, "Retained uploads in the selected dataset");
  await expect(
    page.getByRole("cell", { name: "sales.csv", exact: true }),
  ).toBeVisible();
  await navigate(page, "Team & settings");
  await page.getByLabel("Workspace name", { exact: true }).fill("Private team");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Team · Private team" }),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "sales.csv", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("option", { name: "Monthly sales", exact: true }),
  ).toHaveCount(0);
});

test("invalid session gives an actionable error on a narrow screen", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill("invalid-session");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("alert", { name: "Request error" }),
  ).toContainText("valid session token");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("network dev host activates sign-in and surfaces request errors", async ({
  page,
  baseURL,
}) => {
  const host = process.env.EXECPLUS_BROWSER_NETWORK_HOST ?? "execplus.test";
  const address = `http://${host}:${new URL(baseURL!).port}/workspace`;
  await page.goto(address);
  expect(await page.evaluate(() => window.isSecureContext)).toBe(false);
  await page.getByLabel("Session token").fill("invalid-session");
  const authentication = page.waitForRequest(
    (request) => new URL(request.url()).pathname === "/auth/me",
  );
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await authentication;
  await expect(page).toHaveURL(address);
  await expect(
    page.getByRole("alert", { name: "Request error" }),
  ).toBeVisible();
});

test("sample exploration, profile, cleaning preview, mapping, undo and own upload", async ({
  page,
}) => {
  await signIn(page, token(`profile-${randomUUID()}@example.test`));
  await page
    .getByLabel("Workspace name", { exact: true })
    .fill("Data preparation");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Team · Data preparation" }),
  ).toBeVisible();
  await navigate(page, "Data library");
  await page.getByText("Try a fictional example", { exact: true }).click();
  await page
    .getByRole("button", { name: "Try sales sample", exact: true })
    .click();
  await navigate(page, "Prepare data");
  const profile = page.getByRole("region", { name: "Dataset profile" });
  await expect(profile).toContainText("93.33/100");
  await expect(profile).toContainText("2026-01-01 to 2026-01-02");
  await profile.getByLabel("Trim surrounding whitespace").check();
  await profile.getByLabel("Remove exact duplicate rows").check();
  await profile.getByText("Map column names", { exact: true }).click();
  await profile.getByLabel("Rename amount").fill("sales");
  await profile
    .getByRole("button", { name: "Preview changes", exact: true })
    .click();
  const preview = profile.getByLabel("Cleaning preview");
  await expect(preview).toContainText("1 rows removed · 2 rows remaining");
  await expect(preview).toContainText("100.00/100");
  await expect(
    preview.getByRole("columnheader", { name: "sales", exact: true }),
  ).toBeVisible();
  await profile
    .getByRole("button", { name: "Apply reviewed changes", exact: true })
    .click();
  await expect(profile).toContainText("Changes applied");
  await expect(profile).toContainText("2 rows · 4 columns");
  await profile
    .getByText("Revision history and lineage", { exact: true })
    .click();
  await profile
    .getByRole("button", { name: "Restore original", exact: true })
    .click();
  await expect(profile).toContainText("Revision restored");
  await expect(profile).toContainText("3 rows · 4 columns");
  await expect(profile).toContainText("93.33/100");
  await navigate(page, "Data library");
  await page
    .getByText("Create a named dataset manually", { exact: true })
    .click();
  await page.getByLabel("New dataset name").fill("My first upload");
  await page
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "my-data.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("date,amount\n2026-01-01,12.50\n2026-01-02,15.25\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await navigate(page, "Prepare data");
  await expect(profile).toContainText("100.00/100");
  await expect(profile).toContainText("decimal / metric");
  await navigate(page, "Overview");
  await reveal(page, "Review & refine data understanding");
  await expect(
    page.getByRole("region", { name: "Data journey" }),
  ).toContainText("my-data.csv");
  await navigate(page, "Team & settings");
  await page
    .getByRole("button", { name: "Refresh usage", exact: true })
    .click();
  await expect(page.getByText(/1 of 3 seats used · 2 uploads/)).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("verified filters, drill-down, shared replay, feedback, citations and unsubscribe", async ({
  page,
}) => {
  const session = token(`analytics-${randomUUID()}@example.test`);
  await signIn(page, session);
  await page
    .getByLabel("Workspace name", { exact: true })
    .fill("Analytics acceptance");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await navigate(page, "Data library");
  await page
    .getByText("Create a named dataset manually", { exact: true })
    .click();
  await page.getByLabel("New dataset name").fill("Exact values");
  await page
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "exact.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "date,region,amount\n2026-01-01,East,0.1\n2026-01-02,West,0.2\n",
    ),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await reveal(page, "Charts & dashboard controls");
  const dashboard = page.getByRole("region", { name: "Dataset dashboard" });
  await expect(dashboard.locator(".kpiValue").first()).toHaveText("0.15");
  await dashboard
    .getByText("Customize view & filters", { exact: true })
    .click();
  await dashboard.getByLabel("Filter column").selectOption("region");
  await dashboard.getByLabel("Filter equals").fill("West");
  await dashboard
    .getByRole("button", { name: "Apply dashboard filter" })
    .click();
  await expect(dashboard.locator(".kpiValue").first()).toHaveText("0.2");
  await dashboard.getByRole("button", { name: /West/ }).click();
  await expect(dashboard.locator(".drilldownRows")).toContainText(
    "0.200000000000",
  );
  await expect(dashboard.locator(".drilldownRows")).not.toContainText("East");
  await dashboard.getByText("Evidence & save", { exact: true }).first().click();
  await dashboard
    .getByLabel("Share amount analysis with workspace members")
    .check();
  await dashboard
    .getByRole("button", { name: "Save amount analysis", exact: true })
    .click();
  await navigate(page, "Saved work");
  const saved = page.getByRole("region", { name: "Saved work" });
  await saved
    .getByRole("button", { name: "Open amount analysis", exact: true })
    .click();
  await expect(saved.locator("pre")).toContainText("0.200000000000");
  await saved
    .getByRole("button", { name: "Email amount analysis daily to me" })
    .click();
  await expect(saved).toContainText("Daily report subscribed");
  await saved.getByRole("button", { name: "Unsubscribe report" }).click();
  await expect(saved).not.toContainText("Daily report subscribed");
  const sharedLink = await saved
    .getByRole("link", { name: "Link to amount analysis" })
    .getAttribute("href");
  await navigate(page, "Overview");
  const activation = page.getByRole("region", {
    name: "Insights and next steps",
  });
  await expect(activation.locator("ol > li")).toHaveCount(3);
  await activation
    .getByText("Next steps & product feedback", { exact: true })
    .click();
  await activation
    .getByRole("button", { name: "Send product feedback" })
    .click();
  await expect(activation).toContainText(
    "Feedback recorded without dataset values.",
  );
  await navigate(page, "Documents");
  const knowledge = page.getByRole("region", { name: "Reference documents" });
  await knowledge
    .getByLabel("Reference document", { exact: true })
    .setInputFiles({
      name: "returns.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Refund requests require a receipt."),
    });
  await knowledge.getByRole("button", { name: "Upload document" }).click();
  await expect(knowledge).toContainText("Document stored.");
  await knowledge.getByLabel("Search documents").fill("refund receipt");
  await knowledge.getByRole("button", { name: "Search knowledge" }).click();
  await expect(knowledge.locator("blockquote")).toContainText(
    "Refund requests require a receipt.",
  );
  await knowledge.getByRole("button", { name: "Open citation" }).click();
  await expect(knowledge.locator("details")).toContainText(
    "Refund requests require a receipt.",
  );
  await page.goto(sharedLink!);
  await page.getByLabel("Session token").fill(session);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page
      .getByRole("region", { name: "Saved work" })
      .getByRole("button", { name: "Open amount analysis" }),
  ).toBeVisible();
});

test("upload creates a dataset and opens an interactive responsive exploration", async ({
  page,
}) => {
  await signIn(page, token(`explorer-${randomUUID()}@example.test`));
  await page
    .getByLabel("Workspace name", { exact: true })
    .fill("City exploration");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Team · City exploration" }),
  ).toBeVisible();
  await navigate(page, "Data library");
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "city-demo.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "date,city,revenue\n2026-09-01,Karachi,125.25\n2026-09-02,Lahore,250.25\n2026-09-03,Karachi,375.25\n",
    ),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "A clearer picture." }),
  ).toBeVisible();
  await reveal(page, "Review & refine data understanding");
  const journey = page.getByRole("region", { name: "Data journey" });
  await expect(journey).toContainText("3 columns recognized");
  await journey.getByText("Explore your column map", { exact: false }).click();
  await expect(
    journey.getByRole("button", { name: "revenue decimal" }),
  ).toBeVisible();
  await reveal(page, "Charts & dashboard controls");
  const dashboard = page.getByRole("region", { name: "Dataset dashboard" });
  const point = dashboard.locator(".chartPoint").first();
  await point.focus();
  await expect(dashboard.locator(".chartReadout")).toContainText("125.25");
  await dashboard.getByRole("button", { name: /Karachi/ }).click();
  await expect(dashboard.locator(".drilldownRows")).toContainText(
    "2 of 2 matching",
  );
  await expect(dashboard.locator(".drilldownRows")).not.toContainText("Lahore");
  await expect(page.getByRole("log", { name: "Conversation" })).toContainText(
    "What would you like to discover?",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.screenshot({
    path: "../../data/vps-private/explorer-mobile-check.png",
    fullPage: true,
  });
  const overflowing = await page.evaluate(() =>
    [...document.querySelectorAll("body *")]
      .filter((node) => node.getBoundingClientRect().right > innerWidth + 1)
      .map((node) => ({
        tag: node.tagName,
        cls: node.className,
        width: node.getBoundingClientRect().width,
        right: node.getBoundingClientRect().right,
      }))
      .slice(0, 24),
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    JSON.stringify(overflowing),
  ).toBe(true);
  expect(
    await dashboard
      .locator(".discoveryBarTrack > span")
      .first()
      .evaluate((node) => getComputedStyle(node).animationName),
  ).toBe("none");
});

test("confirm business meaning and private goals without losing the source", async ({
  page,
}) => {
  await signIn(page, token(`meaning-${randomUUID()}@example.test`));
  await page
    .getByLabel("Workspace name", { exact: true })
    .fill("Business meanings");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await navigate(page, "Data library");
  await page
    .getByText("Add context or choose where to save (optional)", {
      exact: true,
    })
    .click();
  await page
    .getByLabel("What is this data about? (optional)")
    .selectOption("sales");
  await page
    .getByLabel("What would you like to understand? (private, optional)")
    .fill("Track paid orders");
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "meaning.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "custno,city,amount,status\n1001,Karachi,0.10,paid\n1002,Lahore,0.20,cancelled\n",
    ),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await reveal(page, "Review & refine data understanding");
  const meaning = page.getByRole("region", {
    name: "Data understanding",
    exact: true,
  });
  await expect(meaning.getByLabel("Business domain")).toHaveValue("sales");
  await meaning
    .getByRole("button", { name: "Confirm business definitions" })
    .click();
  await expect(meaning.getByRole("alert")).toContainText("row");
  await meaning.getByLabel("One row represents").selectOption("order_item");
  await meaning
    .getByLabel("Dataset description")
    .fill("Only paid amounts count toward revenue.");
  await meaning.getByLabel("Column to review").selectOption("custno");
  await meaning.getByLabel("Column role").selectOption("identifier");
  await meaning.getByLabel("Column to review").selectOption("amount");
  await meaning.getByLabel("Currency code").fill("PKR");
  await meaning
    .getByText("Metric definitions and required filters", { exact: true })
    .click();
  await meaning
    .getByRole("button", { name: "Add metric definition", exact: true })
    .click();
  await meaning.getByLabel("Metric name", { exact: true }).fill("Paid amount");
  await meaning.getByRole("button", { name: "Add required filter" }).click();
  await meaning
    .getByRole("combobox", { name: "Filter column", exact: true })
    .selectOption("status");
  await meaning.getByLabel("Filter value", { exact: true }).fill("paid");
  await meaning
    .getByRole("button", { name: "Confirm business definitions" })
    .click();
  await expect(meaning.getByText("confirmed", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Dataset dashboard" }).getByRole("alert"),
  ).toHaveCount(0);
  await reveal(page, "Charts & dashboard controls");
  const cards = page
    .getByRole("region", { name: "Dataset dashboard" })
    .getByRole("article");
  await expect(cards).toHaveCount(1);
  await expect(cards.first().locator(".kpiValue")).toHaveText("0.1");
  await meaning
    .getByText("Your private analysis goal", { exact: true })
    .click();
  await expect(meaning.getByLabel("My analysis goal")).toHaveValue(
    "Track paid orders",
  );
  await navigate(page, "Prepare data");
  await navigate(page, "Overview");
  await expect(meaning.getByText("confirmed", { exact: true })).toBeVisible();
  await meaning
    .getByText("Review business definitions", { exact: true })
    .click();
  await expect(meaning.getByLabel("Dataset description")).toHaveValue(
    "Only paid amounts count toward revenue.",
  );
  await meaning.getByText("Definition history", { exact: true }).click();
  await meaning.getByRole("button", { name: "Inspect version 1" }).click();
  await expect(
    meaning.getByRole("article", { name: "Definition version 1" }),
  ).toContainText("status eq paid");
  await meaning
    .getByRole("button", { name: "Revoke definition", exact: true })
    .click();
  await expect(meaning.getByText("rejected", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Dataset dashboard" }).getByRole("alert"),
  ).toContainText("Review and confirm");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("refresh retains a safe baseline and delivers a private evidenced KPI alert", async ({
  page,
}) => {
  const session = token(`refresh-${randomUUID()}@example.test`);
  await signIn(page, session);
  await page
    .getByLabel("Workspace name", { exact: true })
    .fill("Fictional refresh team");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await navigate(page, "Data library");
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "baseline.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("city,amount\nKarachi,0.10\nLahore,0.20\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await reveal(page, "Review & refine data understanding");
  const meaning = page.getByRole("region", {
    name: "Data understanding",
    exact: true,
  });
  await meaning.getByLabel("One row represents").selectOption("record");
  await meaning.getByLabel("Column to review").selectOption("amount");
  await meaning.getByLabel("Currency code").fill("PKR");
  await meaning
    .getByRole("button", { name: "Confirm business definitions" })
    .click();
  await expect(meaning.getByText("confirmed", { exact: true })).toBeVisible();
  await navigate(page, "Refresh & alerts");
  const panel = page.locator(".refreshWorkspace");
  await panel.getByRole("button", { name: "Save refresh settings" }).click();
  await expect(panel.getByRole("status")).toContainText(
    "Refresh settings saved",
  );
  await panel.getByLabel("Monitor name", { exact: true }).fill("Revenue watch");
  await panel.getByLabel("Metric", { exact: true }).selectOption("amount");
  await panel.getByLabel("Driver segment (sum only)").selectOption("city");
  await panel
    .getByRole("button", { name: "Create monitor", exact: true })
    .click();
  await expect(panel.locator(".observationValue")).toContainText(
    "0.300000000000",
  );
  await panel
    .getByLabel("Alert monitor")
    .selectOption({ label: "Revenue watch" });
  await panel.getByLabel("Threshold", { exact: true }).fill("0.4");
  await panel.getByRole("button", { name: "Subscribe to alert" }).click();
  await expect(panel.getByRole("status")).toContainText(
    "Private alert subscribed",
  );
  await panel.getByLabel("Refresh file", { exact: true }).setInputFiles({
    name: "bad.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("city,amount\nK,1\nL,2\nM,wrong\n"),
  });
  await panel.getByRole("button", { name: "Validate staged file" }).click();
  await expect(panel.getByRole("status")).toContainText("File failed");
  await expect(panel.locator(".observationValue")).toContainText(
    "0.300000000000",
  );
  await panel.getByLabel("Refresh file", { exact: true }).setInputFiles({
    name: "updated.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("city,amount\nKarachi,0.30\nLahore,0.20\n"),
  });
  await panel.getByRole("button", { name: "Validate staged file" }).click();
  await expect(panel.getByRole("status")).toContainText("File queued");
  await panel
    .getByRole("button", { name: "Activate snapshot", exact: true })
    .click();
  await expect(panel.locator(".observationValue")).toContainText(
    "0.500000000000",
  );
  await expect(panel.locator(".refreshDelivery")).toContainText("delivered");
  await expect(
    panel.getByRole("table", { name: "Computed contributions to change" }),
  ).toContainText("0.200000000000");
  await panel
    .getByRole("button", { name: "Open observation evidence", exact: true })
    .click();
  await expect(
    panel.getByText("Method, coverage and query receipts", { exact: true }),
  ).toBeVisible();
  await panel.getByRole("button", { name: "Mark read", exact: true }).click();
  await expect(panel.locator(".refreshDelivery")).toContainText("Read");
  await panel.getByRole("button", { name: "Unsubscribe", exact: true }).click();
  await expect(
    panel.getByRole("button", { name: "Unsubscribe", exact: true }),
  ).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
