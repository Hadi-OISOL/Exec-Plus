/* Use case: Reviews complete observed periods with explicit seasonal or two-window rules.
What it does: Saves private reproducible findings, displays exact evidence and records human review without predictions or automatic corrections. */
"use client";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import type { AnalysisOptions, AnalysisSummary } from "./decision-types";
import { AnswerVisualization } from "./answer-visualization";
import { ResultExportActions } from "./result-export-actions";
import { DRIFT_METHOD, SEASONAL_METHOD, fractionText } from "./calendar-anomaly-types";
import type { CalendarBody, CalendarMethod, DriftResult, SeasonalResult } from "./calendar-anomaly-types";
import styles from "./calendar-anomaly-panel.module.css";

const post = (body: object): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export function CalendarAnomalyPanel({ root, request, onReview, method }: { root: string; request: ApiRequest; onReview: () => void; method: CalendarMethod }) {
  const datasetRoot = root.split("/uploads/")[0];
  const runsRoot = `${datasetRoot}/decision-analysis`;
  const methodId = method === "seasonal" ? SEASONAL_METHOD : DRIFT_METHOD;
  const [options, setOptions] = useState<AnalysisOptions | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [selected, setSelected] = useState<CalendarBody | null>(null);
  const [name, setName] = useState("");
  const [metric, setMetric] = useState("");
  const [dateColumn, setDateColumn] = useState("");
  const [frequency, setFrequency] = useState("daily");
  const [aggregation, setAggregation] = useState<"sum" | "avg">("sum");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [boundary, setBoundary] = useState("");
  const [comparisonStart, setComparisonStart] = useState("");
  const [comparisonEnd, setComparisonEnd] = useState("");
  const [threshold, setThreshold] = useState(method === "seasonal" ? "3.5" : "0.2");
  const [materiality, setMateriality] = useState("0");
  const [filter, setFilter] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const operation = useRef<AbortController | null>(null);
  const source = options?.calendar_anomalies;
  const metricName = metric || source?.metrics[0]?.name || "";
  const timeName = dateColumn || source?.date_columns[0] || "";
  const allowedAggregations = source?.metrics.find(item => item.name === metricName)?.aggregations.filter(item => item === "sum" || item === "avg") || [];
  const calculation = allowedAggregations.includes(aggregation) ? aggregation : allowedAggregations[0] || "sum";
  const unit = source?.metrics.find(item => item.name === metricName)?.unit || "";
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([request<AnalysisOptions>(`${root}/decision-analysis/options`, { signal: controller.signal }), request<AnalysisSummary[]>(runsRoot, { signal: controller.signal })])
      .then(([nextOptions, saved]) => { if (!controller.signal.aborted) { setOptions(nextOptions); setHistory(saved); } })
      .catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load calendar options."); });
    return () => { controller.abort(); operation.current?.abort(); };
  }, [root, runsRoot, request]);
  async function work(label: string, action: (signal: AbortSignal) => Promise<void>) {
    if (operation.current) return;
    const controller = new AbortController(); operation.current = controller;
    setPending(label); setError(""); setMessage("");
    try { await action(controller.signal); }
    catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "This check could not complete."); }
    finally { if (!controller.signal.aborted) setPending(""); if (operation.current === controller) operation.current = null; }
  }
  async function reload() {
    await work("Checking available sources and saved results…", async signal => {
      const [nextOptions, saved] = await Promise.all([request<AnalysisOptions>(`${root}/decision-analysis/options`, { signal }), request<AnalysisSummary[]>(runsRoot, { signal })]);
      if (!signal.aborted) { setOptions(nextOptions); setHistory(saved); setConfirmed(false); }
    });
  }
  async function create(event: FormEvent) {
    event.preventDefault(); if (!source || !confirmed) return;
    await work("Checking every period and saving private evidence…", async signal => {
      const common = { name: name.trim() || (method === "seasonal" ? "Seasonal unusual values" : "Two-window comparison"), model: methodId, revision_id: source.revision_id, understanding_id: source.understanding_id, metric: metricName, time_column: timeName, aggregation: calculation, frequency, coverage_confirmed: confirmed, materiality, filters: filter ? [{ column: filter, operator: "eq", value: filterValue }] : [] };
      const settings = method === "seasonal" ? { coverage_start: start, coverage_end: end, training_end: boundary, season_length: frequency === "daily" ? 7 : 12, threshold } : { reference_start: start, reference_end: end, comparison_start: comparisonStart, comparison_end: comparisonEnd, minimum_cdf_separation: threshold };
      const value = await request<CalendarBody>(`${root}/decision-analysis/${method === "seasonal" ? "seasonal-anomalies" : "distribution-drift"}`, { ...post({ ...common, ...settings }), signal });
      if (signal.aborted) return;
      setSelected(value); setConfirmed(false); setMessage("Saved privately. The source data has not changed.");
      try { const saved = await request<AnalysisSummary[]>(runsRoot, { signal }); if (!signal.aborted) setHistory(saved); }
      catch (cause) { if (!signal.aborted) throw new Error(`Your result is saved. History could not reload: ${cause instanceof Error ? cause.message : "Try Reload saved results."}`); }
    });
  }
  async function open(id: string) {
    await work("Replaying the original private evidence…", async signal => {
      const body = await request<CalendarBody>(`${runsRoot}/${id}`, { signal });
      if (!signal.aborted) { setSelected(body); setMessage("The original result and every receipt were verified."); }
    });
  }
  async function review(target: string, status: string, note: string) {
    if (!selected) return;
    await work("Recording your review…", async signal => {
      const body = await request<CalendarBody>(`${runsRoot}/${selected.run.id}/reviews`, { ...post({ target, status, note, expected_version: selected.review_version }), signal });
      if (!signal.aborted) { setSelected(body); setMessage("Review saved. No source values or detection rules changed."); }
    });
  }
  const saved = history.filter(item => item.method_version === methodId);
  return <section className={`panel ${styles.panel}`} aria-label="Calendar analysis">
    <header><p className="eyebrow">OBSERVED DATA · PRIVATE REVIEW</p><h2>{method === "seasonal" ? "Did a day or month behave unusually?" : "Did the values change between two periods?"}</h2>
      <p>{method === "seasonal" ? "Choose an earlier learning period. Later values are compared with the same day last week or month last year, using a fixed reference." : "Choose two complete time windows. We compare their observed values using the same measure, unit and population."}</p>
      <p>No future forecast, automatic correction or proven cause is produced.</p></header>
    {pending && <p role="status">{pending}</p>}{message && <p role="status">{message}</p>}{error && <p role="alert" className="error">{error}</p>}
    {!options ? <p>Loading calendar options…</p> : !source || source.state !== "ready" ? <div className={styles.notice}><h3>A confirmed date and measure are needed</h3><p>Review the date field and fixed measurement unit first. Files without dates can still use the snapshot unusual-values check or explore patterns.</p>{source?.blockers?.map(item => <p key={item.code}>{item.message}</p>)}<button type="button" onClick={onReview}>Review data meanings</button></div> : <form className={styles.form} onSubmit={create} onChange={event => { if (!(event.target instanceof HTMLInputElement) || event.target.name !== "coverage-confirmation") setConfirmed(false); }}>
      <fieldset disabled={Boolean(pending)}><legend>1. Choose what to compare</legend><div className={styles.grid}>
        <label>Analysis name<input maxLength={100} value={name} onChange={event => setName(event.target.value)} placeholder="Optional name" /></label>
        <label>Measure<select required value={metricName} onChange={event => setMetric(event.target.value)}>{source.metrics.map(item => <option key={item.name} value={item.name}>{item.name} · {item.unit}</option>)}</select></label>
        <label>Date field<select required value={timeName} onChange={event => setDateColumn(event.target.value)}>{source.date_columns.map(item => <option key={item}>{item}</option>)}</select></label>
        <label>Period size<select value={frequency} onChange={event => setFrequency(event.target.value)}><option value="daily">Daily</option><option value="monthly">Monthly</option></select></label>
        <label>Calculation per period<select value={calculation} onChange={event => setAggregation(event.target.value as "sum" | "avg")}>{allowedAggregations.map(item => <option key={item} value={item}>{item === "sum" ? "Total" : "Average"}</option>)}</select></label>
      </div><details><summary>Optional population filter</summary><div className={styles.grid}><label>Include only this group<select value={filter} onChange={event => setFilter(event.target.value)}><option value="">All permitted rows</option>{options.entities.filter(item => !source.date_columns.includes(item)).map(item => <option key={item}>{item}</option>)}</select></label><label>Group equals<input required={Boolean(filter)} value={filterValue} onChange={event => setFilterValue(event.target.value)} /></label></div></details></fieldset>
      <fieldset disabled={Boolean(pending)}><legend>2. Declare complete time windows</legend><p>Choose dates you know are complete. Gaps and missing measurements are refused, never filled with zero. Monthly windows must cover whole calendar months.</p>
        {source.defaults.coverage_start && <p>Observed source dates: {source.defaults.coverage_start} to {source.defaults.coverage_end}. These dates alone do not prove completeness.</p>}
        <div className={styles.grid}><label>{method === "seasonal" ? "Coverage starts" : "Reference window starts"}<input type="date" required value={start} onChange={event => setStart(event.target.value)} /></label><label>{method === "seasonal" ? "Coverage ends" : "Reference window ends"}<input type="date" required value={end} onChange={event => setEnd(event.target.value)} /></label>
          {method === "seasonal" ? <label>Last training period<input type="date" required value={boundary} onChange={event => setBoundary(event.target.value)} /></label> : <><label>Comparison window starts<input type="date" required value={comparisonStart} onChange={event => setComparisonStart(event.target.value)} /></label><label>Comparison window ends<input type="date" required value={comparisonEnd} onChange={event => setComparisonEnd(event.target.value)} /></label></>}
        </div><p>{method === "seasonal" ? `Cycle: ${frequency === "daily" ? "7 days; at least 28 training days" : "12 months; at least 36 training months"}, followed by at least 3 later periods. For monthly data, the training boundary is the first day of the last training month.` : "Each window needs at least 8 complete periods. The comparison window must come after the reference window; the windows cannot overlap."} At most 1,200 included periods.</p>
      </fieldset><fieldset disabled={Boolean(pending)}><legend>3. Choose a review rule</legend><div className={styles.grid}>
        <label>{method === "seasonal" ? "Unusualness threshold · 3 to 10" : "Minimum cumulative share separation · 0 to 1"}<input required inputMode="decimal" value={threshold} onChange={event => setThreshold(event.target.value)} /></label>
        <label>{method === "seasonal" ? "Minimum difference from seasonal reference" : "Minimum average distribution distance"} · {unit}<input required inputMode="decimal" value={materiality} onChange={event => setMateriality(event.target.value)} /></label>
      </div><p>{method === "seasonal" ? "A 3.5 threshold is an exploratory review rule, not a probability or guaranteed error rate. An isolated spike may also flag the same day one week later." : "For example, 0.2 means a gap greater than one fifth between the cumulative shares at some observed value. The distance threshold uses the measure’s unit. These rules are not a significance test."}</p>
        <label className="checkLabel"><input type="checkbox" name="coverage-confirmation" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />I confirm these windows contain complete historical periods for the same measure, unit and population. No missing periods should be treated as zero.</label>
      </fieldset><button disabled={Boolean(pending) || !confirmed || !allowedAggregations.length}>Calculate and save privately</button>
    </form>}
    <section className={styles.history} aria-label="Saved calendar checks"><h3>Your saved {method === "seasonal" ? "seasonal checks" : "window comparisons"}</h3><p>These results and reviews are private to you.</p><button type="button" disabled={Boolean(pending)} onClick={reload}>Reload saved results</button>{saved.length ? <ul>{saved.map(item => <li key={item.id}><button type="button" disabled={Boolean(pending)} onClick={() => open(item.id)}>{item.name}</button></li>)}</ul> : <p>No saved checks of this type yet.</p>}</section>
    {selected && <CalendarResult key={selected.run.id} body={selected} datasetRoot={datasetRoot} pending={Boolean(pending)} onReplay={() => open(selected.run.id)} onReview={review} />}
  </section>;
}

