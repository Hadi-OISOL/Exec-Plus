/* Use case: Verifies the redesigned private analytics interface with eight independent users.
What it does: Exercises the approved fictional source, real guidance and exact saved evidence while retaining only identifiers and sanitized outcomes. */

import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { mkdir, open, readFile } from "node:fs/promises";
import { dirname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, expect as baseExpect } from "@playwright/test";

const API = "http://localhost:18401";
const WEB = "http://localhost:18400";
const expect = baseExpect.configure({ timeout: 60_000 });
const json = (body) => ({
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

function sanitizedFailure(error) {
  return {
    error_type: ["AssertionError", "TimeoutError", "TypeError", "SyntaxError"].includes(error?.name) ? error.name : "Error",
    error_code: /^http_\d{3}$/.test(error?.code) ? error.code : "check_failed",
  };
}

function mark(state, stage) {
  state.summary.stage = stage;
  console.log(JSON.stringify({ user: state.summary.user, stage }));
}

async function api(account, path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    signal: AbortSignal.timeout(120_000), ...options,
    headers: { Authorization: `Bearer ${account.token}`, ...options.headers },
  });
  if (!response.ok) {
    const error = new Error("API request failed");
    error.code = `http_${response.status}`;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}

async function browserResponse(page, predicate, action) {
  const pending = page.waitForResponse(predicate, { timeout: 120_000 }).catch(() => null);
  await action();
  const response = await pending;
  assert.ok(response, "Expected browser response was absent");
  if (!response.ok()) {
    const error = new Error("Browser API request failed");
    error.code = `http_${response.status()}`;
    throw error;
  }
  return response.json();
}

async function navigate(page, name) {
  await page.getByRole("navigation", { name: "Workspace navigation" })
    .getByRole("button", { name, exact: true }).click();
}

async function selectedSource(state) {
  await expect(state.page.getByRole("combobox", { name: "Current workspace", exact: true })).toHaveValue(state.workspace_id);
  await expect(state.page.getByRole("combobox", { name: "Dataset", exact: true })).toHaveValue(state.dataset_id);
  await expect(state.page.getByRole("combobox", { name: "Profile upload", exact: true })).toHaveValue(state.upload_id);
}

async function layouts(state, locator, view, artifactPath) {
  await state.page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [1440, 390, 320]) {
    await state.page.setViewportSize({ width, height: 1000 });
    await expect.poll(() => state.page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    )).toBe(true);
    await expect(locator).toBeVisible();
    assert.equal(await state.page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches), true);
    await selectedSource(state);
    state.summary.layouts.push({ view, width, no_overflow: true, reduced_motion: true });
    if (state.summary.user === 1) {
      const output = await open(`${artifactPath}/${view}-${width}.png`, "wx", 0o600);
      try { await output.writeFile(await locator.screenshot({ timeout: 15_000 })); }
      finally { await output.close(); }
      state.summary.screenshots += 1;
    }
  }
  await state.page.setViewportSize({ width: 1440, height: 1000 });
}

async function signIn(state) {
  mark(state, "open_sign_in");
  await state.page.goto(`${WEB}/workspace?workspace=${state.workspace_id}`);
  mark(state, "submit_session");
  await state.page.getByLabel("Session token").fill(state.account.token);
  await state.page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(state.page.getByText(`Signed in as ${state.account.email}`)).toBeVisible();
  mark(state, "select_workspace");
  await state.page.getByRole("combobox", { name: "Current workspace", exact: true }).selectOption(state.workspace_id);
  mark(state, "select_dataset");
  await state.page.getByRole("combobox", { name: "Dataset", exact: true }).selectOption(state.dataset_id);
  mark(state, "select_upload");
  await state.page.getByRole("combobox", { name: "Profile upload", exact: true }).selectOption(state.upload_id);
  mark(state, "verify_selected_home");
  await selectedSource(state);
  await expect(state.page.getByRole("region", { name: "Analytics home", exact: true })).toBeVisible();
}

