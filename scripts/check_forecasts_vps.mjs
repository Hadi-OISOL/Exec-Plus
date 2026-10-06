/* Use case: Rehearses private basic forecasts for eight deployed demo users.
What it does: Checks fictional source refresh, exact replay, private comparisons and responsive UI without recording sessions or source rows. */

import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { mkdir, open, readFile } from "node:fs/promises";
import { dirname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, expect as baseExpect } from "@playwright/test";

const API = "http://localhost:18401";
const WEB = "http://localhost:18400";
const expect = baseExpect.configure({ timeout: 120_000 });
const canonical = (value) => String(value).replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1");
const json = (body, method = "POST") => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

function dailyFile(count) {
  const lines = ["day,amount,city"];
  for (let index = 0; index < count; index += 1) {
    const period = new Date(Date.UTC(2024, 0, index + 1)).toISOString().slice(0, 10);
    const amount = `${Math.floor((index + 1) / 10)}.${(index + 1) % 10}`;
    lines.push(`${period},${amount},Karachi`);
  }
  return lines.join("\n") + "\n";
}

async function api(account, path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    signal: AbortSignal.timeout(120_000),
    ...options,
    headers: { Authorization: `Bearer ${account.token}`, ...options.headers },
  });
  if (!response.ok) {
    const error = new Error("API request failed");
    error.code = `http_${response.status}`;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}

function failure(error) {
  const type = ["AssertionError", "TimeoutError", "TypeError", "SyntaxError"].includes(error?.name)
    ? error.name : "Error";
  return { error_type: type, error_code: /^http_\d{3}$/.test(error?.code) ? error.code : "check_failed" };
}

async function navigate(page, name) {
  await page.getByRole("navigation", { name: "Workspace navigation" })
    .getByRole("button", { name, exact: true }).click();
}

