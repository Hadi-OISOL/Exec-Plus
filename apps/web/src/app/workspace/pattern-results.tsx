/* Use case: Makes measured relationships understandable without inventing causes.
What it does: Presents server-calculated findings, exact evidence labels and accessible exploratory charts. */

import { useEffect, useId, useRef, useState } from "react";
import styles from "./pattern-results.module.css";

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
  chart: { kind: "scatter" | "bar" | "matrix"; x: string; y: string; x_unit?: string; y_unit?: string; points: { x: string; y: string; count?: number; group?: string }[] };
  notes: string[];
};
type ExplorationResult = {
  version: string;
  engine_version: string;
  findings: PatternFinding[];
  exploratory?: PatternFinding[];
  coverage: { source_rows: number; filtered_rows: number; eligible_columns: number; checked_candidates: number; suppressed_candidates: number; selected_findings: number };
  limitations: string[];
  exclusions: { column: string; reason: string }[];
  status: "patterns_found" | "no_strong_patterns" | "insufficient_data";
};
type Correlations = { pearson: string | null; spearman: string | null };
type Direction = "positive" | "negative" | "weak" | "unavailable";
type Directions = { pearson: Direction; spearman: Direction };
export type GroupRelationshipResult = {
  version: "group-relationship-comparison-v1";
  engine_version: string;
  status: "compared" | "insufficient_data";
  reason?: string | null;
  columns: string[];
  group_by: string;
  units: Record<string, string>;
  pooled: { support: number; statistics: Correlations; directions: Directions; chart: { kind: "scatter"; x: string; y: string; x_unit?: string; y_unit?: string; points: { x: string; y: string; group: string }[] }; notes: string[] } | null;
  groups: { id: string; label: string; rows: number; complete_pairs: number; excluded_pairs: number; status: "eligible" | "sparse" | "constant" | "unstable"; statistics: Correlations | null; directions: Directions | null }[];
  comparisons: { pearson: { reversal_groups: string[]; same_direction_groups: string[]; weak_groups: string[] }; spearman: { reversal_groups: string[]; same_direction_groups: string[]; weak_groups: string[] } };
  coverage: { source_rows: number; filtered_rows: number; covered_rows: number; excluded_rows: number; missing_category_rows: number; missing_pair_rows: number; sparse_group_rows: number; constant_group_rows: number; unstable_group_rows: number; observed_groups: number; eligible_groups: number };
  limitations: string[];
  exclusions: { column: string; reason: string }[];
};
export type CohortComparisonResult = {
  version: "cohort-comparison-v1";
  engine_version: string;
  status: "compared" | "insufficient_data";
  target: { column: string; value: string };
  coverage: { source_rows: number; filtered_rows: number; target_rows: number; other_rows: number; missing_target_rows: number };
  numeric: { column: string; unit: string; target_count: number; other_count: number; target_mean: string | null; other_mean: string | null; target_median: string | null; other_median: string | null; difference: string | null; standardized_difference: string | null; status: "compared" | "insufficient_data" }[];
  categories: { column: string; levels: { value: string; target_count: number; other_count: number; target_share: string | null; other_share: string | null }[]; target_observed: number; other_observed: number }[];
  limitations: string[];
  exclusions: { column: string; reason: string }[];
  next_steps: string[];
  suggestions: string[];
};
export type PatternResult = ExplorationResult | GroupRelationshipResult | CohortComparisonResult;
export type PatternEvidence = { query_id: string; method_version?: string; result_checksum?: string };
const groupColors = ["#087f8c", "#b35438", "#6657a5", "#406c3c", "#936713", "#a74473", "#276596", "#786650", "#34866e", "#8463a7", "#a14743", "#5d6684"];

