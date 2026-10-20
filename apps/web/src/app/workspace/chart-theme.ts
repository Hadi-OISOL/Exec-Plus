/* Use case: Makes the attributed Lieflat/documd chart presets follow the shared design tokens in both appearances.
What it does: Maps each preset's fixed colour to its role in the chart-kit tokens (ink, muted, grid, series) and swaps the preset font for the page font; data, callbacks and exact values remain intact. */

import type { ChartTokens } from "./charts/chart-tokens";

type Role = "ink" | "muted" | "grid" | "primary" | "negative";
const roles: Record<string, Role> = {
  "#deddd6": "grid", "#e0e8e2": "grid", "#a8bdb4": "grid",
  "#53625f": "muted", "#304c43": "muted", "#929e99": "muted", "#8f8e88": "muted",
  "#173e3b": "ink", "#213a32": "ink", "#123e32": "ink", "#23483d": "ink",
  "#176c64": "primary", "#176b57": "primary", "#a56730": "negative",
};

function recolor(value: string, tokens: ChartTokens): string {
  const role = roles[value.toLowerCase()];
  return role === "primary" ? tokens.series[0] : role === "negative" ? tokens.series[1] : role ? tokens[role] : value;
}

export function chartTheme<T>(value: T, tokens: ChartTokens, property = ""): T {
  if (typeof value === "string") {
    if (property === "fontFamily") return tokens.font as T;
    return (property === "color" || property.endsWith("Color") ? recolor(value, tokens) : value) as T;
  }
  if (Array.isArray(value)) return (property === "data" ? value : value.map(item => chartTheme(item, tokens, property))) as T;
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, chartTheme(item, tokens, key)])) as T;
  return value;
}