async function guidance(state, artifactPath) {
  mark(state, "home_layout");
  const home = state.page.getByRole("region", { name: "Analytics home", exact: true });
  await layouts(state, home.locator(".homeComposer"), "home-composer", artifactPath);
  mark(state, "home_to_guidance");
  await home.getByRole("textbox", { name: "Ask about your data", exact: true }).fill("Help me understand my data");
  const job = await browserResponse(state.page,
    (response) => new URL(response.url()).pathname.startsWith(`${state.workspace_root}/threads/`) &&
      new URL(response.url()).pathname.endsWith("/jobs") && response.request().method() === "POST",
    () => home.getByRole("button", { name: "Explore this question", exact: true }).click());
  assert.equal(job.workspace_id, state.workspace_id);
  state.summary.guidance_job_id = job.id;
  await expect.poll(async () => {
    const current = await api(state.account, `${state.workspace_root}/jobs/${job.id}`);
    if (["failed", "cancelled", "expired"].includes(current.status)) throw new Error("Guidance job did not complete");
    return current.status;
  }, { timeout: 180_000 }).toBe("succeeded");
  const response = await api(state.account, `${state.workspace_root}/jobs/${job.id}/result`);
  assert.equal(response.answer.kind, "overview");
  assert.ok(response.answer.sources.length > 0);
  const chat = state.page.getByRole("region", { name: "Ask a question", exact: true });
  await expect(chat.locator(".conversationTurn").last().locator(".datasetGuidance")).toBeVisible();
  await expect(chat.locator(".conversationTurn").last()).toContainText("Definition status:");
  await selectedSource(state);
  state.summary.guidance_verified = true;
}

async function dashboard(state, artifactPath) {
  mark(state, "search_dashboard");
  const result = await browserResponse(state.page,
    (response) => new URL(response.url()).pathname === `${state.root}/dashboard` && response.request().method() === "POST",
    () => navigate(state.page, "Search data"));
  assert.ok(result.cards.length > 0);
  state.dashboard = result;
  const panel = state.page.getByRole("region", { name: "Dataset dashboard", exact: true });
  const visual = panel.locator("[data-visualization]").first();
  await expect(visual).toBeVisible();
  await visual.getByRole("button", { name: "Table", exact: true }).click();
  await expect(visual.getByRole("table")).toBeVisible();
  await visual.getByRole("button", { name: "Chart", exact: true }).click();
  const expand = visual.getByRole("button", { name: /^Expand / });
  await expand.click();
  const modal = state.page.getByRole("dialog");
  await expect(modal).toBeVisible();
  await expect(modal.getByRole("button", { name: "Close", exact: true })).toBeFocused();
  await state.page.keyboard.press("Escape");
  await expect(modal).not.toBeVisible();
  await expect(expand).toBeFocused();
  state.summary.chart_table_expand = true;
  await layouts(state, panel, "dashboard", artifactPath);
}

async function saveAnalysis(state, runName) {
  mark(state, "create_private_analysis");
  const card = state.dashboard.cards.find((value) => value.lineage.metric === "revenue" && value.lineage.aggregation === "sum") ??
    state.dashboard.cards.find((value) => ["sum", "avg", "min", "max", "count"].includes(value.lineage.aggregation));
  assert.ok(card, "No governed dashboard metric is available");
  const evidence = await api(state.account, `${state.root}/query`, json({
    metric: card.lineage.metric, aggregation: card.lineage.aggregation, group_by: [], filters: [],
  }));
  assert.ok(evidence.lineage.query_id);
  assert.ok(evidence.lineage.receipt.sources.some((source) => source.upload_id === state.upload_id));
  assert.equal(evidence.columns.length, 1);
  assert.equal(evidence.rows.length, 1);
  assert.notEqual(evidence.rows[0][0], null);
  state.evidence = evidence;
  state.name = `${runName} user ${state.summary.user}`;
  const saved = await api(state.account, `${state.root}/saved-items`, json({
    name: state.name, kind: "analysis", shared: false, payload: { query_id: evidence.lineage.query_id },
  }));
  assert.equal(saved.shared, false);
  assert.equal(saved.workspace_id, state.workspace_id);
  assert.equal(saved.upload_id, state.upload_id);
  state.saved_id = saved.id;
  state.summary.saved_item_id = saved.id;
  state.summary.query_id = evidence.lineage.query_id;
}

