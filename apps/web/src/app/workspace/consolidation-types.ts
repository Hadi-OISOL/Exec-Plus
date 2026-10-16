/* Use case: Describes explicit company worksheet inputs and exact saved output.
What it does: Keeps account mappings, declared rates and raw source rows typed without numerical browser calculations. */

export type CompanyOption = { workspace_id: string; name: string; datasets: { id: string; name: string; uploads: { id: string; filename: string }[] }[] };
export type SourceOptions = { workspace_id: string; dataset_id: string; upload_id: string; revision_id: string; understanding_id: string; name: string; row_count: number; accounts: string[]; counterparties: string[]; amounts: { name: string; currency: string }[] };
export type Mapping = { account: string; group_account: string; rate_key: string };
export type Rate = { key: string; basis: "closing" | "transaction_average" | "historical"; value: string; as_of: string; reference: string };
export type Entry = { company_id: string; account: string; counterparty: string; amount: string };
export type Journal = { name: string; entries: Entry[] };
export type CompanyDraft = { workspace_id: string; file: string; options?: SourceOptions; account_column: string; amount_column: string; counterparty_column: string; currency: string; preview?: { accounts: string[]; counterparties: string[]; row_count: number }; mappings: Mapping[]; rates: Rate[]; parties: Record<string, string> };
export type Balance = { group_account: string; amount: string };
export type WorksheetRecord = { current: boolean; run: { id: string; name: string; organization_id: string; created_at: string; request: Record<string, unknown>; evidence: Record<string, unknown>; result: { version: string; reporting_currency: string; period_start: string; period_end: string; sign_convention: string; combined: Balance[]; elimination_totals: Balance[]; consolidated: Balance[]; totals: Record<string, string>; contributions: { company_id: string; name: string; currency: string; source_total: string; translated_total: string; accounts: Balance[]; rates: Rate[] }[]; source_balances: Record<string, string | boolean | null>[]; eliminations: Journal[]; remaining_internal_balances: Record<string, string | boolean | null>[]; warnings: string[]; limitation: string } }; source_rows: { company_id: string; query_id: string; columns: string[]; rows: (string | null)[][] }[] };
