/* Use case: Makes measured relationships understandable without inventing causes.
What it does: Presents server-calculated findings, exact evidence labels and accessible exploratory charts. */

import { useId } from "react";

export type PatternFinding = {
  id: string;
  type: "numeric_relationship" | "group_difference" | "category_association";
  title: string;
  summary: string;
  columns: string[];
  score: string;
  support: number;
  excluded: number;
  strength?: "strong" | "weak";
  statistics?: Record<string, string | null>;
  chart: { kind: "scatter" | "bar" | "matrix"; x: string; y: string; x_unit?: string; y_unit?: string; points: { x: string; y: string; count?: number }[] };
  notes: string[];
};
export type PatternResult = {
  version: string;
  engine_version: string;
  findings: PatternFinding[];
  exploratory?: PatternFinding[];
  coverage: { source_rows: number; filtered_rows: number; eligible_columns: number; checked_candidates: number; suppressed_candidates: number; selected_findings: number };
  limitations: string[];
  exclusions: { column: string; reason: string }[];
  status: "patterns_found" | "no_strong_patterns" | "insufficient_data";
};
export type PatternEvidence = { query_id: string; method_version?: string; result_checksum?: string };

function PatternChart({ finding }: { finding: PatternFinding }) {
  const { chart } = finding;
  if (chart.kind === "matrix") {
    const maximum = Math.max(1, ...chart.points.map(point => point.count ?? 0));
    const recorded = chart.points.filter(point => (point.count ?? 0) > 0);
    const shown = [...recorded].sort((left, right) => (right.count ?? 0) - (left.count ?? 0)).slice(0, 8);
    return <div className="patternCategoryChart" role="group" aria-label={`${chart.x} and ${chart.y}: recorded combinations`}>
      {shown.map((point, index) => <div className="patternCategoryRow" key={index}>
        <span>{point.x} <span aria-hidden="true">·</span> {point.y}</span>
        <div className="patternCountTrack" aria-hidden="true"><span style={{ width: `${(point.count ?? 0) / maximum * 100}%` }} /></div>
        <strong>{point.count ?? 0}<span className="srOnly"> rows</span></strong>
      </div>)}
      {recorded.length > shown.length && <small>Showing the {shown.length} most frequent recorded combinations. All returned counts are in the values below.</small>}
    </div>;
  }
  if (chart.kind === "bar") {
    const maximum = Math.max(1, ...chart.points.map(point => Math.abs(Number(point.y))).filter(Number.isFinite));
    const values = chart.points.map(point => Number.isFinite(Number(point.y)) ? Number(point.y) / maximum : 0);
    const low = Math.min(0, ...values), high = Math.max(0, ...values);
    const position = (value: number) => high === low ? 0 : (value - low) / (high - low) * 100;
    const zero = position(0);
    return <div className="patternBarChart" role="group" aria-label={`Average ${chart.y} by ${chart.x}`}>
      {chart.points.map((point, index) => <div className="patternBarRow" key={index}>
        <div className="patternBarLabel"><span>{point.x}</span><strong>{point.y}{chart.y_unit ? ` ${chart.y_unit}` : ""}</strong></div>
        <div className="patternBarTrack" aria-hidden="true"><i style={{ left: `${zero}%` }} /><span data-negative={Number(point.y) < 0} style={{ left: `${Math.min(zero, position(values[index]))}%`, width: `${Math.abs(position(values[index]) - zero)}%` }} /></div>
        <small>{point.count ?? 0} rows</small>
      </div>)}
    </div>;
  }
  const points = chart.points.filter(point => Number.isFinite(Number(point.x)) && Number.isFinite(Number(point.y)));
  if (!points.length) return <p>Open the values below to inspect this relationship.</p>;
  const xs = points.map(point => Number(point.x)), ys = points.map(point => Number(point.y));
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const position = (value: number, minimum: number, maximum: number) => {
    if (maximum === minimum) return .5;
    const scale = Math.max(Math.abs(minimum), Math.abs(maximum), 1);
    return (value / scale - minimum / scale) / (maximum / scale - minimum / scale);
  };
  return <figure className="patternScatter">
    <svg role="img" aria-label={`${chart.x} versus ${chart.y}; illustrative coordinates, source values below`} viewBox="0 0 440 200">
      <title>{`${chart.x} versus ${chart.y}`}</title>
      {[30, 75, 120, 165].map(y => <line key={y} x1="20" y1={y} x2="420" y2={y} className="patternGridLine" />)}
      {points.map((point, index) => <circle key={index} cx={24 + position(Number(point.x), minX, maxX) * 392} cy={168 - position(Number(point.y), minY, maxY) * 144} r="3.5"><title>{`${chart.x}: ${point.x}; ${chart.y}: ${point.y}`}</title></circle>)}
    </svg>
    <figcaption><span>{chart.x}{chart.x_unit ? ` (${chart.x_unit})` : ""} <span aria-hidden="true">↔</span> {chart.y}{chart.y_unit ? ` (${chart.y_unit})` : ""}</span><small>{points.length} displayed points · approximate coordinates</small></figcaption>
  </figure>;
}

