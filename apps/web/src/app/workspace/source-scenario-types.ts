/* Use case: Defines exact source-derived scenario values for the workspace.
What it does: Separates declared changes, saved amounts and source evidence without browser arithmetic. */

import type { AnalysisSummary } from "./decision-types";

export const SOURCE_SCENARIO_METHOD = "source-unit-economics-v1";
export const CONSTRAINED_SCENARIO_METHOD = "source-unit-economics-constrained-v2";
export const isSourceScenarioMethod = (method?: string) => method === SOURCE_SCENARIO_METHOD || method === CONSTRAINED_SCENARIO_METHOD;
type SourceMethod = typeof SOURCE_SCENARIO_METHOD | typeof CONSTRAINED_SCENARIO_METHOD;
export const scenarioDrivers = ["price", "quantity", "variable_cost", "fixed_cost"] as const;
export type ScenarioDriver = typeof scenarioDrivers[number];
export const driverLabels: Record<ScenarioDriver, string> = {
  price: "Price", quantity: "Quantity", variable_cost: "Variable cost per unit", fixed_cost: "Included fixed cost",
};
export type SourceAlternative = { name: string } & Record<ScenarioDriver, string>;
export type SourceScenarioRequest = {
  model: SourceMethod;
  constraints?: ScenarioConstraint[] | null;
  basis: "per_unit" | "row_totals";
  quantity_column: string; sales_column: string; cost_column: string;
  fixed_cost_column: string | null;
  filters: { column: string; operator: string; value: string | number | boolean }[];
  alternatives: SourceAlternative[];
  sensitivity: { driver: ScenarioDriver; percent_changes: string[] } | null;
  parent_run_id?: string | null;
};
export const amountFields = ["quantity", "revenue", "variable_cost", "fixed_cost", "total_cost", "contribution", "remaining", "margin_percent"] as const;
export type AmountField = typeof amountFields[number];
export type ScenarioConstraint = { field: AmountField; operator: "minimum" | "maximum"; value: string; unit: string };
export type ScenarioConstraintCheck = ScenarioConstraint & { status: "passed" | "violated" | "unavailable"; actual: string | null; exact_actual: { numerator: string; denominator: string } | null; reason: string };
export type ScenarioAmounts = Record<Exclude<AmountField, "margin_percent">, string> & { margin_percent: string | null };
export const amountLabels: Record<AmountField, string> = {
  quantity: "Quantity", revenue: "Sales", variable_cost: "Variable costs", fixed_cost: "Included fixed costs",
  total_cost: "Total included costs", contribution: "Contribution before fixed costs", remaining: "Remaining after included costs", margin_percent: "Margin on selected costs",
};
export type SourceScenarioBody = {
  current: boolean;
  run: AnalysisSummary & {
    request: SourceScenarioRequest;
    result: {
      version: SourceMethod;
      constraints?: ScenarioConstraint[];
      baseline_constraints?: ScenarioConstraintCheck[];
      sample_count: number; basis: "per_unit" | "row_totals";
      baseline: ScenarioAmounts;
      alternatives: { name: string; assumptions: Record<ScenarioDriver, string>; result: ScenarioAmounts; difference: Record<Exclude<AmountField, "margin_percent">, string>; constraints?: ScenarioConstraintCheck[] }[];
      sensitivity: { driver: ScenarioDriver; reference: string; points: { percent_change: string; result: ScenarioAmounts; constraints?: ScenarioConstraintCheck[] }[] } | null;
      parent_run_id: string | null;
      assumptions: string[]; limitations: string[]; warnings: string[];
    };
    evidence: { query_id: string; units: Record<string, string>; result_checksum: string };
  };
};

export function blankSourceAlternative(index: number): SourceAlternative {
  return { name: `Alternative ${index}`, price: "0", quantity: "0", variable_cost: "0", fixed_cost: "0" };
}
