/* Use case: Protects cookie-based password sign-in and new-account sign-in.
What it does: Checks automatic login after registration, cookie credentials, in-memory token handoff and honest failure messages. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/app/workspace/account-session.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { signInAccount } = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

function fake(responses) {
  const calls = [];
  const fetcher = async (url, init) => {
    calls.push({ url, body: JSON.parse(init.body), credentials: init.credentials });
    const [status, body] = responses.shift();
    return { ok: status < 300, json: async () => body };
  };
  return { calls, fetcher };
}

test("registration signs straight in with the same credentials", async () => {
  const { calls, fetcher } = fake([[202, { message: "ready" }], [200, { token: "t1" }]]);
  const result = await signInAccount(fetcher, "http://api", { email: "a@b.test", password: "p" }, { display_name: "A", workspace_name: "W" });
  assert.deepEqual(result, { signedIn: true, token: "t1" });
  assert.deepEqual(calls.map(call => call.credentials), ["include", "include"]);
  assert.deepEqual(calls.map(call => call.url), ["http://api/auth/register", "http://api/auth/login"]);
  assert.deepEqual(calls[1].body, { email: "a@b.test", password: "p" });
});

test("a failed automatic sign-in after registration is reported honestly", async () => {
  const { fetcher } = fake([[202, {}], [401, { error: { message: "Email or password is incorrect." } }]]);
  const result = await signInAccount(fetcher, "http://api", { email: "a@b.test", password: "p" }, { display_name: "A", workspace_name: "W" });
  assert.equal(result.registered, true);
  assert.match(result.error, /could not sign you in automatically: Email or password is incorrect\./);
});

test("a rejected registration does not attempt sign-in", async () => {
  const { calls, fetcher } = fake([[422, { error: { message: "Password too short." } }]]);
  const result = await signInAccount(fetcher, "http://api", { email: "a@b.test", password: "p" }, { display_name: "A", workspace_name: "W" });
  assert.deepEqual(result, { error: "Password too short.", registered: false });
  assert.equal(calls.length, 1);
});

test("plain sign-in hands the token to page memory and reports server messages", async () => {
  assert.deepEqual(await signInAccount(fake([[200, { token: "t2" }]]).fetcher, "", { email: "e", password: "p" }), { signedIn: true, token: "t2" });
  assert.deepEqual(await signInAccount(fake([[429, {}]]).fetcher, "", { email: "e", password: "p" }), { error: "Account access is unavailable. Please try again.", registered: false });
});
