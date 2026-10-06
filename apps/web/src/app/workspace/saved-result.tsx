/* Use case: Makes a saved execution readable without hiding its original evidence.
What it does: Renders exact metric, table, dashboard and cited-answer contracts with an optional raw-evidence disclosure. */

import { AnswerVisualization } from "./answer-visualization";
import type { VisualizationCell } from "./answer-visualization";
import { ConversationEvidence } from "./conversation-evidence";
import type { Citation } from "./conversation-evidence";
import type { ApiRequest } from "./profile-panel";
import styles from "./library.module.css";

type SavedAnswer = {
  kind?: string;
  value?: VisualizationCell;
  label?: string;
  columns?: string[];
  rows?: VisualizationCell[][];
  records_analyzed?: number;
  matched_records?: number | null;
  lineage?: { query_id: string; metric?: string; aggregation?: string };
  metric?: string;
  dimension?: string;
  message?: string;
  data?: SavedAnswer | null;
  cards?: SavedAnswer[];
  trend?: SavedAnswer | null;
  breakdown?: SavedAnswer | null;
  citations?: Citation[];
  coverage?: string;
  limitations?: string[];
  guidance?: { columns: string[]; definition_state: string };
  sources?: { revision_id: string; understanding_id?: string | null }[];
};

function hasCalculation(value: SavedAnswer): boolean {
  return Boolean(
    value.lineage?.query_id ||
    (value.data && hasCalculation(value.data)) ||
    value.cards?.some(hasCalculation) ||
    (value.trend && hasCalculation(value.trend)) ||
    (value.breakdown && hasCalculation(value.breakdown)),
  );
}

function SavedAnswerBody({
  value,
  request,
  title,
}: {
  value: SavedAnswer;
  request: ApiRequest;
  title: string;
}) {
  const aggregation = value.lineage?.aggregation;
  const metric = value.lineage?.metric;
  const columns = value.columns?.map((column, index) =>
    column === "__value" && index === value.columns!.length - 1 && metric && aggregation && aggregation !== "rows"
      ? `${aggregation[0].toUpperCase()}${aggregation.slice(1)} of ${metric}`
      : column,
  );
  return (
    <>
      {value.message?.split(/\n\s*\n/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
      {value.guidance && (
        <div>
          <p>Definition status: {value.guidance.definition_state.replaceAll("_", " ")}. Naming-based interpretations are tentative.</p>
          {!!value.guidance.columns.length && <p>Columns discussed: {value.guidance.columns.join(", ")}</p>}
        </div>
      )}
      {!!value.sources?.length && !value.lineage && (
        <details className={styles.evidence}>
          <summary>Source & interpretation</summary>
          {value.sources.map((source) => <p key={source.revision_id}>Source revision: {source.revision_id}{source.understanding_id ? ` · Definition version: ${source.understanding_id}` : " · Profile-based interpretation"}</p>)}
        </details>
      )}
      {value.value !== undefined && (
        <div className={styles.resultMetric}>
          <span>{value.label ?? title}</span>
          <strong>{value.value === null ? "No matching value" : String(value.value)}</strong>
        </div>
      )}
      {value.rows && value.columns && (
        value.rows.length === 1 && value.columns.length === 1 ? (
          <div className={styles.resultMetric}>
            <span>{value.lineage?.metric ?? value.columns[0]}</span>
            <strong>{String(value.rows[0][0] ?? "No matching value")}</strong>
          </div>
        ) : (
          <AnswerVisualization
            title={title}
            columns={columns ?? value.columns}
            rows={value.rows}
            recordsAnalyzed={value.records_analyzed}
            matchedRecords={value.matched_records}
            initialMode="table"
            chartAllowed={value.columns.length === 2 && value.lineage?.aggregation !== "rows"}
          />
        )
      )}
      {value.data && <SavedAnswerBody value={value.data} request={request} title={title} />}
      {value.cards && (
        <div className={styles.grid}>
          {value.cards.map((card, index) => (
            <article className={styles.card} key={card.lineage?.query_id ?? index}>
              <SavedAnswerBody value={card} request={request} title={card.metric ?? "Dashboard measure"} />
            </article>
          ))}
        </div>
      )}
      {value.trend && <SavedAnswerBody value={value.trend} request={request} title={`${value.trend.dimension ?? "Observed"} trend`} />}
      {value.breakdown && <SavedAnswerBody value={value.breakdown} request={request} title={`${value.breakdown.dimension ?? "Category"} breakdown`} />}
      {value.citations && (
        <ConversationEvidence
          citations={value.citations}
          coverage={value.coverage ?? "complete"}
          limitations={value.limitations ?? []}
          request={request}
        />
      )}
      {value.lineage && (
        <p className={styles.metadata}>
          Query receipt: {value.lineage.query_id}
          {value.records_analyzed !== undefined && ` · ${value.records_analyzed.toLocaleString()} source records`}
        </p>
      )}
    </>
  );
}

export function SavedResult({
  value,
  name,
  kind,
  request,
}: {
  value: SavedAnswer;
  name: string;
  kind: string;
  request: ApiRequest;
}) {
  const calculated = hasCalculation(value);
  return (
    <section className={styles.result} aria-label={`Saved result: ${name}`}>
      <div className={styles.resultHeading}>
        <div>
          <span className={styles.eyebrow}>Saved answer</span>
          <h3>{name}</h3>
        </div>
        <span>{calculated ? kind === "analysis" ? "Original evidence replayed" : "Calculated from the current revision" : "Response for the selected revision"}</span>
      </div>
      <SavedAnswerBody value={value} title={name} request={request} />
      <details className={styles.evidence}>
        <summary>{calculated ? "Verified saved result and lineage" : "Response details and source evidence"}</summary>
        <pre>{JSON.stringify(value, null, 2)}</pre>
      </details>
    </section>
  );
}

export type { SavedAnswer };