function SeasonalEvidence({ result, metric, unit }: { result: SeasonalResult; metric: string; unit: string }) {
  const [measure, setMeasure] = useState<"actual" | "expected">("actual");
  const plotted = measure === "expected" ? result.history.filter(row => row.phase === "evaluation") : result.history;
  return <><dl className={styles.cards}><div><dt>Later periods checked</dt><dd>{result.evaluated_periods}</dd></div><div><dt>Periods to review</dt><dd>{result.flagged_periods}</dd></div><div><dt>Training ends</dt><dd>{result.reference.training_end}</dd></div></dl><p className={styles.notice}>An isolated spike can produce an opposite flag one cycle later. A sustained change may become the seasonal reference after one cycle. A flag is a prompt to investigate.</p>
    <label>Values shown on the plot<select value={measure} onChange={event => setMeasure(event.target.value as "actual" | "expected")}><option value="actual">Observed values</option><option value="expected">Seasonal reference for later periods</option></select></label>
    {measure === "expected" && <p>The reference is shown for all {result.evaluated_periods} later periods that were scored. Earlier training periods were not scored; their complete observations remain in the evidence table.</p>}
    <AnswerVisualization key={measure} title={measure === "actual" ? "Observed calendar values" : "Earlier-season comparison reference"} columns={["Period", `${metric} (${unit})`, "Phase", "Flagged"]} rows={plotted.map(row => [row.period, row[measure], row.phase, row.flagged])} initialChart="line" allowLine />
    <details><summary>Every period and exact seasonal comparison</summary><AnswerVisualization title="Complete seasonal evidence" chartAllowed={false} initialMode="table" columns={["Period", "Observed", "Phase", "Earlier period", "Earlier value", "Expected", "Residual", "Absolute difference", "Score (not probability)", "Flagged"]} rows={result.history.map(row => [row.period, row.actual, row.phase, row.reference_period, row.seasonal_reference, row.expected, row.residual, row.absolute_difference, row.score, row.flagged])} /></details>
    <details><summary>How the training reference was fixed</summary><p>The first {result.training_periods} periods define the reference using {result.reference.residual_count} seasonal differences. No later values refit it.</p><dl><dt>Residual center</dt><dd>{result.reference.baseline}</dd><dt>Median absolute deviation</dt><dd>{result.reference.mad}</dd><dt>Interquartile range</dt><dd>{result.reference.iqr}</dd><dt>Rule used</dt><dd>{result.reference.scale_method.replaceAll("_", " ")}</dd><dt>Threshold / minimum difference</dt><dd>{result.threshold} / {result.materiality} {unit}</dd></dl><p>Precision, recall and false-alarm rate are unavailable without independently labelled outcomes. Scores are not probabilities.</p></details></>;
}

