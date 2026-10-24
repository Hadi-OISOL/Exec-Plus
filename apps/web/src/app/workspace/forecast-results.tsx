/* Use case: Makes versioned forecasts and their limitations inspectable.
What it does: Displays server-calculated estimates, holdout errors and comparison evidence without calculating business values in the browser. */

import { useEffect, useId, useRef, useState } from "react";
import styles from "./forecast.module.css";
import { displayMetric } from "./visualization-values";
import { RecordTable } from "./explore-components";
import { ResultExportActions } from "./result-export-actions";
import {
  forecastRows,
  type ForecastComparison,
  type ForecastMetrics,
  type ForecastPoint,
  type ForecastRegressors,
  type ForecastRun,
} from "./forecast-types";

export function ForecastAccuracy({
  value,
  unit,
  title,
}: {
  value: ForecastMetrics;
  unit: string;
  title: string;
}) {
  return (
    <section className="forecastAccuracy" aria-label={title}>
      <h3>{title}</h3>
      <p>
        {value.count} evaluated periods. Lower error is better; these figures do
        not guarantee future performance.
      </p>
      <div className="forecastScoreGrid">
        {[
          ["Mean absolute error", value.mae, unit],
          ["Root mean squared error", value.rmse, unit],
          ["Weighted absolute percentage error", value.wape_percent, "%"],
        ].map(([label, number, suffix]) => (
          <div className="forecastScore" key={label}>
            <span>{label}</span>
            <strong>
              {number === null ? "Not available" : `${number} ${suffix}`}
            </strong>
          </div>
        ))}
      </div>
      <details>
        <summary>How to read the errors</summary>
        <p>
          Mean absolute error is the average size of an error in the metric’s
          unit. Root mean squared error gives larger errors more weight.
          Weighted absolute percentage error compares total absolute error with
          the total magnitude of actual values.
        </p>
        <p>
          Mean absolute percentage error:{" "}
          {value.mape_percent === null
            ? "Not available"
            : `${value.mape_percent}%`}
          . Nonzero actual periods: {value.mape_count}. Zero actual periods:{" "}
          {value.zero_actual_count}. This percentage is unavailable when any
          actual value is zero. Error percentages are not a percentage of
          accuracy.
        </p>
      </details>
    </section>
  );
}

