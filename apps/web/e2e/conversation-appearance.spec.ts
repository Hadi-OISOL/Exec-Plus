/* Synthetic layout checks use the real stylesheet cascade without private data or services. */
import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const files = ["globals.css"];

function contrast(first: string, second: string) {
  const luminance = (color: string) => {
    const channels = color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map(value => {
      const channel = value / 255;
      return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4;
    });
    return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
  };
  const values = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (values[0] + .05) / (values[1] + .05);
}

for (const theme of ["light", "dark"]) {
  test(`conversation stays readable and exact tables scroll in ${theme}`, async ({ page }) => {
    const css = (await Promise.all(files.map(file => readFile(join(process.cwd(), "src/app", file), "utf8")))).join("\n");
    await page.emulateMedia({ reducedMotion: "reduce" });
    for (const width of [320, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 850 });
      await page.setContent(`<html data-theme="${theme}"><head><style>${css}</style></head><body>
        <main class="workbench analyticsShell"><aside class="workbenchRail">ExecPlus</aside><div class="workbenchMain">
        <header class="workbenchTop"><div>Workspace</div><label class="themeControl">Appearance<select><option>${theme}</option></select></label><div class="sessionBar">Fictional tester<button>Sign out</button></div></header>
        <div class="workbenchContent"><div class="dedicatedConversation"><section class="askPanel panel"><header class="chatHeader">Your data conversation</header>
        <div class="conversationLog"><div class="conversationTurn"><div class="userMessage"><p>${"Long_recorded_field_".repeat(8)}</p></div>
        <article class="assistantMessage"><span class="messageAuthor">ExecPlus</span>
        <section class="dataExplanation" aria-label="Result explanation"><p class="explanationPlain">The total Revenue is 6 USD.</p><details><summary>Explanation evidence</summary><p>${"a".repeat(128)}</p></details></section>
        <div class="dataExplanation"><section class="explanationCard" data-kind="fields"><h3>How the fields fit together</h3><p>${"Long_recorded_field_".repeat(8)} measures a recorded condition.</p></section></div>
        <div class="tableScroll" tabindex="0" role="region" aria-label="Exact result table"><table><thead><tr>${Array.from({ length: 8 }, (_, index) => `<th>Recorded column ${index}</th>`).join("")}</tr></thead><tbody><tr>${Array.from({ length: 8 }, () => "<td>1234567890.123456789</td>").join("")}</tr></tbody></table></div>
        <div class="suggestionChips"><button>Show ${"long_category_label_".repeat(4)}</button></div>
        </article></div></div><div class="chatComposer"><p>Ask another question</p><textarea placeholder="Your question"></textarea></div>
        </section></div></div></div></main></body></html>`);
      const dimensions = await page.evaluate(() => {
        const sizes = [".workbenchTop", ".conversationLog", ".assistantMessage", ".dataExplanation", ".explanationCard", ".tableScroll", ".chatComposer"].map(selector => {
          const element = document.querySelector(selector)!;
          const rectangle = element.getBoundingClientRect();
          return { selector, left: rectangle.left, right: rectangle.right, client: element.clientWidth, scroll: element.scrollWidth };
        });
        const narrative = getComputedStyle(document.querySelector(".explanationPlain")!);
        const surface = getComputedStyle(document.querySelector(".dataExplanation")!);
        return { page: document.documentElement.scrollWidth, sizes, ink: narrative.color, background: surface.backgroundColor,
          chatHeight: getComputedStyle(document.querySelector(".conversationLog")!).maxHeight };
      });
      expect(dimensions.page).toBe(width);
      for (const size of dimensions.sizes) {
        expect(size.left, size.selector).toBeGreaterThanOrEqual(-1);
        expect(size.right, size.selector).toBeLessThanOrEqual(width + 1);
        if (size.selector !== ".tableScroll") expect(size.scroll, size.selector).toBeLessThanOrEqual(size.client + 1);
      }
      expect(contrast(dimensions.ink, dimensions.background)).toBeGreaterThanOrEqual(4.5);
      if (width <= 600) expect(dimensions.chatHeight).toBe("none");
      if (width <= 390) {
        const table = page.getByRole("region", { name: "Exact result table" });
        const dimensions = await table.evaluate(element => ({ scroll: element.scrollWidth, client: element.clientWidth }));
        expect(dimensions.scroll).toBeGreaterThan(dimensions.client);
        await table.focus();
        await page.keyboard.press("ArrowRight");
        await expect.poll(() => table.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
      }
    }
  });
}
