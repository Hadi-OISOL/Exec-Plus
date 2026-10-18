/* Preserve each independent calculation in a compound answer, with its own exact evidence. */

import { AnswerVisualization } from "./answer-visualization";
import { RecordTable } from "./explore-components";
import type { Cell } from "./explore-components";

export type AdditionalNumericalAnswer = {
  label?: string;
  value?: string | number;
  columns?: string[];
  rows?: Cell[][];
  records_analyzed?: number;
  matched_records?: number | null;
  lineage: {
    query_id: string;
    metric: string;
    aggregation: string;
    records_analyzed: number;
    filters: string[];
    sql: string;
  };
};

export function CompoundResults({ results }: { results: AdditionalNumericalAnswer[] }) {
  return results.map((result, index) => (
    <section key={result.lineage.query_id} aria-label={`Calculation ${index + 2}`}>
      <h4>{result.label ?? `Calculation ${index + 2}`}</h4>
      {result.value !== undefined && <p className="explanationPlain"><strong>{String(result.value)}</strong></p>}
      {result.rows && (
        result.lineage.aggregation !== "rows" && result.columns?.length === 2 ? (
          <AnswerVisualization
            title={result.label ?? `Calculation ${index + 2}`}
            columns={result.columns.map(column => column === "__value" ? "Calculated value" : column)}
            rows={result.rows}
            recordsAnalyzed={result.records_analyzed ?? result.lineage.records_analyzed}
            matchedRecords={result.matched_records}
          />
        ) : (
          <RecordTable data={{ columns: result.columns ?? [], rows: result.rows,
            records_analyzed: result.records_analyzed ?? result.lineage.records_analyzed,
            matched_records: result.matched_records }} />
        )
      )}
      <details>
        <summary>Calculation evidence</summary>
        <p>{result.lineage.filters.length ? result.lineage.filters.join("; ") : "No additional query filters."}</p>
        <p>{result.lineage.records_analyzed.toLocaleString()} source records analyzed.</p>
        <code style={{ overflowWrap: "anywhere" }}>{result.lineage.query_id}</code>
        <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{result.lineage.sql}</pre>
      </details>
    </section>
  ));
}
