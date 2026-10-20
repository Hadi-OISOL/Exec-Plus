/* Use case: Gives every kit chart one shared light and dark appearance.
What it does: Supplies the validated eight-color categorical order from docs/ui-design-reference.md §7 and resolves the page's design tokens (--chart-1…8, then --color-text, --color-text-muted, --color-border, --color-surface) when they are defined. */

export type ChartTokens = {
  series: string[];
  ink: string;
  muted: string;
  grid: string;
  surface: string;
  font: string;
  other: string;
  diverging: string[];
};

const light: ChartTokens = {
  series: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
  ink: "#161b26", muted: "#677080", grid: "#e1e5eb", surface: "#ffffff", other: "#8a93a0",
  font: "Inter, Manrope, system-ui, sans-serif",
  diverging: ["#b42a2a", "#e34948", "#f19a99", "#f0efec", "#86b6ef", "#2a78d6", "#1c5cab"],
};
const dark: ChartTokens = {
  series: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
  ink: "#e8ecf2", muted: "#8b94a3", grid: "#2a3240", surface: "#161c26", other: "#5f6878",
  font: light.font,
  diverging: ["#b42a2a", "#e34948", "#f19a99", "#2f3644", "#86b6ef", "#3987e5", "#1c5cab"],
};

export function defaultTokens(isDark: boolean): ChartTokens {
  return isDark ? dark : light;
}

const sentinel = "rgb(1, 2, 3)";

export function readTokens(element: HTMLElement, isDark: boolean): ChartTokens {
  const base = defaultTokens(isDark);
  const probe = document.createElement("span");
  probe.hidden = true;
  element.appendChild(probe);
  const resolve = (name: string, fallback: string, token = "") => {
    probe.style.color = token ? `var(${name}, var(${token}, ${sentinel}))` : `var(${name}, ${sentinel})`;
    const value = getComputedStyle(probe).color;
    return value && value !== sentinel ? value : fallback;
  };
  try {
    return {
      ...base,
      series: base.series.map((color, index) => resolve(`--chart-${index + 1}`, color)),
      ink: resolve("--chart-ink", base.ink, "--color-text"),
      muted: resolve("--chart-muted", base.muted, "--color-text-muted"),
      grid: resolve("--chart-grid", base.grid, "--color-border"),
      surface: resolve("--chart-surface", base.surface, "--color-surface"),
      font: getComputedStyle(element).fontFamily || base.font,
    };
  } finally {
    probe.remove();
  }
}
