/* Use case: Shows a verified, at-a-glance dashboard for an authorized upload.
What it does: Renders deterministic KPI cards, a trend line, and a clickable category
breakdown that drills down into the underlying rows, each traceable to its lineage. */

import { useEffect, useState } from "react";

import type { ApiRequest } from "./profile-panel";

type Lineage = {
  metric: string;
  aggregation: string;
  dataset_name: string;
  records_analyzed: number;
  sql: string;
};
type Cell = string | number | boolean | null;
type QueryBody = {
  columns: string[];
  rows: Cell[][];
  records_analyzed: number;
  lineage: Lineage;
};
type KpiInfo = {
  id: string;
  name: string;
  description: string;
  unit: string;
  explanation: string;
};
type Card = QueryBody & { metric: string; kpi?: KpiInfo };
type Breakdown = QueryBody & { dimension: string };
type Dashboard = {
  cards: Card[];
  trend: Breakdown | null;
  breakdown: Breakdown | null;
};

const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
const post = (body: object): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

function label(name: string): string {
  return name.replaceAll("_", " ").replace(/^./, (char) => char.toUpperCase());
}

function asNumber(value: Cell): number | null {
  if (value === null) return null;
  return typeof value === "number" ? value : Number(value);
}

function formatMaybeNumber(value: number | null): string {
  return value === null ? "No data" : numberFormat.format(value);
}

function KpiCard({ card }: { card: Card }) {
  const value = asNumber(card.rows[0]?.[0] ?? null);
  return (
    <article className="kpiCard">
      <span className="kpiLabel">{card.kpi?.name ?? label(card.metric)}</span>
      <strong className="kpiValue">{formatMaybeNumber(value)}</strong>
      <span className="kpiFootnote">
        {card.lineage.aggregation} · verified from {card.records_analyzed.toLocaleString()}{" "}
        records
      </span>
      {card.kpi && <span className="kpiExplain">{card.kpi.explanation}</span>}
    </article>
  );
}

