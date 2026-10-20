/* Use case: Gives every uploaded table a useful first reading without a setup form.
What it does: Shows source-backed discoveries, data checks and relevant questions with inspectable query evidence. */

import { useEffect, useMemo, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import { Icon } from "./explore-components";
import { WorkspaceLoading } from "./workspace-loading";
import { PatternResults, type PatternResult, type PatternEvidence } from "./pattern-results";
import { DiagramResults, type DatasetDiagram } from "./diagram-results";
import { AnswerVisualization } from "./answer-visualization";
import { compareExactNumeric, displayMetric } from "./visualization-values";
import { CountUpValue, StatTile } from "./charts/stat-tile";
import { donutEligible } from "./charts/chart-values";
import { InsightsOverview, ProposedActions, proposedFromInsights, useInsights, useInsightWords } from "./insights/insights-overview";
import type { ProposedItem } from "./insights/insights-overview";
import type { ActionIntent } from "./insights/insights-model";
import styles from "./dashboard-presentation.module.css";
import overview from "./discovery-panel.module.css";

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
  diagram?: DatasetDiagram | null;
  diagram_notice?: string | null;
  scenario_metrics?: { metric: string; aggregation: "avg" | "sum" }[];
  dataset_name: string;
  summary: string;
  definition_state: string;
  sources: { revision_id: string; understanding_id?: string | null }[];
  shape: { rows: number; columns: number; metrics: number; dimensions: number };
  quality: { code: string; text: string; action: string }[];
  findings: Finding[];
  suggestions: string[];
  limitations: string[];
  patterns_evidence?: (PatternEvidence & { result: PatternResult; sources: { revision_id: string; understanding_id?: string }[] }) | null;
  analysis_suggestions?: { tool: "patterns" | "anomalies"; label: string; metric?: string; reason: string }[];
};


type Words = (text: string) => string;
const same: Words = text => text;

function FindingEvidence({
  finding,
  words = same,
}: {
  finding: Finding;
  words?: Words;
}) {
  return (
    <details className="findingEvidence">
      <summary>How this was calculated</summary>
      <p>{words(finding.text)}</p>
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
        <details>
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
  unit,
  words = same,
}: {
  findings: Finding[];
  unit?: string;
  ask: (question: string) => void;
  words?: Words;
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
          <div className="discoveryMetric" key={finding.id} data-long-value={displayMetric(finding.query.rows[0]?.[0] ?? null).length > 24}>
            <span>{labels[finding.aggregation] ?? finding.aggregation}</span>
            <CountUpValue className="discoveryValue" exact={String(finding.query.rows[0]?.[0] ?? "Missing")} value={displayMetric(finding.query.rows[0]?.[0] ?? null)} />
            {unit && finding.aggregation !== "count" && <span>{unit}</span>}
            <button
              className="findingQuestion"
              type="button"
              onClick={() => ask(finding.question)}
              aria-label={words(finding.question)}
            >
              Explore
              <Icon name="arrow" size={13} />
            </button>
            <FindingEvidence finding={finding} words={words} />
          </div>
        ))}
      </div>

      <details className="discoveryMetricNote">
        <summary>Metric notes & assumptions</summary>
        <p>{(findings.find(finding => finding.aggregation === "avg") ?? findings[0]).text}</p>
      </details>
    </article>
  );
}