async function library(state, runName, artifactPath) {
  mark(state, "private_library_and_replay");
  await navigate(state.page, "Saved work");
  const panel = state.page.getByRole("region", { name: "Saved work", exact: true });
  mark(state, "filter_private_library");
  await panel.getByRole("searchbox", { name: "Search saved work", exact: true }).fill(runName);
  await panel.getByRole("combobox", { name: "Visibility for saved work", exact: true }).selectOption("private");
  const cards = panel.getByLabel("Saved items", { exact: true });
  await expect(cards.locator("article")).toHaveCount(1);
  await expect(cards).toContainText(state.name);
  await panel.getByRole("button", { name: "saved work list view", exact: true }).focus();
  await state.page.keyboard.press("Enter");
  await expect(cards).toHaveAttribute("data-library-layout", "list");
  mark(state, "open_saved_evidence");
  const replay = await browserResponse(state.page,
    (response) => new URL(response.url()).pathname === `${state.workspace_root}/saved-items/${state.saved_id}/run` && response.request().method() === "POST",
    () => panel.getByRole("button", { name: `Open ${state.name}`, exact: true }).click());
  assert.equal(replay.lineage.query_id, state.evidence.lineage.query_id);
  assert.deepEqual(replay.columns, state.evidence.columns);
  assert.deepEqual(replay.rows, state.evidence.rows);
  assert.equal(replay.records_analyzed, state.evidence.records_analyzed);
  const result = panel.getByRole("region", { name: `Saved result: ${state.name}`, exact: true });
  await expect(result).toContainText(state.evidence.lineage.query_id);
  await expect(result.getByText(String(state.evidence.rows[0][0]), { exact: true })).toBeVisible();
  state.summary.exact_replay_verified = true;
  mark(state, "saved_evidence_layout");
  await layouts(state, result, "saved-answer", artifactPath);
}

async function isolation(state, states) {
  mark(state, "private_item_isolation");
  const items = await api(state.account, `${state.root}/saved-items`);
  const own = await api(state.account, `${state.workspace_root}/saved-items/${state.saved_id}`);
  assert.equal(own.id, state.saved_id);
  state.summary.authorized_controls += 1;
  const panel = state.page.getByRole("region", { name: "Saved work", exact: true });
  for (const other of states.filter((value) => value !== state)) {
    assert.ok(!items.some((item) => item.id === other.saved_id));
    await expect(panel.getByText(other.name, { exact: true })).toHaveCount(0);
    const response = await fetch(`${API}${state.workspace_root}/saved-items/${other.saved_id}`, {
      signal: AbortSignal.timeout(60_000), headers: { Authorization: `Bearer ${state.account.token}` },
    });
    assert.equal(response.status, 404);
    assert.equal((await response.json()).error.code, "not_found");
    state.summary.other_item_denials += 1;
  }
  state.summary.private_library_isolation = true;
}

async function finalChecks(state) {
  mark(state, "existing_navigation");
  await navigate(state.page, "Support");
  await expect(state.page.getByRole("region", { name: "Your support requests", exact: true })).toBeVisible();
  await navigate(state.page, "Forecasts");
  await expect(state.page.getByRole("region", { name: "Basic forecasting setup", exact: true })).toBeVisible();
  await navigate(state.page, "Overview");
  await expect(state.page.getByRole("region", { name: "Analytics home", exact: true })).toBeVisible();
  await selectedSource(state);
  const uploads = await api(state.account, `${state.dataset_root}/uploads`);
  assert.deepEqual(uploads.find((upload) => upload.id === state.upload_id), state.upload);
  assert.equal(state.summary.browser_errors, 0);
  state.summary.source_unchanged = true;
  state.summary.existing_navigation = true;
}

