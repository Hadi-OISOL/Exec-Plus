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

async function signIn(page: Page, session: string) {
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(session);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
}

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
  await expect(page.getByRole("status")).toContainText("Invitation created");
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page
    .getByRole("button", { name: `Copy link for ${memberEmail}` })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Invitation link copied",
  );
  const invitation = await page.evaluate(() => navigator.clipboard.readText());
  await page.getByLabel("New dataset name").fill("Monthly sales");
  await page
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Dataset created");
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "sales.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("item,amount\nwidget,12\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("uploaded successfully");
  await expect(
    page.getByRole("cell", { name: "Validated and stored" }),
  ).toBeVisible();
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
  await expect(page.getByRole("status")).toContainText("Invitation accepted");
  await expect(
    page.getByRole("button", { name: "Create invitation", exact: true }),
  ).toHaveCount(0);
  await page
    .getByLabel("Dataset", { exact: true })
    .selectOption({ label: "Monthly sales" });
  await expect(
    page.getByRole("cell", { name: "sales.csv", exact: true }),
  ).toBeVisible();
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
    page.getByRole("region", { name: "Getting started" }),
  ).toContainText("Workspace ready");
  await page
    .getByRole("button", { name: "Try sales sample", exact: true })
    .click();
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
  await page.getByLabel("New dataset name").fill("My first upload");
  await page
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  await page
    .getByLabel("CSV or Excel file")
    .setInputFiles({
      name: "my-data.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("date,amount\n2026-01-01,12.50\n2026-01-02,15.25\n"),
    });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await expect(profile).toContainText("100.00/100");
  await expect(profile).toContainText("decimal / metric");
  await expect(
    page.getByRole("region", { name: "Getting started" }),
  ).toContainText("File uploaded");
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
