/* Use case: Reads the insights-v1 analyst overview (docs/insights-engine.md) for the overview screen.
What it does: Types the payload, maps each server chart into an exact chart-kit specification and turns proposed action payloads into workspace navigation intents. */

import type { ChartSpec } from "../charts/chart-values";

type Axis = { field: string; label: string; unit?: string | null };
export type InsightChart = { type: string; title: string; x: Axis; y: Axis; value?: Axis | null; rows: Record<string, string | number | null>[]; outliers?: { value: string; count?: string | number | null }[] };
export type InsightAction = { id: string; kind: string; label: string; payload: Record<string, unknown> & { type: string } };
export type InsightCheck = { label: string; primary: string; secondary: string; method: string; query_id?: string | null; agrees: boolean };
export type InsightCard = {
  id: string;
  analyst: string;
  title: string;
  summary: string;
  statements?: string[];
  evidence?: { label: string; value: string; unit?: string | null }[];
  chart?: InsightChart | null;
  cross_check?: { status: string; checks: InsightCheck[] } | null;
  actions?: InsightAction[];
};
export type InsightsPayload = {
  version: string;
  dataset_name: string;
  definition_state: string;
  narration?: { route: string; fallback_reason?: string | null };
  kpis: { id: string; label: string; value: string; unit?: string | null; detail?: string | null }[];
  insights: InsightCard[];
  next_actions?: InsightAction[];
  cross_check?: { verified: number; dropped: { id: string; reason: string }[] };
  limitations?: string[];
};
export type ActionIntent =
  | { type: "ask"; question: string }
  | { type: "prepare" }
  | { type: "anomalies"; metric?: string }
  | { type: "scenario"; metric: string; aggregation: "avg" | "sum" }
  | { type: "review" };

const text = (value: unknown) => (value === null || value === undefined ? null : String(value));
const unique = (values: (string | null)[]) => [...new Set(values.filter((value): value is string => value !== null))];

export function chartSpecFromInsight(chart: InsightChart | null | undefined): ChartSpec | null {
  if (!chart?.rows?.length) return null;
  const { rows, x, y } = chart;
  const unit = y.unit ?? undefined;
  const subtitle = [y.label, unit].filter(Boolean).join(" · ") || undefined;
  switch (chart.type) {
    case "pie":
    case "donut": return { kind: "donut", title: chart.title, unit, maxSlices: 8, slices: rows.map(row => {
      const label = text(row[x.field]) ?? "Missing";
      return { label, value: text(row[y.field]) ?? "0", ...(/^other\b/i.test(label) ? { members: [] } : {}) };
    }) };
    case "bar": return { kind: "bar", title: chart.title, subtitle, unit, horizontal: true, categories: rows.map(row => text(row[x.field]) ?? "Missing"), series: [{ name: y.label, values: rows.map(row => text(row[y.field])) }] };
    case "histogram": return { kind: "histogram", title: chart.title, subtitle: [x.label, x.unit].filter(Boolean).join(" · ") || undefined, bins: rows.map(row => ({ label: text(row[x.field]) ?? "", count: text(row[y.field]) ?? "0" })) };
    case "heatmap": {
      const field = chart.value?.field ?? "score";
      const xs = unique(rows.map(row => text(row[x.field])));
      const ys = unique(rows.map(row => text(row[y.field])));
      const cells = rows.map(row => ({ x: text(row[x.field]) ?? "", y: text(row[y.field]) ?? "", value: text(row[field]) }));
      const square = xs.length === ys.length && xs.every(name => ys.includes(name));
      if (!square || xs.length < 3) return { kind: "heatmap", title: chart.title, x: xs, y: ys, cells };
      const lower = cells.filter(cell => xs.indexOf(cell.x) < xs.indexOf(cell.y));
      return { kind: "heatmap", title: chart.title, x: xs.slice(0, -1), y: xs.slice(1), cells: lower };
    }
    case "box": return { kind: "boxplot", title: chart.title, subtitle, unit, groups: rows.map(row => ({ label: text(row[x.field]) ?? "", min: text(row.low) ?? "", q1: text(row.q1) ?? "", median: text(row.median) ?? "", q3: text(row.q3) ?? "", max: text(row.high) ?? "" })),
      outliers: (chart.outliers ?? []).map(point => ({ group: text(rows[0]?.[x.field]) ?? undefined, value: String(point.value), count: text(point.count) ?? undefined })) };
    case "scatter": return { kind: "scatter", title: chart.title, xName: x.label, yName: y.label, points: rows.flatMap(row => { const px = text(row[x.field]); const py = text(row[y.field]); return px !== null && py !== null ? [{ x: px, y: py }] : []; }) };
    default: return null;
  }
}

export function insightFields(payload: InsightsPayload): string[] {
  const names = new Set<string>();
  const add = (value: unknown) => { if (typeof value === "string" && value) names.add(value); };
  for (const card of payload.insights) {
    const chart = card.chart;
    if (chart) {
      [chart.x?.label, chart.y?.label, chart.value?.label].forEach(add);
      if (chart.type === "heatmap") chart.rows.forEach(row => { add(row[chart.x.field]); add(row[chart.y.field]); });
      if (chart.type === "box") chart.rows.forEach(row => add(row[chart.x.field]));
      if (card.analyst === "quality" && chart.type === "bar") chart.rows.forEach(row => add(row[chart.x.field]));
    }
    for (const action of [...(card.actions ?? []), ...(payload.next_actions ?? [])]) {
      add(action.payload?.metric); add(action.payload?.column);
      if (Array.isArray(action.payload?.columns)) action.payload.columns.forEach(add);
    }
  }
  return [...names];
}

export function actionIntent(action: InsightAction): ActionIntent | null {
  const payload = action.payload ?? { type: "" };
  const metric = typeof payload.metric === "string" ? payload.metric : undefined;
  switch (payload.type) {
    case "ask": return typeof payload.question === "string" && payload.question ? { type: "ask", question: payload.question } : null;
    case "prepare": return { type: "prepare" };
    case "anomalies": return { type: "anomalies", metric };
    case "patterns": {
      const columns = Array.isArray(payload.columns) ? payload.columns.map(String) : [];
      return { type: "ask", question: columns.length >= 2 ? `Find patterns between ${columns[0]} and ${columns[1]}` : "Find patterns in my data" };
    }
    case "scenario": return metric && (payload.aggregation === "avg" || payload.aggregation === "sum") ? { type: "scenario", metric, aggregation: payload.aggregation } : null;
    case "review_meaning": return { type: "review" };
    default: return null;
  }
}

export const analystNames: Record<string, string> = {
  quality: "Data quality", composition: "Composition", distribution: "Distribution",
  segment: "Segments", relationship: "Relationships", outlier: "Unusual values",
};
