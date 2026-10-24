/* Use case: Verifies each person's private chat history in a real browser.
What it does: Asks, finds the chat in "Your chats", reloads, reopens its saved answer, continues the same thread, opens a chat from another file, renames and removes it. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { finishInitialReview, openConversation, openLatestChat } from "./workspace-helpers";

function session() {
  return execFileSync(
    "python3",
    ["-m", "execplus.manage", "provision-user", "--email", `chats-${randomUUID()}@example.test`],
    { cwd: "../..", encoding: "utf8" },
  ).trim();
}

async function signIn(page: Page, token: string) {
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
}

async function upload(page: Page, filename: string) {
  const nav = page.getByRole("navigation", { name: "Workspace navigation" });
  if (await nav.count()) await nav.getByRole("button", { name: "Data library", exact: true }).click();
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: filename,
    mimeType: "text/csv",
    buffer: Buffer.from("branch,amount\nNorth,0.10\nSouth,0.20\nNorth,0.30\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await openConversation(page);
}

function jobPost(page: Page) {
  return page.waitForResponse(
    (response) => response.request().method() === "POST" && /\/threads\/[^/]+\/jobs$/.test(new URL(response.url()).pathname),
  );
}

async function ask(page: Page, question: string) {
  const chat = page.getByRole("region", { name: "Ask a question", exact: true });
  const posted = jobPost(page);
  await chat.getByLabel("Your question", { exact: true }).fill(question);
  await chat.getByRole("button", { name: "Ask", exact: true }).click();
  return new URL((await posted).url()).pathname.split("/threads/")[1].split("/")[0];
}

test("a chat is listed, reopens after reload and continues in the same thread", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const token = session();
  await signIn(page, token);
  await upload(page, "first-branches.csv");
  const chat = page.getByRole("region", { name: "Ask a question", exact: true });
  const chats = page.getByRole("list", { name: "Your chats", exact: true });
  const thread = await ask(page, "How many records are there by branch?");
  await expect(chat.locator(".conversationTurn").last().locator(".verifiedBadge")).toBeVisible();
  await expect(chats.getByRole("listitem")).toHaveCount(1);
  await expect(chats).toContainText("How many records are there by branch?");
  await expect(chats).toContainText("first-branches.csv");

  await page.reload();
  await signIn(page, token);
  await openConversation(page);
  await expect(chat.locator(".conversationTurn")).toHaveCount(0);
  await openLatestChat(page);
  const reopened = chat.locator(".conversationTurn").first();
  await expect(reopened).toContainText("How many records are there by branch?");
  await expect(reopened.locator(".verifiedBadge")).toBeVisible();
  await expect(reopened).toContainText("North");
  await expect(reopened.getByRole("button", { name: "Load saved answer", exact: true })).toHaveCount(0);
  await expect(chats.getByRole("button", { name: /^How many records/ })).toHaveAttribute("aria-current", "true");

  expect(await ask(page, "What is the total of amount?")).toBe(thread);
  await expect(chat.locator(".conversationTurn")).toHaveCount(2);
  await expect(chat.locator(".conversationTurn").last().locator(".kpiValue")).toHaveText("0.6");
  await expect(chats.getByRole("listitem")).toHaveCount(1);

  await upload(page, "second-branches.csv");
  await expect(chat.locator(".conversationTurn")).toHaveCount(0);
  await chats.getByRole("button", { name: /^How many records/ }).click();
  await expect(page.locator(".chatSource")).toContainText("first-branches.csv");
  await expect(chat.locator(".conversationTurn")).toHaveCount(2);
  await expect(chat.locator(".conversationTurn").last().locator(".kpiValue")).toHaveText("0.6");

  await chats.getByRole("button", { name: "Rename How many records are there by branch?", exact: true }).click();
  await chats.getByLabel("Chat name", { exact: true }).fill("Branch check");
  await chats.getByRole("button", { name: "Save", exact: true }).click();
  await expect(chats.getByRole("button", { name: /^Branch check/ })).toBeVisible();
  await page.getByLabel("Search your chats", { exact: true }).fill("nothing like this");
  await expect(chats.getByRole("listitem")).toHaveCount(0);
  await page.getByLabel("Search your chats", { exact: true }).fill("branch");
  await expect(chats.getByRole("listitem")).toHaveCount(1);
  for (const theme of ["light", "dark"]) {
    await page.getByLabel("Appearance", { exact: true }).selectOption(theme);
    for (const width of [320, 390, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      await chat.screenshot({ path: `test-results/chat-history-${theme}-${width}.png` });
    }
  }
  page.once("dialog", (dialog) => dialog.accept());
  await chats.getByRole("button", { name: "Remove Branch check", exact: true }).click();
  await expect(chats.getByRole("listitem")).toHaveCount(0);
  await expect(chat.locator(".conversationTurn")).toHaveCount(0);
  const hidden = await page.request.get(`http://127.0.0.1:8001/workspaces/${await workspaceId(page, token)}/threads/${thread}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(hidden.status()).toBe(404);
  expect(errors).toEqual([]);
});

async function workspaceId(page: Page, token: string) {
  const response = await page.request.get("http://127.0.0.1:8001/workspaces", { headers: { Authorization: `Bearer ${token}` } });
  return (await response.json())[0].id as string;
}
