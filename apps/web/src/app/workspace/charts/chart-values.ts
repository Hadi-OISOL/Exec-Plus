/* Use case: Keeps every chart in the kit faithful to the exact values a query returned.
What it does: Adds plain decimal strings exactly, folds small slices into "Other", formats display shares, picks a chart form and builds exact table views and count-up frames. */

import { compareExactNumeric, displayMetric, exactCell, plotNumber } from "../visualization-values";
import type { VisualizationCell } from "../visualization-values";

export type Slice = { label: string; value: string; members?: Slice[] };
export type Series = { name: string; values: (string | null)[] };
export type TreeNode = { id?: string; name: string; value?: string; children?: TreeNode[] };
export type ChartSpec = { title: string; subtitle?: string; unit?: string } & (
  | { kind: "donut"; slices: Slice[]; total?: string; maxSlices?: number }
  | { kind: "bar"; categories: string[]; series: Series[]; horizontal?: boolean }
  | { kind: "line"; x: string[]; series: Series[]; area?: boolean }
  | { kind: "histogram"; bins: { label: string; count: string }[] }
  | { kind: "scatter"; xName: string; yName: string; points: { x: string; y: string; label?: string }[] }
  | { kind: "heatmap"; x: string[]; y: string[]; cells: { x: string; y: string; value: string | null }[] }
  | { kind: "boxplot"; groups: { label: string; min: string; q1: string; median: string; q3: string; max: string }[]; outliers?: { group?: string; value: string; count?: string }[] }
  | { kind: "treemap"; nodes: TreeNode[] }
  | { kind: "sankey"; nodes: string[]; links: { source: string; target: string; value: string }[] }
  | { kind: "tree"; root: TreeNode }
);
export type ChartKind = ChartSpec["kind"];
export type AnswerChart = "bar" | "line" | "dot" | "pie";

const plainDecimal = /^([+-]?)(\d*)(?:\.(\d*))?$/;

function parts(value: string) {
  const match = value.trim().match(plainDecimal);
  if (!match || !(match[2] || match[3])) return null;
  const fraction = match[3] ?? "";
  return { units: BigInt(`${match[1] === "-" ? "-" : ""}${match[2] || "0"}${fraction}`), scale: fraction.length };
}

export function addExact(values: string[]): string | null {
  const parsed = values.map(parts);
  if (!parsed.length || parsed.some(item => item === null)) return null;
  const scale = Math.max(...parsed.map(item => item!.scale));
  const sum = parsed.reduce((total, item) => total + item!.units * BigInt(10) ** BigInt(scale - item!.scale), BigInt(0));
  const negative = sum < BigInt(0);
  const digits = (negative ? -sum : sum).toString().padStart(scale + 1, "0");
  const whole = digits.slice(0, digits.length - scale);
  return `${negative ? "-" : ""}${whole}${scale ? `.${digits.slice(digits.length - scale)}` : ""}`;
}

export function shareText(value: string, total: string | null): string {
  const part = plotNumber(value);
  const whole = total === null ? null : plotNumber(total);
  if (part === null || !whole) return "";
  const share = (part / whole) * 100;
  if (share > 0 && share < 0.1) return "<0.1%";
  return `${share.toFixed(1)}%`;
}

export function donutEligible(values: VisualizationCell[]): boolean {
  const text = values.map(value => (value === null ? null : String(value)));
  return text.length >= 2 && text.every(value => value !== null && parts(value) !== null && !value.trim().startsWith("-")) && text.some(value => (plotNumber(value) ?? 0) > 0);
}

export function bucketSlices(slices: Slice[], maxSlices = 7): Slice[] {
  const ordered = [...slices].sort((left, right) => compareExactNumeric(right.value, left.value) || left.label.localeCompare(right.label));
  if (ordered.length <= maxSlices) return ordered;
  const kept = ordered.slice(0, Math.max(1, maxSlices - 1));
  const rest = ordered.slice(kept.length);
  const total = addExact(rest.map(slice => slice.value));
  return total === null ? ordered : [...kept, { label: `Other (${rest.length} groups)`, value: total, members: rest }];
}

