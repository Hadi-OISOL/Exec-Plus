/* Presentation fixtures only: real sign-in/upload/job flow, synthetic verified-result responses.
   Backend synthesis faithfulness and authorization are checked separately by backend tests. */

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { finishInitialReview, openConversation } from "./workspace-helpers";

const exact = "9007199254740993.000001";
const limit = "Recorded associations do not establish causation or predict a changed outcome.";

for (const mode of ["selected", "fallback"] as const) {
  test(`synthetic ${mode} narrative and nested compound results retain exact evidence at three widths`, async ({ page }) => {
    test.setTimeout(180_000);
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    const token = execFileSync("python3", ["-m", "execplus.manage", "provision-user", "--email", `harness-presentation-${randomUUID()}@example.test`], { cwd: "../..", encoding: "utf8" }).trim();
    await page.goto("/workspace");
    await page.getByLabel("Session token").fill(token);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
    await page.getByLabel("CSV or Excel file").setInputFiles({ name: "fictional-harness-presentation.csv", mimeType: "text/csv", buffer: Buffer.from("region,amount\nWest,1\nEast,2\n") });
    await page.getByRole("button", { name: "Upload file", exact: true }).click();
    await finishInitialReview(page);
    await openConversation(page);

    const firstId = randomUUID(), secondId = randomUUID();
    const lineage = { query_id: firstId, metric: "amount", aggregation: "sum", records_analyzed: 2, sql: "SELECT SUM(amount) FROM fictional_data", filters: ["region = West"], model_route: "synthetic:presentation-only", receipt: { sources: [] } };
    let payloads = 0;
    await page.route(/\/jobs\/[^/]+\/result$/, async route => {
      const response = await route.fetch();
      const body = await response.json();
      payloads += 1;
      await route.fulfill({ json: { ...body, answer: {
        kind: "mixed", coverage: "data", citations: [], limitations: [],
        // The parent fields must survive flatten(answer.data).
        narrative: { version: "verified-narrative-v1", mode, segments: [
          { statement_id: "F1", text: `The total amount is ${exact} USD.`, evidence_ids: [firstId], kind: "observation" },
          { statement_id: "F2", text: "This result covers region = West only.", evidence_ids: [firstId], kind: "scope" },
          { statement_id: "F3", text: limit, evidence_ids: [firstId, secondId], kind: "limitation" },
        ] },
        data: { label: "First exact calculation", value: exact, lineage },
        additional_data: [{ label: "Second exact calculation", value: "0.000000000001", lineage: { ...lineage, query_id: secondId, metric: "weight", filters: ["region = East"] } },
          { label: "Additional exact records", columns: ["ID", "Recorded value"], rows: [["fictional-1", exact], ["fictional-2", null]], records_analyzed: 2, matched_records: 2, lineage: { ...lineage, query_id: randomUUID(), aggregation: "rows" } }],
      } } });
    });
    await page.getByLabel("Your question", { exact: true }).fill("Help me understand my data");
    await page.getByLabel("Your question", { exact: true }).press("Enter");
    const turn = page.locator(".conversationTurn").last();
    const narrative = turn.getByRole("region", { name: "Result explanation", exact: true });
    await expect(narrative).toContainText(`${exact} USD`);
    await expect(narrative).toContainText(limit);
    await expect(turn.getByRole("region", { name: "Calculation 2", exact: true })).toContainText("0.000000000001");
    const records = turn.getByRole("region", { name: "Calculation 3", exact: true });
    await expect(records.getByRole("table")).toContainText(exact);
    await expect(records.getByRole("table")).toContainText("fictional-2");
    await expect(turn.getByRole("region", { name: "Document evidence", exact: true })).toHaveCount(0);
    expect(payloads).toBe(1);

    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      await narrative.scrollIntoViewIfNeeded();
      await expect(narrative).toBeVisible();
      await expect(narrative).toContainText(limit);
      await expect(turn.locator(".kpiValue")).toHaveAttribute("title", exact);
      const evidence = narrative.locator("summary");
      await evidence.focus();
      await expect(evidence).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(narrative.locator("details")).toHaveAttribute("open", "");
      await expect(narrative).toContainText(firstId);
      await expect(narrative).toContainText(secondId);
      await page.keyboard.press("Enter");
      await expect(narrative.locator("details")).not.toHaveAttribute("open", "");
      const second = turn.getByRole("region", { name: "Calculation 2", exact: true });
      const calculationEvidence = second.locator("summary");
      await calculationEvidence.focus();
      await page.keyboard.press("Space");
      await expect(second.locator("details")).toHaveAttribute("open", "");
      await expect(second).toContainText("region = East");
      await page.keyboard.press("Space");
      await records.getByRole("table").scrollIntoViewIfNeeded();
      await expect(records.getByRole("table")).toContainText(exact);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    }
    expect(errors).toEqual([]);
  });
}
