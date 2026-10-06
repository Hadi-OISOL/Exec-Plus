/* Use case: Makes basic forecasts and their limitations inspectable.
What it does: Displays server-calculated estimates, holdout errors and comparison evidence without calculating business values in the browser. */

import { useState } from "react";
import { RecordTable } from "./explore-components";
import {
  forecastRows,
  type ForecastComparison,
  type ForecastMetrics,
  type ForecastPoint,
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

function ForecastChart({
  run,
  rows,
}: {
  run: ForecastRun;
  rows: ForecastPoint[];
}) {
  const [selected, setSelected] = useState<string | null>(null);
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
    .filter((value) => value !== null && value !== undefined)
    .map(Number)
    .filter(Number.isFinite);
  if (!all.length) return null;
  const minimum = Math.min(...all);
  const maximum = Math.max(...all);
  const span = maximum - minimum || Math.max(Math.abs(maximum), 1);
  const x = (index: number) =>
    26 + (index * 648) / Math.max(points.length - 1, 1);
  const y = (value: string) => 200 - ((Number(value) - minimum) / span) * 155;
  const forecastStart = history.length;
  const band = rows.every(
    (point) =>
      Number.isFinite(Number(point.lower)) &&
      Number.isFinite(Number(point.upper)),
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
  const selectedPoint = points.find((point) => point.period === selected);
  return (
    <div className="forecastChart">
      <div className="forecastLegend">
        <span>
          <i className="actualKey" />
          Observed
        </span>
        <span>
          <i className="estimateKey" />
          Forecast
        </span>
        <span>
          <i className="rangeKey" />
          Uncertainty range
        </span>
      </div>
      <svg
        viewBox="0 0 700 235"
        role="img"
        aria-label="Observed history and saved forecast with uncertainty range; exact values follow in the table"
      >
        <path d="M26 210H674" stroke="currentColor" opacity="0.25" />
        {band && <polygon points={band} className="forecastBand" />}
        {points.map((point, index) => (
          <g key={point.period}>
            {point.actual !== null &&
              point.actual !== undefined &&
              Number.isFinite(Number(point.actual)) && (
                <circle
                  cx={x(index)}
                  cy={y(point.actual)}
                  r={selected === point.period ? 6 : 3.5}
                  className="forecastActual"
                >
                  <title>
                    {point.period}: observed {point.actual}
                  </title>
                </circle>
              )}
            {point.estimate !== null &&
              Number.isFinite(Number(point.estimate)) && (
                <circle
                  cx={x(index)}
                  cy={y(point.estimate)}
                  r={selected === point.period ? 6 : 3.5}
                  className="forecastEstimate"
                >
                  <title>
                    {point.period}: forecast {point.estimate}
                  </title>
                </circle>
              )}
          </g>
        ))}
        <text x="26" y="230" fontSize="10" fill="currentColor">
          {points[0]?.period}
        </text>
        <text
          x="674"
          y="230"
          textAnchor="end"
          fontSize="10"
          fill="currentColor"
        >
          {points.at(-1)?.period}
        </text>
      </svg>
      <p className="chartCaption">
        Chart positions are approximate; all labels and tables retain the exact
        server values.{" "}
        {run.result.history.length > 48
          ? "The chart shows the last 48 historical periods and all forecast periods."
          : "Observed points are not filled across missing periods."}
      </p>
      <label>
        Inspect a forecast period
        <select
          value={selected ?? ""}
          onChange={(event) => setSelected(event.target.value || null)}
        >
          <option value="">Choose a period</option>
          {rows.map((point) => (
            <option key={point.period} value={point.period}>
              {point.period}
            </option>
          ))}
        </select>
      </label>
      {selectedPoint && (
        <p role="status">
          {selectedPoint.period} · Forecast: {selectedPoint.estimate} ·
          Observed: {selectedPoint.actual ?? "Awaiting actual data"} · Range:{" "}
          {selectedPoint.lower} to {selectedPoint.upper}
        </p>
      )}
    </div>
  );
}

export function ForecastResults({
  run,
  comparison,
}: {
  run: ForecastRun;
  comparison?: ForecastComparison;
}) {
  const result = run.result;
  const rows = forecastRows(result.predictions, comparison);
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
      <p className="forecastUncertainty">
        {result.uncertainty.label}
        {!result.uncertainty.coverage_guaranteed &&
          " This range has no guaranteed coverage probability."}
      </p>
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
      {result.commentary?.length || comparison?.result.commentary?.length ? (
        <section
          className="forecastCommentary"
          aria-label="Grounded forecast commentary"
        >
          <h3>What the results say</h3>
          {[
            ...(result.commentary ?? []),
            ...(comparison?.result.commentary ?? []),
          ].map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </section>
      ) : null}
      <ul className="studyLimitations">
        {[...limits, ...(comparison?.result.limitations ?? [])].map(
          (text, index) => (
            <li key={index}>{text}</li>
          ),
        )}
      </ul>
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
