/* Use case: Verifies resumable conversation work against real services and the worker.
What it does: Exercises recorded actions, explicit cancellation races, network recovery and presentation-only evidence views. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

function session() {
  return execFileSync(
    "python3",
    [
      "-m",
      "execplus.manage",
      "provision-user",
      "--email",
      `jobs-${randomUUID()}@example.test`,
    ],
    { cwd: "../..", encoding: "utf8" },
  ).trim();
}

async function signIn(page: Page, token: string) {
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
}

async function upload(page: Page, filename = "activity-example.csv") {
  if (
    await page.getByRole("navigation", { name: "Workspace navigation" }).count()
  )
    await page
      .getByRole("navigation", { name: "Workspace navigation" })
      .getByRole("button", { name: "Data library", exact: true })
      .click();
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: filename,
    mimeType: "text/csv",
    buffer: Buffer.from("branch,amount\nNorth,0.10\nSouth,0.20\nNorth,0.30\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(page.locator(".discoveryValue")).toHaveText([
    "0.1",
    "0.3",
    "0.2",
  ]);
}

function submitResponse(page: Page) {
  return page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/threads\/[^/]+\/jobs$/.test(new URL(response.url()).pathname),
  );
}

test("durable conversation shows actual actions and Expert changes only the evidence view", async ({
  page,
}) => {
  const token = session();
  await signIn(page, token);
  await upload(page);
  let computations = 0;
  page.on("request", (request) => {
    if (/\/(discovery|ask|query|jobs)$/.test(new URL(request.url()).pathname))
      computations += 1;
  });
  const submitted = submitResponse(page);
  await page
    .getByRole("button", { name: "Help me understand my data", exact: true })
    .click();
  const response = await submitted;
  expect(response.status()).toBe(202);
  const job = await response.json();
  const chat = page.getByRole("region", {
    name: "Ask a question",
    exact: true,
  });
  await expect(chat.locator(".datasetGuidance")).toContainText(
    "3 rows and 2 columns",
  );
  const count = computations;
  await page.getByRole("radio", { name: "Expert", exact: true }).check();
  await expect(
    chat.getByText("Request completed", { exact: true }),
  ).toBeVisible();
  await expect(
    chat.getByText("Checking the selected source", { exact: true }).first(),
  ).toBeVisible();
  await expect(chat).not.toContainText("Running a read-only calculation");
  await expect(chat).not.toContainText("Finding supporting document passages");
  await expect(chat).not.toContainText("Planning and checking your request");
  await expect(chat.locator(".verifiedBadge")).toHaveCount(0);
  await expect(page.locator(".discoveryValue")).toHaveText([
    "0.1",
    "0.3",
    "0.2",
  ]);
  expect(computations).toBe(count);
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    await chat.screenshot({
      path: `../../data/vps-private/jobs-evidence-${width}.png`,
    });
  }
  const eventsResponse = await page.request.get(
    `http://127.0.0.1:8001/workspaces/${job.workspace_id}/jobs/${job.id}/events?after=0`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  expect(eventsResponse.ok()).toBe(true);
  const events = await eventsResponse.json();
  expect(
    events.events.some(
      (event: { stage: string }) => event.stage === "checking_source",
    ),
  ).toBe(true);
  await page.getByRole("radio", { name: "Simple", exact: true }).check();
  expect(computations).toBe(count);
  await page.getByRole("radio", { name: "Expert", exact: true }).check();
  await page
    .getByText("Source capabilities & recorded quality", { exact: false })
    .click();
  const sourceDetails = page.locator(".sourceDetails");
  await expect(sourceDetails).toContainText("dataset snapshot");
  await expect(sourceDetails).toContainText("Supported operations:");
  await expect(sourceDetails).toContainText("Profile version:");
  await sourceDetails
    .getByText("Version & provenance", { exact: true })
    .first()
    .click();
  await expect(sourceDetails).toContainText("Checksum (");
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
  }
  expect(computations).toBe(count);
  await page.reload();
  await signIn(page, token);
  await page.getByText("Private conversation history", { exact: true }).click();
  await page.getByLabel("Saved conversation").selectOption({ index: 1 });
  await page
    .getByRole("button", { name: "Open conversation", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Load saved answer", exact: true })
    .click();
  await expect(chat.locator(".datasetGuidance")).toContainText(
    "3 rows and 2 columns",
  );
  await page.getByRole("radio", { name: "Expert", exact: true }).check();
  await expect(
    chat.getByText("Request completed", { exact: true }),
  ).toBeVisible();
  await expect(chat.locator(".activityIdentifiers")).toContainText(job.id);
});

test("a lost activity connection resumes the same durable request without another submission", async ({
  page,
}) => {
  await signIn(page, session());
  await upload(page);
  let submittedCount = 0;
  let interrupted = false;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      /\/threads\/[^/]+\/jobs$/.test(new URL(request.url()).pathname)
    )
      submittedCount += 1;
  });
  await page.route(/\/jobs\/[^/?]+$/, async (route) => {
    if (!interrupted && route.request().method() === "GET") {
      interrupted = true;
      await route.abort("connectionfailed");
    } else await route.continue();
  });
  await page
    .getByRole("button", { name: "Help me understand my data", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Resume activity", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Resume activity", exact: true })
    .click();
  await expect(page.locator(".datasetGuidance")).toContainText(
    "3 rows and 2 columns",
  );
  expect(submittedCount).toBe(1);
  expect(interrupted).toBe(true);
  await expect(page.locator(".conversationTurn")).toHaveCount(1);
});

test("explicit cancellation reports the actual terminal outcome and remains usable on a narrow screen", async ({
  page,
}) => {
  const token = session();
  await signIn(page, token);
  await upload(page);
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  let paused = false;
  await page.route(/\/jobs\/[^/?]+$/, async (route) => {
    if (!paused && route.request().method() === "GET") {
      paused = true;
      await held;
    }
    await route.continue();
  });
  try {
    const submitted = submitResponse(page);
    await page
      .getByRole("button", { name: "Help me understand my data", exact: true })
      .click();
    const job = await (await submitted).json();
    await expect(
      page.getByRole("button", { name: "Cancel request", exact: true }),
    ).toBeVisible();
    await page.setViewportSize({ width: 320, height: 844 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect(page.locator(".activityIndicator")).toHaveCSS(
      "animation-name",
      "none",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    for (const width of [320, 390, 1280]) {
      await page.setViewportSize({ width, height: 844 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBe(true);
      await page.locator(".askPanel > .conversationActivity").screenshot({
        path: `../../data/vps-private/jobs-active-${width}.png`,
      });
    }
    await page.setViewportSize({ width: 320, height: 844 });
    const cancelled = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().endsWith(`/jobs/${job.id}/cancel`),
    );
    await page
      .getByRole("button", { name: "Cancel request", exact: true })
      .click();
    expect((await cancelled).ok()).toBe(true);
    release();
    await expect(page.locator(".conversationTurn")).toHaveCount(1);
    await page.getByRole("radio", { name: "Expert", exact: true }).check();
    const statusResponse = await page.request.get(
      `http://127.0.0.1:8001/workspaces/${job.workspace_id}/jobs/${job.id}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    const finalJob = await statusResponse.json();
    expect(["cancelled", "succeeded"]).toContain(finalJob.status);
    await expect(
      page.getByText(
        finalJob.status === "cancelled"
          ? "Request cancelled"
          : "Request completed",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Cancel request", exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "New conversation", exact: true }),
    ).toBeEnabled();
  } finally {
    release();
    await page.unroute(/\/jobs\/[^/?]+$/);
  }
});

test("switching files detaches old activity without cancelling or overwriting the new conversation", async ({
  page,
}) => {
  const token = session();
  await signIn(page, token);
  await upload(page, "first-activity.csv");
  const first = await page.getByLabel("Dataset", { exact: true }).inputValue();
  await upload(page, "second-activity.csv");
  const second = await page.getByLabel("Dataset", { exact: true }).inputValue();
  await page.getByLabel("Dataset", { exact: true }).selectOption(first);
  await expect(page.locator(".chatSource")).toContainText("first-activity.csv");
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  let paused = false;
  let cancelRequests = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      /\/jobs\/[^/]+\/cancel$/.test(new URL(request.url()).pathname)
    )
      cancelRequests += 1;
  });
  await page.route(/\/jobs\/[^/?]+$/, async (route) => {
    if (!paused && route.request().method() === "GET") {
      paused = true;
      await held;
    }
    await route.continue().catch(() => {});
  });
  try {
    const submitted = submitResponse(page);
    await page
      .getByRole("button", { name: "Help me understand my data", exact: true })
      .click();
    const job = await (await submitted).json();
    await expect(
      page.getByRole("button", { name: "Cancel request", exact: true }),
    ).toBeVisible();
    const detached = page.waitForEvent("requestfailed", (request) =>
      new URL(request.url()).pathname.endsWith(`/jobs/${job.id}`),
    );
    await page.getByLabel("Dataset", { exact: true }).selectOption(second);
    await detached;
    release();
    await expect(page.locator(".chatSource")).toContainText(
      "second-activity.csv",
    );
    await expect(page.locator(".conversationTurn")).toHaveCount(0);
    await expect(
      page.getByRole("region", {
        name: "Recorded request activity",
        exact: true,
      }),
    ).toHaveCount(0);
    await expect
      .poll(async () => {
        const response = await page.request.get(
          `http://127.0.0.1:8001/workspaces/${job.workspace_id}/jobs/${job.id}`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        return (await response.json()).status;
      })
      .toBe("succeeded");
    expect(cancelRequests).toBe(0);
    await expect(page.locator(".conversationTurn")).toHaveCount(0);
  } finally {
    release();
    await page.unroute(/\/jobs\/[^/?]+$/);
  }
});