export function ForecastChart({
  run,
  rows,
}: {
  run: ForecastRun;
  rows: ForecastPoint[];
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const inspectionId = useId();
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(700);
  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(120, Math.min(1200, entry.contentRect.width - 64))));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const history = run.result.history.slice(-48);
  const points = [
    ...history.map((point) => ({
      period: point.period,
      actual: point.actual,
      estimate: null,
      lower: null,
      upper: null,
    })),
    ...rows,
  ];
  const all = points
    .flatMap((point) => [
      point.actual,
      point.estimate,
      point.lower,
      point.upper,
    ])
    .filter((value) => value !== null && value !== undefined && value.trim() !== "")
    .map(Number)
    .filter(Number.isFinite);
  if (!all.length) return <p>No finite values can be plotted. The original values remain in the table below.</p>;
  const minimum = Math.min(...all);
  const maximum = Math.max(...all);
  const scale = Math.max(Math.abs(minimum), Math.abs(maximum), 1);
  const span = maximum / scale - minimum / scale;
  const x = (index: number) =>
    12 + (index * (width - 24)) / Math.max(points.length - 1, 1);
  const y = (value: string) => span === 0 ? 132 : 238 - ((Number(value) / scale - minimum / scale) / span) * 212;
  const forecastStart = history.length;
  const finite = (value: string | null | undefined): value is string => value !== null && value !== undefined && value.trim() !== "" && Number.isFinite(Number(value));
  const band = rows.length > 1 && rows.every(
    (point) =>
      finite(point.lower) && finite(point.upper),
  )
    ? [
        ...rows.map(
          (point, index) => `${x(index + forecastStart)},${y(point.upper)}`,
        ),
        ...rows
          .map(
            (point, index) => `${x(index + forecastStart)},${y(point.lower)}`,
          )
          .reverse(),
      ].join(" ")
    : "";
  const selectedIndex = Math.max(0, selected === null ? forecastStart < points.length ? forecastStart : points.length - 1 : points.findIndex(point => point.period === selected));
  const hoveredIndex = points.findIndex(point => point.period === hovered);
  const inspectedIndex = hoveredIndex < 0 ? selectedIndex : hoveredIndex;
  const selectedPoint = points[inspectedIndex];
  const latestObserved = history.findLast(point => finite(point.actual));
  const boundary = forecastStart ? x(forecastStart - .5) : 0;
  const axisLabel = (value: number) => value === 0 ? "0" : Math.abs(value) >= 1e6 || Math.abs(value) < .001 ? value.toExponential(1) : Number(value.toPrecision(4)).toLocaleString("en-US");
  const levels = [0, 1 / 3, 2 / 3, 1];
  const move = (step: number) => { setHovered(null); setSelected(points[Math.max(0, Math.min(points.length - 1, selectedIndex + step))].period); };
  return (
    <div className={`forecastChart ${styles.chart}`}>
      <header className={styles.heading}><div><span className={styles.eyebrow}>OBSERVED & ESTIMATED</span><h4>{run.request.metric} <span>· {run.evidence.unit}</span></h4></div><span>{run.request.frequency === "daily" ? "By day" : "By month"}</span></header>
      <div className={styles.highlights}>
        <div><span>Last value before forecast</span><strong title={latestObserved?.actual ?? "Not available"}>{displayMetric(latestObserved?.actual ?? "Not available")}</strong><small>{latestObserved?.period ?? "No recorded observation"}</small></div>
        <div data-estimate="true"><span>First forecast value</span><strong title={rows[0]?.estimate ?? "Not available"}>{displayMetric(rows[0]?.estimate ?? "Not available")}</strong><small>{rows[0]?.period ?? "No forecast period"} · {run.evidence.unit}</small></div>
      </div>
      <div className={`forecastLegend ${styles.legend}`}>
        <span>
          <i className="actualKey" aria-hidden="true" />
          Observed
        </span>
        <span>
          <i className="estimateKey" aria-hidden="true" />
          Forecast
        </span>
        <span>
          <i className="rangeKey" aria-hidden="true" />
          Uncertainty range
        </span>
      </div>
      <div className={styles.plotShell} ref={container}>
        <div className={styles.axis} aria-label="Approximate value scale">{levels.map(level => <span key={level}>{axisLabel((maximum / scale * (1 - level) + minimum / scale * level) * scale)}</span>)}</div>
        <div className={styles.plot} role="group" tabIndex={0} aria-label="Forecast chart. Use left and right arrow keys to inspect periods." aria-describedby={inspectionId}
          onFocus={() => setHovered(null)} onPointerLeave={() => setHovered(null)}
          onKeyDown={event => { if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); setHovered(null); move(event.key === "ArrowLeft" ? -1 : 1); } }}>
          <svg viewBox={`0 0 ${width} 264`} role="img" aria-label="Observed history and saved forecast with uncertainty range; exact values follow in the table">
        {rows.length > 0 && <rect x={boundary} y="12" width={width - boundary} height="238" className={styles.forecastZone} />}
        {levels.map(level => <line key={level} x1="0" x2={width} y1={26 + level * 212} y2={26 + level * 212} className={styles.grid} />)}
        {rows.length > 0 && forecastStart > 0 && <line x1={boundary} x2={boundary} y1="12" y2="250" className={styles.boundary} />}
        {band && <polygon points={band} className="forecastBand" />}
        <line x1={x(inspectedIndex)} x2={x(inspectedIndex)} y1="12" y2="250" className={styles.cursor} />
        {points.map((point, index) => (
          <g key={point.period} onPointerMove={() => setHovered(point.period)} onClick={() => { setHovered(null); setSelected(point.period); }}>
            <rect x={Math.max(0, x(index) - Math.max(8, (width - 24) / Math.max(points.length - 1, 1) / 2))} y="12" width={Math.max(16, (width - 24) / Math.max(points.length - 1, 1))} height="238" fill="transparent" />
            {finite(point.lower) && finite(point.upper) && <line x1={x(index)} x2={x(index)} y1={y(point.lower)} y2={y(point.upper)} className={styles.interval} />}
            {finite(point.actual) && (
                <circle
                  cx={x(index)}
                  cy={y(point.actual)}
                  r={inspectedIndex === index ? 6 : 3.5}
                  className="forecastActual"
                >
                  <title>{`${point.period}: observed ${point.actual}`}</title>
                </circle>
              )}
            {finite(point.estimate) && (
                <circle
                  cx={x(index)}
                  cy={y(point.estimate)}
                  r={inspectedIndex === index ? 6 : 3.5}
                  className="forecastEstimate"
                >
                  <title>{`${point.period}: forecast ${point.estimate}`}</title>
                </circle>
              )}
          </g>
        ))}
          </svg>
          <div className={styles.dateRange} aria-label="Chart date range"><span>{points[0]?.period}</span><span>{points.at(-1)?.period}</span></div>
        </div>
      </div>
      <div className={styles.periodRegions}><span>History: {history.length} shown periods</span><span>Forecast starts {rows[0]?.period ?? "—"}</span></div>
      <p className="chartCaption">
        Axis labels and chart positions are approximate; the inspector and tables retain the exact
        values.{" "}
        {run.result.history.length > 48
          ? "The chart shows the last 48 historical periods and all forecast periods."
          : "Observed points are not filled across missing periods."} No lines connect missing observations or turn forecasts into observations.
      </p>
      <div className={styles.inspection} id={inspectionId} role="status">
        <div><span>{selectedPoint.period}</span><strong>{selectedPoint.estimate === null ? "Observed history" : "Forecast period"}</strong></div>
        <dl><div><dt>Observed</dt><dd>{selectedPoint.actual ?? "Awaiting actual data"}</dd></div>{selectedPoint.estimate !== null && <><div><dt>Forecast</dt><dd>{selectedPoint.estimate}</dd></div><div><dt>Uncertainty range</dt><dd>{selectedPoint.lower} to {selectedPoint.upper}</dd></div></>}</dl>
      </div>
      <div className={styles.controls}><label>
        Inspect a forecast period
        <select
          value={rows.some(point => point.period === selected) ? selected ?? "" : ""}
          onChange={(event) => { setHovered(null); setSelected(event.target.value || null); }}
        >
          <option value="">Choose a period</option>
          {rows.map((point) => (
            <option key={point.period} value={point.period}>
              {point.period}
            </option>
          ))}
        </select>
      </label><div><button type="button" onClick={() => move(-1)} disabled={selectedIndex === 0} aria-label="Inspect previous period">←</button><button type="button" onClick={() => move(1)} disabled={selectedIndex === points.length - 1} aria-label="Inspect next period">→</button></div></div>
    </div>
  );
}

