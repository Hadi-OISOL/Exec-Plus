/* Use case: Shapes inventory reorder requests and saved plans for the workspace.
What it does: Keeps typed item values as exact strings and leaves out any input taken from a column. */

export const REORDER_METHOD = "inventory-reorder-v1";
export const serviceLevels = ["0.90", "0.95", "0.975", "0.99"] as const;
export type ReorderInput = "stock" | "reorder_point" | "lead_time_days" | "unit_cost";
export const reorderInputs: ReorderInput[] = ["stock", "reorder_point", "lead_time_days", "unit_cost"];
export const reorderLabels: Record<ReorderInput, string> = { stock: "Stock on hand", reorder_point: "Reorder point", lead_time_days: "Lead time (days)", unit_cost: "Unit cost" };
export type TypedItem = { item: string } & Record<ReorderInput, string>;
export type ReorderItemRequest = { item: string; stock: string | null; reorder_point: string | null; lead_time_days: number | null; unit_cost: string | null };

export function reorderItems(rows: TypedItem[], fromColumn: Partial<Record<ReorderInput, string>>): ReorderItemRequest[] {
  const value = (row: TypedItem, key: ReorderInput) => (fromColumn[key] || !row[key].trim() ? null : row[key].trim());
  return rows.filter(row => row.item.trim()).map(row => {
    const lead = value(row, "lead_time_days");
    return { item: row.item.trim(), stock: value(row, "stock"), reorder_point: value(row, "reorder_point"), lead_time_days: lead === null ? null : Number(lead), unit_cost: value(row, "unit_cost") };
  });
}

export type ReorderRow = {
  rank: number; candidate: string; stock: string; reorder_point: string; lead_time_days: number;
  total_demand: string; mean_daily_demand: string; daily_demand_deviation: string; lead_time_demand: string;
  safety_stock: string; target_level: string; days_of_cover: string | null; below_reorder_point: boolean;
  recommended_quantity: number; quantity: number; unit_cost: string | null; cost: string | null; urgency_weight: number | null;
};
export type ReorderResult = {
  version: string; status: string; funding: "complete" | "budget_limited" | "unresolved"; reason: string;
  history: { start: string; end: string; calendar_days: number };
  budget: string | null; cost: string | null; unused_budget: string | null; items_to_order: number;
  allocations: ReorderRow[]; verification: Record<string, string>; assumptions: string[]; limitations: string[];
};