async function main() {
  const [sessionsPath, requestedOutput] = process.argv.slice(2);
  if (!sessionsPath || !requestedOutput) throw new Error("Pass private sessions and a fresh output path");
  const outputPath = resolve(requestedOutput);
  const dataRoot = fileURLToPath(new URL("../data/", import.meta.url));
  assert.ok(outputPath.startsWith(dataRoot.endsWith(sep) ? dataRoot : `${dataRoot}${sep}`));
  await mkdir(dirname(outputPath), { recursive: true, mode: 0o700 });
  const output = await open(outputPath, "wx", 0o600);
  const artifactPath = `${outputPath}.artifacts`;
  const states = [];
  const started = performance.now();
  let browser;
  let fatal;
  let stage = "private_inputs";
  try {
    const sessions = JSON.parse(await readFile(sessionsPath, "utf8"));
    assert.equal(sessions.scope, "private-fictional-demo");
    assert.equal(sessions.accounts.length, 8);
    assert.equal(new Set(sessions.accounts.map((account) => account.token)).size, 8);
    assert.equal(new Set(sessions.accounts.map((account) => account.email)).size, 8);
    assert.ok(Date.parse(sessions.expires_at) > Date.now());
    for (const id of [sessions.workspace_id, sessions.dataset_id, sessions.upload_id])
      assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
    const runName = `Fictional interface ${randomUUID().slice(0, 8)}`;
    await mkdir(artifactPath, { mode: 0o700 });
    for (const [index, account] of sessions.accounts.entries()) {
      const workspace_root = `/workspaces/${sessions.workspace_id}`;
      const dataset_root = `${workspace_root}/datasets/${sessions.dataset_id}`;
      states.push({ account, workspace_root, dataset_root, root: `${dataset_root}/uploads/${sessions.upload_id}`,
        workspace_id: sessions.workspace_id, dataset_id: sessions.dataset_id, upload_id: sessions.upload_id,
        summary: { user: index + 1, passed: false, stage, guidance_verified: false, chart_table_expand: false,
          exact_replay_verified: false, private_library_isolation: false, other_item_denials: 0,
          authorized_controls: 0, source_unchanged: false, existing_navigation: false, layouts: [], screenshots: 0, browser_errors: 0 },
      });
    }
    stage = "fictional_source_preflight";
    assert.equal((await api(states[0].account, "/health/ready")).status, "ready");
    for (const state of states) {
      const uploads = await api(state.account, `${state.dataset_root}/uploads`);
      state.upload = uploads.find((upload) => upload.id === state.upload_id);
      assert.equal(state.upload?.sample_id, "finance-v1");
      assert.equal((await api(state.account, "/auth/me")).email, state.account.email);
    }
    browser = await chromium.launch({ headless: true });
    for (const state of states) {
      state.context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
      state.page = await state.context.newPage();
      state.page.setDefaultTimeout(60_000);
      state.page.on("pageerror", () => { state.summary.browser_errors += 1; });
    }
    async function wave(name, action) {
      stage = name;
      await Promise.all(states.map(async (state) => {
        try { await action(state); }
        catch (error) {
          state.failed = true;
          Object.assign(state.summary, sanitizedFailure(error));
          console.log(JSON.stringify({ user: state.summary.user, stage: state.summary.stage, ...sanitizedFailure(error) }));
        }
      }));
      assert.ok(states.every((state) => !state.failed), "A concurrent browser wave failed");
    }
    await wave("sign_in", signIn);
    await wave("guidance", (state) => guidance(state, artifactPath));
    await wave("dashboard", (state) => dashboard(state, artifactPath));
    await wave("private_save", (state) => saveAnalysis(state, runName));
    await wave("library", (state) => library(state, runName, artifactPath));
    await wave("isolation", (state) => isolation(state, states));
    await wave("existing_navigation", finalChecks);
    for (const state of states) { state.summary.passed = true; mark(state, "complete"); }
  } catch (error) {
    fatal = { stage, ...sanitizedFailure(error) };
    console.log(JSON.stringify(fatal));
  } finally {
    for (const state of states) if (state.context) {
      try { await state.context.close(); }
      catch { fatal ??= { stage: "browser_cleanup", error_type: "Error", error_code: "cleanup_failed" }; }
    }
    if (browser) {
      try { await browser.close(); }
      catch { fatal ??= { stage: "browser_cleanup", error_type: "Error", error_code: "cleanup_failed" }; }
    }
    const report = {
      file_use_case: "Records eight concurrent private-demo interface journeys.",
      responsibility: "Retains identifiers, exact replay outcomes, isolation and responsive checks without tokens or source values.",
      created_at: new Date().toISOString(), scope: "private-fictional-demo-interface", production_evidence: false,
      concurrent_browsers: 8, total: 8, passed: states.filter((state) => state.summary.passed).length,
      elapsed_ms: Math.round(performance.now() - started), ...(fatal ? { fatal_error: fatal } : {}),
      limitations: [
        "Functional rehearsal on the approved finance-v1 sample, not sustained load or complete ThoughtSpot parity.",
        "Saved private analyses and guidance jobs are intentionally retained; no source or customer data is changed.",
        "Screenshots cover only the selected fictional source, composer and newly created private evidence.",
      ], results: states.map((state) => state.summary),
    };
    try { await output.writeFile(JSON.stringify(report, null, 2) + "\n"); }
    finally { await output.close(); }
    console.log(JSON.stringify(report));
    process.exitCode = !fatal && report.passed === 8 ? 0 : 1;
  }
}

await main().catch(() => {
  console.error("Interface rehearsal could not initialize; no private details are logged.");
  process.exitCode = 1;
});