export function CalendarEffects({ value, unit }: { value: ForecastRegressors; unit: string }) {
  const rows = [
    ["Best without calendar effects", value.best_without_regressors],
    ["Best with calendar effects", value.best_with_regressors ?? value.best_calendar_only ?? null],
  ] as const;
  return (
    <section aria-label="Calendar effects comparison">
      <h3>Calendar effects comparison</h3>
      <p>
        {value.selected === "calendar_regression"
          ? "Calendar effects won on the earlier windows, so this forecast uses them."
          : value.selected === "declared_regressors"
          ? "Holidays and outside predictors won on the earlier windows; see their comparison below."
          : "Calendar effects did not beat the best smoothing method on the earlier windows, so they are not used."}{" "}
        The later test window is shown for comparison only and never chooses the method.
      </p>
      <div className="tableWrap">
        <table>
          <thead><tr><th>Approach</th><th>Method</th><th>Earlier-window error ({unit})</th><th>Later test error ({unit})</th></tr></thead>
          <tbody>
            {rows.map(([label, item]) => <tr key={label}><td>{label}</td><td>{item ? item.method.replaceAll("_", " ") : "Not eligible"}</td><td>{item?.validation_mae ?? "—"}</td><td>{item?.test_mae ?? "—"}</td></tr>)}
          </tbody>
        </table>
      </div>
      {value.effects && <details>
        <summary>Fitted calendar and event effects</summary>
        <p className="chartCaption">{value.effects_label}</p>
        <div className="tableWrap">
          <table aria-label="Fitted effects">
            <thead><tr><th>Effect</th><th>Average difference ({unit})</th></tr></thead>
            <tbody>{Object.entries(value.effects).map(([name, amount]) => <tr key={name}><td>{name}</td><td>{amount}</td></tr>)}</tbody>
          </table>
        </div>
      </details>}
      {value.best_with_declared && <DeclaredRegressors value={value} unit={unit} />}
      {value.event_declared && <p className="chartCaption">Declared future event periods: {value.future_event_periods.length ? value.future_event_periods.join(", ") : "none"}. The event schedule is assumed known in advance.</p>}
    </section>
  );
}