function PatternChart({ finding }: { finding: PatternFinding }) {
  const [selected, setSelected] = useState(0);
  const [hovered, setHovered] = useState<number | null>(null);
  const inspectionId = useId();
  const plotRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(440);
  const { chart } = finding;
  useEffect(() => {
    if (!plotRef.current) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(100, Math.min(1200, entry.contentRect.width))));
    observer.observe(plotRef.current);
    return () => observer.disconnect();
  }, [chart.kind]);
  if (chart.kind === "matrix") {
    const maximum = Math.max(1, ...chart.points.map(point => point.count ?? 0));
    const recorded = chart.points.filter(point => (point.count ?? 0) > 0);
    const shown = [...recorded].sort((left, right) => (right.count ?? 0) - (left.count ?? 0)).slice(0, 8);
    return <div className="patternCategoryChart" role="group" aria-label={`${chart.x} and ${chart.y}: recorded combinations`}>
      <div className={styles.chartHeading}><strong>Recorded combinations</strong><span>{chart.x} · {chart.y}</span></div>
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
      <div className={styles.chartHeading}><strong>Average {chart.y}{chart.y_unit ? ` (${chart.y_unit})` : ""}</strong><span>By {chart.x} · bars share a zero baseline</span></div>
      {chart.points.map((point, index) => <div className="patternBarRow" key={index}>
        <div className="patternBarLabel"><span>{point.x}</span><strong>{point.y}{chart.y_unit ? ` ${chart.y_unit}` : ""}</strong></div>
        <div className="patternBarTrack" aria-hidden="true"><i style={{ left: `${zero}%` }} /><span data-negative={Number(point.y) < 0} style={{ left: `${Math.min(zero, position(values[index]))}%`, width: `${Math.abs(position(values[index]) - zero)}%` }} /></div>
        <small>{point.count ?? 0} rows</small>
      </div>)}
    </div>;
  }
  const points = chart.points.filter(point => point.x.trim() !== "" && point.y.trim() !== "" && Number.isFinite(Number(point.x)) && Number.isFinite(Number(point.y)));
  const groups = [...new Set(points.flatMap(point => point.group === undefined ? [] : [point.group]))];
  if (!points.length) return <p>Open the values below to inspect this relationship.</p>;
  const xs = points.map(point => Number(point.x)), ys = points.map(point => Number(point.y));
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const position = (value: number, minimum: number, maximum: number) => {
    if (maximum === minimum) return .5;
    const scale = Math.max(Math.abs(minimum), Math.abs(maximum), 1);
    return (value / scale - minimum / scale) / (maximum / scale - minimum / scale);
  };
  const activeIndex = Math.min(hovered ?? selected, points.length - 1);
  const activePoint = points[activeIndex];
  const label = (value: number) => value === 0 ? "0" : Math.abs(value) >= 1e6 || Math.abs(value) < .001 ? value.toExponential(1) : Number(value.toPrecision(4)).toLocaleString("en-US");
  return <figure className={`patternScatter ${styles.scatter}`}>
    <div className={styles.chartHeading}><strong>{chart.y}{chart.y_unit ? ` (${chart.y_unit})` : ""}</strong><span>One dot = one returned record</span></div>
    <div className={styles.scatterLayout}>
      <div className={styles.valueScale} aria-label="Approximate vertical scale"><span>{label(maxY)}</span><span>{label(minY)}</span></div>
      <div ref={plotRef} className={styles.scatterPlot} role="group" tabIndex={0} aria-label={`Record chart for ${chart.x} and ${chart.y}. Use left and right arrow keys to inspect records.`} aria-describedby={inspectionId}
        onFocus={() => setHovered(null)} onPointerLeave={() => setHovered(null)}
        onKeyDown={event => { if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); setHovered(null); setSelected(Math.max(0, Math.min(points.length - 1, selected + (event.key === "ArrowLeft" ? -1 : 1)))); } }}>
    <svg role="img" aria-label={`${chart.x} versus ${chart.y}; illustrative coordinates, source values below`} viewBox={`0 0 ${width} 220`}>
      <title>{`${chart.x} versus ${chart.y}`}</title>
      {[12, 77, 143, 208].map(y => <line key={y} x1="12" y1={y} x2={width - 12} y2={y} className="patternGridLine" />)}
      {[0, .25, .5, .75, 1].map(level => <line key={level} x1={12 + level * (width - 24)} y1="12" x2={12 + level * (width - 24)} y2="208" className="patternGridLine" />)}
      <line x1={12 + position(Number(activePoint.x), minX, maxX) * (width - 24)} x2={12 + position(Number(activePoint.x), minX, maxX) * (width - 24)} y1="12" y2="208" className={styles.cursor} />
      {points.map((point, index) => <circle key={index} onPointerMove={() => setHovered(index)} onClick={() => { setHovered(null); setSelected(index); }} style={point.group === undefined ? undefined : { fill: groupColors[groups.indexOf(point.group) % groupColors.length] }} cx={12 + position(Number(point.x), minX, maxX) * (width - 24)} cy={208 - position(Number(point.y), minY, maxY) * 196} r={index === activeIndex ? 6 : 4} data-selected={index === activeIndex}><title>{`${point.group === undefined ? "" : `${point.group}; `}${chart.x}: ${point.x}; ${chart.y}: ${point.y}`}</title></circle>)}
    </svg>
      <div className={styles.horizontalScale} aria-label="Approximate horizontal scale"><span>{label(minX)}</span><span>{label(maxX)}</span></div>
      </div>
    </div>
    <div className={styles.horizontalTitle}>{chart.x}{chart.x_unit ? ` (${chart.x_unit})` : ""}</div>
    <div className={styles.pointInspection} id={inspectionId} role="status"><span>Record {activeIndex + 1}{activePoint.group === undefined ? "" : ` · ${activePoint.group}`}</span><dl><div><dt>{chart.x}</dt><dd>{activePoint.x}{chart.x_unit ? ` ${chart.x_unit}` : ""}</dd></div><div><dt>{chart.y}</dt><dd>{activePoint.y}{chart.y_unit ? ` ${chart.y_unit}` : ""}</dd></div></dl></div>
    <label className={styles.recordPicker}>Inspect a plotted record<select value={selected} onChange={event => { setHovered(null); setSelected(Number(event.target.value)); }}>{points.map((point, index) => <option key={index} value={index}>Record {index + 1}{point.group === undefined ? "" : ` · ${point.group}`}</option>)}</select></label>
    <figcaption><small>{points.length} displayed points · approximate coordinates and axis labels. Exact values are in the inspector and table.</small></figcaption>
    {!!groups.length && <ul className="relationshipLegend" aria-label="Groups in the chart">{groups.map((group, index) => <li key={group}><i style={{ background: groupColors[index % groupColors.length] }} aria-hidden="true" />{group}</li>)}</ul>}
  </figure>;
}