function PatternCard({ finding, index, instance, weak = false }: { finding: PatternFinding; index: number; instance: string; weak?: boolean }) {
  const labels = { numeric_relationship: "Move together", group_difference: "Groups differ", category_association: "Appear together" };
  const scores = { numeric_relationship: "Relationship strength", group_difference: "Group difference score", category_association: "Category association score" };
  const statistics: Record<string, string> = { pearson: "Straight-line relationship", spearman: "Rank relationship", eta_squared: "Group difference (eta squared)", cramers_v: "Category association (Cramér’s V)" };
  return <article className="patternFinding" data-strength={weak ? "weak" : "screened"} aria-labelledby={`${instance}-${finding.id}`}>
    <div className="patternFindingTop"><span className="patternNumber">{index + 1}</span><span className="patternType">{weak ? "Weak relationship · exploratory" : labels[finding.type]}</span><span className="patternSupport">{finding.support} rows</span></div>
    <h4 id={`${instance}-${finding.id}`}>{finding.title}</h4>
    <p className="patternSummary">{finding.summary}</p>
    <PatternChart finding={finding} />
    <p className="patternCoverageNote">Based on {finding.support} rows · {finding.excluded} excluded from this comparison.</p>
    <details className="patternDetails"><summary>See values and method</summary>
      <p>{scores[finding.type]}: <strong>{finding.score}</strong> · approximate statistical score, not a probability.</p>
      {finding.statistics && <dl className="patternStatistics">{Object.entries(finding.statistics).map(([name, value]) => <div key={name}><dt>{statistics[name] ?? name}</dt><dd>{value ?? "Unavailable"}</dd></div>)}</dl>}
      <ul>{finding.notes.map((note, noteIndex) => <li key={noteIndex}>{note}</li>)}</ul>
      <div className="tableWrap"><table><caption>Returned values for this chart</caption><thead><tr><th>{finding.chart.x}{finding.chart.x_unit ? ` (${finding.chart.x_unit})` : ""}</th><th>{finding.chart.y}{finding.chart.y_unit ? ` (${finding.chart.y_unit})` : ""}</th>{finding.chart.kind !== "scatter" && <th>Rows</th>}</tr></thead><tbody>{finding.chart.points.map((point, pointIndex) => <tr key={pointIndex}><td>{point.x}</td><td>{point.y}</td>{finding.chart.kind !== "scatter" && <td>{point.count ?? 0}</td>}</tr>)}</tbody></table></div>
    </details>
  </article>;
}

export function PatternResults({ result, evidence, sources }: { result: PatternResult; evidence?: PatternEvidence; sources?: { revision_id: string; understanding_id?: string }[] }) {
  const instance = useId();
  const empty = result.status === "insufficient_data" ? "A little more data is needed" : "No clear pattern found";
  return <section className="patternResults" aria-label="Measured data patterns">
    <header className="patternOverview">
      <span className="analysisEyebrow">MEASURED FROM YOUR FILE</span>
      <h3>{result.findings.length ? "Here is what stands out" : empty}</h3>
      <p>{result.findings.length ? "These relationships appear in the recorded rows. They can guide your next question; they do not prove that one thing caused another." : result.status === "insufficient_data" ? "The available rows or eligible fields are too limited for a supported comparison. Check the details below before adding more data." : "The comparisons did not pass this method’s screening rules. A weak result is useful too: it keeps us from inventing a story."}</p>
      <dl className="patternCoverage"><div><dt>Rows checked</dt><dd>{result.coverage.filtered_rows}</dd></div><div><dt>Fields explored</dt><dd>{result.coverage.eligible_columns}</dd></div><div><dt>Comparisons tested</dt><dd>{result.coverage.checked_candidates}</dd></div></dl>
    </header>
    <div className="patternFindings">{result.findings.slice(0, 6).map((finding, index) => <PatternCard key={finding.id} finding={finding} index={index} instance={instance} />)}</div>
    {!!result.exploratory?.length && <section className="patternExploratory" aria-label="Exploratory relationships"><h4>Small relationships worth a look</h4><p>These comparisons were measured, but the relationships are weak. Treat them as questions to investigate, not reliable rules or predictions.</p><div className="patternFindings">{result.exploratory.slice(0, 2).map((finding, index) => <PatternCard key={finding.id} finding={finding} index={index} instance={`${instance}-weak`} weak />)}</div></section>}
    <details className="patternEvidence"><summary>Scope, limitations and source evidence</summary>
      <p>{result.coverage.source_rows} source rows; {result.coverage.filtered_rows} rows after required filters. {result.coverage.suppressed_candidates} comparisons did not pass screening. Results shown are exploratory and need independent checking before a decision.</p>
      <ul>{result.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>
      {!!result.exclusions.length && <><h4>Fields left out</h4><ul>{result.exclusions.map((item, index) => <li key={index}><strong>{item.column}</strong>: {item.reason}</li>)}</ul></>}
      <p>Method: {result.version} · Engine: {result.engine_version}</p>
      {evidence && <p className="checksum">Source receipt: {evidence.query_id}{evidence.result_checksum ? ` · Result checksum: ${evidence.result_checksum}` : ""}</p>}
      {sources?.map(source => <p className="checksum" key={source.revision_id}>Source revision: {source.revision_id}{source.understanding_id ? ` · Definitions: ${source.understanding_id}` : ""}</p>)}
    </details>
  </section>;
}
