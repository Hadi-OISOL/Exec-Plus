/* Use case: Gives every kit chart one shared light and dark appearance.
What it does: Supplies the receipt palette (ink green, saffron, saffron-ink, mint, olive, brown, slate-teal, sand) as fallbacks and resolves the page's design tokens (--chart-1…8, then --color-text, --color-text-muted, --color-border, --color-surface) at render time, including a brown → paper → green diverging ramp mixed from those tokens. */

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
  series: ["#0f3b2e", "#ff9f1c", "#8a4600", "#9fd8b8", "#6b7f3a", "#a0522d", "#2f6f6f", "#d9b26f"],
  ink: "#14201b", muted: "#5a665f", grid: "#d8cfb6", surface: "#f4ecd8", other: "#a39a84",
  font: "Inter, system-ui, sans-serif",
  diverging: ["#a0522d", "#c48a6c", "#e2c3ad", "#f4ecd8", "#a9c9b3", "#5b8f77", "#0f3b2e"],
};
const dark: ChartTokens = {
  series: ["#7fc9a3", "#ff9f1c", "#e0924a", "#c7eed8", "#a8bf6a", "#d58a62", "#6fb3b3", "#e8c98a"],
  ink: "#efe7d4", muted: "#a9b8ad", grid: "#2a4a3d", surface: "#0f2a21", other: "#6e8277",
  font: light.font,
  diverging: ["#d58a62", "#a86a4c", "#5c4537", "#0f2a21", "#2d5744", "#56937a", "#7fc9a3"],
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
  const compute = (expression: string, fallback: string) => {
    probe.style.color = expression;
    const value = getComputedStyle(probe).color;
    return value && value !== sentinel && /^(rgb|#|color\()/.test(value) ? value : fallback;
  };
  const resolve = (name: string, fallback: string, token = "") => compute(token ? `var(${name}, var(${token}, ${sentinel}))` : `var(${name}, ${sentinel})`, fallback);
  const channels = (color: string) => color.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/)?.slice(1, 4).map(Number) ?? null;
  const mix = (color: string, share: number, surface: string, fallback: string) => {
    const [from, to] = [channels(color), channels(surface)];
    return from && to ? `rgb(${from.map((value, index) => Math.round(value * share / 100 + to[index] * (1 - share / 100))).join(", ")})` : fallback;
  };
  try {
    const series = base.series.map((color, index) => resolve(`--chart-${index + 1}`, color));
    const surface = resolve("--chart-surface", base.surface, "--color-surface");
    const [brown, green] = [series[5], series[0]];
    return {
      ...base,
      series,
      surface,
      ink: resolve("--chart-ink", base.ink, "--color-text"),
      muted: resolve("--chart-muted", base.muted, "--color-text-muted"),
      grid: resolve("--chart-grid", base.grid, "--color-border"),
      font: getComputedStyle(element).fontFamily || base.font,
      diverging: [brown, mix(brown, 60, surface, base.diverging[1]), mix(brown, 28, surface, base.diverging[2]), surface, mix(green, 28, surface, base.diverging[4]), mix(green, 60, surface, base.diverging[5]), green],
    };
  } finally {
    probe.remove();
  }
}
