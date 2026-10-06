/* Use case: Rehearses internal operations and private support with eight demo users.
What it does: Checks fictional support lifecycles, aggregate usage, staff boundaries and mobile views without recording credentials or customer data. */

import assert from "node:assert/strict";
import { mkdir, open, readFile } from "node:fs/promises";
import { dirname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, expect as baseExpect } from "@playwright/test";

const API = "http://localhost:18401";
const WEB = "http://localhost:18400";
const expect = baseExpect.configure({ timeout: 60_000 });
const json = (body, method = "POST") => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});
const ticketRoot = (state, staff = false) => `${staff ? "/admin" : ""}/workspaces/${state.workspace_id}/support-tickets/${state.ticket.ticket.id}`;

function failure(error) {
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

async function denied(account, path, status) {
  const response = await fetch(`${API}${path}`, {
    signal: AbortSignal.timeout(60_000), headers: { Authorization: `Bearer ${account.token}` },
  });
  assert.equal(response.status, status);
  assert.equal((await response.json()).error.code, status === 403 ? "staff_required" : "not_found");
}

async function responseFor(page, path, method, action) {
  const pending = page.waitForResponse(
    (response) => new URL(response.url()).pathname === path && response.request().method() === method,
    { timeout: 120_000 },
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

async function navigate(page, name) {
  await page.getByRole("navigation", { name: "Workspace navigation" })
    .getByRole("button", { name, exact: true }).click();
}

async function signIn(state) {
  mark(state, "sign_in");
  await state.page.goto(`${WEB}/workspace?workspace=${state.workspace_id}`);
  await state.page.getByLabel("Session token").fill(state.account.token);
  await state.page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(state.page.getByText(`Signed in as ${state.account.email}`)).toBeVisible();
  await expect(state.page.getByRole("combobox", { name: "Current workspace", exact: true }))
    .toHaveValue(state.workspace_id);
}

async function setup(states) {
  const owner = states[0].account;
  assert.equal((await api(owner, "/health/ready")).status, "ready");
  const contract = await api(owner, "/openapi.json");
  for (const path of ["/admin/access", "/admin/workspaces", "/workspaces/{workspace_id}/product-usage", "/workspaces/{workspace_id}/support-tickets"])
    assert.ok(contract.paths[path]);
  for (const state of states) {
    const current = await api(state.account, "/auth/me");
    assert.equal(current.email, state.account.email);
    state.actor_id = current.id;
    const access = await api(state.account, "/admin/access");
    assert.equal(access.role, state.summary.user === 1 ? "admin" : null);
  }
  for (const state of states) {
    mark(state, "fictional_workspace_setup");
    const workspace = await api(state.account, "/workspaces", json({
      name: `Fictional operations rehearsal ${new Date().toISOString()} user ${state.summary.user}`, seat_limit: 3,
    }));
    state.workspace_id = workspace.id;
    state.workspace_name = workspace.name;
    const dataset = await api(state.account, `/workspaces/${workspace.id}/datasets`, json({ name: "Fictional activity seed" }));
    state.dataset_id = dataset.id;
    const upload = await api(state.account, `/workspaces/${workspace.id}/datasets/${dataset.id}/uploads?filename=fictional-operations.csv`, {
      method: "POST", headers: { "Content-Type": "text/csv" },
      body: "day,amount,city\n2026-10-01,0.10,Karachi\n2026-10-02,0.20,Lahore\n",
    });
    state.upload_id = upload.id;
    state.summary.workspace_id = workspace.id;
  }
}

function checkDetail(detail, state, version, status) {
  assert.equal(detail.ticket.id, state.ticket?.ticket.id ?? detail.ticket.id);
  assert.equal(detail.ticket.workspace_id, state.workspace_id);
  assert.equal(detail.ticket.requester_id, state.actor_id);
  assert.equal(detail.ticket.version, version);
  assert.equal(detail.ticket.status, status);
  assert.equal(detail.events.length, version);
  assert.deepEqual(detail.events.map((event) => event.sequence), Array.from({ length: version }, (_, index) => index + 1));
  assert.equal(detail.diagnostics, null);
  assert.equal(detail.ticket.job_id, null);
  assert.equal(detail.ticket.feedback_id, null);
}

async function createTicket(state) {
  await signIn(state);
  mark(state, "open_requester_support");
  await navigate(state.page, "Support");
  const panel = state.page.getByRole("region", { name: "Your support requests", exact: true });
  await panel.getByText("Open a support request", { exact: true }).click();
  await panel.getByLabel("Request subject", { exact: true }).fill(`Fictional walkthrough ${state.summary.user}`);
  await panel.getByRole("combobox", { name: "Support feature", exact: true }).selectOption("dashboard");
  await panel.getByRole("combobox", { name: "Request category", exact: true }).selectOption("question");
  await panel.getByLabel("What happened?", { exact: true }).fill("Fictional rehearsal: explain the dashboard walkthrough. No customer data is attached.");
  mark(state, "submit_support_request");
  state.ticket = await responseFor(state.page, `/workspaces/${state.workspace_id}/support-tickets`, "POST",
    () => panel.getByRole("button", { name: "Submit support request", exact: true }).click());
  checkDetail(state.ticket, state, 1, "open");
  state.summary.tickets_created = 1;
  state.summary.ticket_id = state.ticket.ticket.id;
  await expect(panel.getByRole("article", { name: "Selected support request", exact: true })).toContainText(state.ticket.ticket.id);
  if (state.summary.user !== 1)
    await expect(state.page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Admin console", exact: true })).toHaveCount(0);
  mark(state, "request_created");
}

async function openTicket(page, state, staff) {
  const panel = page.getByRole("region", { name: staff ? "Internal support queue" : "Your support requests", exact: true });
  await panel.getByLabel("Search requests", { exact: true }).fill(state.ticket.ticket.id);
  await panel.getByRole("button", { name: "Filter requests", exact: true }).click();
  const detail = await responseFor(page, ticketRoot(state, staff), "GET", () => panel.locator(".supportRequestList")
    .getByRole("button").filter({ hasText: state.ticket.ticket.id }).click());
  await expect(panel.getByRole("article", { name: "Selected support request", exact: true })).toContainText(state.ticket.ticket.id);
  return detail;
}

async function staffTriage(admin, state, status, version) {
  mark(state, `staff_${status}`);
  const detail = admin.page.getByRole("article", { name: "Selected support request", exact: true });
  await expect(detail).toContainText(state.ticket.ticket.id);
  await detail.getByRole("combobox", { name: "Update status", exact: true }).selectOption(status);
  await detail.getByRole("combobox", { name: "Update priority", exact: true }).selectOption("high");
  await detail.getByRole("combobox", { name: "Assign support staff", exact: true }).selectOption(admin.actor_id);
  await detail.getByLabel("Public triage note", { exact: true }).fill(`Fictional rehearsal status: ${status}.`);
  const result = await responseFor(admin.page, ticketRoot(state, true), "PATCH", () => detail.getByRole("button", { name: "Save triage", exact: true }).click());
  checkDetail(result, state, version, status);
  assert.equal(result.ticket.assignee_id, admin.actor_id);
  assert.equal(result.ticket.priority, "high");
  state.ticket = result;
  state.summary.staff_transitions += 1;
}

async function staffWork(states) {
  const admin = states[0];
  await navigate(admin.page, "Admin console");
  await admin.page.getByRole("button", { name: "Support queue", exact: true }).click();
  for (const state of states) {
    const original = await openTicket(admin.page, state, true);
    checkDetail(original, state, 1, "open");
    await staffTriage(admin, state, "triaged", 2);
    mark(state, "staff_reply");
    const article = admin.page.getByRole("article", { name: "Selected support request", exact: true });
    await article.getByLabel("Reply to this request", { exact: true }).fill("Fictional support reply: review the calculated evidence and visible filters.");
    const reply = await responseFor(admin.page, `${ticketRoot(state, true)}/messages`, "POST",
      () => article.getByRole("button", { name: "Send reply", exact: true }).click());
    checkDetail(reply, state, 3, "triaged");
    state.ticket = reply;
    state.summary.staff_replies = 1;
    await staffTriage(admin, state, "escalated", 4);
    await staffTriage(admin, state, "resolved", 5);
    assert.ok(state.ticket.ticket.resolved_at);
  }
}

async function requesterResume(state) {
  mark(state, "requester_reload");
  await signIn(state);
  await navigate(state.page, "Support");
  const original = await openTicket(state.page, state, false);
  checkDetail(original, state, 5, "resolved");
  const detail = state.page.getByRole("article", { name: "Selected support request", exact: true });
  await expect(detail).toContainText("Fictional support reply");
  mark(state, "requester_reopen");
  await detail.getByLabel("Why reopen? (optional)", { exact: true }).fill("Fictional follow-up to verify the retained support history.");
  const reopened = await responseFor(state.page, `${ticketRoot(state)}/reopen`, "POST",
    () => detail.getByRole("button", { name: "Reopen request", exact: true }).click());
  checkDetail(reopened, state, 6, "open");
  assert.equal(reopened.ticket.resolved_at, null);
  assert.deepEqual(reopened.events.slice(0, 5), original.events);
  state.ticket = reopened;
  mark(state, "requester_reply");
  await detail.getByLabel("Reply to this request", { exact: true }).fill("Fictional requester reply: the previous history remains visible.");
  const replied = await responseFor(state.page, `${ticketRoot(state)}/messages`, "POST",
    () => detail.getByRole("button", { name: "Send reply", exact: true }).click());
  checkDetail(replied, state, 7, "open");
  assert.equal(replied.events[6].actor_role, "requester");
  state.ticket = replied;
  const saved = await api(state.account, ticketRoot(state));
  assert.deepEqual(saved, replied);
  state.summary.requester_reopens = 1;
  state.summary.requester_replies = 1;
  state.summary.timeline_events = saved.events.length;
  state.summary.saved_history_verified = true;
  mark(state, "requester_history_preserved");
}

function checkUsage(report, state) {
  assert.equal(report.workspace_id, state.workspace_id);
  assert.equal(report.version, "usage-v1");
  assert.equal(report.summary.current_members, 1);
  assert.equal(report.summary.active_users, 1);
  assert.equal(report.summary.active_members, 1);
  assert.equal(report.usage.uploads, 1);
  assert.equal(report.weekly.at(-1).complete, false);
  assert.equal(report.cohorts.length, 1);
  assert.ok(report.cohorts[0].cells.every((cell) => cell.eligible === false && cell.retained === null && cell.rate_percent === null));
  assert.ok(report.features.some((item) => item.feature === "uploads" && item.users === 1));
}

async function usage(state) {
  mark(state, "usage_report");
  const path = `/workspaces/${state.workspace_id}/product-usage`;
  const report = await responseFor(state.page, path, "GET", () => navigate(state.page, "Usage & retention"));
  checkUsage(report, state);
  const panel = state.page.getByRole("region", { name: "Product usage and retention", exact: true });
  await expect(panel.getByRole("region", { name: "Weekly product activity", exact: true })).toContainText("In progress");
  await expect(panel.getByRole("region", { name: "Weekly retention cohorts", exact: true })).toContainText("Not mature");
  await expect(panel.getByRole("region", { name: "Feature adoption", exact: true })).toContainText("uploads");
  const wider = await responseFor(state.page, path, "GET", () => panel.getByRole("combobox", { name: "Reporting window", exact: true }).selectOption("12"));
  checkUsage(wider, state);
  assert.equal(wider.period.weeks, 12);
  state.summary.usage_reports_verified = 2;
}

async function privacy(states) {
  for (const [index, state] of states.entries()) {
    mark(state, "access_boundaries");
    const other = states[(index + 1) % states.length];
    const authorizedTicket = await api(other.account, ticketRoot(other));
    assert.equal(authorizedTicket.ticket.id, other.ticket.ticket.id);
    await denied(state.account, ticketRoot(other), 404);
    state.summary.authorized_controls += 1;
    state.summary.other_ticket_denials = 1;
    if (index > 0) {
      const directoryPath = `/admin/workspaces?q=${state.workspace_id}`;
      const queuePath = `/admin/support-tickets?workspace_id=${state.workspace_id}`;
      const directory = await api(states[0].account, directoryPath);
      assert.ok(directory.workspaces.some((workspace) => workspace.id === state.workspace_id));
      const queue = await api(states[0].account, queuePath);
      assert.ok(queue.tickets.some((ticket) => ticket.id === state.ticket.ticket.id));
      await denied(state.account, directoryPath, 403);
      await denied(state.account, queuePath, 403);
      state.summary.authorized_controls += 2;
      state.summary.nonstaff_denials = 2;
      const datasetPath = `/workspaces/${state.workspace_id}/datasets`;
      const profilePath = `${datasetPath}/${state.dataset_id}/uploads/${state.upload_id}/profile`;
      const datasets = await api(state.account, datasetPath);
      assert.ok(datasets.some((dataset) => dataset.id === state.dataset_id));
      const profile = await api(state.account, profilePath);
      assert.equal(profile.upload_id, state.upload_id);
      await denied(states[0].account, datasetPath, 404);
      await denied(states[0].account, profilePath, 404);
      state.summary.authorized_controls += 2;
      state.summary.staff_data_denials = 2;
    }
    const metadata = await api(states[0].account, `/admin/workspaces/${state.workspace_id}`);
    assert.equal(metadata.id, state.workspace_id);
    assert.equal(metadata.active_seats, 1);
    assert.equal(metadata.uploads, 1);
    assert.equal(metadata.datasets, 1);
    assert.equal(metadata.plan.billing, "unconfigured");
    assert.equal(metadata.support.open, 1);
    for (const forbidden of ["rows", "question", "answer", "description", "content", "storage_key"])
      assert.equal(Object.hasOwn(metadata, forbidden), false);
    const aggregate = await api(states[0].account, `/admin/workspaces/${state.workspace_id}/product-usage?weeks=12`);
    checkUsage(aggregate, state);
    state.summary.staff_metadata_verified = true;
  }
}

async function staffDirectory(states) {
  const admin = states[0];
  const target = states[7];
  mark(admin, "staff_directory_ui");
  await navigate(admin.page, "Admin console");
  const directory = admin.page.getByRole("region", { name: "Admin workspace directory", exact: true });
  await directory.getByLabel("Find a workspace", { exact: true }).fill(target.workspace_id);
  await directory.getByRole("button", { name: "Search workspaces", exact: true }).click();
  const metadata = await responseFor(admin.page, `/admin/workspaces/${target.workspace_id}`, "GET",
    () => directory.getByRole("button", { name: target.workspace_name, exact: true }).click());
  assert.equal(metadata.id, target.workspace_id);
  const detail = admin.page.getByRole("region", { name: "Admin workspace details", exact: true });
  await expect(detail).toContainText(target.workspace_id);
  await expect(detail).toContainText("Billing unconfigured");
  const report = await responseFor(admin.page, `/admin/workspaces/${target.workspace_id}/product-usage`, "GET",
    () => detail.getByRole("button", { name: "View product usage", exact: true }).click());
  checkUsage(report, target);
  admin.summary.staff_directory_ui = true;
}

async function screenshot(state, locator, artifactPath, name) {
  const file = await open(`${artifactPath}/user-${state.summary.user}-${name}.png`, "wx", 0o600);
  try { await file.writeFile(await locator.screenshot({ timeout: 10_000 })); }
  finally { await file.close(); }
  state.summary.screenshots += 1;
}

async function layouts(state, artifactPath) {
  mark(state, "responsive_usage");
  await navigate(state.page, "Usage & retention");
  await expect(state.page.getByRole("combobox", { name: "Current workspace", exact: true })).toHaveValue(state.workspace_id);
  const usagePanel = state.page.getByRole("region", { name: "Product usage and retention", exact: true });
  await expect(usagePanel.getByRole("region", { name: "Weekly retention cohorts", exact: true })).toContainText("Not mature");
  for (const width of [1440, 390, 320]) {
    await state.page.setViewportSize({ width, height: 1000 });
    await state.page.emulateMedia({ reducedMotion: "reduce" });
    assert.ok(await state.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await screenshot(state, usagePanel, artifactPath, `usage-${width}`);
    state.summary.layout_widths.push(width);
  }
  mark(state, "responsive_support");
  await navigate(state.page, "Support");
  const reopened = await openTicket(state.page, state, false);
  assert.deepEqual(reopened, state.ticket);
  const article = state.page.getByRole("article", { name: "Selected support request", exact: true });
  for (const width of [1440, 390, 320]) {
    await state.page.setViewportSize({ width, height: 1000 });
    assert.ok(await state.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await expect(article).toContainText(state.ticket.ticket.id);
    await screenshot(state, article, artifactPath, `support-${width}`);
  }
}

async function failureCapture(state, artifactPath) {
  if (state.summary.failure_screenshot) return;
  try {
    if (!state.ticket) return;
    const article = state.page.getByRole("article", { name: "Selected support request", exact: true });
    if (!await article.isVisible() || !(await article.innerText()).includes(state.ticket.ticket.id)) return;
    await screenshot(state, article, artifactPath, "failed-ticket");
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
  const states = [];
  let browser;
  let fatal;
  let stage = "private_inputs";
  const started = performance.now();
  try {
    await mkdir(artifactPath, { mode: 0o700 });
    const sessions = JSON.parse(await readFile(sessionsPath, "utf8"));
    assert.equal(sessions.accounts.length, 8);
    assert.equal(new Set(sessions.accounts.map((account) => account.email)).size, 8);
    assert.equal(new Set(sessions.accounts.map((account) => account.token)).size, 8);
    for (const [index, account] of sessions.accounts.entries()) states.push({ account, summary: {
      user: index + 1, passed: false, stage: "private_inputs", tickets_created: 0,
      staff_transitions: 0, staff_replies: 0, requester_reopens: 0, requester_replies: 0,
      timeline_events: 0, saved_history_verified: false, usage_reports_verified: 0,
      other_ticket_denials: 0, nonstaff_denials: 0, staff_data_denials: 0, authorized_controls: 0,
      staff_metadata_verified: false, staff_directory_ui: false, layout_widths: [], screenshots: 0,
    } });
    stage = "fictional_setup";
    await setup(states);
    browser = await chromium.launch({ headless: true });
    for (const state of states) {
      state.context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
      state.page = await state.context.newPage();
      state.page.setDefaultTimeout(60_000);
    }
    async function wave(action) {
      await Promise.all(states.map(async (state) => {
        if (state.failed) return;
        try { await action(state); }
        catch (error) {
          state.failed = true;
          Object.assign(state.summary, failure(error));
          console.log(JSON.stringify({ user: state.summary.user, stage: state.summary.stage, ...failure(error) }));
          await failureCapture(state, artifactPath);
        }
      }));
      assert.ok(states.every((state) => !state.failed), "A synchronized browser wave failed");
    }
    stage = "create_eight_requests";
    await wave(createTicket);
    stage = "staff_lifecycle";
    await staffWork(states);
    stage = "requester_resume";
    await wave(requesterResume);
    stage = "eight_usage_views";
    await wave(usage);
    stage = "privacy";
    await privacy(states);
    stage = "staff_directory";
    await staffDirectory(states);
    stage = "responsive_views";
    await wave((state) => layouts(state, artifactPath));
    for (const state of states) { state.summary.passed = true; mark(state, "complete"); }
  } catch (error) {
    fatal = { stage, ...failure(error) };
    console.log(JSON.stringify(fatal));
    for (const state of states) if (state.page) await failureCapture(state, artifactPath);
  } finally {
    for (const state of states) if (state.context) { try { await state.context.close(); } catch {
      fatal ??= { stage: "browser_cleanup", error_type: "Error", error_code: "cleanup_failed" };
    } }
    if (browser) { try { await browser.close(); } catch {
      fatal ??= { stage: "browser_cleanup", error_type: "Error", error_code: "cleanup_failed" };
    } }
    const report = {
      file_use_case: "Records an eight-user fictional operations and support rehearsal.",
      responsibility: "Retains safe outcomes, private-access checks and rendered fictional views.",
      created_at: new Date().toISOString(), production_evidence: false,
      scope: "private-demo-fictional-operations", total: 8,
      passed: states.filter((state) => state.summary.passed).length,
      elapsed_ms: Math.round(performance.now() - started), ...(fatal ? { fatal_error: fatal } : {}),
      limitations: [
        "Short functional rehearsal, not sustained load, production security or churn prediction evidence.",
        "Staff grant is provided explicitly by the operator; the checker never grants privileges.",
        "Staff audit persistence is checked by separate database tests; no staff-audit API is exposed.",
      ], results: states.map((state) => state.summary),
    };
    try { await output.writeFile(JSON.stringify(report, null, 2) + "\n"); }
    finally { await output.close(); }
    console.log(JSON.stringify(report));
    process.exitCode = !fatal && report.passed === 8 ? 0 : 1;
  }
}

await main().catch(() => {
  console.error("Operations rehearsal could not initialize; no private details are logged.");
  process.exitCode = 1;
});