async function responseFor(page, path, method, action) {
  const pending = page.waitForResponse(
    (response) => new URL(response.url()).pathname === path && response.request().method() === method,
    { timeout: 150_000 },
  ).catch(() => null);
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

function mark(state, stage) {
  state.summary.stage = stage;
  console.log(JSON.stringify({ user: state.summary.user, stage }));
}

async function selectSource(state, target, uploadId) {
  const { page } = state;
  mark(state, "select_workspace");
  await page.getByLabel("Current workspace").selectOption(target.workspace_id);
  await expect(page.getByLabel("Current workspace")).toHaveValue(target.workspace_id);
  await expect(page.getByLabel("Dataset", { exact: true })
    .locator(`option[value="${target.dataset_id}"]`)).toHaveCount(1);
  mark(state, "select_dataset");
  await page.getByLabel("Dataset", { exact: true }).selectOption(target.dataset_id);
  const uploads = page.getByLabel("Profile upload");
  await expect(uploads.locator(`option[value="${uploadId}"]`)).toHaveCount(1);
  mark(state, "select_upload");
  await uploads.selectOption(uploadId);
  await expect(uploads).toHaveValue(uploadId);
  mark(state, "open_forecasts");
  await navigate(page, "Forecasts");
  await expect(page.getByRole("region", { name: "Basic forecasting setup" })).toBeVisible();
}

async function setup(accounts, target) {
  const owner = accounts[0];
  const ready = await api(owner, "/health/ready");
  assert.equal(ready.status, "ready");
  const contract = await api(owner, "/openapi.json");
  assert.ok(contract.paths["/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/forecasts"]);
  for (const account of accounts) {
    const identity = await api(account, "/auth/me");
    assert.equal(identity.email, account.email);
  }
  const workspace = await api(owner, "/workspaces", json({
    name: `Fictional forecast rehearsal ${new Date().toISOString()}`,
    seat_limit: 8,
  }));
  target.workspace_id = workspace.id;
  const workspaceRoot = `/workspaces/${workspace.id}`;
  for (const account of accounts.slice(1)) {
    const invitation = await api(owner, `${workspaceRoot}/invitations`, json({ email: account.email, role: "member" }));
    await api(account, `${workspaceRoot}/invitations/${invitation.id}/accept`, { method: "POST" });
  }
  const dataset = await api(owner, `${workspaceRoot}/datasets`, json({ name: "Fictional daily receipts" }));
  target.dataset_id = dataset.id;
  const root = `${workspaceRoot}/datasets/${dataset.id}`;
  const upload = await api(owner, `${root}/uploads?filename=fictional-history.csv`, {
    method: "POST", headers: { "Content-Type": "text/csv" }, body: dailyFile(40),
  });
  target.original_upload_id = upload.id;
  const source = `${root}/uploads/${upload.id}`;
  const current = await api(owner, `${source}/understanding`);
  const definition = structuredClone(current.definition);
  definition.domain = "sales";
  definition.grain = "record";
  for (const column of definition.columns) {
    if (column.role === "metric") column.unit = "PKR";
  }
  const confirmed = await api(owner, `${source}/understanding`, json({
    revision_id: current.revision_id, expected_version: current.version,
    state: "confirmed", definition,
  }));
  const options = await api(owner, `${source}/forecasts/options`);
  assert.equal(options.state, "ready");
  await api(owner, `${root}/refresh`, json({
    upload_id: upload.id, revision_id: current.revision_id, understanding_id: confirmed.id,
    expected_version: 0, as_of: new Date(Date.now() - 60_000).toISOString(),
    interval_hours: 1, freshness_hours: 48, enabled: false,
  }, "PUT"));
}

async function refresh(account, target) {
  const root = `/workspaces/${target.workspace_id}/datasets/${target.dataset_id}`;
  const state = await api(account, `${root}/refresh`);
  const data = new FormData();
  data.set("options", JSON.stringify({
    request_id: randomUUID(), expected_version: state.feed.version, mode: "replace",
    keys: [], duplicates: "keep_all", as_of: new Date().toISOString(),
  }));
  data.set("file", new Blob([dailyFile(43)], { type: "text/csv" }), "fictional-later-actuals.csv");
  const candidate = await api(account, `${root}/refresh/candidates`, { method: "POST", body: data });
  assert.equal(candidate.status, "queued");
  const activated = await api(account, `/workspaces/${target.workspace_id}/refresh-candidates/${candidate.id}/activate`, { method: "POST" });
  assert.equal(activated.status, "activated");
  const current = await api(account, `${root}/refresh`);
  target.later_upload_id = current.feed.source.upload_id;
  target.refresh_candidate_id = candidate.id;
  assert.notEqual(target.later_upload_id, target.original_upload_id);
  assert.equal(current.feed.enabled, false);
  const options = await api(account, `${root}/uploads/${target.later_upload_id}/forecasts/options`);
  assert.equal(options.state, "ready");
}

async function createForecast(state, target) {
  const { page, account } = state;
  state.summary.stage = "sign_in";
  await page.goto(`${WEB}/workspace`);
  await page.getByLabel("Session token").fill(account.token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText(`Signed in as ${account.email}`)).toBeVisible();
  state.summary.stage = "forecast_setup";
  await selectSource(state, target, target.original_upload_id);
  const setup = page.getByRole("region", { name: "Basic forecasting setup" });
  mark(state, "select_date_column");
  await setup.getByRole("combobox", { name: "Date column", exact: true }).selectOption("day");
  mark(state, "select_metric");
  await setup.getByRole("combobox", { name: "Forecast metric", exact: true }).selectOption("amount");
  mark(state, "select_aggregation");
  await setup.getByRole("combobox", { name: "Aggregation", exact: true }).selectOption("sum");
  mark(state, "select_frequency");
  await setup.getByRole("combobox", { name: "Period", exact: true }).selectOption("daily");
  mark(state, "set_horizon");
  await setup.getByLabel("Periods to forecast", { exact: true }).fill("3");
  mark(state, "set_coverage_start");
  await setup.getByLabel("Source coverage start").fill("2024-01-01");
  mark(state, "set_coverage_end");
  await setup.getByLabel("Source coverage end").fill("2024-02-09");
  mark(state, "confirm_coverage");
  await setup.getByLabel("I confirm the source covers every complete period in this range.").check();
  mark(state, "open_forecast_details");
  await setup.getByText("Forecast name and seasonal comparison", { exact: true }).click();
  mark(state, "set_name");
  await setup.getByLabel("Forecast name", { exact: true }).fill(`Private forecast ${state.summary.user}`);
  const path = `/workspaces/${target.workspace_id}/datasets/${target.dataset_id}/uploads/${target.original_upload_id}/forecasts`;
  mark(state, "forecast_create");
  state.forecast = await responseFor(page, path, "POST", () => setup.getByRole("button", { name: "Create forecast", exact: true }).click());
  assert.equal(state.forecast.result.method.id, "linear_trend");
  assert.deepEqual(state.forecast.result.predictions.map((row) => canonical(row.estimate)), ["4.1", "4.2", "4.3"]);
  assert.equal(canonical(state.forecast.result.accuracy.mae), "0");
  const displayed = page.getByRole("article", { name: `Forecast result: ${state.forecast.name}` });
  await expect(displayed).toBeVisible();
  await expect(displayed.getByRole("region", { name: "Result records", exact: true }).first()).toContainText("2024-02-10");
  await expect(displayed).toContainText("no guaranteed coverage");
  await expect(displayed.locator(".verifiedBadge")).toHaveCount(0);
  state.summary.forecasts_created = 1;
  mark(state, "forecast_saved");
}

async function compareActuals(state, target) {
  const { page, account } = state;
  state.summary.stage = "select_refreshed_source";
  await page.reload();
  await page.getByLabel("Session token").fill(account.token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText(`Signed in as ${account.email}`)).toBeVisible();
  await expect(page.getByLabel("Current workspace")).toBeVisible();
  await selectSource(state, target, target.later_upload_id);
  await page.getByRole("combobox", { name: "Saved forecast", exact: true }).selectOption(state.forecast.id);
  const root = `/workspaces/${target.workspace_id}/datasets/${target.dataset_id}/forecasts/${state.forecast.id}`;
  state.summary.stage = "original_forecast_reopen";
  const original = await responseFor(page, root, "GET", () => page.getByRole("button", { name: "Open saved forecast", exact: true }).click());
  assert.deepEqual(original.result, state.forecast.result);
  const panel = page.getByRole("region", { name: "Compare later actual data" });
  await panel.getByLabel("Actual coverage start").fill("2024-02-10");
  await panel.getByLabel("Actual coverage end").fill("2024-02-12");
  await panel.getByLabel("I confirm this source completely covers the declared actual periods.").check();
  state.summary.stage = "actual_comparison";
  state.comparison = await responseFor(page, `${root}/compare`, "POST", () => panel.getByRole("button", { name: "Compare actual data", exact: true }).click());
  assert.equal(state.comparison.result.observed_count, 3);
  assert.equal(state.comparison.result.pending_count, 0);
  assert.equal(canonical(state.comparison.result.metrics.mae), "0");
  assert.deepEqual(state.comparison.result.rows.map((row) => canonical(row.actual)), ["4.1", "4.2", "4.3"]);
  assert.deepEqual(state.comparison.result.rows.map((row) => canonical(row.estimate)), ["4.1", "4.2", "4.3"]);
  await expect(page.getByRole("region", { name: "Accuracy against later actual data", exact: true })).toContainText("0 PKR");
  const preserved = await api(account, root);
  assert.deepEqual(preserved.result, state.forecast.result);
  await panel.getByText("Saved actual comparisons (1)", { exact: true }).click();
  const reopened = await responseFor(page, `${root}/comparisons/${state.comparison.id}`, "GET", () => panel.getByRole("button", { name: "Open comparison", exact: true }).click());
  assert.deepEqual(reopened.result, state.comparison.result);
  state.summary.comparisons_created = 1;
  state.summary.original_preserved = true;
  state.summary.saved_results_reopened = 2;
  state.summary.stage = "receipt_replay";
  for (const [run, count, start] of [[state.forecast, 40, 1], [state.comparison, 3, 41]]) {
    assert.equal(run.evidence.query_ids.length, 3);
    for (const [index, identifier] of run.evidence.query_ids.entries()) {
      const replay = await api(account, `/workspaces/${target.workspace_id}/queries/${identifier}/replay`, { method: "POST" });
      assert.equal(replay.rows.length, count);
      for (const [offset, row] of replay.rows.entries()) {
        const expected = index === 0 ? `${Math.floor((start + offset) / 10)}.${(start + offset) % 10}` : "1";
        assert.equal(String(row[0]).slice(0, 10), new Date(Date.UTC(2024, 0, start + offset)).toISOString().slice(0, 10));
        assert.equal(canonical(row[1]), canonical(expected));
      }
      state.summary.receipts_replayed += 1;
    }
  }
}

async function privateChecks(state, other, target) {
  state.summary.stage = "private_access";
  const base = `/workspaces/${target.workspace_id}/datasets/${target.dataset_id}/forecasts/${other.forecast.id}`;
  for (const path of [base, `${base}/comparisons/${other.comparison.id}`]) {
    const response = await fetch(`${API}${path}`, {
      signal: AbortSignal.timeout(120_000), headers: { Authorization: `Bearer ${state.account.token}` },
    });
    assert.equal(response.status, 404);
    state.summary.private_access_denials += 1;
  }
  for (const identifier of [other.forecast.id, other.comparison.id]) {
    const result = await api(state.account, `/workspaces/${target.workspace_id}/audit-history?q=${identifier}&limit=100`);
    assert.deepEqual(result.events, []);
    assert.equal(result.next_cursor, null);
    state.summary.private_audit_checks += 1;
  }
  await navigate(state.page, "Audit history");
  const audit = state.page.getByRole("region", { name: "Workspace audit history", exact: true });
  await audit.getByLabel("Search audit history").fill(state.forecast.id);
  await audit.getByRole("button", { name: "Apply audit filters", exact: true }).click();
  await expect(audit).toContainText("forecast.created");
  await expect(audit).toContainText(state.forecast.id);
  state.summary.audit_ui_verified = true;
}

async function layout(state, target, artifactPath) {
  const { page } = state;
  state.summary.stage = "responsive_layout";
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    state.summary.layout_widths.push(width);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await navigate(page, "Forecasts");
  await page.getByRole("combobox", { name: "Saved forecast", exact: true }).selectOption(state.forecast.id);
  const root = `/workspaces/${target.workspace_id}/datasets/${target.dataset_id}/forecasts/${state.forecast.id}`;
  await responseFor(page, root, "GET", () => page.getByRole("button", { name: "Open saved forecast", exact: true }).click());
  const comparisons = page.getByRole("region", { name: "Compare later actual data" });
  await comparisons.getByText("Saved actual comparisons (1)", { exact: true }).click();
  await responseFor(page, `${root}/comparisons/${state.comparison.id}`, "GET", () => comparisons.getByRole("button", { name: "Open comparison", exact: true }).click());
  const article = page.getByRole("article", { name: `Forecast result: ${state.forecast.name}` });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await expect(article.getByRole("region", { name: "Grounded forecast commentary" })).toBeVisible();
    const output = await open(`${artifactPath}/user-${state.summary.user}-${width}.png`, "wx", 0o600);
    try { await output.writeFile(await article.screenshot()); }
    finally { await output.close(); }
    state.summary.screenshots += 1;
  }
}

