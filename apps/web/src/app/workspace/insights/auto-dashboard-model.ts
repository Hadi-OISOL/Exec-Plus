/* Use case: Reads the auto-dashboard-v1 payload that the server builds for each dataset.
What it does: Types tiles and candidates, and maps a tile to an existing descriptive study method so it can be saved and pinned on a six-pin dashboard. */

import type { InsightChart } from "./insights-model";

export type DashboardTile = {
  id: string;
  kind: string;
  title: string;
  reason: string;
  columns: string[];
  unit?: string | null;
  kpi?: { label: string; value: string; unit?: string | null } | null;
  chart?: InsightChart | null;
  summary?: string | null;
  analyst?: string | null;
  query_ids: string[];
};
export type AutoDashboard = {
  version: string;
  id: string;
  number: number;
  shared: boolean;
  owned: boolean;
  created_at: string;
  dataset_name: string;
  definition_state: string;
  needs_confirmation: boolean;
  sources: { revision_id: string; understanding_id?: string | null }[];
  brief_summary: { rows: string; columns: number; date_coverage?: { column: string; min: string; max: string; months_with_data: string } | null; analyst_findings: string[] };
  selection: { route: string; fallback_reason?: string | null };
  tiles: DashboardTile[];
  candidates: { id: string; kind: string; title: string; columns: string[] }[];
  limitations: string[];
};
export type AutoDashboardResponse = { dashboard: AutoDashboard; shared: { id: string; number: number; created_at: string }[] };

export type StudyMethod = { kind: "metric" | "distribution"; column: string; aggregation: string; group_by: string[] };

export function studyMethod(tile: DashboardTile): StudyMethod | null {
  const aggregation = tile.id.split(":")[1];
  const [first, second] = tile.columns;
  if (tile.kind === "kpi" && first) return { kind: "metric", column: first, aggregation, group_by: [] };
  if ((tile.kind === "trend" || tile.kind === "top") && first && second) return { kind: "metric", column: first, aggregation, group_by: [second] };
  if (tile.kind === "share" && first && second) return { kind: "metric", column: first, aggregation: "sum", group_by: [second] };
  if (tile.kind === "category" && first) return { kind: "distribution", column: first, aggregation: "count", group_by: [] };
  return null;
}

export function selectionNote(dashboard: AutoDashboard): string {
  const route = dashboard.selection.route;
  if (route === "user:edit") return "You chose these tiles.";
  if (route.startsWith("deterministic:")) return "Tiles were picked by a fixed score: column roles, group sizes and checked findings.";
  return "A language model ranked the candidate tiles and wrote their titles; every value comes from a server query.";
}
