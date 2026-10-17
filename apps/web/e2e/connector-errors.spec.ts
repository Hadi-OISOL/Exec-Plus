/* Use case: Verifies the Google sign-in button, the return from Google and the sheet import flow.
What it does: Mocks Google's configuration and picker while the real API creates the imported upload. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const sheet = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms";

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

for (const readStatus of [403, 503]) {
for (const tabCount of [1, 2]) {
const selectedTab = tabCount === 1 ? 0 : 7;
test(`Google allowance failure preserves the selected tab for retry (${tabCount} tabs, read ${readStatus})`, async ({ page }) => {
  const person = account();
  await enableGoogle(page, true);
  await fakePicker(page);
  await page.route("**/integrations/google/status", route => route.fulfill({ json: { connected: true, email: person.email } }));
  await page.route("**/integrations/google/picker-token", route => route.fulfill({ json: { access_token: "t", expires_in: 3600 } }));
  await page.route("**/integrations/google/spreadsheets/*", route => route.fulfill({ json: { title: "Private orders", tabs: [{ id: 0, title: "Jan", rows: 3, columns: 4 }, { id: 7, title: "Feb", rows: 3, columns: 4 }].slice(0, tabCount) } }));
  const bodies: unknown[] = [];
  await page.route("**/google-sheets/import", route => {
    bodies.push(route.request().postDataJSON());
    return route.fulfill({ status: 429, json: { error: { code: "plan_allowance_exceeded", message: "Your import allowance is used up. Try again later." } } });
  });
  await signInWithToken(page, person.token);
  const panel = page.getByRole("region", { name: "Import from Google Sheets", exact: true });
  await panel.getByRole("button", { name: "Choose a Google Sheet", exact: true }).click();
  if (tabCount === 2) {
    await panel.getByRole("combobox").selectOption({ label: "Feb" });
    await panel.getByRole("button", { name: "Import this tab", exact: true }).click();
  }
  await expect(panel.getByRole("alert")).toContainText("allowance is used up");
  await expect(panel.getByRole("combobox")).toHaveValue(String(selectedTab));
  await panel.getByRole("button", { name: "Import this tab", exact: true }).click();
  await expect.poll(() => bodies.length).toBe(2);
  expect(bodies).toEqual([{ spreadsheet_id: sheet, sheet_id: selectedTab }, { spreadsheet_id: sheet, sheet_id: selectedTab }]);
  await expect(page.getByText("imported from Google Sheets", { exact: false })).toHaveCount(0);
  // A later revoked read must clear the old private title and selection.
  await page.route("**/integrations/google/picker-token", route => route.fulfill({ status: readStatus, json: { error: { code: "forbidden", message: "This connection is no longer available." } } }));
  await panel.getByRole("button", { name: "Choose a Google Sheet", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("no longer available");
  await expect(panel.getByRole("combobox")).toHaveCount(0);
  await expect(panel).not.toContainText("Private orders");
  await expect(panel).not.toContainText(person.email);
});
}

