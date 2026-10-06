/* Use case: Creates and revisits governed basic time-series forecasts.
What it does: Collects complete-period declarations and displays persisted forecasts, later comparisons and server-grounded commentary. */

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import { ForecastResults } from "./forecast-results";
import type {
  ComparisonSummary,
  ForecastComparison,
  ForecastOptions,
  ForecastRun,
  ForecastSummary,
} from "./forecast-types";

const json = (body: object): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export function ForecastPanel({
  root,
  filename,
  request,
  onReview,
  onRefresh,
}: {
  root: string;
  filename: string;
  request: ApiRequest;
  onReview: () => void;
  onRefresh: () => void;
}) {
  const datasetRoot = root.split("/uploads/")[0];
  const uploadId = root.split("/uploads/")[1];
  const [options, setOptions] = useState<ForecastOptions | null>(null);
  const [history, setHistory] = useState<ForecastSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [selected, setSelected] = useState<ForecastRun | null>(null);
  const [comparisons, setComparisons] = useState<ComparisonSummary[]>([]);
  const [comparison, setComparison] = useState<
    ForecastComparison | undefined
  >();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [pending, setPending] = useState("");
  const [name, setName] = useState("");
  const [time, setTime] = useState("");
  const [metric, setMetric] = useState("");
  const [aggregation, setAggregation] = useState("");
  const [frequency, setFrequency] = useState<"daily" | "monthly">("monthly");
  const [horizon, setHorizon] = useState(3);
  const [seasonal, setSeasonal] = useState(false);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [actualStart, setActualStart] = useState("");
  const [actualEnd, setActualEnd] = useState("");
  const [actualConfirmed, setActualConfirmed] = useState(false);
  const operation = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      request<ForecastOptions>(`${root}/forecasts/options`, {
        signal: controller.signal,
      }),
      request<ForecastSummary[]>(`${datasetRoot}/forecasts`, {
        signal: controller.signal,
      }),
    ])
      .then(([nextOptions, runs]) => {
        if (controller.signal.aborted) return;
        setOptions(nextOptions);
        setHistory(runs);
        setStart(nextOptions.defaults.coverage_start ?? "");
        setEnd(nextOptions.defaults.coverage_end ?? "");
        setActualStart(nextOptions.defaults.coverage_start ?? "");
        setActualEnd(nextOptions.defaults.coverage_end ?? "");
        setLoading(false);
      })
      .catch((cause) => {
        if (controller.signal.aborted) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Forecast options could not be loaded.",
        );
        setLoading(false);
      });
    return () => controller.abort();
  }, [root, datasetRoot, request, reload]);
  useEffect(() => () => operation.current?.abort(), []);
  const metricName = metric || options?.metrics[0]?.name || "";
  const selectedMetric = options?.metrics.find(
    (item) => item.name === metricName,
  );
  const selectedAggregation = selectedMetric?.aggregations.includes(aggregation)
    ? aggregation
    : (selectedMetric?.aggregations[0] ?? "");
  const ready = options?.state === "ready";
  async function run(
    label: string,
    action: (signal: AbortSignal) => Promise<void>,
  ) {
    if (pending) return;
    operation.current?.abort();
    const controller = new AbortController();
    operation.current = controller;
    setPending(label);
    setError("");
    try {
      await action(controller.signal);
    } catch (cause) {
      if (!controller.signal.aborted)
        setError(
          cause instanceof Error
            ? cause.message
            : "This forecast request could not complete.",
        );
    } finally {
      if (!controller.signal.aborted) setPending("");
    }
  }
  async function create(event: FormEvent) {
    event.preventDefault();
    if (!options || !ready || !confirmed) return;
    await run(
      "Checking the time series and evaluating forecast methods…",
      async (signal) => {
        const result = await request<ForecastRun>(`${root}/forecasts`, {
          ...json({
            name: name.trim() || `${metricName} forecast`,
            time_column: time || options.date_columns[0],
            metric: metricName,
            aggregation: selectedAggregation,
            filters: [],
            frequency,
            horizon,
            season_length: seasonal ? (frequency === "daily" ? 7 : 12) : null,
            coverage_start: start,
            coverage_end: end,
            coverage_confirmed: true,
            revision_id: options.revision_id,
            understanding_id: options.understanding_id,
          }),
          signal,
        });
        if (signal.aborted) return;
        setSelected(result);
        setSelectedId(result.id);
        setComparison(undefined);
        setComparisons([]);
        setHistory((items) => [
          result,
          ...items.filter((item) => item.id !== result.id),
        ]);
      },
    );
  }
  async function openForecast() {
    if (!selectedId) return;
    await run(
      "Checking the saved forecast and its original evidence…",
      async (signal) => {
        const value = await request<ForecastRun>(
          `${datasetRoot}/forecasts/${selectedId}`,
          { signal },
        );
        if (signal.aborted) return;
        setSelected(value);
        setComparison(undefined);
        setComparisons([]);
        const saved = await request<ComparisonSummary[]>(
          `${datasetRoot}/forecasts/${selectedId}/comparisons`,
          { signal },
        );
        if (!signal.aborted) setComparisons(saved);
      },
    );
  }
  async function compare(event: FormEvent) {
    event.preventDefault();
    if (!selected || !options || !actualConfirmed) return;
    await run(
      "Checking the selected source against the saved forecast…",
      async (signal) => {
        const value = await request<ForecastComparison>(
          `${datasetRoot}/forecasts/${selected.id}/compare`,
          {
            ...json({
              upload_id: uploadId,
              revision_id: options.revision_id,
              understanding_id: options.understanding_id,
              coverage_start: actualStart,
              coverage_end: actualEnd,
              coverage_confirmed: true,
            }),
            signal,
          },
        );
        if (signal.aborted) return;
        setComparison(value);
        setComparisons((items) => [value, ...items]);
      },
    );
  }
  return (
    <div className="forecastWorkspace">
      <section
        className="panel forecastIntro"
        aria-label="Basic forecasting setup"
      >
        <p className="eyebrow">LOOK AHEAD, WITH CONTEXT</p>
        <h2>Basic forecasts</h2>
        <p>
          Estimate future values from a complete daily or monthly series. Each
          run keeps its method, past accuracy and uncertainty visible.
        </p>
        {loading && <p role="status">Checking forecast eligibility…</p>}
        {options && (
          <>
            {options.limitations.length > 0 && (
              <ul className="studyLimitations">
                {options.limitations.map((text) => (
                  <li key={text}>{text}</li>
                ))}
              </ul>
            )}
            {!ready && (
              <div className="forecastPrerequisite">
                <h3>
                  {options.state === "needs_review"
                    ? "Review meanings before forecasting"
                    : "This source is not ready for a time-series forecast"}
                </h3>
                <p>
                  Forecasts need a confirmed date column, an eligible metric
                  with a declared unit and enough consecutive complete periods.
                  Descriptive exploration remains available.
                </p>
                <button type="button" onClick={onReview}>
                  Review data meanings
                </button>
              </div>
            )}
            {ready && (
              <form className="forecastForm" onSubmit={create}>
                <h3>Create a forecast</h3>
                <div className="forecastFields">
                  <label>
                    Date column
                    <select
                      value={time || options.date_columns[0] || ""}
                      disabled={!!pending}
                      onChange={(event) => {
                        setTime(event.target.value);
                        setConfirmed(false);
                      }}
                    >
                      {options.date_columns.map((item) => (
                        <option key={item}>{item}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Forecast metric
                    <select
                      value={metricName}
                      disabled={!!pending}
                      onChange={(event) => {
                        setMetric(event.target.value);
                        setAggregation("");
                      }}
                    >
                      {options.metrics.map((item) => (
                        <option key={item.name} value={item.name}>
                          {item.name} · {item.unit}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Aggregation
                    <select
                      value={selectedAggregation}
                      disabled={!!pending}
                      onChange={(event) => setAggregation(event.target.value)}
                    >
                      {selectedMetric?.aggregations.map((item) => (
                        <option key={item} value={item}>
                          {item.toUpperCase()}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Period
                    <select
                      value={frequency}
                      disabled={!!pending}
                      onChange={(event) => {
                        setFrequency(event.target.value as "daily" | "monthly");
                        setHorizon((value) =>
                          Math.min(
                            value,
                            event.target.value === "daily" ? 30 : 12,
                          ),
                        );
                        setConfirmed(false);
                      }}
                    >
                      <option value="monthly">Monthly</option>
                      <option value="daily">Daily</option>
                    </select>
                  </label>
                  <label>
                    Periods to forecast
                    <input
                      type="number"
                      min={1}
                      max={frequency === "daily" ? 30 : 12}
                      required
                      value={horizon}
                      disabled={!!pending}
                      onChange={(event) =>
                        setHorizon(Number(event.target.value))
                      }
                    />
                  </label>
                </div>
                <div className="forecastCoverage">
                  <h4>Complete source coverage</h4>
                  <p>
                    Choose a period range for which this file contains all
                    required observations. Monthly ranges must start on the
                    first day and end on the last day of a month. Missing
                    periods are not replaced with zero.
                  </p>
                  <div className="forecastFields">
                    <label>
                      Source coverage start
                      <input
                        type="date"
                        required
                        value={start}
                        max={end || undefined}
                        disabled={!!pending}
                        onChange={(event) => {
                          setStart(event.target.value);
                          setConfirmed(false);
                        }}
                      />
                    </label>
                    <label>
                      Source coverage end
                      <input
                        type="date"
                        required
                        value={end}
                        min={start || undefined}
                        disabled={!!pending}
                        onChange={(event) => {
                          setEnd(event.target.value);
                          setConfirmed(false);
                        }}
                      />
                    </label>
                  </div>
                  <label className="forecastCheck">
                    <input
                      type="checkbox"
                      checked={confirmed}
                      disabled={!!pending}
                      onChange={(event) => setConfirmed(event.target.checked)}
                    />
                    I confirm the source covers every complete period in this
                    range.
                  </label>
                </div>
                <details>
                  <summary>Forecast name and seasonal comparison</summary>
                  <label>
                    Forecast name
                    <input
                      maxLength={100}
                      value={name}
                      placeholder={`${metricName} forecast`}
                      onChange={(event) => setName(event.target.value)}
                      disabled={!!pending}
                    />
                  </label>
                  <label className="forecastCheck">
                    <input
                      type="checkbox"
                      checked={seasonal}
                      disabled={!!pending}
                      onChange={(event) => setSeasonal(event.target.checked)}
                    />
                    Also evaluate a{" "}
                    {frequency === "daily" ? "7-day" : "12-month"} seasonal
                    baseline.
                  </label>
                  <p>
                    Seasonal comparison needs enough historical cycles. The
                    method is selected using validation errors, then measured on
                    a separate held-out window.
                  </p>
                </details>
                <button
                  disabled={
                    !!pending ||
                    !confirmed ||
                    !metricName ||
                    !options.date_columns.length
                  }
                >
                  Create forecast
                </button>
              </form>
            )}
          </>
        )}
        {!loading && !options && (
          <button
            type="button"
            onClick={() => {
              setError("");
              setLoading(true);
              setReload((value) => value + 1);
            }}
          >
            Retry forecast options
          </button>
        )}
      </section>
      <section className="panel forecastHistory" aria-label="Saved forecasts">
        <h2>Your saved forecasts</h2>
        <p>
          Private to you. Opening a saved run rechecks its original source
          evidence.
        </p>
        {history.length ? (
          <div className="forecastActions">
            <label>
              Saved forecast
              <select
                value={selectedId}
                disabled={!!pending}
                onChange={(event) => setSelectedId(event.target.value)}
              >
                <option value="">Choose a saved forecast</option>
                {history.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {new Date(item.created_at).toLocaleString()}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={!selectedId || !!pending}
              onClick={() => void openForecast()}
            >
              Open saved forecast
            </button>
          </div>
        ) : (
          <p>
            {loading
              ? "Loading saved forecasts…"
              : "No saved forecast runs yet."}
          </p>
        )}
      </section>
      {pending && (
        <p role="status" className="notice">
          {pending}
        </p>
      )}
      {error && (
        <p role="alert" className="errorNotice">
          {error}
        </p>
      )}
      {selected && (
        <>
          <ForecastResults
            key={selected.id}
            run={selected}
            comparison={comparison}
          />
          <section
            className="panel forecastComparison"
            aria-label="Compare later actual data"
          >
            <h2>Compare with actual results</h2>
            <p>
              Selected file: <strong>{filename}</strong>. Choose an updated
              upload in the data selector above, reopen this saved forecast,
              then compare a complete date range. The forecast itself is never
              retrained by a comparison.
            </p>
            <button type="button" onClick={onRefresh}>
              Open refresh & alerts
            </button>
            {ready ? (
              <form onSubmit={compare}>
                <div className="forecastFields">
                  <label>
                    Actual coverage start
                    <input
                      type="date"
                      required
                      value={actualStart}
                      max={actualEnd || undefined}
                      disabled={!!pending}
                      onChange={(event) => {
                        setActualStart(event.target.value);
                        setActualConfirmed(false);
                      }}
                    />
                  </label>
                  <label>
                    Actual coverage end
                    <input
                      type="date"
                      required
                      value={actualEnd}
                      min={actualStart || undefined}
                      disabled={!!pending}
                      onChange={(event) => {
                        setActualEnd(event.target.value);
                        setActualConfirmed(false);
                      }}
                    />
                  </label>
                </div>
                <label className="forecastCheck">
                  <input
                    type="checkbox"
                    checked={actualConfirmed}
                    disabled={!!pending}
                    onChange={(event) =>
                      setActualConfirmed(event.target.checked)
                    }
                  />
                  I confirm this source completely covers the declared actual
                  periods.
                </label>
                <button disabled={!!pending || !actualConfirmed}>
                  Compare actual data
                </button>
              </form>
            ) : (
              <p>
                Review the selected source’s meanings before creating a new
                comparison.
              </p>
            )}
            {comparisons.length > 0 && (
              <details>
                <summary>
                  Saved actual comparisons ({comparisons.length})
                </summary>
                <ul className="forecastComparisonList">
                  {comparisons.map((item) => (
                    <li key={item.id}>
                      <span>{new Date(item.created_at).toLocaleString()}</span>
                      <button
                        type="button"
                        disabled={!!pending}
                        onClick={() =>
                          void run(
                            "Rechecking saved comparison evidence…",
                            async (signal) => {
                              const value = await request<ForecastComparison>(
                                `${datasetRoot}/forecasts/${selected.id}/comparisons/${item.id}`,
                                { signal },
                              );
                              if (!signal.aborted) setComparison(value);
                            },
                          )
                        }
                      >
                        Open comparison
                      </button>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </section>
        </>
      )}
    </div>
  );
}
