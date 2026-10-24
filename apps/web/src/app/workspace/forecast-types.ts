/* Use case: Defines the forecast wire contract used by the analysis workspace.
What it does: Keeps exact server values and separates saved predictions, holdout tests and later observations. */

export type ForecastMetrics = {
  count: number;
  mae: string | null;
  rmse: string | null;
  wape_percent: string | null;
  mape_percent: string | null;
  mape_count: number;
  zero_actual_count: number;
};
export type ForecastPoint = {
  period: string;
  estimate: string;
  actual?: string | null;
  lower: string;
  upper: string;
  error?: string | null;
  absolute_error?: string | null;
  status?: "observed" | "pending";
};
type Window = { start: string; end: string; count: number };
export type ForecastResult = {
  version: string;
  frequency: "daily" | "monthly";
  horizon: number;
  method: { id: string; version: number; parameters: Record<string, unknown> };
  windows: {
    training: Window;
    validation: Window;
    test: Window;
    test_training: Window;
    forecast_training: Window;
  };
  history: { period: string; actual: string }[];
  backtest: ForecastPoint[];
  accuracy: ForecastMetrics;
  predictions: ForecastPoint[];
  selection: {
    criterion: string;
    candidates: {
      method: string;
      parameters: object;
      metrics: ForecastMetrics;
    }[];
    registry_version?: string;
    requested_family?: string;
    folds?: { training: Window; validation: Window }[];
    excluded?: { method: string; reason: string }[];
    state_updates_bound?: number;
    state_updates_limit?: number;
  };
  uncertainty: {
    method: string;
    label: string;
    coverage_guaranteed: boolean;
    backtest_coverage?: { inside: number; count: number; label: string };
  };
  regressors?: ForecastRegressors;
  benchmark?: {
    method: string;
    accuracy: ForecastMetrics;
    beats_baseline_mae: boolean;
    mae_difference: string;
  };
  limitations: string[];
  commentary?: string[];
};
export type RegressorSummary = {
  method: string;
  parameters: Record<string, unknown>;
  validation_mae: string;
  test_mae: string;
};
export type ForecastRegressors = {
  method: string;
  calendar: "day_of_week" | "month_of_year";
  event_declared: boolean;
  future_event_periods: string[];
  best_without_regressors: RegressorSummary | null;
  best_with_regressors: RegressorSummary | null;
  selected: "calendar_regression" | "smoothing";
  rule: string;
  effects: Record<string, string> | null;
  effects_label: string;
};
export type ForecastEngine = "basic-v1" | "advanced-v2" | "advanced-v3" | "advanced-v4";
export type ForecastEvidence = {
  query_ids: string[];
  sources: object[];
  definition: object;
  unit: string;
  limitations: string[];
};
export type ForecastRun = {
  id: string;
  name: string;
  dataset_id: string;
  upload_id: string;
  revision_id: string;
  understanding_id: string;
  method: string;
  method_version: string;
  request: {
    engine?: ForecastEngine;
    method_family?: string;
    event_column?: string;
    future_event_periods?: string[];
    metric: string;
    time_column: string;
    aggregation: string;
    frequency: "daily" | "monthly";
    horizon: number;
    coverage_start: string;
    coverage_end: string;
  };
  evidence: ForecastEvidence;
  result: ForecastResult;
  created_at: string;
};
export type ForecastComparison = {
  id: string;
  forecast_id: string;
  upload_id: string;
  evidence: ForecastEvidence;
  result: {
    rows: ForecastPoint[];
    metrics: ForecastMetrics;
    observed_count: number;
    pending_count: number;
    commentary?: string[];
    limitations?: string[];
  };
  created_at: string;
};
export type ForecastSummary = Pick<
  ForecastRun,
  | "id"
  | "name"
  | "created_at"
  | "upload_id"
  | "revision_id"
  | "understanding_id"
  | "method"
  | "method_version"
  | "request"
>;
export type ComparisonSummary = Pick<
  ForecastComparison,
  "id" | "forecast_id" | "created_at" | "upload_id"
>;
export type ForecastOptions = {
  advanced_methods?: { id: string; label: string; requires_season: boolean }[];
  event_columns?: string[];
  meaning_state?: string;
  blockers?: { code: string; message: string }[];
  state: "ready" | "needs_review" | "unsupported";
  revision_id: string;
  understanding_id: string | null;
  date_columns: string[];
  metrics: { name: string; unit: string; aggregations: string[] }[];
  limitations: string[];
  defaults: { coverage_start: string | null; coverage_end: string | null };
  quick_start?: ForecastQuickStart;
};

export type ForecastQuickStart =
  | {
      kind: "forecast";
      message: string;
      name: string;
      time_column: string;
      metric: string;
      unit: string;
      aggregation: string;
      frequency: "daily" | "monthly";
      horizon: number;
      coverage_start: string;
      coverage_end: string;
      periods: number;
    }
  | {
      kind: "no_timeline";
      title: string;
      message: string;
      alternatives: { tool: "unusual_values" | "patterns" | "scenario"; label: string; description: string; available: boolean }[];
    }
  | { kind: "needs_review" | "advanced" | "too_short"; message: string };

export function advancedMinimumHistory(
  frequency: "daily" | "monthly",
  horizon: number,
  method: string,
  calibrated = false,
): number | null {
  if (!Number.isInteger(horizon) || horizon < 1) return null;
  const holdout = Math.max(horizon, frequency === "daily" ? 4 : 3);
  const training = method === "holt_winters_additive"
    ? (frequency === "daily" ? 14 : 24)
    : (frequency === "daily" ? 14 : 6);
  return training + 4 * holdout + (calibrated ? 8 + holdout : 0);
}

export function eventPeriods(text: string): string[] {
  return text.split(/[\s,]+/).filter(Boolean);
}

export function forecastRows(
  predictions: ForecastPoint[],
  comparison?: ForecastComparison,
): ForecastPoint[] {
  if (!comparison)
    return predictions.map((point) => ({
      ...point,
      actual: null,
      error: null,
      absolute_error: null,
      status: "pending",
    }));
  const observed = new Map(
    comparison.result.rows.map((point) => [point.period, point]),
  );
  return predictions.map((point) => {
    const match = observed.get(point.period);
    return {
      ...point,
      actual: match?.actual ?? null,
      error: match?.error ?? null,
      absolute_error: match?.absolute_error ?? null,
      status: match?.status ?? "pending",
    };
  });
}
