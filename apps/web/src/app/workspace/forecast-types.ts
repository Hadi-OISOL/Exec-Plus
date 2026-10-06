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
  };
  uncertainty: {
    method: string;
    label: string;
    coverage_guaranteed: boolean;
    backtest_coverage?: { inside: number; count: number; label: string };
  };
  benchmark?: {
    method: string;
    accuracy: ForecastMetrics;
    beats_baseline_mae: boolean;
    mae_difference: string;
  };
  limitations: string[];
  commentary?: string[];
};
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
  state: "ready" | "needs_review" | "unsupported";
  revision_id: string;
  understanding_id: string | null;
  date_columns: string[];
  metrics: { name: string; unit: string; aggregations: string[] }[];
  limitations: string[];
  defaults: { coverage_start: string | null; coverage_end: string | null };
};

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
