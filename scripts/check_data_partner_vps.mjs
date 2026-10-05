/* Use case: Rehearses the private data partner with eight users and attributed public data.
What it does: Checks discoveries, receipt replay, concurrent durable conversations, owner privacy and responsive layout without exposing sessions or source rows. */

import assert from "node:assert/strict";
import { open, readFile } from "node:fs/promises";
import { chromium, expect as baseExpect } from "@playwright/test";

const expect = baseExpect.configure({ timeout: 120_000 });
const [sessionsPath, targetPath, outputPath] = process.argv.slice(2);
if (!sessionsPath || !targetPath || !outputPath)
  throw new Error(
    "Pass private sessions, public evaluation target and fresh output paths",
  );
async function privateJson(path) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch {
    throw new Error("A private input file could not be read.");
  }
}
const sessions = await privateJson(sessionsPath);
const target = await privateJson(targetPath);
assert.equal(sessions.accounts.length, 8);
assert.equal(
  new Set(sessions.accounts.map((account) => account.email)).size,
  8,
);
assert.equal(
  new Set(sessions.accounts.map((account) => account.token)).size,
  8,
);
assert.ok(target.workspace_id && target.bank && target.retail);
assert.ok(target.bank.total_balance !== undefined);
assert.ok(target.bank.retired_balance !== undefined);
assert.ok(Number.isSafeInteger(target.bank.retired_count));

const canonical = (value) =>
  String(value).replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1");
