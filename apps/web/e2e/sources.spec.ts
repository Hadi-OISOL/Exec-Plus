/* Use case: Proves approved source imports through the real owner screen.
What it does: Uses a disposable SELECT-only PostgreSQL source and checks saved retries, staged activation, private boundaries and narrow layouts. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";

const api = "http://127.0.0.1:8001";
const fixture = `
import json,re,sys
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url
from execplus.config import Settings
s=Settings()
assert s.environment=='test' and s.source_allow_test_loopback
operation,key=sys.argv[1:]
assert re.fullmatch('[a-f0-9]{32}',key)
url=make_url(s.database_url)
assert url.host in {'localhost','127.0.0.1'}
database,role='browser_source_'+key,'source_reader_'+key
params=dict(host='127.0.0.1',port=url.port or 5432,dbname=url.database,user=url.username,password=url.password)
secret=Path(s.source_secret_directory)/(key+'.json')
with psycopg.connect(**params,autocommit=True) as control:
    if operation=='create':
        password=uuid4().hex
        control.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
        control.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS').format(sql.Identifier(role),sql.Literal(password)))
        with psycopg.connect(**{**params,'dbname':database},autocommit=True) as db:
            db.execute('CREATE TABLE sales(city text,amount numeric(38,12),cost numeric(38,12))')
            db.execute("INSERT INTO sales VALUES ('Karachi',0.1,0.05),('Lahore',0.2,0.15)")
            db.execute(sql.SQL('GRANT SELECT ON sales TO {}').format(sql.Identifier(role)))
        secret.write_text(json.dumps(dict(username=role,password=password)))
        secret.chmod(0o600)
        print(json.dumps(dict(database=database,port=params['port'],secret_ref=key)))
    elif operation=='update':
        with psycopg.connect(**{**params,'dbname':database},autocommit=True) as db:
            db.execute("INSERT INTO sales VALUES ('Multan',0.3,0.25)")
    elif operation=='check':
        with psycopg.connect(**{**params,'dbname':database}) as db:
            print(json.dumps([[str(v) for v in row] for row in db.execute('SELECT * FROM sales ORDER BY city').fetchall()]))
    elif operation=='destroy':
        control.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(database)))
        control.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(role)))
        secret.unlink(missing_ok=True)
`;

test("approved database imports retain exact copies and need explicit refresh activation", async ({ page }) => {
  test.setTimeout(120_000);
  page.setDefaultTimeout(20_000);
  const command = (args: string[]) => execFileSync("python3", args, { cwd: "../..", encoding: "utf8" }).trim();
  const key = randomUUID().replaceAll("-", "");
  const email = `source-${key}@example.test`;
  const token = command(["-m", "execplus.manage", "provision-user", "--email", email]);
  command(["-m", "execplus.manage", "grant-staff", "--email", email, "--role", "admin"]);
  const headers = { Authorization: `Bearer ${token}` };
  const created = await page.request.post(`${api}/workspaces`, { headers, data: { name: "Source import fixture", seat_limit: 3 } });
  expect(created.ok()).toBe(true);
  const wid = (await created.json()).id;
  const dataset = await page.request.post(`${api}/workspaces/${wid}/datasets`, { headers, data: { name: "Approved sales" } });
  expect(dataset.ok()).toBe(true);
  const did = (await dataset.json()).id;
  const sourceId = randomUUID();
  let sourceCreated = false;
  try {
    const source = JSON.parse(command(["-c", fixture, "create", key]));
    sourceCreated = true;
    const original = command(["-c", fixture, "check", key]);
    const registered = await page.request.put(`${api}/admin/workspaces/${wid}/sources/${sourceId}`, {
      headers, data: { expected_version: 0, label: "Approved sales database", host: "localhost", address: "127.0.0.1",
        ...source, tables: [{ schema_name: "public", table: "sales", columns: ["city", "amount", "cost"] }] },
    });
    expect(registered.ok()).toBe(true);
    const publicCatalog = await (await page.request.get(`${api}/workspaces/${wid}/sources`, { headers })).text();
    expect(publicCatalog).not.toContain(source.secret_ref);
    expect(publicCatalog).not.toContain(source.database);
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto("/workspace");
    await page.getByLabel("Session token").fill(token);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Data library", exact: true }).click();
    await page.getByLabel("Dataset", { exact: true }).selectOption(did);
    const panel = page.getByRole("region", { name: "Database sources", exact: true });
    await expect(panel.getByRole("combobox", { name: "Approved source", exact: true })).toHaveValue(sourceId);
    await expect(panel.getByRole("button", { name: "Import snapshot", exact: true })).toBeEnabled();
    expect((await (await page.request.get(`${api}/workspaces/${wid}/datasets/${did}/source-imports`, { headers })).json()).imports).toEqual([]);
    await panel.getByText("Fields to import (3)", { exact: true }).click();
    for (const name of ["city", "amount", "cost"]) await panel.getByRole("checkbox", { name, exact: true }).uncheck();
    await expect(panel.getByRole("button", { name: "Import snapshot", exact: true })).toBeDisabled();
    await panel.getByRole("button", { name: "Refresh sources", exact: true }).click();
    await expect(panel.getByText("Fields to import (0)", { exact: true })).toBeVisible();
    await panel.getByText("Fields to import (0)", { exact: true }).click();
    for (const name of ["city", "amount", "cost"]) await panel.getByRole("checkbox", { name, exact: true }).check();
    let lostResponse = false;
    await page.route(`**/workspaces/${wid}/datasets/${did}/source-imports`, async route => {
      if (route.request().method() === "POST" && !lostResponse) {
        lostResponse = true;
        const saved = await route.fetch();
        expect(saved.ok()).toBe(true);
        await route.fulfill({ status: 503, json: { error: { code: "temporary", message: "The response was interrupted. Retry the same attempt." } } });
      } else await route.continue();
    });
    await panel.getByRole("button", { name: "Import snapshot", exact: true }).click();
    await expect(panel.getByRole("alert")).toContainText("interrupted");
    await expect(panel.getByRole("combobox", { name: "Source table", exact: true })).toHaveValue("0");
    await panel.getByRole("button", { name: "Retry same attempt", exact: true }).click();
    await expect(panel.getByText("Import saved", { exact: true })).toBeVisible();
    await expect(panel.getByText("2 rows · Read", { exact: false })).toBeVisible();
    const history = (await (await page.request.get(`${api}/workspaces/${wid}/datasets/${did}/source-imports`, { headers })).json()).imports;
    expect(history).toHaveLength(1);
    const uid = history[0].upload_id;
    expect(command(["-c", fixture, "check", key])).toBe(original);
    const download = await page.request.get(`${api}/workspaces/${wid}/datasets/${did}/uploads/${uid}/content`, { headers });
    expect(download.ok()).toBe(true);
    const originalFile = await download.text();
    expect(originalFile).toContain("Karachi,0.100000000000,0.050000000000");
    const root = `${api}/workspaces/${wid}/datasets/${did}/uploads/${uid}`;
    const meaning = await (await page.request.get(`${root}/understanding`, { headers })).json();
    expect(meaning.state).not.toBe("confirmed");
    meaning.definition.domain = "sales"; meaning.definition.grain = "record";
    for (const column of meaning.definition.columns) if (column.role === "metric") column.unit = "PKR";
    const confirmed = await page.request.post(`${root}/understanding`, { headers, data: {
      revision_id: meaning.revision_id, expected_version: meaning.version, state: "confirmed", definition: meaning.definition,
    } });
    expect(confirmed.ok()).toBe(true);
    const understanding = await confirmed.json();
    const configured = await page.request.put(`${api}/workspaces/${wid}/datasets/${did}/refresh`, { headers, data: {
      upload_id: uid, revision_id: meaning.revision_id, understanding_id: understanding.id, expected_version: 0,
      interval_hours: 24, freshness_hours: 48, enabled: false, as_of: new Date().toISOString(),
    } });
    expect(configured.ok()).toBe(true);
    command(["-c", fixture, "update", key]);
    await panel.getByRole("button", { name: "Choose another import", exact: true }).click();
    await panel.getByRole("button", { name: "Refresh sources", exact: true }).click();
    await expect(panel.getByRole("combobox", { name: "Import action", exact: true })).toBeEnabled();
    await panel.getByRole("combobox", { name: "Import action", exact: true }).selectOption("refresh");
    await panel.getByRole("button", { name: "Stage source refresh", exact: true }).click();
    await expect(panel.getByText("Refresh ready for review", { exact: true })).toBeVisible();
    const staged = (await (await page.request.get(`${api}/workspaces/${wid}/datasets/${did}/source-imports`, { headers })).json()).imports.find((item: { status: string }) => item.status === "staged");
    const beforeActivation = await (await page.request.get(`${api}/workspaces/${wid}/datasets/${did}/refresh`, { headers })).json();
    expect(beforeActivation.feed.source.upload_id).toBe(uid);
    expect(staged.snapshot.row_count).toBe(3);
    expect(await (await page.request.get(`${root}/content`, { headers })).text()).toBe(originalFile);
    const directory = "../../data/verification/2026-10-16/remaining-work/sources-browser";
    mkdirSync(directory, { recursive: true });
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      await panel.scrollIntoViewIfNeeded();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      expect((await panel.getByRole("button", { name: "Review staged refresh", exact: true }).boundingBox())!.height).toBeGreaterThanOrEqual(44);
      await panel.screenshot({ path: `${directory}/sources-${width}.png`, animations: "disabled" });
    }
    await panel.getByRole("button", { name: "Review staged refresh", exact: true }).click();
    await expect(page.getByRole("button", { name: "Activate snapshot", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Activate snapshot", exact: true }).click();
    await expect.poll(async () => (await (await page.request.get(`${api}/workspaces/${wid}/datasets/${did}/refresh`, { headers })).json()).feed.source.upload_id).toBe(staged.upload_id);
    expect(JSON.parse(command(["-c", fixture, "check", key]))).toHaveLength(3);
    await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Data library", exact: true }).click();
    const revised = await page.request.put(`${api}/admin/workspaces/${wid}/sources/${sourceId}`, {
      headers, data: { expected_version: 1, label: "Approved sales database", host: "localhost", address: "127.0.0.1",
        ...source, tables: [{ schema_name: "public", table: "sales", columns: ["city", "amount"] }] },
    });
    expect(revised.ok()).toBe(true);
    await panel.getByRole("button", { name: "Refresh sources", exact: true }).click();
    await expect(panel.getByText("Fields to import (2)", { exact: true })).toBeVisible();
    await panel.getByText("Connection settings", { exact: true }).click();
    await panel.getByRole("button", { name: "Disconnect selected source", exact: true }).click();
    await expect(panel.getByText("No database source is connected yet.", { exact: false })).toBeVisible();
    expect(await (await page.request.get(`${root}/content`, { headers })).text()).toBe(originalFile);
    expect(errors).toEqual([]);
  } finally {
    if (sourceCreated) command(["-c", fixture, "destroy", key]);
  }
});
