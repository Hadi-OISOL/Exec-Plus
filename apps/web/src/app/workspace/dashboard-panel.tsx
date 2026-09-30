/* Use case: Shows a verified, at-a-glance dashboard for an authorized upload.
What it does: Renders deterministic KPI cards, a trend line, and a clickable category
breakdown that drills down into the underlying rows, each traceable to its lineage. */

import { useEffect, useState } from "react";
import { Icon } from "./explore-components";

import { SaveControl } from "./saved-panel";

import type { ApiRequest } from "./profile-panel";

type Lineage = {
  query_id: string;
  metric: string;
  aggregation: string;
  dataset_name: string;
  records_analyzed: number;
  sql: string;
};
type Filter = {
  column: string;
  operator: string;
  value: string | number | boolean;
};
type Column = { name: string; type: string };
type Cell = string | number | boolean | null;
type QueryBody = {
  columns: string[];
  rows: Cell[][];
  records_analyzed: number;
  matched_records: number | null;
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
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatValue(value: Cell): string {
  return value === null
    ? "No data"
    : String(value).replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1");
}

function KpiCard({
  card,
  root,
  request,
}: {
  card: Card;
  root: string;
  request: ApiRequest;
}) {
  const value = card.rows[0]?.[0] ?? null;
  return (
    <article className="kpiCard">
      <span className="kpiLabel">{card.kpi?.name ?? label(card.metric)}</span>
      <strong className="kpiValue">{formatValue(value)}</strong>
      <span className="kpiFootnote">
        {card.lineage.aggregation} · verified from{" "}
        {card.records_analyzed.toLocaleString()} records
      </span>
      <details className="cardDetails">
        <summary>Evidence & save</summary>
        {card.kpi && <p className="kpiExplain">{card.kpi.explanation}</p>}
        <SaveControl
          root={root}
          request={request}
          kind="analysis"
          payload={{ query_id: card.lineage.query_id }}
          name={`${card.metric} analysis`}
        />
      </details>
    </article>
  );
}

function TrendChart({ trend }: { trend: Breakdown }) {
  const [active, setActive] = useState<number | null>(null);
  const points = [...trend.rows]
    .map((row) => ({
      key: String(row[0]),
      value: asNumber(row[1]),
      raw: row[1],
    }))
    .sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
  const known = points.filter((point) => point.value !== null) as {
    key: string;
    value: number;
  }[];
  const max = Math.max(0, ...known.map((point) => point.value));
  const min = Math.min(0, ...known.map((point) => point.value));
  const width = 320;
  const height = 96;
  const step = points.length > 1 ? width / (points.length - 1) : 0;
  const coordinateFor = (value: number) =>
    height - ((value - min) / (max - min || 1)) * (height - 12) - 6;
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
        {label(trend.lineage.metric)} by {label(trend.dimension)} · verified
        from {trend.records_analyzed.toLocaleString()} records
      </p>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="group"
        aria-label={`${label(trend.lineage.metric)} trend across ${points.length} ${label(trend.dimension).toLowerCase()} values`}
        className="trendSvg"
      >
        {[0, 0.5, 1].map((fraction) => (
          <line
            key={fraction}
            x1={0}
            x2={width}
            y1={fraction * height}
            y2={fraction * height}
            stroke="var(--line)"
            strokeDasharray="3 4"
          />
        ))}
        <polyline
          points={coordinates.join(" ")}
          fill="none"
          stroke="var(--green)"
          strokeWidth={2}
        />
        {points.map(
          (point, index) =>
            point.value !== null && (
              <circle
                key={point.key + index}
                cx={points.length > 1 ? index * step : width / 2}
                cy={coordinateFor(point.value)}
                r={active === index ? 5 : 3}
                fill="var(--green)"
                className="chartPoint"
                tabIndex={0}
                role="img"
                aria-label={`${point.key}: ${formatValue(point.raw)}`}
                onMouseEnter={() => setActive(index)}
                onFocus={() => setActive(index)}
                onClick={() => setActive(index)}
              />
            ),
        )}
      </svg>
      <div className="chartReadout" aria-live="polite">
        <span>
          {active === null
            ? "Hover or focus a point to explore"
            : points[active]?.key}
        </span>
        <strong>
          {active === null ? "" : formatValue(points[active]?.raw ?? null)}
        </strong>
      </div>
      <details className="cardDetails">
        <summary>View trend values</summary>
        <div className="tableScroll">
          <table>
            <caption>Underlying trend values</caption>
            <tbody>
              {points.map((point) => (
                <tr key={point.key}>
                  <th scope="row">{point.key}</th>
                  <td>{formatValue(point.raw)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
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
                <td key={column}>
                  {cell === null ? "(missing)" : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="chartCaption">
        {rows.rows.length} of{" "}
        {(rows.matched_records ?? rows.records_analyzed).toLocaleString()}{" "}
        matching records shown.
      </p>
    </div>
  );
}

function BreakdownChart({
  breakdown,
  root,
  request,
  filters,
}: {
  breakdown: Breakdown;
  root: string;
  request: ApiRequest;
  filters: Filter[];
}) {
  const bars = [...breakdown.rows]
    .map((row) => ({
      key: JSON.stringify(row[0]),
      label: row[0] === null ? "Missing value" : String(row[0]),
      filterValue: row[0],
      value: asNumber(row[1]),
      raw: row[1],
    }))
    .sort((a, b) => (b.value ?? -Infinity) - (a.value ?? -Infinity));
  const max = Math.max(1, ...bars.map((bar) => Math.abs(bar.value ?? 0)));
  const [expanded, setExpanded] = useState<string | null>(null);
  const [drilldown, setDrilldown] = useState<QueryBody | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function toggle(key: string, value: Cell) {
    if (value === null) return;
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
          filters: [
            ...filters,
            { column: breakdown.dimension, operator: "eq", value },
          ],
          limit: 20,
        }),
      );
      setDrilldown(result);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not load matching rows.",
      );
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
        Verified from {breakdown.records_analyzed.toLocaleString()} records ·
        select a value to see its underlying rows
      </p>
      <ul className="barList">
        {bars.map((bar) => (
          <li key={bar.key}>
            <button
              type="button"
              className="barButton"
              aria-expanded={expanded === bar.key}
              disabled={busy || bar.filterValue === null}
              title={
                bar.filterValue === null
                  ? "Inspect missing values in Prepare data"
                  : undefined
              }
              onClick={() => void toggle(bar.key, bar.filterValue)}
            >
              <span className="barLabel">{bar.label}</span>
              <span className="barTrack">
                <span
                  className="barFill"
                  style={{
                    width: `${(Math.abs(bar.value ?? 0) / max) * 100}%`,
                  }}
                />
              </span>
              <span className="barValue">{formatValue(bar.raw)}</span>
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

export function DashboardPanel({
  root,
  request,
}: {
  root: string;
  request: ApiRequest;
}) {
  const [columns, setColumns] = useState<Column[]>([]);
  const [templates, setTemplates] = useState<{ id: string; name: string }[]>(
    [],
  );
  const [template, setTemplate] = useState("");
  const [filters, setFilters] = useState<Filter[]>([]);
  const [filterColumn, setFilterColumn] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    request<{ columns: Column[] }>(`${root}/schema`)
      .then((value) => {
        if (!cancelled) setColumns(value.columns);
      })
      .catch(() => {});
    request<{ id: string; name: string }[]>(`${root}/dashboard-templates`)
      .then((value) => {
        if (!cancelled) setTemplates(value);
      })
      .catch(() => {});
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

  async function applyFilters(clear = false) {
    setBusy(true);
    setError("");
    try {
      const kind = columns.find((column) => column.name === filterColumn)?.type;
      const value =
        kind === "boolean"
          ? filterValue === "true"
          : ["integer", "decimal"].includes(kind ?? "")
            ? filterValue
            : filterValue;
      const selected: Filter[] =
        !clear && filterColumn
          ? [{ column: filterColumn, operator: "eq", value }]
          : [];
      const result = await request<Dashboard>(
        `${root}/dashboard`,
        post({ filters: selected, template_id: template || null }),
      );
      setDashboard(result);
      setFilters(selected);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not load dashboard.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel dashboardPanel" aria-label="Dataset dashboard">
      <div className="sectionHeading">
        <h2>Your data at a glance</h2>
        <span>
          <Icon name="check" size={12} /> Verified calculations
        </span>
      </div>
      <p>
        Explore the numbers. Select a category to see the records behind it.
      </p>
      <details className="dashboardTools">
        <summary>Customize view & filters</summary>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void applyFilters();
          }}
        >
          <label>
            Dashboard template
            <select
              value={template}
              onChange={(event) => setTemplate(event.target.value)}
            >
              <option value="">Recommended cards</option>
              {templates.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Filter column
            <select
              value={filterColumn}
              onChange={(event) => setFilterColumn(event.target.value)}
            >
              <option value="">All rows</option>
              {columns.map((column) => (
                <option key={column.name}>{column.name}</option>
              ))}
            </select>
          </label>
          <label>
            Filter equals
            <input
              value={filterValue}
              onChange={(event) => setFilterValue(event.target.value)}
            />
          </label>
          <button disabled={busy}>Apply dashboard filter</button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void applyFilters(true)}
          >
            Clear dashboard filter
          </button>
        </form>
        {dashboard && (
          <SaveControl
            root={root}
            request={request}
            kind="dashboard"
            payload={{ filters, template_id: template || null }}
            name="dashboard configuration"
          />
        )}
      </details>
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
                <KpiCard
                  key={card.lineage.query_id}
                  card={card}
                  root={root}
                  request={request}
                />
              ))}
            </div>
          ) : (
            <p>No numeric columns were found to summarize.</p>
          )}
          <div className="chartGrid">
            {dashboard.trend && (
              <TrendChart
                key={dashboard.trend.lineage.query_id}
                trend={dashboard.trend}
              />
            )}
            {dashboard.breakdown && (
              <BreakdownChart
                key={dashboard.breakdown.lineage.query_id}
                breakdown={dashboard.breakdown}
                root={root}
                request={request}
                filters={filters}
              />
            )}
          </div>
          {!dashboard.trend && !dashboard.breakdown && (
            <p>
              No date or category column was found for a trend or breakdown
              view.
            </p>
          )}
        </>
      )}
    </section>
  );
}