test(`connector failed reads clear private browsing and failed imports remain retryable (${readStatus})`, async ({ page }) => {
  const person = account();
  await page.route("**/connectors", route => route.fulfill({ json: [{ id: "odoo", label: "Odoo", kind: "credentials", description: "Invoices", fields: [], connected: true, account: "Private account" }] }));
  await page.route("**/connectors/odoo/sources**", route => route.fulfill({ json: [{ id: "invoices", label: "Private invoices", container: false }] }));
  let attempts = 0;
  await page.route("**/connectors/odoo/import", route => {
    attempts += 1;
    return route.fulfill({ status: 429, json: { error: { code: "plan_allowance_exceeded", message: "Your import allowance is used up." } } });
  });
  await signInWithToken(page, person.token);
  const panel = page.getByRole("region", { name: "Connect your data", exact: true });
  await panel.getByRole("button", { name: "Choose data", exact: true }).click();
  await panel.getByRole("button", { name: "Import Private invoices", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("allowance is used up");
  await panel.getByRole("button", { name: "Import Private invoices", exact: true }).click();
  await expect.poll(() => attempts).toBe(2);
  await page.route("**/connectors/odoo/sources**", route => route.fulfill({ status: readStatus, json: { error: { code: "forbidden", message: "This connection is no longer available." } } }));
  await panel.getByRole("button", { name: "Choose data", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("no longer available");
  await expect(panel).not.toContainText("Private invoices");
  await expect(panel).not.toContainText("Private account");
});

}

for (const provider of ["google", "odoo"]) {
for (const readStatus of [403, 503]) {
test(`${provider} saved import with failed refresh (${readStatus}) retries only the read`, async ({ page }) => {
  const person = account();
  if (provider === "google") {
    await enableGoogle(page, true);
    await fakePicker(page);
    await page.route("**/integrations/google/status", route => route.fulfill({ json: { connected: true, email: person.email } }));
    await page.route("**/integrations/google/picker-token", route => route.fulfill({ json: { access_token: "t", expires_in: 3600 } }));
    await page.route("**/integrations/google/spreadsheets/*", route => route.fulfill({ json: { title: "Private orders", tabs: [{ id: 0, title: "Jan", rows: 3, columns: 2 }, { id: 7, title: "Feb", rows: 3, columns: 2 }] } }));
  } else {
    await page.route("**/connectors", route => route.fulfill({ json: [{ id: "odoo", label: "Odoo", kind: "credentials", description: "Invoices", fields: [], connected: true, account: "Private account" }] }));
    await page.route("**/connectors/odoo/sources**", route => route.fulfill({ json: [{ id: "invoices", label: "Private invoices", container: false }] }));
  }
  let posts = 0;
  let failRead = true;
  await page.route(provider === "google" ? "**/google-sheets/import" : "**/connectors/odoo/import", async route => {
    posts += 1;
    const [, workspace, dataset] = route.request().url().match(/workspaces\/([^/]+)\/datasets\/([^/]+)\//)!;
    const prefix = `/workspaces/${workspace}/datasets/${dataset}/uploads`;
    const created = await page.request.post(`http://127.0.0.1:8001${prefix}?filename=Saved.csv`, { headers: { ...person.headers, "Content-Type": "text/csv" }, data: "Id,Total\n1,10\n2,20\n" });
    expect(created.status()).toBe(201);
    await page.route(`**${prefix}`, read => failRead
      ? read.fulfill({ status: readStatus, json: { error: { code: "unavailable", message: "The updated data could not be read." } } })
      : read.continue());
    await route.fulfill({ status: 201, json: await created.json() });
  });
  await signInWithToken(page, person.token);
  if (provider === "google") {
    const panel = page.getByRole("region", { name: "Import from Google Sheets", exact: true });
    await panel.getByRole("button", { name: "Choose a Google Sheet", exact: true }).click();
    await panel.getByRole("button", { name: "Import this tab", exact: true }).click();
    await expect(panel.getByRole("combobox")).toHaveCount(0);
  } else {
    const panel = page.getByRole("region", { name: "Connect your data", exact: true });
    await panel.getByRole("button", { name: "Choose data", exact: true }).click();
    await panel.getByRole("button", { name: "Import Private invoices", exact: true }).click();
    await expect(panel.getByRole("button", { name: "Import Private invoices", exact: true })).toHaveCount(0);
  }
  await expect(page.getByRole("status")).toContainText("Import saved, but the updated data could not be loaded");
  expect(posts).toBe(1);
  await expect(page.getByLabel("Profile upload")).toBeDisabled();
  await expect(page.getByLabel("Profile upload")).toHaveValue("");
  await expect(page.getByLabel("Profile upload").locator("option")).toHaveCount(1);
  // Failed read-only retry keeps the reload action, without repeating the import.
  await page.getByRole("button", { name: "Reload saved data", exact: true }).click();
  await expect(page.getByRole("alert", { name: "Request error", exact: true })).toContainText("could not be read");
  expect(posts).toBe(1);
  failRead = false;
  await page.getByRole("button", { name: "Reload saved data", exact: true }).click();
  await expect(page.getByText("Saved import loaded.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Reload saved data", exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Profile upload").locator("option:checked")).toHaveText("Saved.csv");
  expect(posts).toBe(1);
});
}
}
