/* Use case: Keeps external sign-in distinct from password and operator accounts.
What it does: Uses an isolated synthetic Google principal and the real account API without any provider calls. */
import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";

function externalAccount(): { email: string; token: string; id: string } {
  const setup = `
import json
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from execplus.config import Settings
from execplus.infrastructure.identity import DatabaseSessionIdentity
from execplus.infrastructure.persistence import schema as s
settings = Settings()
assert settings.environment == "test"
assert make_url(str(settings.database_url)).query["options"].startswith("-csearch_path=browser_")
engine = create_engine(str(settings.database_url))
email = "external-browser-" + uuid4().hex + "@example.test"
token = DatabaseSessionIdentity(engine).provision(email)
with engine.begin() as db:
    uid = db.execute(select(s.users.c.id).where(s.users.c.email == email)).scalar_one()
    db.execute(s.external_identities.insert().values(provider="google", subject=uuid4().hex, user_id=uid, created_at=datetime.now(timezone.utc)))
    db.execute(s.account_events.insert().values(id=uuid4(), user_id=uid, action="google.registered", reason="", created_at=datetime.now(timezone.utc)))
print(json.dumps(dict(email=email, token=token, id=str(uid))))
engine.dispose()
`;
  return JSON.parse(execFileSync("python3", ["-c", setup], { cwd: "../..", encoding: "utf8" }));
}

test("Google account settings show the actual sign-in method without local password or operator claims", async ({ page }) => {
  const person = externalAccount();
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/workspace");
  await page.getByLabel("Session token", { exact: true }).fill(person.token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText(`Signed in as ${person.email}`, { exact: true })).toBeVisible();
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("button", { name: "Team & settings", exact: true }).click();
  const security = page.getByRole("region", { name: "Your account settings", exact: true });
  await expect(security).toContainText("You sign in with Google.");
  await expect(security).toContainText(person.id);
  await expect(security).toContainText("Share this ID with your workspace manager");
  await expect(security.getByText("Your access is managed by the local operator.", { exact: false })).toHaveCount(0);
  await expect(security.getByText("Change your password", { exact: true })).toHaveCount(0);
  await expect(security.getByText("Disable your account", { exact: true })).toHaveCount(0);
  await security.getByText("Recent account activity", { exact: true }).click();
  await expect(security).toContainText("google registered");
  expect(errors).toEqual([]);
});