async function captureFailure(state, target, artifactPath) {
  const { page } = state;
  try {
    if (await page.getByLabel("Current workspace").inputValue({ timeout: 1000 }) !== target.workspace_id) return;
    if (await page.getByLabel("Dataset", { exact: true }).inputValue({ timeout: 1000 }) !== target.dataset_id) return;
    const panel = page.getByRole("region", { name: "Basic forecasting setup" });
    if (!await panel.isVisible()) return;
    const screenshot = await panel.screenshot({ timeout: 5000 });
    const output = await open(`${artifactPath}/failed-user-${state.summary.user}.png`, "wx", 0o600);
    try { await output.writeFile(screenshot); }
    finally { await output.close(); }
    state.summary.failure_screenshot = true;
  } catch { state.summary.failure_screenshot = false; }
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
  let browser;
  let stage = "private_inputs";
  let fatal;
  const target = {};
  const states = [];
  const started = performance.now();
  try {
    await mkdir(artifactPath, { mode: 0o700 });
    const sessions = JSON.parse(await readFile(sessionsPath, "utf8"));
    assert.equal(sessions.accounts.length, 8);
    assert.equal(new Set(sessions.accounts.map((account) => account.email)).size, 8);
    assert.equal(new Set(sessions.accounts.map((account) => account.token)).size, 8);
    stage = "fictional_setup";
    await setup(sessions.accounts, target);
    browser = await chromium.launch({ headless: true });
    for (const [index, account] of sessions.accounts.entries()) {
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
      const page = await context.newPage();
      page.setDefaultTimeout(120_000);
      states.push({ account, context, page, started: performance.now(), summary: {
        user: index + 1, passed: false, stage: "created_browser", forecasts_created: 0,
        comparisons_created: 0, original_preserved: false, saved_results_reopened: 0,
        receipts_replayed: 0, private_access_denials: 0, private_audit_checks: 0,
        audit_ui_verified: false, layout_widths: [], screenshots: 0,
      } });
    }
    async function wave(action) {
      await Promise.all(states.map(async (state, index) => {
        if (state.failed) return;
        try { await action(state, index); }
        catch (error) {
          state.failed = true;
          Object.assign(state.summary, failure(error));
          console.log(JSON.stringify({ user: state.summary.user, stage: state.summary.stage, ...failure(error) }));
          await captureFailure(state, target, artifactPath);
        }
      }));
      assert.ok(states.every((state) => !state.failed), "A synchronized browser wave failed");
    }
    stage = "create_wave";
    await wave((state) => createForecast(state, target));
    console.log(JSON.stringify({ stage: "eight_forecasts_created", users: states.length }));
    stage = "staged_refresh";
    await refresh(sessions.accounts[0], target);
    console.log(JSON.stringify({ stage: "fictional_refresh_activated", users: states.length }));
    stage = "comparison_wave";
    await wave((state) => compareActuals(state, target));
    stage = "privacy_and_layout";
    await wave(async (state, index) => {
      await privateChecks(state, states[(index + 1) % states.length], target);
      await layout(state, target, artifactPath);
      state.summary.passed = true;
      state.summary.stage = "complete";
    });
  } catch (error) { fatal = { stage, ...failure(error) }; }
  finally {
    for (const state of states) {
      state.summary.elapsed_ms = Math.round(performance.now() - state.started);
      try { await state.context.close(); } catch {
        fatal ??= { stage: "browser_cleanup", error_type: "Error", error_code: "cleanup_failed" };
      }
    }
    if (browser) { try { await browser.close(); } catch {
      fatal ??= { stage: "browser_cleanup", error_type: "Error", error_code: "cleanup_failed" };
    } }
    const report = {
      file_use_case: "Records an eight-user fictional forecasting rehearsal on the private demo.",
      responsibility: "Retains outcomes and counters without session tokens, prompts or uploaded rows.",
      created_at: new Date().toISOString(), production_evidence: false,
      scope: "private-demo-fictional-forecasting", total: 8,
      passed: states.filter((state) => state.summary.passed).length,
      elapsed_ms: Math.round(performance.now() - started), target,
      ...(fatal ? { fatal_error: fatal } : {}),
      limitations: ["Short functional rehearsal, not a sustained-load or speed benchmark.", "Refresh is explicitly staged and manually activated; scheduled-worker behavior is covered separately."],
      results: states.map((state) => state.summary),
    };
    try { await output.writeFile(JSON.stringify(report, null, 2) + "\n"); }
    finally { await output.close(); }
    console.log(JSON.stringify(report));
    process.exitCode = !fatal && report.passed === 8 ? 0 : 1;
  }
}

await main().catch(() => {
  console.error("Forecast rehearsal could not initialize; no private details are logged.");
  process.exitCode = 1;
});