function DriftEvidence({ result, metric, unit }: { result: DriftResult; metric: string; unit: string }) {
  const separation = result.maximum_cdf_separation;
  const distance = result.wasserstein_distance;
  return <><p className={styles.notice}>{result.review_flag ? "The two-window difference meets your declared review rule." : "This comparison does not meet your declared review rule."} This does not prove a cause, an error or that individual records are normal.</p>
    <dl className={styles.cards}><div><dt>Cumulative share separation</dt><dd>{separation.display_exact ? separation.display : `${separation.numerator}/${separation.denominator}`}</dd></div><div><dt>Average distribution distance · {unit}</dt><dd>{distance.display_exact ? distance.display : `${distance.numerator}/${distance.denominator}`}</dd></div><div><dt>Median change · {unit}</dt><dd>{result.median_change}</dd></div></dl><p>Fractions retain exact values. Cumulative separation compares shares; average distance measures how far the observed distributions differ in {unit}.</p><details><summary>Decimal displays and exact fractions</summary><p>Share separation: {fractionText(separation)}.</p><p>Average distance: {fractionText(distance)} {unit}.</p><p>A ≈ decimal display is rounded; the fraction remains exact.</p></details>
    <div className="tableWrap" tabIndex={0} role="region" aria-label="Declared comparison windows"><table><thead><tr><th>Window</th><th>Start</th><th>End</th><th>Periods</th><th>Minimum</th><th>Median</th><th>Maximum</th></tr></thead><tbody>{(["reference", "comparison"] as const).map(name => <tr key={name}><th>{name}</th><td>{result.windows[name].start}</td><td>{result.windows[name].end}</td><td>{result.windows[name].count}</td><td>{result.windows[name].minimum}</td><td>{result.windows[name].median}</td><td>{result.windows[name].maximum}</td></tr>)}</tbody></table></div>
    <AnswerVisualization title="Observed values in the declared windows" columns={["Period", `${metric} (${unit})`, "Window"]} rows={result.observations.map(row => [row.period, row.value, row.window])} initialChart="line" allowLine connectLinePoints={false} />
    <p>Dots show recorded periods. Gaps between windows are not filled or connected. A different mix of weekdays or seasons can explain a distribution change.</p>
    <details><summary>Exact distribution counts and distances</summary><AnswerVisualization title="Exact empirical distributions" chartAllowed={false} initialMode="table" columns={["Observed value", "Reference count", "Comparison count", "Reference cumulative count", "Comparison cumulative count", "Reference share", "Comparison share", "Absolute share gap", "Next value", "Distance contribution"]} rows={result.distribution.map(row => [row.value, row.reference_count, row.comparison_count, row.reference_cumulative, row.comparison_cumulative, fractionText(row.reference_cdf), fractionText(row.comparison_cdf), fractionText(row.absolute_cdf_difference), row.next_value, fractionText(row.distance_contribution)])} /></details><p>Review requires separation greater than {result.minimum_cdf_separation} and a nonzero average distance of at least {result.materiality} {unit}. There is no significance test or calibrated false-alarm guarantee.</p></>;
}

