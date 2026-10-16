/* Use case: Presents complete exact company worksheet layers for review.
What it does: Separates contributions, declared adjustments, unresolved balances and original source evidence with explicit protected downloads. */

import { AnswerVisualization } from "./answer-visualization";
import { ResultExportActions } from "./result-export-actions";
import type { WorksheetRecord } from "./consolidation-types";
import styles from "./consolidation.module.css";

export function ConsolidationResults({ value }: { value: WorksheetRecord }) {
  const { run } = value; const result = run.result;
  const columns = ["Group account", result.reporting_currency];
  const names = new Map(result.contributions.map(item => [item.company_id, item.name]));
  return <section className={styles.results} aria-label="Saved company worksheet">
    <header><p className="studioEyebrow">PRIVATE · VERIFIED SAVED WORKSHEET</p><h3>{run.name}</h3><p>{result.period_start} to {result.period_end} · {result.reporting_currency} · {result.sign_convention.replaceAll("_", " ")}</p></header>
    {!value.current && <p className={styles.notice} role="status">This is a historical worksheet. A company has a newer source or meaning; the saved result stays unchanged.</p>}
    <p>{result.limitation}</p>
    {result.warnings.length > 0 && <aside className={styles.notice}><h4>Still needs review</h4><ul>{result.warnings.map(warning => <li key={warning}>{warning === "reporting_balance_not_zero" ? `The final signed balance is ${result.totals.consolidated} ${result.reporting_currency}. No balancing entry was added.` : "Some declared internal company balances remain. Review the detail below."}</li>)}</ul></aside>}
    <AnswerVisualization title="Consolidated balances" columns={columns} rows={result.consolidated.map(item => [item.group_account, item.amount])} initialMode="chart" />
    <div className={styles.layers}>{[["Combined balances", result.combined], ["Elimination adjustments", result.elimination_totals]] .map(([title, rows]) => <AnswerVisualization key={String(title)} title={String(title)} columns={columns} rows={(rows as typeof result.combined).map(item => [item.group_account, item.amount])} initialMode="table" chartAllowed={false} />)}</div>
    <details><summary>Each company’s contribution and rates</summary>{result.contributions.map(company => <article key={company.company_id}><h4>{company.name} · {company.currency}</h4><p>Original signed total: {company.source_total} {company.currency}. Translated signed total: {company.translated_total} {result.reporting_currency}.</p><AnswerVisualization title={`${company.name} contribution`} columns={columns} rows={company.accounts.map(item => [item.group_account, item.amount])} initialMode="table" chartAllowed={false} /><AnswerVisualization title={`${company.name} declared rates`} columns={["Key", "Basis", "Rate", "As of", "Reference"]} rows={company.rates.map(rate => [rate.key, rate.basis, rate.value, rate.as_of, rate.reference])} initialMode="table" chartAllowed={false} /></article>)}</details>
    <details><summary>Account translations and remaining internal balances</summary><AnswerVisualization title="Exact account translations" columns={["Company", "Account", "Group account", "Other company", "Source amount", "Translated", "Elimination", "Remaining"]} rows={result.source_balances.map(row => [names.get(String(row.company_id)) ?? String(row.company_id), String(row.account), String(row.group_account), row.counterparty ? names.get(String(row.counterparty)) ?? String(row.counterparty) : "External / unmapped", String(row.source_amount), String(row.translated_amount), String(row.elimination), String(row.remaining)])} initialMode="table" chartAllowed={false} /><p>{result.remaining_internal_balances.length} internal balances remain. External or unmapped names are never eligible for elimination.</p></details>
    <details><summary>Original ledger rows and private evidence</summary>{value.source_rows.map(source => <AnswerVisualization key={source.company_id} title={`${names.get(source.company_id) ?? "Company"} original rows`} columns={source.columns} rows={source.rows} initialMode="table" chartAllowed={false} />)}<pre>{JSON.stringify({ inputs: run.request, evidence: run.evidence }, null, 2)}</pre></details>
    <ResultExportActions path={`/organizations/${run.organization_id}/consolidations/${run.id}/export`} label="Download worksheet" charts={["Consolidated balances"]} />
  </section>;
}