function DeclaredRegressors({ value, unit }: { value: ForecastRegressors; unit: string }) {
  const rows = [
    ["Best smoothing method", value.best_without_regressors],
    ["Best with calendar effects only", value.best_calendar_only],
    ["Best with holidays and predictors", value.best_with_declared],
  ] as const;
  return (
    <section aria-label="Holidays and predictors comparison">
      <h4>Holidays and outside predictors</h4>
      <p>
        {value.selected === "declared_regressors"
          ? "Holidays and outside predictors beat every other method on the earlier windows, so this forecast uses them."
          : "Holidays and outside predictors did not beat the best other method on the earlier windows, so they are not used."}
      </p>
      <div className="tableWrap">
        <table aria-label="Declared regressor comparison">
          <thead><tr><th>Approach</th><th>Method</th><th>Earlier-window error ({unit})</th><th>Later test error ({unit})</th></tr></thead>
          <tbody>
            {rows.map(([label, item]) => <tr key={label}><td>{label}</td><td>{item ? item.method.replaceAll("_", " ") : "Not eligible"}</td><td>{item?.validation_mae ?? "—"}</td><td>{item?.test_mae ?? "—"}</td></tr>)}
          </tbody>
        </table>
      </div>
      <div className="tableWrap">
        <table aria-label="Fitted holiday and predictor effects">
          <thead><tr><th>Input</th><th>Fitted effect ({unit})</th><th>Future values used</th></tr></thead>
          <tbody>
            {value.holidays && <tr><td>Holiday days ({value.holidays.history_periods_with_holidays} past periods)</td><td>{value.holidays.effect} {value.holidays.effect_unit}</td><td>{value.holidays.future_holiday_periods.map(item => item.period).join(", ") || "none"}</td></tr>}
            {value.predictors?.map(item => <tr key={item.name}><td>{item.name}</td><td>{item.effect} · {item.effect_unit}</td><td>{item.future_values.join(", ")}</td></tr>)}
          </tbody>
        </table>
      </div>
      <p className="chartCaption">{value.effects_label}</p>
    </section>
  );
}