function FindingCard({
  finding,
  ask,
  words = same,
}: {
  finding: Finding;
  ask: (question: string) => void;
  words?: Words;
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
        title={words(finding.title)}
        columns={finding.query.columns.map(column => words(column)).map((column, index) =>
          column === "__value" && index === finding.query.columns.length - 1
            ? finding.aggregation === "count" ? "Count" : finding.metric
            : column,
        )}
        rows={rows}
        recordsAnalyzed={finding.query.records_analyzed}
        compact
        initialChart={finding.aggregation === "count" && rows.length <= 7 && donutEligible(rows.map(row => row[1])) ? "pie" : "bar"}
        chartLimit={8}
        chartClassName="discoveryBars"
      />
      {rows.length > 8 && (
        <p>
          All {rows.length} returned groups are available in Chart and Table.
        </p>
      )}
      <button
        type="button"
        className="findingQuestion"
        onClick={() => ask(finding.question)}
      >
        {words(finding.question)}
        <Icon name="arrow" size={15} />
      </button>
      <FindingEvidence finding={finding} words={words} />
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
  onAnalysis,
  onScenario,
  enabled,
}: {
  root: string;
  request: ApiRequest;
  onQuestion: (question: string) => void;
  onReady: (questions: string[]) => void;
  onPrepare: () => void;
  onReview: () => void;
  onChat: () => void;
  onAnalysis?: (tool: "patterns" | "anomalies", metric?: string) => void;
  onScenario?: (metric: string, aggregation: "avg" | "sum") => void;
  enabled: boolean;
  expert?: boolean;
}) {
  const [loaded, setLoaded] = useState<{ root: string; discovery: Discovery } | null>(null);
  const discovery = loaded?.root === root ? loaded.discovery : null;
  const [failure, setFailure] = useState<{ root: string; message: string } | null>(null);
  const error = failure?.root === root ? failure.message : "";
  const [attempt, setAttempt] = useState(0);
  const [insights, retryInsights] = useInsights(root, request, enabled);
  const knownFields = useMemo(() => discovery?.diagram?.nodes.filter(node => node.kind === "field").map(node => node.label) ?? [], [discovery]);
  const [fields, words] = useInsightWords(insights?.payload, knownFields);
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      request<Discovery>(`${root}/discovery`, { signal: controller.signal })
        .then((result) => {
          if (active) {
            setFailure(null);
            setLoaded({ root, discovery: result });
            onReady(result.suggestions);
          }
        })
        .catch((cause) => {
          if (active && !controller.signal.aborted) {
            setLoaded(null);
            setFailure({ root, message: cause instanceof Error ? cause.message : "The first reading could not load." });
          }
        });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [root, request, attempt, onReady, enabled]);

  if (!enabled) return null;
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
            setFailure(null);
            setLoaded(null);
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
        <WorkspaceLoading title="Getting to know your data" detail="Checking columns and calculating useful starting points from your file." />
        <p className="readingHint">
          You can start a conversation while this loads.
        </p>
      </section>
    );
  const act = (intent: ActionIntent) => {
    if (intent.type === "ask") onQuestion(intent.question);
    else if (intent.type === "prepare") onPrepare();
    else if (intent.type === "review") onReview();
    else if (intent.type === "anomalies") onAnalysis?.("anomalies", intent.metric);
    else if (intent.type === "scenario") onScenario?.(intent.metric, intent.aggregation);
  };
  const proposed: ProposedItem[] = [
    ...proposedFromInsights(insights?.payload?.next_actions ?? [], act, words),
    ...(onAnalysis ? discovery.analysis_suggestions ?? [] : []).map(item => ({ key: `analysis:${item.tool}:${item.metric ?? ""}`, label: words(item.label), reason: words(item.reason), group: "Check", run: () => onAnalysis?.(item.tool, item.metric) })),
    ...(onScenario ? discovery.scenario_metrics ?? [] : []).map(item => ({ key: `scenario:${item.metric}:${item.aggregation}`, label: `What if ${item.metric.replaceAll("_", " ")} changes?`, reason: `Start from the ${item.aggregation === "avg" ? "average" : "total"} in this file and adjust it yourself. Hypothetical arithmetic, not a prediction.`, group: "What-if", run: () => onScenario?.(item.metric, item.aggregation) })),
    ...discovery.suggestions.slice(0, 4).map(question => ({ key: `ask:${question}`, label: words(question), group: "Ask", run: () => onQuestion(question) })),
  ].filter((item, index, all) => all.findIndex(other => other.label.toLowerCase() === item.label.toLowerCase()) === index);
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
    <section className={`discoveryPanel ${overview.overview}`} aria-label="First reading of your data">
      <div className={`discoveryIntro ${overview.intro}`}>
        <div className="discoveryTitle">
          <span className="readingMark">
            <Icon name="sparkle" size={23} />
          </span>
          <div>
            <h2>Here’s what’s in your data</h2>
          </div>
        </div>
        <p className="discoveryFilename">{discovery.dataset_name}</p>
        <p className={overview.summary}>{words(discovery.summary.split("\n\n")[0])}</p>
        <span className="meaningState">{discovery.definition_state === "confirmed" ? "Confirmed meanings" : "Inferred meanings — not confirmed"}</span>
        {!insights?.payload?.kpis.length && <div className={`discoveryShape ${overview.shape}`} aria-label="File structure">
          <StatTile label="Rows" value={discovery.shape.rows.toLocaleString()} />
          <StatTile label="Columns" value={discovery.shape.columns.toLocaleString()} />
          <StatTile label={discovery.shape.metrics === 1 ? "Measure" : "Measures"} value={String(discovery.shape.metrics)} />
          <StatTile label={discovery.shape.dimensions === 1 ? "Category" : "Categories"} value={String(discovery.shape.dimensions)} />
        </div>}
        {discovery.definition_state !== "confirmed" && <div className={overview.meaningPrompt}>
          <div><strong>Help me put these numbers in context</strong><p>Confirm what one record represents and the units of your measures. This helps keep comparisons meaningful.</p></div>
          <button type="button" onClick={onReview}>Review data meaning<Icon name="arrow" size={15} /></button>
        </div>}
        <button className="discoveryChatJump" type="button" onClick={onChat}>
          <Icon name="chat" size={16} /> Ask about this file
        </button>
        <details className="discoveryProvenance">
          <summary>Source & interpretation</summary>
          {discovery.summary.split("\n\n").map((paragraph, index) => <p key={index}>{words(paragraph)}</p>)}
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
      <InsightsOverview state={insights} retry={retryInsights} onAction={act} fields={fields} words={words} />
      {discovery.findings.length > 0 && <details className={`legacyCalculations ${overview.legacy}`} open={Boolean(insights?.error || (insights && !insights.payload?.insights.length))}>
      <summary>More detail: individual calculations</summary>
      <header className={overview.sectionHeading}>
        <span>YOUR STARTING POINT</span><h3>The numbers and groups in your file</h3>
        <p>These charts are calculated from the accessible records. Open a calculation only when you want the details.</p>
      </header>
        <div
          className="discoveryFindings"
          aria-label="Calculated starting points"
        >
          {metricGroups.map((findings) => (
            <MetricGroup
              key={findings[0].metric}
              findings={findings}
              unit={(() => {
                const field = discovery.diagram?.nodes.find(node => node.kind === "field" && node.label === findings[0].metric);
                return field && !field.unit_column ? field.currency || field.unit : undefined;
              })()}
              ask={onQuestion}
              words={words}
            />
          ))}
          {discovery.findings
            .filter((finding) => finding.kind === "distribution")
            .map((finding) => (
              <FindingCard
                key={finding.id}
                finding={finding}
                ask={onQuestion}
                words={words}
              />
            ))}
        </div>
      </details>}
      {discovery.diagram && <section className={overview.dataMap} aria-label="Map of your data">
        <DiagramResults key={discovery.sources.map(source => source.revision_id).join(":")} diagram={discovery.diagram} sources={discovery.sources.map(source => ({ revision_id: source.revision_id, understanding_id: source.understanding_id ?? undefined }))} />
      </section>}
      {discovery.diagram_notice && <p className={overview.mapNotice}>{discovery.diagram_notice}</p>}
      {discovery.patterns_evidence && <div className="automaticPatterns" aria-label="Automatically checked relationships">
        <PatternResults result={discovery.patterns_evidence.result} evidence={discovery.patterns_evidence} sources={discovery.patterns_evidence.sources} onAsk={onQuestion} />
      </div>}
      {discovery.quality.length > 0 && (
        <div className={`discoveryChecks ${overview.checks}`}>
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
                  <p>{words(item.text)}</p>
                  <span>{words(item.action)}</span>
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
              <li key={index}>{words(item)}</li>
            ))}
          </ul>
        </div>
      )}
      <ProposedActions items={proposed} />
    </section>
  );
}
