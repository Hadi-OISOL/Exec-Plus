/* Use case: Verifies internal administration, private support and aggregate adoption reporting.
What it does: Exercises real requester/staff rights, optimistic support updates, cohort maturity and deferred workspace requests. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page, APIRequestContext } from "@playwright/test";

const api = "http://127.0.0.1:8001";
test.use({ actionTimeout: 20_000 });
function account(role?: "admin" | "support") {
  const email = `operations-${randomUUID()}@example.test`;
  const token = execFileSync(
    "python3",
    ["-m", "execplus.manage", "provision-user", "--email", email],
    { cwd: "../..", encoding: "utf8" },
  ).trim();
  if (role)
    execFileSync(
      "python3",
      [
        "-m",
        "execplus.manage",
        "grant-staff",
        "--email",
        email,
        "--role",
        role,
      ],
      { cwd: "../..", encoding: "utf8" },
    );
  return { email, token, headers: { Authorization: `Bearer ${token}` } };
}
async function workspace(
  request: APIRequestContext,
  owner: ReturnType<typeof account>,
  name: string,
) {
  const response = await request.post(`${api}/workspaces`, {
    headers: owner.headers,
    data: { name, seat_limit: 3 },
  });
  expect(response.ok()).toBe(true);
  return response.json();
}
async function join(
  request: APIRequestContext,
  wid: string,
  owner: ReturnType<typeof account>,
  member: ReturnType<typeof account>,
) {
  const invitation = await request.post(
    `${api}/workspaces/${wid}/invitations`,
    { headers: owner.headers, data: { email: member.email, role: "member" } },
  );
  expect(invitation.ok()).toBe(true);
  const accepted = await request.post(
    `${api}/workspaces/${wid}/invitations/${(await invitation.json()).id}/accept`,
    { headers: member.headers },
  );
  expect(accepted.ok()).toBe(true);
}
async function privateResourceDenied(
  request: APIRequestContext,
  path: string,
  blocked: ReturnType<typeof account>,
  allowed: ReturnType<typeof account>,
) {
  const control = await request.get(`${api}${path}`, {
    headers: allowed.headers,
  });
  expect(control.status()).toBe(200);
  expect(control.headers()["content-type"]).toContain("application/json");
  const response = await request.get(`${api}${path}`, {
    headers: blocked.headers,
  });
  expect(response.status()).toBe(404);
  expect(await response.json()).toEqual({
    error: {
      code: "not_found",
      message: "The requested resource is unavailable.",
    },
  });
}
async function signIn(page: Page, token: string) {
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
}
async function navigate(page: Page, name: string) {
  await page
    .getByRole("navigation", { name: "Workspace navigation" })
    .getByRole("button", { name, exact: true })
    .click();
}
async function layout(page: Page, artifact: string) {
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `../../data/operations/${artifact}-${width}.png`,
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1280, height: 900 });
}

test("private support spans requester and staff with triage, conflict recovery, resolution and reopening", async ({
  page,
  browser,
}) => {
  test.setTimeout(150_000);
  const owner = account();
  const member = account();
  const staff = account("support");
  const space = await workspace(
    page.request,
    owner,
    `Support privacy ${randomUUID()}`,
  );
  await join(page.request, space.id, owner, member);
  await signIn(page, member.token);
  await expect(
    page.getByRole("button", { name: "Admin console", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Usage & retention", exact: true }),
  ).toHaveCount(0);
  await navigate(page, "Support");
  const own = page.getByRole("region", {
    name: "Your support requests",
    exact: true,
  });
  await own.getByText("Open a support request", { exact: true }).click();
  await own.getByLabel("Request subject").fill("Need help with an upload");
  await own
    .getByLabel("What happened?")
    .fill("The fictional sample upload needs a clearer explanation.");
  const createdResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/support-tickets"),
  );
  await own
    .getByRole("button", { name: "Submit support request", exact: true })
    .click();
  const created = await createdResponse;
  expect(created.status()).toBe(201);
  const ticket = (await created.json()).ticket;
  await expect(
    own.getByRole("article", { name: "Selected support request" }),
  ).toContainText(ticket.subject);
  await privateResourceDenied(
    page.request,
    `/workspaces/${space.id}/support-tickets/${ticket.id}`,
    owner,
    member,
  );
  expect(
    (
      await page.request.get(`${api}/workspaces/${space.id}/support-tickets`, {
        headers: owner.headers,
      })
    ).ok(),
  ).toBe(true);
  const ownerList = await page.request.get(
    `${api}/workspaces/${space.id}/support-tickets`,
    { headers: owner.headers },
  );
  expect((await ownerList.json()).tickets).toHaveLength(0);

  const staffPage = await browser.newPage();
  try {
    await signIn(staffPage, staff.token);
    await navigate(staffPage, "Admin console");
    await expect(
      staffPage.getByRole("button", {
        name: "Workspaces & health",
        exact: true,
      }),
    ).toHaveCount(0);
    const queue = staffPage.getByRole("region", {
      name: "Internal support queue",
      exact: true,
    });
    await queue.getByLabel("Search requests").fill(ticket.id);
    await queue
      .getByRole("button", { name: "Filter requests", exact: true })
      .click();
    await queue
      .locator(".supportRequestList")
      .getByRole("button")
      .filter({ hasText: ticket.subject })
      .click();
    const selected = queue.getByRole("article", {
      name: "Selected support request",
    });
    await selected
      .getByRole("combobox", { name: "Update status", exact: true })
      .selectOption("triaged");
    await selected
      .getByRole("combobox", { name: "Update priority", exact: true })
      .selectOption("high");
    const me = await staffPage.request.get(`${api}/auth/me`, {
      headers: staff.headers,
    });
    await selected
      .getByRole("combobox", { name: "Assign support staff", exact: true })
      .selectOption((await me.json()).id);
    await selected
      .getByLabel("Public triage note")
      .fill("We are reviewing the upload steps.");
    await selected
      .getByRole("button", { name: "Save triage", exact: true })
      .click();
    await expect(selected).toContainText("We are reviewing the upload steps.");
    await privateResourceDenied(
      staffPage.request,
      `/workspaces/${space.id}/datasets`,
      staff,
      owner,
    );
    await own
      .getByLabel("Reply to this request")
      .fill("Here is a second explanation.");
    await own.getByRole("button", { name: "Send reply", exact: true }).click();
    await expect(own.getByRole("alert")).toBeVisible();
    await own
      .getByRole("button", { name: "Reload selected request", exact: true })
      .click();
    await expect(own).toContainText("We are reviewing the upload steps.");
    await own
      .getByLabel("Reply to this request")
      .fill("Thank you, please explain the expected format.");
    await own.getByRole("button", { name: "Send reply", exact: true }).click();
    await expect(own.locator(".supportTimeline")).toContainText(
      "Thank you, please explain the expected format.",
    );
    await queue
      .getByRole("button", { name: "Refresh requests", exact: true })
      .click();
    await queue
      .locator(".supportRequestList")
      .getByRole("button")
      .filter({ hasText: ticket.subject })
      .click();
    await selected
      .getByRole("combobox", { name: "Update status", exact: true })
      .selectOption("escalated");
    await selected
      .getByLabel("Public triage note")
      .fill("Escalated for product review.");
    await selected
      .getByRole("button", { name: "Save triage", exact: true })
      .click();
    await expect(selected.locator(".operationsBadge")).toHaveText("escalated");
    await selected
      .getByLabel("Reply to this request")
      .fill("CSV and single-sheet XLSX files are supported.");
    await selected
      .getByRole("button", { name: "Send reply", exact: true })
      .click();
    await expect(selected.locator(".supportTimeline")).toContainText(
      "CSV and single-sheet XLSX files are supported.",
    );
    await selected
      .getByRole("combobox", { name: "Update status", exact: true })
      .selectOption("resolved");
    await selected
      .getByLabel("Public triage note")
      .fill("The format guidance has been provided.");
    await selected
      .getByRole("button", { name: "Save triage", exact: true })
      .click();
    await expect(
      selected.getByRole("button", { name: "Reopen request", exact: true }),
    ).toBeVisible();
    await layout(staffPage, "support-staff");
    await own
      .getByRole("button", { name: "Refresh requests", exact: true })
      .click();
    await own
      .locator(".supportRequestList")
      .getByRole("button")
      .filter({ hasText: ticket.subject })
      .click();
    await own
      .getByLabel("Why reopen? (optional)")
      .fill("I have a follow-up about formatting.");
    await own
      .getByRole("button", { name: "Reopen request", exact: true })
      .click();
    await expect(own.locator(".supportTimeline")).toContainText(
      "I have a follow-up about formatting.",
    );
    await expect(own.getByLabel("Reply to this request")).toBeVisible();
    await layout(page, "support-requester");
    const removal = await page.request.delete(
      `${api}/workspaces/${space.id}/members/${ticket.requester_id}`,
      { headers: owner.headers },
    );
    expect(removal.status()).toBe(204);
    await own
      .getByLabel("Reply to this request")
      .fill("This must not be submitted after membership ends.");
    await own.getByRole("button", { name: "Send reply", exact: true }).click();
    await expect(own.getByRole("alert")).toContainText("unavailable");
    await expect(
      own.getByRole("article", { name: "Selected support request" }),
    ).toHaveCount(0);
    await expect(own.locator(".supportRequestList > button")).toHaveCount(0);
  } finally {
    await staffPage.close();
  }
});

test("platform admin sees operational metadata without membership and revocation blocks further access", async ({
  page,
}) => {
  const owner = account();
  const admin = account("admin");
  const space = await workspace(
    page.request,
    owner,
    `Admin scope ${randomUUID()}`,
  );
  await signIn(page, admin.token);
  await navigate(page, "Admin console");
  const directory = page.getByRole("region", {
    name: "Admin workspace directory",
  });
  await directory.getByLabel("Find a workspace").fill(space.id);
  await directory
    .getByRole("button", { name: "Search workspaces", exact: true })
    .click();
  await directory
    .getByRole("button", { name: space.name, exact: true })
    .click();
  const detail = page.getByRole("region", { name: "Admin workspace details" });
  await expect(detail).toContainText(owner.email);
  await expect(detail).toContainText("Billing unconfigured");
  await detail
    .getByRole("button", { name: "View product usage", exact: true })
    .click();
  await expect(
    detail.getByRole("region", { name: "Product usage and retention" }),
  ).toContainText("Never active current members");
  await privateResourceDenied(
    page.request,
    `/workspaces/${space.id}/datasets`,
    admin,
    owner,
  );
  await layout(page, "admin");
  execFileSync(
    "python3",
    ["-m", "execplus.manage", "revoke-staff", "--email", admin.email],
    { cwd: "../..", encoding: "utf8" },
  );
  await directory
    .getByRole("button", { name: space.name, exact: true })
    .click();
  await expect(directory.getByRole("alert")).toBeVisible();
  await expect(
    directory.getByRole("region", { name: "Admin workspace metadata" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("region", { name: "Admin workspace details" }),
  ).toHaveCount(0);
  const revokedAccess = await page.request.get(`${api}/admin/access`, {
    headers: admin.headers,
  });
  expect(revokedAccess.status()).toBe(200);
  expect(await revokedAccess.json()).toEqual({ role: null });
  const revokedDirectory = await page.request.get(`${api}/admin/workspaces`, {
    headers: admin.headers,
  });
  expect(revokedDirectory.status()).toBe(403);
  expect((await revokedDirectory.json()).error.code).toBe("staff_required");
  await page.reload();
  await signIn(page, admin.token);
  await expect(
    page.getByRole("button", { name: "Admin console", exact: true }),
  ).toHaveCount(0);
});

test("manager reports mature cohorts and optional admin data stays off the first-reading path", async ({
  page,
}) => {
  const owner = account();
  const space = await workspace(
    page.request,
    owner,
    `Usage scope ${randomUUID()}`,
  );
  let invitationReads = 0;
  let usageReads = 0;
  page.on("request", (request) => {
    if (
      request.method() === "GET" &&
      new URL(request.url()).pathname.endsWith("/invitations")
    )
      invitationReads += 1;
    if (new URL(request.url()).pathname.endsWith("/product-usage"))
      usageReads += 1;
  });
  await signIn(page, owner.token);
  await expect(
    page.getByRole("button", { name: "Admin console", exact: true }),
  ).toHaveCount(0);
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "usage-fixture.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("branch,amount\nNorth,0.10\nSouth,0.20\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(page.locator(".discoveryValue")).toHaveText([
    "0.1",
    "0.2",
    "0.15",
  ]);
  expect(invitationReads).toBe(0);
  expect(usageReads).toBe(0);
  const me = await page.request.get(`${api}/auth/me`, {
    headers: owner.headers,
  });
  const actorId = (await me.json()).id;
  execFileSync(
    "python3",
    [
      "-c",
      "from datetime import datetime,timedelta,timezone\nfrom uuid import UUID,uuid4\nfrom execplus.bootstrap import build_runtime\nfrom execplus.config import Settings\nfrom execplus.domain.ingestion import AuditEvent\nimport sys\nr=build_runtime(Settings())\nnow=datetime.now(timezone.utc)\nstart=(now-timedelta(days=now.weekday(),weeks=2)).replace(hour=12,minute=0,second=0,microsecond=0)\nwith r.service.uow() as repo: repo.add(AuditEvent(uuid4(),UUID(sys.argv[1]),UUID(sys.argv[2]),'study.opened','study',uuid4(),start))\nr.engine.dispose()",
      space.id,
      actorId,
    ],
    { cwd: "../..", encoding: "utf8" },
  );
  await navigate(page, "Usage & retention");
  const usage = page.getByRole("region", {
    name: "Product usage and retention",
  });
  await expect(
    usage.getByRole("region", { name: "Weekly retention cohorts" }),
  ).toContainText("100.00%");
  await expect(
    usage.getByRole("region", { name: "Weekly retention cohorts" }),
  ).toContainText("0.00%");
  await expect(
    usage.getByRole("region", { name: "Weekly retention cohorts" }),
  ).toContainText("Not mature");
  await expect(usage).toContainText("inactivity is not a prediction");
  await expect(usage).toContainText("UTC");
  const firstReportReads = usageReads;
  await usage
    .getByRole("combobox", { name: "Reporting window", exact: true })
    .selectOption("4");
  await expect(
    usage
      .getByRole("region", { name: "Weekly product activity" })
      .locator("tbody tr"),
  ).toHaveCount(4);
  await layout(page, "usage");
  await navigate(page, "Team & settings");
  await expect.poll(() => invitationReads).toBe(1);
  expect(usageReads).toBe(firstReportReads + 1);
});

test("an expired session clears workspace and staff metadata before another person signs in", async ({
  page,
}) => {
  const first = account("admin");
  const next = account();
  const space = await workspace(
    page.request,
    first,
    `Private previous workspace ${randomUUID()}`,
  );
  await signIn(page, first.token);
  await expect(
    page.getByRole("combobox", { name: "Current workspace", exact: true }),
  ).toHaveValue(space.id);
  const revoked = await page.request.post(`${api}/auth/logout`, {
    headers: first.headers,
  });
  expect(revoked.status()).toBe(204);
  await navigate(page, "Usage & retention");
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  let release: () => void = () => {};
  let received: () => void = () => {};
  let fulfilled: () => void = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  const responseReady = new Promise<void>((resolve) => {
    received = resolve;
  });
  const responseFulfilled = new Promise<void>((resolve) => {
    fulfilled = resolve;
  });
  await page.route(`${api}/workspaces`, async (route) => {
    const response = await route.fetch();
    received();
    await held;
    try {
      await route.fulfill({ response });
    } finally {
      fulfilled();
    }
  });
  try {
    await page.getByLabel("Session token").fill(next.token);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await responseReady;
    await expect(page.getByText(`Signed in as ${next.email}`)).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Selected data", exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Admin console", exact: true }),
    ).toHaveCount(0);
    await expect(page.getByText(space.name, { exact: true })).toHaveCount(0);
  } finally {
    release();
    await responseFulfilled;
    await page.unroute(`${api}/workspaces`);
  }
  await expect(
    page.getByRole("button", { name: "Add data", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "Upload file", exact: true }),
  ).toBeVisible();
});
