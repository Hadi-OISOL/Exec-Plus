/* Use case: Verifies connecting accounting systems and databases and importing one source in the browser.
What it does: Mocks the platform endpoints while the real API creates the imported upload. */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const api = "http://127.0.0.1:8001";
const csv = "Id,Total\n1,10.5\n2,20\n";

type Platform = { id: string; label: string; kind: "oauth" | "credentials"; description: string; fields: { name: string; label: string; secret: boolean; placeholder: string }[]; connected: boolean; account: string };

function account() {
  const email = `connector-${randomUUID()}@example.test`;
  const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", email], { cwd: "../..", encoding: "utf8" }).trim();
  return { email, token, headers: { Authorization: `Bearer ${token}` } };
}

const odoo = (connected: boolean): Platform => ({
  id: "odoo", label: "Odoo", kind: "credentials", description: "Invoices and contacts", connected, account: connected ? "odoo.example / prod" : "",
  fields: [{ name: "url", label: "Odoo address", secret: false, placeholder: "" }, { name: "api_key", label: "API key", secret: true, placeholder: "" }],
});
const quickbooks = (connected: boolean): Platform => ({
  id: "quickbooks", label: "QuickBooks Online", kind: "oauth", description: "Invoices and bills", connected, account: connected ? "Acme" : "", fields: [],
});

async function signIn(page: Page, token: string) {
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
}

async function mockImport(page: Page, person: ReturnType<typeof account>, provider: string, bodies: unknown[]) {
  await page.route(`**/connectors/${provider}/import`, async route => {
    bodies.push(route.request().postDataJSON());
    const [, workspace, dataset] = route.request().url().match(/workspaces\/([^/]+)\/datasets\/([^/]+)\//)!;
    const created = await page.request.post(`${api}/workspaces/${workspace}/datasets/${dataset}/uploads?filename=${encodeURIComponent("Imported.csv")}`, { headers: { ...person.headers, "Content-Type": "text/csv" }, data: Buffer.from(csv) });
    await route.fulfill({ status: 201, json: await created.json() });
  });
}

test("no connectors configured means no connect panel", async ({ page }) => {
  const person = account();
  await signIn(page, person.token);
  await expect(page.getByRole("region", { name: "Connect your data", exact: true })).toHaveCount(0);
});

test("a database or Odoo user fills the form, connects, browses and imports a source", async ({ page }) => {
  const person = account();
  let connected = false;
  const bodies: unknown[] = [];
  let credentials: unknown = null;
  await page.route("**/connectors", route => route.fulfill({ json: [odoo(connected)] }));
  await page.route("**/connectors/odoo/credentials", route => {
    credentials = route.request().postDataJSON();
    connected = true;
    return route.fulfill({ json: { connected: true, account: "odoo.example / prod" } });
  });
  await page.route("**/connectors/odoo/sources**", route => route.fulfill({ json: [{ id: "invoices", label: "Customer invoices", container: false }] }));
  await mockImport(page, person, "odoo", bodies);
  await signIn(page, person.token);
  const panel = page.getByRole("region", { name: "Connect your data", exact: true });
  await expect(panel).toContainText("Odoo");
  await panel.getByRole("button", { name: "Connect Odoo", exact: true }).click();
  await panel.getByLabel("Odoo address").fill("https://odoo.example");
  await expect(panel.getByLabel("API key")).toHaveAttribute("type", "password");
  await panel.getByLabel("API key").fill("secret-key");
  await panel.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(panel).toContainText("Connected as odoo.example / prod");
  expect(credentials).toEqual({ values: { url: "https://odoo.example", api_key: "secret-key" } });
  await panel.getByRole("button", { name: "Choose data", exact: true }).click();
  await panel.getByRole("button", { name: "Import Customer invoices", exact: true }).click();
  await expect(page.getByText("imported from Odoo", { exact: false })).toBeVisible();
  expect(bodies).toEqual([{ source_id: "invoices" }]);
  await expect(page.getByLabel("Profile upload").locator("option:checked")).toHaveText("Imported.csv");
});

test("browsing a hierarchy drills into containers and the breadcrumb goes back", async ({ page }) => {
  const person = account();
  const parents: (string | null)[] = [];
  const bodies: unknown[] = [];
  const bigquery: Platform = { id: "bigquery", label: "Google BigQuery", kind: "oauth", description: "Tables", connected: true, account: "me@example.test", fields: [] };
  await page.route("**/connectors", route => route.fulfill({ json: [bigquery] }));
  await page.route("**/connectors/bigquery/sources**", route => {
    const parent = new URL(route.request().url()).searchParams.get("parent");
    parents.push(parent);
    const items = parent === null ? [{ id: "p/acme", label: "Acme", container: true }] : parent === "p/acme" ? [{ id: "d/acme/sales", label: "sales", container: true }] : [{ id: "t/acme/sales/orders", label: "orders", container: false }];
    return route.fulfill({ json: items });
  });
  await mockImport(page, person, "bigquery", bodies);
  await signIn(page, person.token);
  const panel = page.getByRole("region", { name: "Connect your data", exact: true });
  await panel.getByRole("button", { name: "Choose data", exact: true }).click();
  await panel.getByRole("button", { name: "Acme ›", exact: true }).click();
  await panel.getByRole("button", { name: "sales ›", exact: true }).click();
  await expect(panel.getByRole("button", { name: "Import orders", exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "/ Acme", exact: true }).click();
  await expect(panel.getByRole("button", { name: "sales ›", exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "sales ›", exact: true }).click();
  await panel.getByRole("button", { name: "Import orders", exact: true }).click();
  await expect(page.getByText("imported from Google BigQuery", { exact: false })).toBeVisible();
  expect(parents.slice(0, 3)).toEqual([null, "p/acme", "d/acme/sales"]);
  expect(bodies).toEqual([{ source_id: "t/acme/sales/orders" }]);
});

test("an OAuth platform sends the user away and brings them back signed in with a message", async ({ page }) => {
  const person = account();
  await page.route("**/connectors", route => route.fulfill({ json: [quickbooks(false)] }));
  await page.route("**/connectors/quickbooks/connect", route => route.fulfill({ json: { url: "http://127.0.0.1:3001/workspace?connector_connected=quickbooks" } }));
  await signIn(page, person.token);
  await page.getByRole("region", { name: "Connect your data", exact: true }).getByRole("button", { name: "Connect QuickBooks Online", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
  await expect(page.getByText("Connected. Choose what to import.")).toBeVisible();
  expect(page.url()).not.toContain("connector_connected");
});

test("a refused connection is explained and credential errors are shown", async ({ page }) => {
  const person = account();
  await page.route("**/connectors", route => route.fulfill({ json: [odoo(false)] }));
  await page.route("**/connectors/odoo/credentials", route => route.fulfill({ status: 422, json: { error: { code: "connector_credentials_rejected", message: "The platform did not accept the sign-in." } } }));
  await signIn(page, person.token);
  const panel = page.getByRole("region", { name: "Connect your data", exact: true });
  await panel.getByRole("button", { name: "Connect Odoo", exact: true }).click();
  await panel.getByLabel("Odoo address").fill("https://odoo.example");
  await panel.getByLabel("API key").fill("wrong");
  await panel.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("did not accept the sign-in");
  await page.goto("/workspace?connector_error=connector_denied&connector=quickbooks");
  await expect(page.getByText("The connection was cancelled.")).toBeVisible();
});