export function ForecastResults({
  run,
  comparison,
  exportPath,
}: {
  run: ForecastRun;
  comparison?: ForecastComparison;
  exportPath?: string;
}) {
  const result = run.result;
  const rows = forecastRows(result.predictions, comparison);
  const commentary = [...(result.commentary ?? []), ...(comparison?.result.commentary ?? [])];
  const limits = [
    ...new Set([...result.limitations, ...run.evidence.limitations]),
  ];
  return (
    <article
      className="panel forecastResult"
      aria-label={`Forecast result: ${run.name}`}
    >
      <div className="sectionHeading">
        <div>
          <p className="eyebrow">SAVED FORECAST · PRIVATE</p>
          <h2>{run.name}</h2>
        </div>
        <span className="forecastBadge">Estimate, not an observed result</span>
      </div>
      <p>
        {run.request.aggregation.toUpperCase()} of {run.request.metric} ·{" "}
        {result.frequency} · Unit: {run.evidence.unit}
      </p>
      <p className="chartCaption">
        Created {new Date(run.created_at).toLocaleString()} · Method:{" "}
        {result.method.id.replaceAll("_", " ")}
      </p>
      {exportPath && <ResultExportActions path={`${exportPath}/export`} charts={["Observed values and forecast estimates"]} label="Download saved forecast" />}
      {exportPath && comparison && <ResultExportActions path={`${exportPath}/comparisons/${comparison.id}/export`} charts={["Forecast versus later actuals"]} label="Download actual-data comparison" />}
      <p className="forecastUncertainty">
        {result.uncertainty.label}
        {!result.uncertainty.coverage_guaranteed &&
          " This range has no guaranteed coverage probability."}
      </p>
      {result.version === "forecast-v3" && <p className="chartCaption">Calibrated ranges · Nine earlier windows, separate from method choice and testing, set an 80% range for each step ahead. Coverage can drop if the pattern changes.</p>}
      {result.regressors && <CalendarEffects value={result.regressors} unit={run.evidence.unit} />}
      {result.version !== "forecast-v1" && <p className="chartCaption">Advanced comparison · Three earlier windows choose the method. A separate later window measures its error. The simple baseline can still be the best choice.</p>}
      <ForecastChart
        key={`${run.id}-${comparison?.id ?? "forecast"}`}
        run={run}
        rows={rows}
      />
      <h3>Forecast and actual values</h3>
      <p>
        {comparison
          ? `${comparison.result.observed_count} observed periods · ${comparison.result.pending_count} awaiting complete actual data. This comparison does not rewrite the saved forecast.`
          : "The saved estimates remain unchanged. Compare a later, complete source below to add observed values."}
      </p>
      <RecordTable
        key={`prediction-${run.id}-${comparison?.id}`}
        countLabel="forecast periods"
        data={{
          columns: [
            "Period",
            "Forecast",
            "Lower range",
            "Upper range",
            "Actual",
            "Error (actual − forecast)",
            "State",
          ],
          rows: rows.map((point) => [
            point.period,
            point.estimate,
            point.lower,
            point.upper,
            point.actual ?? null,
            point.error ?? null,
            point.status === "observed" ? "Observed" : "Pending",
          ]),
          records_analyzed: rows.length,
        }}
      />
      {result.benchmark && !result.benchmark.beats_baseline_mae && <p className="forecastBenchmark">This forecast did not beat a simple last-value estimate on the held-out data. Check the errors before relying on it.</p>}
      {commentary.length > 0 && <section className="forecastCommentary" aria-label="Grounded forecast commentary">
        <h3>What the results say</h3>
        {commentary.slice(0, 3).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
        {commentary.length > 3 && <details><summary>More about these results</summary>{commentary.slice(3).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</details>}
      </section>}
      <details className="forecastEvidence">
        <summary>How accurate was this forecast?</summary>
        <p>These checks compare estimates with known values. Past accuracy does not guarantee future results.</p>
      {comparison && (
        <ForecastAccuracy
          title="Accuracy against later actual data"
          value={comparison.result.metrics}
          unit={run.evidence.unit}
        />
      )}
      <ForecastAccuracy
        title="Held-out backtest accuracy"
        value={result.accuracy}
        unit={run.evidence.unit}
      />
      {result.benchmark && (
        <p className="forecastBenchmark">
          Last-value baseline MAE:{" "}
          {result.benchmark.accuracy.mae ?? "Not available"} {run.evidence.unit}
          .{" "}
          {result.benchmark.beats_baseline_mae
            ? "The selected method had lower held-out mean absolute error than this baseline."
            : "The selected method did not beat this baseline on held-out mean absolute error."}
        </p>
      )}
      {result.uncertainty.backtest_coverage && (
        <p>
          {result.uncertainty.backtest_coverage.inside} of{" "}
          {result.uncertainty.backtest_coverage.count} held-out actual values
          fell within the estimated range.{" "}
          {result.uncertainty.backtest_coverage.label}
        </p>
      )}
      </details>
      <details className="forecastEvidence">
        <summary>What this forecast assumes</summary>
        <ul className="studyLimitations">
          {[...limits, ...(comparison?.result.limitations ?? [])].map((text, index) => <li key={index}>{text}</li>)}
        </ul>
      </details>
      <details className="forecastEvidence">
        <summary>Method, backtest and source evidence</summary>
        <h3>Time windows</h3>
        <dl>
          {Object.entries(result.windows).map(([name, window]) => (
            <div key={name}>
              <dt>{name.replaceAll("_", " ")}</dt>
              <dd>
                {window.start} to {window.end} · {window.count} periods
              </dd>
            </div>
          ))}
        </dl>
        <p>
          Selection criterion: {result.selection.criterion.replaceAll("_", " ")}
          . Candidate comparison used validation data; held-out test errors are
          shown separately.
        </p>
        {result.selection.folds && <>
          <h3>Rolling validation windows</h3>
          <RecordTable countLabel="earlier windows" data={{
            columns: ["Training ends", "Training periods", "Validation starts", "Validation ends", "Validation periods"],
            rows: result.selection.folds.map(fold => [fold.training.end, fold.training.count, fold.validation.start, fold.validation.end, fold.validation.count]),
            records_analyzed: result.selection.folds.length,
          }} />
          <p>Registry: {result.selection.registry_version}. The parameter search is bounded and can finish without choosing an advanced method.</p>
          {result.selection.excluded?.map((item, index) => <p key={index}>{item.method}: {item.reason}</p>)}
        </>}
        <RecordTable
          countLabel="methods evaluated"
          data={{
            columns: [
              "Candidate",
              "Validation MAE",
              "Validation RMSE",
              "Parameters",
            ],
            rows: result.selection.candidates.map((candidate) => [
              candidate.method,
              candidate.metrics.mae,
              candidate.metrics.rmse,
              JSON.stringify(candidate.parameters),
            ]),
            records_analyzed: result.selection.candidates.length,
          }}
        />
        <h3>Held-out predictions</h3>
        <RecordTable
          countLabel="held-out periods"
          data={{
            columns: [
              "Period",
              "Actual",
              "Estimate",
              "Error",
              "Lower range",
              "Upper range",
            ],
            rows: result.backtest.map((point) => [
              point.period,
              point.actual ?? null,
              point.estimate,
              point.error ?? null,
              point.lower,
              point.upper,
            ]),
            records_analyzed: result.backtest.length,
          }}
        />
        <h3>Observed history</h3>
        <RecordTable
          countLabel="observed periods"
          data={{
            columns: ["Period", "Actual"],
            rows: result.history.map((point) => [point.period, point.actual]),
            records_analyzed: result.history.length,
          }}
        />
        <p>
          Forecast ID: {run.id}
          <br />
          Source upload: {run.upload_id}
          <br />
          Revision: {run.revision_id}
          <br />
          Reviewed meaning: {run.understanding_id}
          <br />
          Method version: {run.method_version}
        </p>
        <p>Query receipts: {run.evidence.query_ids.join(", ")}</p>
        {comparison && (
          <p>
            Comparison ID: {comparison.id}
            <br />
            Actual upload: {comparison.upload_id}
            <br />
            Comparison receipts: {comparison.evidence.query_ids.join(", ")}
          </p>
        )}
        <details>
          <summary>Source and definition details</summary>
          <pre>
            {JSON.stringify(
              {
                sources: run.evidence.sources,
                definition: run.evidence.definition,
                method: result.method,
                ...(comparison
                  ? { comparison_sources: comparison.evidence.sources }
                  : {}),
              },
              null,
              2,
            )}
          </pre>
        </details>
      </details>
    </article>
  );
}
