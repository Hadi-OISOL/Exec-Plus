/* Use case: Gives every uploaded table a useful first reading without a setup form.
What it does: Shows source-backed discoveries, data checks and relevant questions with inspectable query evidence. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import { Icon } from "./explore-components";
import { AnswerVisualization } from "./answer-visualization";
import { compareExactNumeric } from "./visualization-values";
import styles from "./dashboard-presentation.module.css";

type Cell = string | number | boolean | null;
type Finding = {
  id: string;
  title: string;
  text: string;
  kind: "metric" | "distribution";
  metric: string;
  column?: string;
  aggregation: string;
  question: string;
  query: {
    columns: string[];
    rows: Cell[][];
    records_analyzed: number;
    matched_records: number | null;
    lineage: { query_id: string; sql?: string; [key: string]: unknown };
  };
};
type Discovery = {
  version: string;
  dataset_name: string;
  summary: string;
  definition_state: string;
  sources: { revision_id: string; understanding_id?: string | null }[];
  shape: { rows: number; columns: number; metrics: number; dimensions: number };
  quality: { code: string; text: string; action: string }[];
  findings: Finding[];
  suggestions: string[];
  limitations: string[];
};

function exact(value: Cell): string {
  if (value === null) return "Missing";
  return String(value).replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1");
}

function FindingEvidence({
  finding,
  expert,
}: {
  finding: Finding;
  expert: boolean;
}) {
  return (
    <details className="findingEvidence" open={expert}>
      <summary>How this was calculated</summary>
      <p>{finding.text}</p>
      <p>
        {finding.aggregation} · {finding.metric} ·{" "}
        {finding.query.records_analyzed.toLocaleString()} source records.
      </p>
      <p>Query receipt: {finding.query.lineage.query_id}</p>
      <div
        className="tableScroll"
        tabIndex={0}
        role="region"
        aria-label={`Exact values for ${finding.title}`}
      >
        <table>
          <thead>
            <tr>
              {finding.query.columns.map((column) => (
                <th key={column} scope="col">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {finding.query.rows.map((row, index) => (
              <tr key={index}>
                {row.map((cell, position) => (
                  <td key={position}>
                    {cell === null ? "Missing" : String(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {finding.query.lineage.sql && (
        <details open={expert}>
          <summary>Executed query</summary>
          <pre>{finding.query.lineage.sql}</pre>
        </details>
      )}
    </details>
  );
}

function MetricGroup({
  findings,
  ask,
  expert,
}: {
  findings: Finding[];
  ask: (question: string) => void;
  expert: boolean;
}) {
  const labels: Record<string, string> = {
    min: "Lowest",
    max: "Highest",
    avg: "Average",
    sum: "Total",
    count: "Present values",
  };
  return (
    <article className="discoveryMetricGroup">
      <div className="findingEyebrow">
        <Icon name="check" size={13} /> Calculated from your file
      </div>
      <h3>{findings[0].metric.replaceAll("_", " ")}</h3>
      <div className="discoveryMetricRange">
        {findings.map((finding) => (
          <div className="discoveryMetric" key={finding.id}>
            <span>{labels[finding.aggregation] ?? finding.aggregation}</span>
            <strong className="discoveryValue">
              {exact(finding.query.rows[0]?.[0] ?? null)}
            </strong>
            <button
              className="findingQuestion"
              type="button"
              onClick={() => ask(finding.question)}
              aria-label={finding.question}
            >
              Explore
              <Icon name="arrow" size={13} />
            </button>
            <FindingEvidence finding={finding} expert={expert} />
          </div>
        ))}
      </div>
      <p className="discoveryMetricNote">
        {
          (
            findings.find((finding) => finding.aggregation === "avg") ??
            findings[0]
          ).text
        }
      </p>
    </article>
  );
}

function FindingCard({
  finding,
  ask,
  expert,
}: {
  finding: Finding;
  ask: (question: string) => void;
  expert: boolean;
}) {
  const rows = [...finding.query.rows].sort(
    (left, right) =>
      compareExactNumeric(right[1], left[1]) ||
      String(left[0]).localeCompare(String(right[0])),
  );
  return (
    <article
      className={`discoveryFinding distribution ${styles.discoveryCard}`}
    >
      <div className="findingEyebrow">
        <Icon name="check" size={13} /> Calculated from your file
      </div>
      <AnswerVisualization
        title={finding.title}
        columns={finding.query.columns.map((column, index) =>
          column === "__value" && index === finding.query.columns.length - 1
            ? finding.aggregation === "count" ? "Count" : finding.metric
            : column,
        )}
        rows={rows}
        recordsAnalyzed={finding.query.records_analyzed}
        compact
        chartLimit={8}
        chartClassName="discoveryBars"
      />
      <p>{finding.text}</p>
      {rows.length > 8 && (
        <p>
          Top 8 of {rows.length} groups shown. All groups are available in the
          calculation evidence.
        </p>
      )}
      <button
        type="button"
        className="findingQuestion"
        onClick={() => ask(finding.question)}
      >
        {finding.question}
        <Icon name="arrow" size={15} />
      </button>
      <FindingEvidence finding={finding} expert={expert} />
    </article>
  );
}

export function DiscoveryPanel({
  root,
  request,
  onQuestion,
  onReady,
  onPrepare,
  onReview,
  onChat,
  enabled,
  expert = false,
}: {
  root: string;
  request: ApiRequest;
  onQuestion: (question: string) => void;
  onReady: (questions: string[]) => void;
  onPrepare: () => void;
  onReview: () => void;
  onChat: () => void;
  enabled: boolean;
  expert?: boolean;
}) {
  const [discovery, setDiscovery] = useState<Discovery | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      request<Discovery>(`${root}/discovery`, { signal: controller.signal })
        .then((result) => {
          if (active) {
            setError("");
            setDiscovery(result);
            onReady(result.suggestions);
          }
        })
        .catch((cause) => {
          if (active && !controller.signal.aborted)
            setError(
              cause instanceof Error
                ? cause.message
                : "The first reading could not load.",
            );
        });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [root, request, attempt, onReady, enabled]);

  if (error)
    return (
      <section
        className="panel discoveryPanel"
        aria-label="First reading of your data"
      >
        <h2>Your file is ready to explore</h2>
        <p role="alert">{error}</p>
        <p>
          You can ask about your columns while the first reading is unavailable.
        </p>
        <button
          type="button"
          onClick={() => {
            setError("");
            setAttempt((value) => value + 1);
          }}
        >
          Retry first reading
        </button>
      </section>
    );
  if (!discovery)
    return (
      <section
        className="panel discoveryPanel discoveryLoading"
        aria-label="First reading of your data"
        aria-busy="true"
      >
        <span className="readingMark">
          <Icon name="sparkle" size={28} />
        </span>
        <h2>Getting to know your data</h2>
        <p>
          Checking the columns, calculating useful starting points, and finding
          questions worth asking.
        </p>
        <div className="readingProgress" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <p className="readingHint">
          You can start a conversation while this loads.
        </p>
      </section>
    );
  const metricGroups = [
    ...new Set(
      discovery.findings
        .filter((finding) => finding.kind === "metric")
        .map((finding) => finding.metric),
    ),
  ].map((metric) =>
    discovery.findings.filter(
      (finding) => finding.kind === "metric" && finding.metric === metric,
    ),
  );
  return (
    <section className="discoveryPanel" aria-label="First reading of your data">
      <div className="discoveryIntro">
        <div className="discoveryTitle">
          <span className="readingMark">
            <Icon name="sparkle" size={23} />
          </span>
          <div>
            <p className="eyebrow">YOUR FIRST READING</p>
            <h2>Here’s what’s in your data</h2>
          </div>
        </div>
        <p className="discoveryFilename">{discovery.dataset_name}</p>
        <div className="discoveryShape" aria-label="File structure">
          <span>
            <strong>{discovery.shape.rows.toLocaleString()}</strong> rows
          </span>
          <span>
            <strong>{discovery.shape.columns.toLocaleString()}</strong> columns
          </span>
          <span>
            <strong>{discovery.shape.metrics}</strong>{" "}
            {discovery.shape.metrics === 1 ? "measure" : "measures"}
          </span>
          <span>
            <strong>{discovery.shape.dimensions}</strong>{" "}
            {discovery.shape.dimensions === 1 ? "category" : "categories"}
          </span>
        </div>
        {discovery.summary.split("\n\n").map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
        <button className="discoveryChatJump" type="button" onClick={onChat}>
          <Icon name="chat" size={16} /> Ask about this file
        </button>
        <details className="discoveryProvenance" open={expert}>
          <summary>Source & interpretation</summary>
          <p>
            Structure comes from your file. Suggested business meanings remain
            tentative until reviewed.
          </p>
          <p>
            Business definition status:{" "}
            {discovery.definition_state.replaceAll("_", " ")}
          </p>
          <button type="button" className="findingQuestion" onClick={onReview}>
            Review data meaning
            <Icon name="arrow" size={13} />
          </button>
          {discovery.sources.map((source) => (
            <p key={source.revision_id}>
              Source revision: {source.revision_id}
              {source.understanding_id
                ? ` · Definition: ${source.understanding_id}`
                : ""}
            </p>
          ))}
        </details>
      </div>
      {discovery.findings.length > 0 && (
        <div
          className="discoveryFindings"
          aria-label="Calculated starting points"
        >
          {metricGroups.map((findings) => (
            <MetricGroup
              key={findings[0].metric}
              findings={findings}
              ask={onQuestion}
              expert={expert}
            />
          ))}
          {discovery.findings
            .filter((finding) => finding.kind === "distribution")
            .map((finding) => (
              <FindingCard
                key={finding.id}
                finding={finding}
                ask={onQuestion}
                expert={expert}
              />
            ))}
        </div>
      )}
      {discovery.quality.length > 0 && (
        <div className="discoveryChecks">
          <h3>
            {discovery.quality.every((item) => item.code === "basic_checks")
              ? "Data checks"
              : "What deserves a closer look"}
          </h3>
          <ul>
            {discovery.quality.map((item) => (
              <li key={item.code}>
                <Icon name="prepare" size={17} />
                <div>
                  <p>{item.text}</p>
                  <span>{item.action}</span>
                </div>
              </li>
            ))}
          </ul>
          {discovery.quality.some((item) => item.code !== "basic_checks") && (
            <button
              type="button"
              className="findingQuestion"
              onClick={onPrepare}
            >
              Inspect and prepare data
              <Icon name="arrow" size={13} />
            </button>
          )}
        </div>
      )}
      {discovery.limitations.length > 0 && (
        <div className="discoveryLimits">
          <h3>Before drawing conclusions</h3>
          {discovery.sources.some((source) => source.understanding_id) &&
            discovery.definition_state !== "confirmed" && (
              <button
                type="button"
                className="findingQuestion"
                onClick={onReview}
              >
                Review saved business definitions
                <Icon name="arrow" size={13} />
              </button>
            )}
          <ul>
            {discovery.limitations.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="discoveryNext">
        <h3>Where would you like to go next?</h3>
        <div className="suggestionChips">
          {discovery.suggestions.slice(0, 4).map((question) => (
            <button
              key={question}
              type="button"
              onClick={() => onQuestion(question)}
            >
              {question}
              <Icon name="arrow" size={14} />
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