assert.equal(canonical(target.bank.total_balance), "6431836");
const output = await open(outputPath, "wx", 0o600);
const actionStages = new Set([
  "queued",
  "authorizing",
  "checking_source",
  "planning",
  "validating_plan",
  "executing_query",
  "retrieving_documents",
  "verifying_evidence",
  "finished",
]);
let readyUsers = 0;
let preflightFailed = false;
let releaseTotals;
const totalsReady = new Promise((resolve) => {
  releaseTotals = resolve;
});
const totalRuns = [];
let browser;
let results = [];
let fatalError;
try {
  browser = await chromium.launch({ headless: true });
  results = await Promise.all(
    sessions.accounts.map(async (account, index) => {
      let stage = "sign_in";
      const started = performance.now();
      const context = await browser.newContext({
        viewport: { width: 1440, height: 1000 },
      });
      const page = await context.newPage();
      page.setDefaultTimeout(120_000);
      let discoveryCount = 0;
      let liveTurns = 0;
      let completedJobs = 0;
      let recordedEvents = 0;
      let privacyChecks = 0;
      let reachedTotals = false;
      async function api(path, options = {}) {
        const response = await fetch(`http://localhost:18401${path}`, {
          signal: AbortSignal.timeout(120_000),
          ...options,
          headers: {
            Authorization: `Bearer ${account.token}`,
            "Content-Type": "application/json",
            ...options.headers,
          },
        });
        assert.ok(response.ok, `API status ${response.status}`);
        return response.json();
      }
      async function ask(
        question,
        { query = false, totalWave = false, checkPrivacy = false } = {},
      ) {
        await page.getByLabel("Your question").fill(question);
        const response = page
          .waitForResponse(
            (item) =>
              /\/threads\/[^/]+\/jobs$/.test(new URL(item.url()).pathname) &&
              item.request().method() === "POST",
            { timeout: 180_000 },
          )
          .catch(() => null);
        const resultResponse = page
          .waitForResponse(
            (item) =>
              /\/jobs\/[^/]+\/result$/.test(new URL(item.url()).pathname) &&
              item.request().method() === "GET" &&
              item.ok(),
            { timeout: 240_000 },
          )
          .catch(() => null);
        await page.getByRole("button", { name: "Ask", exact: true }).click();
        const received = await response;
        assert.ok(
          received,
          "The browser did not receive a job submission response",
        );
        assert.equal(received.status(), 202);
        const submitted = await received.json();
        assert.equal(submitted.workspace_id, target.workspace_id);
        const jobPath = `/workspaces/${target.workspace_id}/jobs/${submitted.id}`;
        if (checkPrivacy) {
          const other =
            sessions.accounts[(index + 1) % sessions.accounts.length];
          for (const [suffix, method] of [
            ["", "GET"],
            ["/events?after=0", "GET"],
            ["/result", "GET"],
            ["/cancel", "POST"],
          ]) {
            const denied = await fetch(
              `http://localhost:18401${jobPath}${suffix}`,
              {
                method,
                headers: { Authorization: `Bearer ${other.token}` },
                signal: AbortSignal.timeout(30_000),
              },
            );
            assert.equal(
              denied.status,
              404,
              "Other workspace members must not see or cancel a private job",
            );
            privacyChecks += 1;
          }
        }
        const resolved = await resultResponse;
        assert.ok(
          resolved,
          "The browser did not receive a terminal job result",
        );
        assert.equal(new URL(resolved.url()).pathname, `${jobPath}/result`);
        const result = await resolved.json();
        const job = await api(jobPath);
        assert.equal(job.status, "succeeded");
        assert.equal(job.cancel_requested, false);
        assert.equal(job.turn_id, result.turn.id);
        assert.equal(result.turn.job_id, submitted.id);
        assert.equal(result.turn.status, "complete");
        const activity = await api(`${jobPath}/events?after=0`);
        assert.ok(activity.events.length >= 6);
        let previousSequence = 0;
        const starts = new Set();
        for (const event of activity.events) {
          assert.deepEqual(Object.keys(event).sort(), [
            "created_at",
            "sequence",
            "stage",
            "status",
          ]);
          assert.ok(
            Number.isSafeInteger(event.sequence) &&
              event.sequence > previousSequence,
          );
          assert.ok(actionStages.has(event.stage));
          assert.ok(
            ["started", "completed", "failed", "cancelled"].includes(
              event.status,
            ),
          );
          assert.ok(Number.isFinite(Date.parse(event.created_at)));
          if (event.status === "started") starts.add(event.stage);
          if (
            event.status === "completed" &&
            !["queued", "finished"].includes(event.stage)
          )
            assert.ok(
              starts.has(event.stage),
              "A completed action needs its recorded start",
            );
          previousSequence = event.sequence;
        }
        assert.equal(activity.next_sequence, previousSequence);
        assert.equal(activity.events.at(-1).stage, "finished");
        assert.equal(activity.events.at(-1).status, "completed");
        assert.ok(
          starts.has("checking_source") && starts.has("verifying_evidence"),
        );
        if (query) {
          assert.ok(
            starts.has("planning") &&
              starts.has("validating_plan") &&
              starts.has("executing_query"),
          );
        } else {
          assert.ok(
            !starts.has("executing_query") &&
              !starts.has("retrieving_documents"),
          );
        }
        completedJobs += 1;
        recordedEvents += activity.events.length;
        if (totalWave)
          totalRuns.push({
            user: index + 1,
            created_at: job.created_at,
            completed_at: job.updated_at,
          });
        const displayed = page.locator(".conversationTurn").last();
        await expect(displayed.locator(".userMessage p")).toHaveText(question);
        if (result.answer.value !== undefined) {
          await expect(displayed.locator(".kpiValue")).toHaveText(
            canonical(result.answer.value),
          );
          await expect(displayed.locator(".verifiedBadge")).toBeVisible();
        }
        return result.answer;
      }
      async function select(dataset) {
        const datasetSelect = page.getByLabel("Dataset", { exact: true });
        await datasetSelect.selectOption(dataset.dataset_id);
        await expect(datasetSelect).toHaveValue(dataset.dataset_id);
        const datasetName = await datasetSelect
          .locator("option:checked")
          .textContent();
        const uploadSelect = page.getByLabel("Profile upload");
        await uploadSelect.selectOption(dataset.upload_id);
        await expect(uploadSelect).toHaveValue(dataset.upload_id);
        const reading = page.getByRole("region", {
          name: "First reading of your data",
        });
        await expect(reading.locator(".findingEvidence")).toHaveCount(7);
        await expect(reading.locator(".discoveryMetricGroup")).toHaveCount(2);
        await expect(
          reading.locator(".discoveryFinding.distribution"),
        ).toHaveCount(1);
        await expect(reading).toContainText(datasetName);
        await expect(reading.getByLabel("File structure")).toContainText(
          (
            dataset.rows ?? (dataset === target.bank ? 4521 : 10000)
          ).toLocaleString(),
        );
        return reading;
      }
      try {
        await page.goto("http://localhost:18400/workspace");
        await page.getByLabel("Session token").fill(account.token);
        await page
          .getByRole("button", { name: "Sign in", exact: true })
          .click();
        await expect(
          page.getByText(`Signed in as ${account.email}`),
        ).toBeVisible();
        await page
          .getByLabel("Current workspace")
          .selectOption(target.workspace_id);
        stage = "automatic_bank_reading";
        const reading = await select(target.bank);
        await expect(reading).toContainText("balance");
        await expect(page.getByLabel("Your question")).toBeVisible();
        await reading.locator(".findingEvidence > summary").first().click();
        await expect(
          reading.locator(".findingEvidence[open]").first(),
        ).toContainText("Query receipt:");
        stage = "receipt_replay";
        const root = `/workspaces/${target.workspace_id}/datasets/${target.bank.dataset_id}/uploads/${target.bank.upload_id}`;
        const brief = await api(`${root}/discovery`);
        assert.equal(brief.version, "discovery-v1");
        assert.equal(brief.shape.rows, target.bank.rows ?? 4521);
        assert.equal(
          brief.findings.length,
          7,
          "All seven bank findings must complete",
        );
        for (const finding of brief.findings) {
          const replay = await api(
            `/workspaces/${target.workspace_id}/queries/${finding.query.lineage.query_id}/replay`,
            { method: "POST" },
          );
          assert.deepEqual(replay.rows, finding.query.rows);
          assert.equal(replay.records_analyzed, brief.shape.rows);
          discoveryCount += 1;
        }
        stage = "concurrent_total_barrier";
        readyUsers += 1;
        if (readyUsers === sessions.accounts.length) releaseTotals();
        await totalsReady;
        assert.equal(
          preflightFailed,
          false,
          "All eight users must reach the total-query wave",
        );
        reachedTotals = true;
        stage = "live_exact_total";
        const total = await ask("What is the total balance?", {
          query: true,
          totalWave: true,
          checkPrivacy: true,
        });
        assert.equal(
          canonical(total.value),
          canonical(target.bank.total_balance),
        );
        assert.ok(total.lineage.query_id);
        liveTurns += 1;
        stage = "quality_conversation";
        const quality = await ask("Are there any data quality issues?");
        assert.equal(quality.kind, "overview");
        assert.equal(quality.guidance.focus, "quality");
        assert.ok(quality.sources.length);
        assert.match(quality.model_route, /^deterministic:/);
        await expect(page.locator(".datasetGuidance").last()).toBeVisible();
        assert.equal(
          await page
            .locator(".conversationTurn")
            .last()
            .getByText("Verified", { exact: true })
            .count(),
          0,
        );
        if (index === 0) {
          stage = "live_filtered_records";
          const records = await ask(
            "Show all records where job equals retired",
            { query: true },
          );
          assert.equal(records.matched_records, target.bank.retired_count);
          const job = records.columns.indexOf("job");
          assert.ok(job >= 0);
          assert.ok(records.rows.length > 0);
          assert.ok(records.rows.every((row) => row[job] === "retired"));
          liveTurns += 1;
          stage = "live_filtered_followup";
          const followup = await ask("What is their total balance?", {
            query: true,
          });
          assert.equal(
            canonical(followup.value),
            canonical(target.bank.retired_balance),
          );
          assert.ok(followup.lineage.filters.length);
          liveTurns += 1;
          stage = "automatic_retail_reading";
          const retail = await select(target.retail);
          await expect(retail).toContainText("Quantity");
          await expect(retail).not.toContainText("Minimum CustomerID");
        }
        stage = "desktop_layout";
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth + 1,
          ),
          true,
        );
        stage = "mobile_layout";
        await page.emulateMedia({ reducedMotion: "reduce" });
        for (const width of [320, 390]) {
          await page.setViewportSize({ width, height: 844 });
          await expect(page.getByLabel("Your question")).toBeVisible();
          assert.equal(
            await page.evaluate(
              () => document.documentElement.scrollWidth <= innerWidth + 1,
            ),
            true,
          );
        }
        return {
          user: index + 1,
          passed: true,
          stage: "complete",
          receipts_replayed: discoveryCount,
          live_model_turns: liveTurns,
          completed_jobs: completedJobs,
          recorded_events: recordedEvents,
          private_job_checks: privacyChecks,
          elapsed_ms: Math.round(performance.now() - started),
        };
      } catch (error) {
        if (!reachedTotals) {
          preflightFailed = true;
          releaseTotals();
        }
        return {
          user: index + 1,
          passed: false,
          stage,
          error: error?.name || "Error",
          rendered_findings: await page.locator(".findingEvidence").count(),
          rendered_metric_groups: await page
            .locator(".discoveryMetricGroup")
            .count(),
          rendered_distributions: await page
            .locator(".discoveryFinding.distribution")
            .count(),
          receipts_replayed: discoveryCount,
          live_model_turns: liveTurns,
          completed_jobs: completedJobs,
          recorded_events: recordedEvents,
          private_job_checks: privacyChecks,
          elapsed_ms: Math.round(performance.now() - started),
        };
      } finally {
        await context.close();
      }
    }),
  );
} catch (error) {
  fatalError = error?.name || "Error";
} finally {
  if (browser) {
    try {
      await browser.close();
    } catch (error) {
      fatalError = error?.name || "Error";
    }
  }
}
const totalIntervals = totalRuns
  .flatMap((run) => [
    { time: Date.parse(run.created_at), change: 1 },
    { time: Date.parse(run.completed_at), change: -1 },
  ])
  .sort((left, right) => left.time - right.time || left.change - right.change);
let pendingTotals = 0;
let peakPendingTotals = 0;
for (const entry of totalIntervals) {
  pendingTotals += entry.change;
  peakPendingTotals = Math.max(peakPendingTotals, pendingTotals);
}
const report = {
  scope: "private-demo-public-real-data",
  production_evidence: false,
  created_at: new Date().toISOString(),
  concurrent_browsers: 8,
  passed: results.filter((result) => result.passed).length,
  total: sessions.accounts.length,
  total_query_wave: {
    measurement: "Overlap among successful total jobs, including queue time.",
    ready_users: readyUsers,
    successful_jobs: totalRuns.length,
    peak_pending_jobs: peakPendingTotals,
    jobs: totalRuns,
  },
  ...(fatalError ? { fatal_error: fatalError } : {}),
  limitations: [
    "Short functional rehearsal, not a sustained-load or production acceptance benchmark.",
  ],
  results,
};
try {
  await output.writeFile(JSON.stringify(report, null, 2) + "\n");
} finally {
  await output.close();
}
console.log(JSON.stringify(report));
process.exitCode = !fatalError && report.passed === report.total ? 0 : 1;