export function selectAnswerChart(input: { recommended?: string | null; fallback: AnswerChart; values: VisualizationCell[]; allowLine: boolean }): AnswerChart {
  const wanted = (input.recommended ?? "").toLowerCase();
  const pie = donutEligible(input.values);
  if (["pie", "donut", "share", "composition"].includes(wanted)) return pie ? "pie" : "bar";
  if (["line", "area", "time", "trend"].includes(wanted)) return input.allowLine ? "line" : "bar";
  if (["scatter", "dot", "relationship"].includes(wanted)) return "dot";
  if (["bar", "column", "ranking", "comparison"].includes(wanted)) return "bar";
  if (input.fallback === "pie" && !pie) return "bar";
  if (input.fallback === "line" && !input.allowLine) return "bar";
  return input.fallback;
}

function flatten(nodes: TreeNode[], path: string[] = []): string[][] {
  return nodes.flatMap(node => [[[...path, node.name].join(" › "), node.value ?? ""], ...flatten(node.children ?? [], [...path, node.name])]);
}

export function specTable(spec: ChartSpec): { columns: string[]; rows: string[][] } {
  const cell = (value: string | null | undefined) => exactCell(value ?? null);
  switch (spec.kind) {
    case "donut": {
      const total = spec.total ?? addExact(spec.slices.map(slice => slice.value));
      return { columns: ["Group", spec.unit ? `Value (${spec.unit})` : "Value", "Share"], rows: spec.slices.map(slice => [slice.label, slice.value, shareText(slice.value, total)]) };
    }
    case "bar": return { columns: ["Group", ...spec.series.map(series => series.name)], rows: spec.categories.map((category, index) => [category, ...spec.series.map(series => cell(series.values[index]))]) };
    case "line": return { columns: ["Period", ...spec.series.map(series => series.name)], rows: spec.x.map((x, index) => [x, ...spec.series.map(series => cell(series.values[index]))]) };
    case "histogram": return { columns: ["Range", "Count"], rows: spec.bins.map(bin => [bin.label, bin.count]) };
    case "scatter": return { columns: ["Point", spec.xName, spec.yName], rows: spec.points.map((point, index) => [point.label ?? String(index + 1), point.x, point.y]) };
    case "heatmap": return { columns: ["", ...spec.x], rows: spec.y.map(y => [y, ...spec.x.map(x => cell(spec.cells.find(item => item.x === x && item.y === y)?.value))]) };
    case "boxplot": return { columns: ["Group", "Lowest", "Lower quartile", "Median", "Upper quartile", "Highest"], rows: [...spec.groups.map(group => [group.label, group.min, group.q1, group.median, group.q3, group.max]), ...(spec.outliers ?? []).map(point => [`Unusual value${point.count && point.count !== "1" ? ` × ${point.count}` : ""}`, point.value, "", "", "", ""])] };
    case "treemap": return { columns: ["Group", "Value"], rows: flatten(spec.nodes) };
    case "sankey": return { columns: ["From", "To", "Value"], rows: spec.links.map(link => [link.source, link.target, link.value]) };
    case "tree": return { columns: ["Path", "Value"], rows: flatten([spec.root]) };
  }
}

const kindNames: Record<ChartKind, string> = { donut: "Donut chart", bar: "Bar chart", line: "Line chart", histogram: "Histogram", scatter: "Scatter plot", heatmap: "Heatmap", boxplot: "Box plot", treemap: "Treemap", sankey: "Flow diagram", tree: "Tree diagram" };

export function chartSummary(spec: ChartSpec): string {
  const { rows } = specTable(spec);
  const lead = spec.kind === "donut" ? bucketSlices(spec.slices, spec.maxSlices)[0] : null;
  const largest = lead ? ` Largest: ${lead.label}, ${displayMetric(lead.value)}${spec.unit ? ` ${spec.unit}` : ""}.` : "";
  return `${kindNames[spec.kind]}: ${spec.title}. ${rows.length} ${rows.length === 1 ? "item" : "items"}.${largest} Use arrow keys to step through items, or view as a table for exact values.`;
}

