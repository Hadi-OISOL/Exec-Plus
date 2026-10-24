/* Use case: Creates and revisits governed basic and advanced time-series forecasts.
What it does: Collects complete-period declarations and displays persisted forecasts, later comparisons and server-grounded commentary. */

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import { ForecastResults } from "./forecast-results";
import { UnusualValues } from "./unusual-values";
import styles from "./forecast.module.css";
import { advancedMinimumHistory, declaredRegressors, eventPeriods } from "./forecast-types";
import type { PredictorDraft } from "./forecast-types";
import type {
  ComparisonSummary,
  ForecastEngine,
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
  onExplore,
  onPatterns,
  onScenario,
  initialMetric = "",
}: {
  root: string;
  filename: string;
  request: ApiRequest;
  onReview: () => void;
  onRefresh: () => void;
  onExplore?: () => void;
  onPatterns?: () => void;
  onScenario?: () => void;
  initialMetric?: string;
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
  const [metric, setMetric] = useState(initialMetric);
  const [aggregation, setAggregation] = useState("");
  const [frequency, setFrequency] = useState<"daily" | "monthly">("monthly");
  const [horizon, setHorizon] = useState(3);
  const [seasonal, setSeasonal] = useState(false);
  const [engine, setEngine] = useState<ForecastEngine>("basic-v1");
  const [eventColumn, setEventColumn] = useState("");
  const [futureEvents, setFutureEvents] = useState("");
  const [holidayCalendar, setHolidayCalendar] = useState("");
  const [holidayDates, setHolidayDates] = useState("");
  const [predictors, setPredictors] = useState<PredictorDraft[]>([0, 1, 2].map(() => ({ column: "", aggregation: "avg", future: "" })));
  const [methodFamily, setMethodFamily] = useState("auto");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [actualStart, setActualStart] = useState("");
  const [actualEnd, setActualEnd] = useState("");
  const [actualConfirmed, setActualConfirmed] = useState(false);
  const [scanning, setScanning] = useState(false);
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
  const quick = options?.quick_start;
  async function submit(body: object) {
    if (!options) return;
    await run(
      "Checking the time series and evaluating forecast methods…",
      async (signal) => {
        const result = await request<ForecastRun>(`${root}/forecasts`, {
          ...json({
            ...body,
            filters: [],
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
  async function create(event: FormEvent) {
    event.preventDefault();
    if (!options || !ready || !confirmed) return;
    await submit({
      name: name.trim() || `${metricName} forecast`,
      time_column: time || options.date_columns[0],
      metric: metricName,
      aggregation: selectedAggregation,
      frequency,
      horizon,
      season_length: seasonal ? (frequency === "daily" ? 7 : 12) : null,
      ...(engine !== "basic-v1" ? { engine, method_family: methodFamily } : {}),
      ...((engine === "advanced-v4" || engine === "advanced-v5") && eventColumn
        ? { event_column: eventColumn, future_event_periods: eventPeriods(futureEvents) }
        : {}),
      ...(engine === "advanced-v5" ? declaredRegressors(holidayCalendar, holidayDates, predictors) : {}),
      coverage_start: start,
      coverage_end: end,
    });
  }
  async function quickForecast() {
    if (!ready || quick?.kind !== "forecast") return;
    await submit({
      name: quick.name,
      time_column: quick.time_column,
      metric: quick.metric,
      aggregation: quick.aggregation,
      frequency: quick.frequency,
      horizon: quick.horizon,
      season_length: null,
      coverage_start: quick.coverage_start,
      coverage_end: quick.coverage_end,
    });
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
        <h2>Forecasts</h2>
        <p>
          Estimate future values from the dates in your file. Each run keeps
          its method, past accuracy and uncertainty visible.
        </p>
        {loading && <p role="status">Checking forecast eligibility…</p>}
        {options && (
          <>
            {options.meaning_state === "confirmed" && <p role="status">Your saved data meanings are in use. You do not need to answer the same questions again.</p>}
            {quick?.kind === "no_timeline" && (
              <div className="forecastPrerequisite forecastNoTimeline">
                <h3>{quick.title}</h3>
                <p>{quick.message}</p>
                <div className="forecastAlternatives" aria-label="Explore without dates">
                  {quick.alternatives.filter((item) => item.available).map((item) => {
                    const action = item.tool === "unusual_values" ? () => setScanning(true) : item.tool === "patterns" ? onPatterns : onScenario;
                    return action ? (
                      <article key={item.tool} className="forecastAlternativeCard">
                        <h4>{item.label}</h4>
                        <p>{item.description}</p>
                        <button type="button" onClick={action}>{item.label} <span aria-hidden="true">→</span></button>
                      </article>
                    ) : null;
                  })}
                </div>
                {scanning && <UnusualValues root={root} request={request} onReview={onReview} autoRun />}
                {quick.alternatives.some((item) => !item.available) && (
                  <p>Confirm what your columns mean once to also find patterns and try what-ifs.</p>
                )}
                {onExplore && <button type="button" onClick={onExplore}>Explore observed data</button>}
                {options.state === "needs_review" && <button type="button" onClick={onReview}>Review data meanings</button>}
              </div>
            )}
            {!ready && quick?.kind !== "no_timeline" && (
              <div className="forecastPrerequisite">
                <h3>
                  {options.state === "needs_review"
                    ? "Review meanings before forecasting"
                    : "A forecast needs a measure with a confirmed unit"}
                </h3>
                {options.state === "needs_review" && quick ? <p>{quick.message}</p> : (
                  <ul>
                    {(options.blockers ?? [{ code: "legacy", message: "Confirm a date column and a measure with a fixed unit before forecasting." }]).map(item => <li key={item.code}>{item.message}</li>)}
                  </ul>
                )}
                {onExplore && <button type="button" onClick={onExplore}>Explore observed data</button>}
                <button type="button" onClick={onReview}>
                  {options.state === "needs_review" ? "Review data meanings" : "Review missing meanings or units"}
                </button>
              </div>
            )}
            {ready && quick?.kind === "forecast" && (
              <div className="forecastQuickStart">
                <h3>Ready to forecast</h3>
                <p>{quick.message}</p>
                <button type="button" disabled={!!pending} onClick={() => void quickForecast()}>
                  Forecast {quick.metric}
                </button>
              </div>
            )}
            {ready && quick && quick.kind !== "forecast" && quick.kind !== "no_timeline" && <p role="status">{quick.message}</p>}
            {ready && (
              <details className="forecastAdvanced" open={quick?.kind !== "forecast"}>
                <summary className="forecastAdvancedSummary">Advanced forecast options</summary>
                {options.limitations.length > 0 && (
                  <ul className="studyLimitations">
                    {options.limitations.map((text) => (
                      <li key={text}>{text}</li>
                    ))}
                  </ul>
                )}
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
                <div className={`forecastCoverage ${styles.approach}`}>
                  <h4>Choose a forecast approach</h4>
                  <label>
                    Forecast approach
                    <select value={engine} disabled={!!pending} onChange={event => setEngine(event.target.value as ForecastEngine)}>
                      <option value="basic-v1">Basic — compare simple methods</option>
                      <option value="advanced-v2" disabled={!options.advanced_methods?.length}>Advanced — compare smoothing and trends</option>
                      <option value="advanced-v3" disabled={!options.advanced_methods?.length}>Advanced with calibrated 80% ranges — needs longer history</option>
                      <option value="advanced-v4" disabled={!options.advanced_methods?.length}>Advanced with calendar effects — day of week or month of year</option>
                      <option value="advanced-v5" disabled={!options.advanced_methods?.length}>Advanced with holidays and outside predictors</option>
                    </select>
                  </label>
                  {engine === "advanced-v5" && <fieldset className="forecastFields" aria-label="Holidays and outside predictors">
                    <legend>Holidays and outside predictors</legend>
                    <p>These are tried after smoothing and calendar effects and are used only if they beat all of them on the earlier windows. The comparison is shown with the result.</p>
                    <label className="checkLabel">
                      <input type="checkbox" checked={Boolean(holidayCalendar)} disabled={!!pending} onChange={event => setHolidayCalendar(event.target.checked ? options.holiday_calendars?.[0]?.id ?? "" : "")} />
                      Use the built-in {options.holiday_calendars?.[0]?.label ?? "holiday table"} ({options.holiday_calendars?.[0]?.first_year}–{options.holiday_calendars?.[0]?.last_year}). Eid and other moon-sighting holidays are not included.
                    </label>
                    <label>
                      Holiday or closure dates · history and forecast periods
                      <input value={holidayDates} disabled={!!pending} placeholder="Example: 2024-04-10, 2024-04-11" onChange={event => setHolidayDates(event.target.value)} />
                    </label>
                    {predictors.map((item, index) => <div key={index} className="forecastFields">
                      <label>
                        {`Outside predictor ${index + 1} · optional`}
                        <select value={item.column} disabled={!!pending} onChange={event => setPredictors(current => current.map((value, position) => position === index ? { ...value, column: event.target.value } : value))}>
                          <option value="">None</option>
                          {(options.predictor_columns ?? []).filter(name => name !== metricName && name !== eventColumn).map(name => <option key={name} value={name}>{name}</option>)}
                        </select>
                      </label>
                      {item.column && <>
                        <label>
                          {`Predictor ${index + 1} per period`}
                          <select value={item.aggregation} disabled={!!pending} onChange={event => setPredictors(current => current.map((value, position) => position === index ? { ...value, aggregation: event.target.value as "sum" | "avg" } : value))}>
                            <option value="avg">Average</option>
                            <option value="sum">Total</option>
                          </select>
                        </label>
                        <label>
                          {`Predictor ${index + 1} future values · one per forecast period (${horizon})`}
                          <input value={item.future} disabled={!!pending} placeholder="Example: 120, 118, 130" onChange={event => setPredictors(current => current.map((value, position) => position === index ? { ...value, future: event.target.value } : value))} />
                        </label>
                      </>}
                    </div>)}
                    <p>Future predictor values are your assumptions. If they are wrong, the forecast will be wrong too.</p>
                  </fieldset>}
                  {(engine === "advanced-v4" || engine === "advanced-v5") && <>
                    <p>Also tries a fitted {frequency === "daily" ? "day-of-week" : "month-of-year"} pattern. It is used only when it beats the best smoothing method on the earlier windows; the comparison is shown with the result.</p>
                    <label>
                      Known event column · optional, 0 or 1 per row
                      <select value={eventColumn} disabled={!!pending} onChange={event => setEventColumn(event.target.value)}>
                        <option value="">No event column</option>
                        {(options.event_columns ?? []).filter(item => item !== metricName).map(item => <option key={item} value={item}>{item}</option>)}
                      </select>
                    </label>
                    {eventColumn && <label>
                      Future event dates in the forecast horizon · optional
                      <input value={futureEvents} disabled={!!pending} placeholder="Example: 2024-03-13, 2024-03-20" onChange={event => setFutureEvents(event.target.value)} />
                    </label>}
                  </>}
                  {engine !== "basic-v1" && <>
                    <p>Try methods that follow a changing level, trend or repeating cycle. We compare them on three earlier time windows, then test the selected method on a later window it has not seen.</p>
                    <label>
                      Advanced method family
                      <select value={methodFamily} disabled={!!pending} onChange={event => setMethodFamily(event.target.value)} aria-describedby="advanced-forecast-history">
                        {options.advanced_methods?.map(method => <option key={method.id} value={method.id}>{method.label}</option>)}
                      </select>
                    </label>
                    <p id="advanced-forecast-history">This choice needs at least {advancedMinimumHistory(frequency, horizon, methodFamily, engine === "advanced-v3") ?? "a valid number of"} complete {frequency === "daily" ? "days" : "months"}. Simple baselines stay in the comparison; advanced methods do not always win.</p>
                    {methodFamily === "holt_winters_additive" && !seasonal && <p role="status">Open “Forecast name and seasonal comparison” below and declare the repeating cycle before continuing.</p>}
                    <p>Ranges show earlier forecast errors. They do not promise a probability of being right.</p>
                  </>}
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
                    {engine !== "basic-v1" ? " baseline and eligible seasonal smoothing." : " baseline."}
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
                    (engine !== "basic-v1" && methodFamily === "holt_winters_additive" && !seasonal) ||
                    !options.date_columns.length
                  }
                >
                  Create forecast
                </button>
              </form>
              </details>
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
            exportPath={`${datasetRoot}/forecasts/${selected.id}`}
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
