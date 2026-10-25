/* Use case: Shapes "Build a prediction model" options and saved results for display.
What it does: Keeps server-written numbers as returned strings and explains why fields are unavailable. */

export const PREDICTION_METHOD = "prediction-model-v1";

export type PredictionOptions = {
  model: string;
  state: string;
  available: boolean;
  targets: { name: string; task: "classification" | "regression" }[];
  inputs: { name: string; kind: "numeric" | "category"; excluded_reason: string | null }[];
  maximum_inputs: number;
  maximum_rows: number;
  holdout_percent: number;
};

export type PredictionResult = {
  task: "classification" | "regression";
  target: string;
  positive_label: string | null;
  verdict: { status: "beats_guess" | "not_useful"; text: string };
  details: string[];
  metrics: Record<string, string>;
  baseline: Record<string, string>;
  weights: { input: string; level: string | null; weight: string; direction: string; label: string }[];
  warnings: string[];
  method: { name: string; inputs: string; split: string; seed: number; iterations: number };
  coverage: {
    source_rows: number;
    used_rows: number;
    missing_target_rows: number;
    training_rows: number;
    holdout_rows: number;
    encoded_columns: number;
    missing_inputs: Record<string, number>;
  };
  inputs: string[];
  exclusions: { column: string; reason: string }[];
  limitations: string[];
};

export const isPredictionMethod = (method?: string) => method === PREDICTION_METHOD;

export function inputChoices(options: PredictionOptions, target: string) {
  return options.inputs
    .filter(item => item.name !== target)
    .map(item => ({ ...item, disabled: item.excluded_reason !== null }));
}

export function metricRows(result: PredictionResult): [string, string, string][] {
  if (result.task === "classification")
    return [
      ["AUC (ranking quality, 0.50 = guessing)", result.metrics.auc, result.baseline.auc],
      ["Accuracy on held-back rows", result.metrics.accuracy, result.baseline.accuracy],
    ];
  return [
    ["Average error (MAE)", result.metrics.mae, result.baseline.mae],
    ["R² (1 = perfect, 0 = average)", result.metrics.r2, result.baseline.r2],
  ];
}

export function weightLabel(weight: PredictionResult["weights"][number]) {
  return weight.level === null ? weight.input : `${weight.input} = ${weight.level}`;
}