export function countUpFrames(display: string, steps = 24): string[] {
  const match = display.match(/^([+-]?)(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?$/);
  const target = match ? Number(`${match[1]}${match[2].replaceAll(",", "")}${match[3] ? `.${match[3]}` : ""}`) : NaN;
  if (!match || !Number.isFinite(target) || target === 0) return [display];
  const decimals = match[3]?.length ?? 0;
  const grouped = match[2].includes(",");
  const frames = Array.from({ length: steps - 1 }, (_, index) => {
    const progress = 1 - (1 - (index + 1) / steps) ** 3;
    const text = Math.abs(target * progress).toFixed(Math.min(decimals, 20));
    const [whole, fraction] = text.split(".");
    return `${target < 0 ? "-" : match[1] === "+" ? "+" : ""}${grouped ? whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") : whole}${fraction ? `.${fraction}` : ""}`;
  });
  return [...frames, display];
}

function roundDecimal(value: string, places: number): string {
  const parsed = parts(value);
  if (!parsed || parsed.scale <= places) return value;
  const divisor = BigInt(10) ** BigInt(parsed.scale - places);
  const negative = parsed.units < BigInt(0);
  const magnitude = negative ? -parsed.units : parsed.units;
  const rounded = (magnitude + divisor / BigInt(2)) / divisor;
  const digits = rounded.toString().padStart(places + 1, "0");
  const text = `${digits.slice(0, digits.length - places)}${places ? `.${digits.slice(digits.length - places)}` : ""}`;
  return `${negative && rounded > BigInt(0) ? "-" : ""}${text}`;
}

export function readableMetric(value: VisualizationCell | undefined): string {
  if (value === null || value === undefined) return exactCell(value);
  const text = String(value).trim();
  const match = text.match(plainDecimal);
  if (!match || !(match[2] || match[3])) return displayMetric(value);
  const whole = (match[2] || "0").replace(/^0+/, "");
  const fraction = match[3] ?? "";
  const places = whole ? Math.max(0, Math.min(2, 4 - whole.length)) : (fraction.match(/^0*/)?.[0].length ?? 0) + 3;
  return displayMetric(roundDecimal(text, Math.min(fraction.length, places)));
}

export function humanName(name: string): string {
  return name.replaceAll("_", " ").replace(/\s+/g, " ").trim() || name;
}

export function humanizeFields(text: string, fields: string[]): string {
  const names = [...new Set(fields)].filter(field => field.includes("_")).sort((left, right) => right.length - left.length);
  if (!names.length) return text;
  const pattern = new RegExp(`(?<![A-Za-z0-9_])(${names.map(name => name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})(?![A-Za-z0-9_])`, "g");
  return text.replace(pattern, field => humanName(field));
}

export function humanizeSpec(spec: ChartSpec, fields: string[]): ChartSpec {
  const words = (value: string) => humanizeFields(value, fields);
  const base = { ...spec, title: words(spec.title), subtitle: spec.subtitle && words(spec.subtitle) };
  switch (base.kind) {
    case "donut": return { ...base, slices: base.slices.map(slice => ({ ...slice, label: words(slice.label) })) };
    case "bar": return { ...base, categories: base.categories.map(words), series: base.series.map(series => ({ ...series, name: words(series.name) })) };
    case "line": return { ...base, series: base.series.map(series => ({ ...series, name: words(series.name) })) };
    case "scatter": return { ...base, xName: words(base.xName), yName: words(base.yName) };
    case "heatmap": return { ...base, x: base.x.map(words), y: base.y.map(words), cells: base.cells.map(cell => ({ ...cell, x: words(cell.x), y: words(cell.y) })) };
    case "boxplot": return { ...base, groups: base.groups.map(group => ({ ...group, label: words(group.label) })), outliers: base.outliers?.map(point => ({ ...point, group: point.group && words(point.group) })) };
    default: return base;
  }
}