function CalendarResult({ body, datasetRoot, pending, onReplay, onReview }: { body: CalendarBody; datasetRoot: string; pending: boolean; onReplay: () => void; onReview: (target: string, status: string, note: string) => Promise<void> }) {
  const result = body.run.result;
  const [target, setTarget] = useState(""); const [status, setStatus] = useState("investigate"); const [note, setNote] = useState("");
  const metric = body.run.request.metric; const unit = body.run.evidence.units[metric];
  const finding = target || result.findings[0]?.id || "";
  return <section className={styles.result} aria-label="Saved calendar result"><h3>{body.run.name}</h3><p>{body.current ? "Current source and meanings." : "Historical source or meanings. Review current data before acting."} Method: {body.run.method_version}.</p><ResultExportActions path={`${datasetRoot}/analyses/${body.run.id}/export?kind=anomaly`} charts={[result.version === "temporal-anomaly-v1" ? "Observed periods and seasonal reference" : "Observed values in the two declared windows"]} /><button type="button" onClick={onReplay} disabled={pending}>Replay original calendar evidence</button>
    {result.version === "temporal-anomaly-v1" ? <SeasonalEvidence result={result} metric={metric} unit={unit} /> : <DriftEvidence result={result} metric={metric} unit={unit} />}
    <h4>Findings to review</h4>{result.findings.length ? <>{result.version === "temporal-anomaly-v1" ? <AnswerVisualization title="Recorded calendar findings" initialMode="table" chartAllowed={false} columns={["Finding", "Observed", "Seasonal reference", "Absolute difference", "Score (not probability)"]} rows={result.findings.map(item => [item.period || "Whole window comparison", item.value ?? null, item.baseline ?? null, item.absolute_difference ?? null, item.score ?? null])} /> : <p>The review applies to the whole two-window comparison. It does not label any individual row or period as an error.</p>}<form onSubmit={async event => { event.preventDefault(); await onReview(finding, status, note); }} className={styles.form}><div className={styles.grid}><label>Finding to review<select required value={finding} onChange={event => setTarget(event.target.value)}>{result.findings.map(item => <option value={item.id} key={item.id}>{item.period || "Whole window comparison"}</option>)}</select></label><label>Review decision<select value={status} onChange={event => setStatus(event.target.value)}><option value="investigate">Investigate</option><option value="expected">Expected</option><option value="data_issue">Data issue</option><option value="dismissed">Dismiss</option></select></label></div><label>Reason for your review<textarea required maxLength={1000} value={note} onChange={event => setNote(event.target.value)} /></label><button disabled={pending}>Save private review</button></form></> : <p>No findings met the declared rule. This does not prove there are no other unusual patterns.</p>}
    <details><summary>Review history ({body.reviews.length})</summary>{body.reviews.map(item => <p key={item.id}>{item.sequence}. {item.status.replaceAll("_", " ")} · {item.note}</p>)}</details>
    <details><summary>Method limits and source evidence</summary><ul>{result.limitations.map(item => <li key={item}>{item}</li>)}</ul><p>Matching source records: {body.run.evidence.matching_records}. All included periods were checked for missing values.</p><p>Calculation: {body.run.request.aggregation} of {metric}, in {unit}, per {body.run.request.frequency} period.</p><p>Filters: {body.run.request.filters.length ? JSON.stringify(body.run.request.filters) : "All permitted rows; confirmed required filters also apply."}</p><p>Private source receipts: {body.run.evidence.calendar_query_ids.flat().join(", ")}.</p><p>Result checksum: {body.run.evidence.result_checksum}</p></details>
  </section>;
}