function TrendChart({ trend }: { trend: Breakdown }) {
  const points = [...trend.rows]
    .map((row) => ({ key: String(row[0]), value: asNumber(row[1]) }))
    .sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
  const known = points.filter((point) => point.value !== null) as {
    key: string;
    value: number;
  }[];
  const max = Math.max(1, ...known.map((point) => point.value));
  const width = 320;
  const height = 96;
  const step = points.length > 1 ? width / (points.length - 1) : 0;
  const coordinateFor = (value: number) => height - (value / max) * (height - 12) - 6;
  const coordinates = points
    .map((point, index) =>
      point.value === null
        ? null
        : `${(points.length > 1 ? index * step : width / 2).toFixed(1)},${coordinateFor(point.value).toFixed(1)}`,
    )
    .filter((entry): entry is string => entry !== null);
  return (
    <div className="chartCard">
      <h3>{label(trend.dimension)} trend</h3>
      <p className="chartCaption">
        {label(trend.lineage.metric)} by {label(trend.dimension)} · verified from{" "}
        {trend.records_analyzed.toLocaleString()} records
      </p>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${label(trend.lineage.metric)} trend across ${points.length} ${label(trend.dimension).toLowerCase()} values`}
        className="trendSvg"
      >
        <polyline points={coordinates.join(" ")} fill="none" stroke="var(--green)" strokeWidth={2} />
        {points.map(
          (point, index) =>
            point.value !== null && (
              <circle
                key={point.key + index}
                cx={points.length > 1 ? index * step : width / 2}
                cy={coordinateFor(point.value)}
                r={3}
                fill="var(--orange)"
              />
            ),
        )}
      </svg>
      <table className="visuallyHiddenTable">
        <caption>Underlying trend values</caption>
        <tbody>
          {points.map((point) => (
            <tr key={point.key}>
              <th scope="row">{point.key}</th>
              <td>{formatMaybeNumber(point.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DrilldownRows({ rows }: { rows: QueryBody }) {
  return (
    <div className="drilldownRows tableScroll">
      <table>
        <thead>
          <tr>
            {rows.columns.map((column) => (
              <th scope="col" key={column}>
                {label(column)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, column) => (
                <td key={column}>{cell === null ? "(missing)" : String(cell)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="chartCaption">
        {rows.rows.length} of {rows.records_analyzed.toLocaleString()} matching records shown.
      </p>
    </div>
  );
}

function BreakdownChart({
  breakdown,
  root,
  request,
}: {
  breakdown: Breakdown;
  root: string;
  request: ApiRequest;
}) {
  const bars = [...breakdown.rows]
    .map((row) => ({ key: String(row[0]), value: asNumber(row[1]) }))
    .sort((a, b) => (b.value ?? -Infinity) - (a.value ?? -Infinity));
  const max = Math.max(1, ...bars.map((bar) => bar.value ?? 0));
  const [expanded, setExpanded] = useState<string | null>(null);
  const [drilldown, setDrilldown] = useState<QueryBody | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function toggle(key: string) {
    if (expanded === key) {
      setExpanded(null);
      setDrilldown(null);
      return;
    }
    setExpanded(key);
    setDrilldown(null);
    setError("");
    setBusy(true);
    try {
      const result = await request<QueryBody>(
        `${root}/rows`,
        post({
          filters: [{ column: breakdown.dimension, operator: "eq", value: key }],
          limit: 20,
        }),
      );
      setDrilldown(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load matching rows.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chartCard">
      <h3>
        {label(breakdown.lineage.metric)} by {label(breakdown.dimension)}
      </h3>
      <p className="chartCaption">
        Verified from {breakdown.records_analyzed.toLocaleString()} records · select a value to
        see its underlying rows
      </p>
      <ul className="barList">
        {bars.map((bar) => (
          <li key={bar.key}>
            <button
              type="button"
              className="barButton"
              aria-expanded={expanded === bar.key}
              onClick={() => void toggle(bar.key)}
            >
              <span className="barLabel">{bar.key}</span>
              <span className="barTrack">
                <span className="barFill" style={{ width: `${((bar.value ?? 0) / max) * 100}%` }} />
              </span>
              <span className="barValue">{formatMaybeNumber(bar.value)}</span>
            </button>
            {expanded === bar.key && (
              <div className="drilldownPanel">
                {busy && <p>Loading matching rows…</p>}
                {error && (
                  <p role="alert" className="errorNotice">
                    {error}
                  </p>
                )}
                {drilldown && <DrilldownRows rows={drilldown} />}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DashboardPanel({ root, request }: { root: string; request: ApiRequest }) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    request<Dashboard>(`${root}/dashboard`, post({ filters: [] }))
      .then((result) => {
        if (!cancelled) setDashboard(result);
      })
      .catch((cause: Error) => {
        if (!cancelled) setError(cause.message);
      });
    return () => {
      cancelled = true;
    };
  }, [root, request]);

  return (
    <section className="panel dashboardPanel" aria-label="Dataset dashboard">
      <h2>4. Dashboard</h2>
      <p>
        Every card and chart is computed by the query engine from this upload&rsquo;s current
        revision, not estimated. Each value traces back to its executed SQL and record count.
      </p>
      {error && (
        <p role="alert" aria-label="Dashboard error" className="errorNotice">
          {error}
        </p>
      )}
      {!dashboard && !error && <p>Loading dashboard…</p>}
      {dashboard && (
        <>
          {dashboard.cards.length ? (
            <div className="kpiGrid">
              {dashboard.cards.map((card) => (
                <KpiCard key={card.metric} card={card} />
              ))}
            </div>
          ) : (
            <p>No numeric columns were found to summarize.</p>
          )}
          <div className="chartGrid">
            {dashboard.trend && <TrendChart trend={dashboard.trend} />}
            {dashboard.breakdown && (
              <BreakdownChart breakdown={dashboard.breakdown} root={root} request={request} />
            )}
          </div>
          {!dashboard.trend && !dashboard.breakdown && (
            <p>No date or category column was found for a trend or breakdown view.</p>
          )}
        </>
      )}
    </section>
  );
}
