/* Use case: Preserves exact calendar anomaly and distribution comparison evidence.
What it does: Separates chronological scores from snapshot findings and retains exact rational distances. */
import type { AnalysisBody, AnalysisSummary } from "./decision-types";

export const SEASONAL_METHOD = "seasonal-residual-mad-iqr-v1";
export const DRIFT_METHOD = "empirical-window-distance-v1";
export const ROLLING_METHOD = "rolling-reference-mad-iqr-v1";
export type CalendarMethod = "seasonal" | "drift" | "rolling";
export function isCalendarMethod(method?: string) { return method === SEASONAL_METHOD || method === DRIFT_METHOD || method === ROLLING_METHOD; }
export type ExactFraction = { numerator: string; denominator: string; display: string; display_exact: boolean };
export function fractionText(value: ExactFraction) { return `${value.display_exact ? "" : "≈ "}${value.display} (${value.numerator}/${value.denominator})`; }
export type CalendarFinding = { id: string; period?: string; value?: string; baseline?: string; absolute_difference?: string; score?: string | null; kind?: string };
type Common = { version: string; method_version: string; frequency: string; materiality: string; findings: CalendarFinding[]; limitations: string[] };
export type SeasonalResult = Common & {
  version: "temporal-anomaly-v1";
  sample_count: number; training_periods: number; evaluated_periods: number; flagged_periods: number;
  season_length: number; threshold: string;
  reference: { training_start: string; training_end: string; residual_count: number; baseline: string; mad: string; q1: string; q3: string; iqr: string; scale_method: string; lower_residual_fence: string | null; upper_residual_fence: string | null };
  history: { period: string; actual: string; phase: string; reference_period: string | null; seasonal_reference: string | null; expected: string | null; residual: string | null; absolute_difference: string | null; score: string | null; flagged: boolean | null }[];
};
export type RollingResult = Common & {
  version: "rolling-anomaly-v1"; sample_count: number; evaluated_periods: number; flagged_periods: number;
  reference_window: number; season_length: number; evaluation_start: string; threshold: string;
  history: { period: string; actual: string; phase: string; expected: string | null; absolute_difference: string | null; score: string | null; flagged: boolean | null;
    reference: { start: string; end: string; count: number; step: number; median: string; mad: string; iqr: string; scale_method: string } | null }[];
};
export type DriftResult = Common & {
  version: "calendar-distribution-drift-v1";
  minimum_cdf_separation: string; maximum_cdf_separation: ExactFraction; wasserstein_distance: ExactFraction;
  median_change: string; review_flag: boolean;
  windows: Record<"reference" | "comparison", { start: string; end: string; count: number; distinct_count: number; minimum: string; maximum: string; median: string; q1: string; q3: string }>;
  observations: { window: string; period: string; value: string }[];
  distribution: { value: string; reference_count: number; comparison_count: number; reference_cumulative: number; comparison_cumulative: number; reference_cdf: ExactFraction; comparison_cdf: ExactFraction; absolute_cdf_difference: ExactFraction; next_value: string | null; distance_contribution: ExactFraction }[];
};
export type CalendarBody = Omit<AnalysisBody, "run"> & { run: AnalysisSummary & {
  method_version: string; request: { metric: string; aggregation: string; frequency: string; filters: object[] };
  result: SeasonalResult | DriftResult | RollingResult; evidence: AnalysisBody["run"]["evidence"] & { calendar_query_ids: string[][]; matching_records: number };
} };
