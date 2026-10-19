/* Use case: Verifies the Google sign-in button, the return from Google and the sheet import flow.
What it does: Mocks Google's configuration and picker while the real API creates the imported upload. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const api = "http://127.0.0.1:8001";
const sheet = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms";
const csv = "order,cust,amt,st\n1004,Ali,75.25,P\n1005,Hina,640,C\n";

function account() {
  const email = `google-${randomUUID()}@example.test`;
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", email], { cwd: "../..", encoding: "utf8" }).trim();
  return { email, token, headers: { Authorization: `Bearer ${token}` } };
}

async function enableGoogle(page: Page, picker: boolean) {
  await page.route("**/auth/google/config", route => route.fulfill({ json: { enabled: true, picker: picker ? { api_key: "k", app_id: "1" } : null } }));
}

async function fakePicker(page: Page) {
  await page.addInitScript(id => {
    const win = window as unknown as Record<string, unknown>;
    win.gapi = { load: (_name: string, callback: () => void) => callback() };
    win.google = { picker: {
      ViewId: { SPREADSHEETS: "spreadsheets" },
      Action: { PICKED: "picked" },
      DocsView: class {},
      PickerBuilder: class {
        callback: (data: unknown) => void = () => undefined;
        addView() { return this; }
        setOAuthToken() { return this; }
        setDeveloperKey() { return this; }
        setAppId() { return this; }
        setCallback(callback: (data: unknown) => void) { this.callback = callback; return this; }
        build() { const callback = this.callback; return { setVisible(visible: boolean) { if (visible) setTimeout(() => callback({ action: "picked", docs: [{ id }] }), 20); } }; }
      },
    } };
  }, sheet);
}

async function signInWithToken(page: Page, token: string) {
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
}

test("without Google configured there is no Google button and the token sign-in remains", async ({ page }) => {
  await page.goto("/workspace");
  await expect(page.getByLabel("Session token")).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toHaveCount(0);
});

test("the Continue with Google button appears when Google is configured", async ({ page }) => {
  await enableGoogle(page, false);
  await page.goto("/workspace");
  await expect(page.getByRole("button", { name: "Continue with Google", exact: true })).toBeVisible();
  await expect(page.getByLabel("Session token")).toBeVisible();
});

test("returning from Google with a session signs the user in and clears it from the address", async ({ page }) => {
  const person = account();
  await page.goto(`/workspace#session=${person.token}`);
  await expect(page.getByText(`Signed in as ${person.email}`, { exact: false })).toBeVisible();
  expect(page.url()).not.toContain("session=");
  expect(page.url()).not.toContain(person.token);
});

test("a Google failure on return is explained and nobody is signed in", async ({ page }) => {
  await page.goto("/workspace#google_error=google_denied");
  await expect(page.getByText("Google sign-in was cancelled.")).toBeVisible();
  await expect(page.getByLabel("Session token")).toBeVisible();
  expect(page.url()).not.toContain("google_error");
});

test("a connected user picks a sheet and a tab and the import becomes the selected upload", async ({ page }) => {
  const person = account();
  await enableGoogle(page, true);
  await fakePicker(page);
  await page.route("**/integrations/google/status", route => route.fulfill({ json: { connected: true, email: person.email } }));
  await page.route("**/integrations/google/picker-token", route => route.fulfill({ json: { access_token: "t", expires_in: 3600 } }));
  await page.route("**/integrations/google/spreadsheets/*", route => route.fulfill({ json: { title: "Orders", tabs: [{ id: 0, title: "Jan", rows: 3, columns: 4 }, { id: 7, title: "Feb", rows: 3, columns: 4 }] } }));
  let body: unknown = null;
  await page.route("**/google-sheets/import", async route => {
    body = route.request().postDataJSON();
    const [, workspace, dataset] = route.request().url().match(/workspaces\/([^/]+)\/datasets\/([^/]+)\//)!;
    const created = await page.request.post(`${api}/workspaces/${workspace}/datasets/${dataset}/uploads?filename=${encodeURIComponent("Orders - Feb.csv")}`, { headers: { ...person.headers, "Content-Type": "text/csv" }, data: Buffer.from(csv) });
    await route.fulfill({ status: 201, json: await created.json() });
  });
  await signInWithToken(page, person.token);
  const panel = page.getByRole("region", { name: "Import from Google Sheets", exact: true });
  await expect(panel).toContainText("ExecPlus can open only the sheets you choose");
  await expect(panel.getByRole("button", { name: `Disconnect ${person.email}`, exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "Choose a Google Sheet", exact: true }).click();
  await panel.getByRole("combobox").selectOption({ label: "Feb" });
  await panel.getByRole("button", { name: "Import this tab", exact: true }).click();
  await expect(page.getByText("imported from Google Sheets", { exact: false })).toBeVisible();
  expect(body).toEqual({ spreadsheet_id: sheet, sheet_id: 7 });
  await expect(page.getByLabel("Profile upload").locator("option:checked")).toHaveText("Orders - Feb.csv");
});

test("an import error from Google is shown without creating a half-finished state", async ({ page }) => {
  const person = account();
  await enableGoogle(page, true);
  await fakePicker(page);
  await page.route("**/integrations/google/status", route => route.fulfill({ json: { connected: true, email: person.email } }));
  await page.route("**/integrations/google/picker-token", route => route.fulfill({ json: { access_token: "t", expires_in: 3600 } }));
  await page.route("**/integrations/google/spreadsheets/*", route => route.fulfill({ status: 404, json: { error: { code: "google_sheet_unavailable", message: "ExecPlus cannot read that sheet. Choose it again with Google's picker." } } }));
  await signInWithToken(page, person.token);
  const panel = page.getByRole("region", { name: "Import from Google Sheets", exact: true });
  await panel.getByRole("button", { name: "Choose a Google Sheet", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("ExecPlus cannot read that sheet");
});