const directionLabels: Record<Direction, string> = { positive: "Move in the same direction", negative: "Move in opposite directions", weak: "No clear direction", unavailable: "Not available" };
function RelationshipScore({ name, value, direction }: { name: string; value: string | null; direction: Direction }) {
  const coordinate = value === null ? NaN : Number(value);
  return <div className="relationshipScore"><div><span>{name}</span><strong>{value ?? "Unavailable"}</strong></div>
    <div className="relationshipScale" aria-hidden="true"><span />{Number.isFinite(coordinate) && <i style={{ left: `${(Math.max(-1, Math.min(1, coordinate)) + 1) * 50}%` }} />}</div>
    <div className={styles.scoreAxis} aria-hidden="true"><span>−1</span><span>0</span><span>+1</span></div>
    <small>{directionLabels[direction]}</small>
  </div>;
}

function GroupRelationshipResults({ result, evidence, sources }: { result: GroupRelationshipResult; evidence?: PatternEvidence; sources?: { revision_id: string; understanding_id?: string }[] }) {
  const reversed = [...new Set([...result.comparisons.pearson.reversal_groups, ...result.comparisons.spearman.reversal_groups])];
  const eligible = result.groups.filter(group => group.status === "eligible");
  const excluded = result.groups.filter(group => group.status !== "eligible");
  const reasons = { sparse: "Fewer than 20 complete pairs", constant: "A measure does not vary", unstable: "A stable score could not be calculated" };
  const scoreCards = (statistics: Correlations, directions: Directions) => <div className="relationshipScores"><RelationshipScore name="Straight-line relationship" value={statistics.pearson} direction={directions.pearson} /><RelationshipScore name="Rank relationship" value={statistics.spearman} direction={directions.spearman} /></div>;
  return <section className={`patternResults groupRelationshipResults ${styles.results}`} aria-label="Relationships within groups">
    <header className="patternOverview"><span className="analysisEyebrow">SAME RECORDS · TWO VIEWS</span><h3>{result.status === "compared" ? "Does the overall pattern hold within groups?" : "More comparable groups are needed"}</h3>
      <p>{result.columns[0]} and {result.columns[1]}, grouped by {result.group_by}. The combined result uses exactly the complete pairs from the eligible groups below.</p>
      <dl className="patternCoverage"><div><dt>Usable rows</dt><dd>{result.coverage.covered_rows}</dd></div><div><dt>Usable groups</dt><dd>{result.coverage.eligible_groups}</dd></div><div><dt>Rows left out</dt><dd>{result.coverage.excluded_rows}</dd></div></dl>
    </header>
    {result.pooled ? <>
      <div className="relationshipTakeaway" data-reversal={reversed.length > 0}><h4>{reversed.length ? "The combined view can hide a different direction" : "Read both views before drawing a conclusion"}</h4><p>{reversed.length ? "At least one group points in the opposite direction from the combined result. The comparison below shows which relationship changes." : "A combined relationship may be stronger, weaker or similar inside groups. Weak scores are not a useful rule for prediction."}</p><p>These are observed relationships. They do not show that one measure causes the other.</p></div>
      <article className="relationshipPooled"><header><h4>All included groups together</h4><span>{result.pooled.support} complete pairs</span></header>{scoreCards(result.pooled.statistics, result.pooled.directions)}</article>
      <PatternChart finding={{ id: "group-comparison", type: "numeric_relationship", title: "Grouped relationship", summary: "", columns: result.columns, score: "", support: result.pooled.support, excluded: result.coverage.excluded_rows, chart: result.pooled.chart, notes: [] }} />
      <section aria-label="Group relationship comparisons"><h4>Within each group</h4><div className="relationshipGroupGrid">{eligible.map(group => <article className="relationshipGroup" key={group.id}>
        <header><h5>{group.label}</h5><span>{group.complete_pairs} complete pairs</span></header>
        {group.statistics && group.directions && scoreCards(group.statistics, group.directions)}
        {(["pearson", "spearman"] as const).map(method => result.comparisons[method].reversal_groups.includes(group.label) ? <p className="relationshipReversal" key={method}>{method === "pearson" ? "Straight-line" : "Rank"} direction reverses here.</p> : null)}
      </article>)}</div></section>
      <details className="patternDetails"><summary>See the plotted records and exact values</summary><p>The chart is a limited view of the recorded pairs. Scores above use every covered row; plotted coordinates are approximate.</p>
        <div className="tableWrap"><table><caption>Returned chart values</caption><thead><tr><th>{result.group_by}</th><th>{result.columns[0]} ({result.units[result.columns[0]]})</th><th>{result.columns[1]} ({result.units[result.columns[1]]})</th></tr></thead><tbody>{result.pooled.chart.points.map((point, index) => <tr key={index}><td>{point.group}</td><td>{point.x}</td><td>{point.y}</td></tr>)}</tbody></table></div>
      </details>
    </> : <><p>{result.reason || "At least two groups need 20 complete pairs each, with both measures varying."}</p><p>No combined relationship is claimed for this result.</p></>}
    {!!excluded.length && <aside className="relationshipExcluded"><h4>Groups left out</h4><ul>{excluded.map(group => <li key={group.id}><strong>{group.label}</strong>: {reasons[group.status as keyof typeof reasons]} · {group.complete_pairs} complete pairs.</li>)}</ul><p>These groups were not included in the combined score.</p></aside>}
    <details className="patternEvidence"><summary>Coverage, method and source evidence</summary><p>{result.coverage.source_rows} source rows; {result.coverage.filtered_rows} rows after required filters. {result.coverage.covered_rows} covered; {result.coverage.excluded_rows} excluded.</p>
      <dl className="patternStatistics"><div><dt>Missing group</dt><dd>{result.coverage.missing_category_rows}</dd></div><div><dt>Missing measure</dt><dd>{result.coverage.missing_pair_rows}</dd></div><div><dt>Sparse groups</dt><dd>{result.coverage.sparse_group_rows}</dd></div><div><dt>Constant groups</dt><dd>{result.coverage.constant_group_rows}</dd></div><div><dt>Unstable groups</dt><dd>{result.coverage.unstable_group_rows}</dd></div></dl>
      <p>Scores range from −1 to +1. Positive means the measures tend to move together; negative means they tend to move in opposite directions. These are approximate statistics, not probabilities. Directions are highlighted only when the score is at least 0.5 in size.</p>
      <div className="tableWrap"><table><caption>Every group and its returned scores</caption><thead><tr><th>Group</th><th>Status</th><th>Rows</th><th>Complete pairs</th><th>Missing pairs</th><th>Pearson</th><th>Spearman</th></tr></thead><tbody>{result.groups.map(group => <tr key={group.id}><td>{group.label}</td><td>{group.status}</td><td>{group.rows}</td><td>{group.complete_pairs}</td><td>{group.excluded_pairs}</td><td>{group.statistics?.pearson ?? "Unavailable"}</td><td>{group.statistics?.spearman ?? "Unavailable"}</td></tr>)}</tbody></table></div>
      <ul>{result.limitations.map((item, index) => <li key={index}>{item}</li>)}{result.pooled?.notes.map((item, index) => <li key={`pooled-${index}`}>{item}</li>)}</ul>
      {!!result.exclusions.length && <ul>{result.exclusions.map((item, index) => <li key={index}><strong>{item.column}</strong>: {item.reason}</li>)}</ul>}
      <p>Method: {result.version} · Engine: {result.engine_version}</p>
      {evidence && <p className="checksum">Source receipt: {evidence.query_id}{evidence.result_checksum ? ` · Result checksum: ${evidence.result_checksum}` : ""}</p>}
      {sources?.map(source => <p className="checksum" key={source.revision_id}>Source revision: {source.revision_id}{source.understanding_id ? ` · Definitions: ${source.understanding_id}` : ""}</p>)}
    </details>
  </section>;
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

function CohortComparisonResults({ result, evidence, sources, onAsk, busy }: {
  result: CohortComparisonResult;
  evidence?: PatternEvidence;
  sources?: { revision_id: string; understanding_id?: string }[];
  onAsk?: (question: string) => void;
  busy: boolean;
}) {
  const target = result.target.value;
  const other = "All other named groups";
  return <section className={`patternResults ${styles.results} ${styles.cohort}`} aria-label="Selected group comparison">
    <header className="patternOverview">
      <span className="analysisEyebrow">YOUR GROUP · COMPARED WITH THE REST</span>
      <h3>{result.status === "compared" ? `What is different about ${target}?` : `What we can compare for ${target}`}</h3>
      <p><strong>{result.target.column} = {target}</strong>, compared with all other nonmissing values of {result.target.column}. Missing group labels are kept out of both sides.</p>
      <dl className="patternCoverage">
        <div><dt>{target} rows</dt><dd>{result.coverage.target_rows}</dd></div>
        <div><dt>Other group rows</dt><dd>{result.coverage.other_rows}</dd></div>
        <div><dt>Missing group label</dt><dd>{result.coverage.missing_target_rows}</dd></div>
      </dl>
    </header>
    <aside className={styles.cohortTakeaway}>
      <h4>What this comparison can tell you</h4>
      <p>These are differences in the recorded data. They help you choose what to check next; they do not explain why a difference happened or prove that changing a condition will change the outcome.</p>
      {result.status === "insufficient_data" && <p>There is not enough usable data for a supported numerical comparison. Group counts and available category summaries are still shown.</p>}
    </aside>
    {result.numeric.length > 0 && <section aria-label="Measured group differences">
      <h4>Compare the recorded measures</h4>
      <p>Small, equal and unavailable differences stay visible. Each measure uses its own complete values; missing values are not treated as zero.</p>
      <div className="patternFindings">{result.numeric.map(item => {
        const comparable = item.status === "compared" && item.target_mean !== null && item.other_mean !== null;
        return <article className="patternFinding" aria-label={`Comparison of ${item.column}`} key={item.column}>
          <h5>{item.column} <span className={styles.cohortUnit}>({item.unit})</span></h5>
          {comparable ? <>
            <PatternChart finding={{ id: item.column, type: "group_difference", title: `Average ${item.column}`, summary: "", columns: [result.target.column, item.column], score: "", support: item.target_count + item.other_count, excluded: 0, notes: [], chart: { kind: "bar", x: result.target.column, y: item.column, y_unit: item.unit, points: [{ x: target, y: item.target_mean!, count: item.target_count }, { x: other, y: item.other_mean!, count: item.other_count }] } }} />
            <dl className={styles.cohortDifference}><dt>Average difference · {target} minus the other groups</dt><dd>{item.difference === null ? "Not available" : `${item.difference} ${item.unit}`}</dd></dl>
          </> : <p className={styles.cohortUnavailable}>There are not enough comparable values for a supported difference. The available summaries and counts are shown below.</p>}
          <div className={`tableWrap ${styles.cohortTable}`} tabIndex={0} role="region" aria-label={`Exact group values for ${item.column}`}>
            <table><caption>{item.column}: returned values in {item.unit}</caption><thead><tr><th scope="col">Group</th><th scope="col">Complete values</th><th scope="col">Average</th><th scope="col">Middle value</th></tr></thead><tbody>
              <tr><th scope="row">{target}</th><td>{item.target_count}</td><td>{item.target_mean ?? "Not available"}</td><td>{item.target_median ?? "Not available"}</td></tr>
              <tr><th scope="row">{other}</th><td>{item.other_count}</td><td>{item.other_mean ?? "Not available"}</td><td>{item.other_median ?? "Not available"}</td></tr>
            </tbody></table>
          </div>
          <details className="patternDetails"><summary>How to read this comparison</summary><p>The middle value is the median. Averages and medians retain the server-returned precision; bar lengths are illustrative.</p><p>Standardized difference: <strong>{item.standardized_difference ?? "Not available"}</strong>. This describes the gap relative to variation in these rows. It is not a probability, a cause or a proven action benefit.</p></details>
        </article>;
      })}</div>
    </section>}
    {result.categories.length > 0 && <section className={styles.cohortCategories} aria-label="Category mix comparison">
      <h4>Do the groups contain different kinds of records?</h4>
      <p>Differences in the mix can suggest another comparison. They do not establish the reason for a measured gap.</p>
      {result.categories.map(category => <article key={category.column}>
        <h5>{category.column}</h5><p>{category.target_observed} usable {target} rows · {category.other_observed} usable rows in the other groups. Shares run from 0 to 1 within each side.</p>
        <div className={`tableWrap ${styles.cohortTable}`} tabIndex={0} role="region" aria-label={`Category counts for ${category.column}`}>
          <table><caption>{category.column}: counts and recorded shares</caption><thead><tr><th scope="col">Value</th><th scope="col">{target} rows</th><th scope="col">{target} share</th><th scope="col">Other rows</th><th scope="col">Other share</th></tr></thead><tbody>{category.levels.map((level, index) => <tr key={`${index}-${level.value}`}><th scope="row">{level.value}</th><td>{level.target_count}</td><td>{level.target_share ?? "Not available"}</td><td>{level.other_count}</td><td>{level.other_share ?? "Not available"}</td></tr>)}</tbody></table>
        </div>
      </article>)}
    </section>}
    {(result.next_steps.length > 0 || result.suggestions.length > 0) && <section className={styles.cohortNext} aria-label="Next checks for this group">
      <h4>What to check next</h4>
      {result.next_steps.length > 0 && <ul>{result.next_steps.map((step, index) => <li key={index}>{step}</li>)}</ul>}
      {onAsk && result.suggestions.length > 0 && <div className="suggestionChips" role="group" aria-label="Ask about this comparison">{result.suggestions.map((question, index) => <button key={`${index}-${question}`} type="button" disabled={busy || question.length > 500} onClick={() => onAsk(question)}>{question}</button>)}</div>}
      <p>These are investigation steps. This comparison does not prescribe a treatment, budget or operational change.</p>
    </section>}
    <details className="patternEvidence"><summary>Scope, method and source evidence</summary>
      <p>{result.coverage.source_rows} source rows; {result.coverage.filtered_rows} rows after required filters. The comparison uses every eligible row within the method limits.</p>
      <ul>{result.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>
      {result.exclusions.length > 0 && <><h4>Fields left out</h4><ul>{result.exclusions.map((item, index) => <li key={index}><strong>{item.column}</strong>: {item.reason}</li>)}</ul></>}
      <p>Method: {result.version} · Engine: {result.engine_version}</p>
      {evidence && <p className="checksum">Source receipt: {evidence.query_id}{evidence.result_checksum ? ` · Result checksum: ${evidence.result_checksum}` : ""}</p>}
      {sources?.map(source => <p className="checksum" key={source.revision_id}>Source revision: {source.revision_id}{source.understanding_id ? ` · Definitions: ${source.understanding_id}` : ""}</p>)}
    </details>
  </section>;
}

export function PatternResults({ result, evidence, sources, onAsk, busy = false }: { result: PatternResult; evidence?: PatternEvidence; sources?: { revision_id: string; understanding_id?: string }[]; onAsk?: (question: string) => void; busy?: boolean }) {
  const instance = useId();
  if ("target" in result) return <CohortComparisonResults result={result} evidence={evidence} sources={sources} onAsk={onAsk} busy={busy} />;
  if ("pooled" in result) return <GroupRelationshipResults result={result} evidence={evidence} sources={sources} />;
  const empty = result.status === "insufficient_data" ? "A little more data is needed" : "No clear pattern found";
  return <section className={`patternResults ${styles.results}`} aria-label="Measured data patterns">
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
