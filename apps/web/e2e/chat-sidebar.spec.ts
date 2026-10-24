/* Use case: Verifies the chat-history sidebar beside Ask Syntelio in a real browser.
What it does: Toggles and remembers it, starts and continues a context-titled chat across reloads, renames, loads more than one page and uses the phone drawer. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { finishInitialReview, openConversation } from "./workspace-helpers";

const API = "http://127.0.0.1:8001";

function session() {
  return execFileSync(
    "python3",
    ["-m", "execplus.manage", "provision-user", "--email", `sidebar-${randomUUID()}@example.test`],
    { cwd: "../..", encoding: "utf8" },
  ).trim();
}

async function signIn(page: Page, token: string) {
  await page.goto("/workspace");
  await page.getByLabel("Session token").fill(token);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
}

async function ask(page: Page, question: string) {
  const chat = page.getByRole("region", { name: "Ask a question", exact: true });
  const posted = page.waitForResponse((response) => response.request().method() === "POST" && /\/threads\/[^/]+\/jobs$/.test(new URL(response.url()).pathname));
  await chat.getByLabel("Your question", { exact: true }).fill(question);
  await chat.getByRole("button", { name: "Ask", exact: true }).click();
  return new URL((await posted).url()).pathname;
}

test("the chat sidebar starts, titles, reopens, renames, pages and works as a phone drawer", async ({ page }) => {
  test.setTimeout(180_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 900 });
  const token = session();
  await signIn(page, token);
  await page.getByLabel("CSV or Excel file").setInputFiles({
    name: "branches.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("branch,amount\nNorth,0.10\nSouth,0.20\nNorth,0.30\n"),
  });
  await page.getByRole("button", { name: "Upload file", exact: true }).click();
  await finishInitialReview(page);
  await openConversation(page);
  const chat = page.getByRole("region", { name: "Ask a question", exact: true });
  const sidebar = page.getByRole("complementary", { name: "Chat history", exact: true });
  const chats = sidebar.getByRole("list", { name: "Your chats", exact: true });
  const toggle = chat.getByRole("button", { name: /chat history$/ });

  await expect(sidebar).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await toggle.click();
  await expect(sidebar).toHaveCount(0);
  await page.reload();
  await signIn(page, token);
  await openConversation(page);
  await expect(sidebar).toHaveCount(0);
  await toggle.click();
  await expect(sidebar).toBeVisible();

  await sidebar.getByRole("button", { name: "New chat", exact: true }).click();
  const path = await ask(page, "What is the total of amount?");
  const thread = path.split("/threads/")[1].split("/")[0];
  await expect(chat.locator(".conversationTurn").last().locator(".kpiValue")).toHaveText("0.6");
  await expect(sidebar.getByText("Today", { exact: true })).toBeVisible();
  const row = chats.getByRole("button", { name: /^Total amount/ });
  await expect(row).toBeVisible();
  await expect(row).toHaveAttribute("aria-current", "true");
  await expect(row).toContainText("branches.csv");

  await page.reload();
  await signIn(page, token);
  await openConversation(page);
  await expect(chat.locator(".conversationTurn")).toHaveCount(0);
  await row.click();
  await expect(chat.locator(".conversationTurn").first().locator(".kpiValue")).toHaveText("0.6");
  expect(await ask(page, "How many records are there by branch?")).toContain(`/threads/${thread}/`);
  await expect(chat.locator(".conversationTurn")).toHaveCount(2);
  await expect(chats.getByRole("listitem")).toHaveCount(1);

  await chats.getByRole("button", { name: /^Chat options for Total amount/ }).click();
  await chats.getByRole("button", { name: "Rename", exact: true }).click();
  await chats.getByLabel("Chat name", { exact: true }).fill("Amount review");
  await chats.getByRole("button", { name: "Save", exact: true }).click();
  await expect(chats.getByRole("button", { name: /^Amount review/ })).toBeVisible();

  const workspace = path.split("/threads/")[0];
  const upload = await page.request.get(`${API}${workspace}/threads`, { headers: { Authorization: `Bearer ${token}` } });
  const first = (await upload.json())[0];
  for (let index = 0; index < 51; index += 1) {
    const created = await page.request.post(`${API}${workspace}/datasets/${first.dataset_id}/uploads/${first.upload_id}/threads`, { headers: { Authorization: `Bearer ${token}` } });
    expect(created.status()).toBe(201);
  }
  await toggle.click();
  await toggle.click();
  await expect(chats.getByRole("listitem")).toHaveCount(50);
  await sidebar.getByRole("button", { name: "Load more chats", exact: true }).click();
  await expect(chats.getByRole("listitem")).toHaveCount(52);
  await expect(chats.getByRole("button", { name: /^Amount review/ })).toBeVisible();
  await expect(sidebar.getByRole("button", { name: "Load more chats", exact: true })).toHaveCount(0);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(sidebar).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await toggle.click();
  const drawer = page.getByRole("dialog", { name: "Chat history", exact: true });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByRole("button", { name: "New chat", exact: true })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  expect(await drawer.evaluate((element) => element.contains(document.activeElement))).toBe(true);
  await page.keyboard.press("Tab");
  await expect(drawer.getByRole("button", { name: "New chat", exact: true })).toBeFocused();
  await chat.screenshot({ path: "test-results/chat-sidebar-drawer-390.png" });
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  await expect(toggle).toBeFocused();
  await toggle.click();
  await page.mouse.click(380, 400);
  await expect(drawer).toHaveCount(0);
  await toggle.click();
  await drawer.getByLabel("Search your chats", { exact: true }).fill("amount");
  await drawer.getByRole("button", { name: /^Amount review/ }).click();
  await expect(drawer).toHaveCount(0);
  await expect(chat.locator(".conversationTurn")).toHaveCount(2);
  await expect(chat.locator(".conversationTurn").first().locator(".kpiValue")).toHaveText("0.6");

  for (const theme of ["light", "dark"]) {
    await page.getByLabel("Appearance", { exact: true }).selectOption(theme);
    for (const width of [390, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      await chat.screenshot({ path: `test-results/chat-sidebar-${theme}-${width}.png` });
    }
  }
  expect(errors).toEqual([]);
});
