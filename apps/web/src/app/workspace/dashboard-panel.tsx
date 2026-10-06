/* Use case: Shows a verified, at-a-glance dashboard for an authorized upload.
What it does: Renders deterministic KPI cards, a trend line, and a clickable category
breakdown that drills down into the underlying rows, each traceable to its lineage. */

import { useEffect, useRef, useState } from "react";
import { AnswerVisualization } from "./answer-visualization";
import styles from "./dashboard-presentation.module.css";
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
  const rows = [...trend.rows].sort((left, right) =>
    String(left[0]).localeCompare(String(right[0])),
  );
  return (
    <AnswerVisualization
      title={`${label(trend.dimension)} trend`}
      columns={trend.columns.map((column, index) =>
        column === "__value" && index === trend.columns.length - 1
          ? label(trend.lineage.metric) : column,
      )}
      rows={rows}
      initialChart="line"
      allowLine
      recordsAnalyzed={trend.records_analyzed}
    />
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
  const [selected, setSelected] = useState<Cell>(null);
  const [drilldown, setDrilldown] = useState<QueryBody | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);

  function clear() {
    pending.current?.abort();
    setSelected(null);
    setDrilldown(null);
    setError("");
    setBusy(false);
  }

  async function select(value: Cell) {
    if (value === null) return;
    if (value === selected) {
      clear();
      return;
    }
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setSelected(value);
    setDrilldown(null);
    setError("");
    setBusy(true);
    try {
      const result = await request<QueryBody>(`${root}/rows`, {
        ...post({
          filters: [
            ...filters,
            { column: breakdown.dimension, operator: "eq", value },
          ],
          limit: 20,
        }),
        signal: controller.signal,
      });
      if (!controller.signal.aborted) setDrilldown(result);
    } catch (cause) {
      if (!controller.signal.aborted)
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not load matching rows.",
        );
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return (
    <div className={styles.breakdown}>
      <AnswerVisualization
        title={`${label(breakdown.lineage.metric)} by ${label(breakdown.dimension)}`}
        columns={breakdown.columns.map((column, index) =>
          column === "__value" && index === breakdown.columns.length - 1
            ? label(breakdown.lineage.metric) : column,
        )}
        rows={breakdown.rows}
        recordsAnalyzed={breakdown.records_analyzed}
        onSelect={(value) => void select(value)}
        selectionDisabled={busy}
      />
      <p className={styles.drillHint}>
        Select a category to inspect its matching source records.
      </p>
      {selected !== null && (
        <div className="drilldownPanel">
          <div className={styles.drillHeading}>
            <strong>
              {label(breakdown.dimension)}: {String(selected)}
            </strong>
            <button type="button" onClick={clear}>
              Close matching records
            </button>
          </div>
          {busy && <p role="status">Loading matching rows…</p>}
          {error && (
            <p role="alert" className="errorNotice">
              {error}
            </p>
          )}
          {drilldown && (
            <div className="drilldownRows">
              <AnswerVisualization
                title="Matching source records"
                columns={drilldown.columns}
                rows={drilldown.rows}
                initialMode="table"
                chartAllowed={false}
                recordsAnalyzed={drilldown.records_analyzed}
                matchedRecords={drilldown.matched_records}
              />
              <p className="chartCaption">
                {drilldown.rows.length} of{" "}
                {(
                  drilldown.matched_records ?? drilldown.records_analyzed
                ).toLocaleString()}{" "}
                matching records shown.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DashboardContent({
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
  const [appliedTemplate, setAppliedTemplate] = useState("");
  const pending = useRef<AbortController | null>(null);
  const [filterColumn, setFilterColumn] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    pending.current = controller;
    request<{ columns: Column[] }>(`${root}/schema`, {
      signal: controller.signal,
    })
      .then((value) => {
        if (!cancelled) setColumns(value.columns);
      })
      .catch(() => {});
    request<{ id: string; name: string }[]>(`${root}/dashboard-templates`, {
      signal: controller.signal,
    })
      .then((value) => {
        if (!cancelled) setTemplates(value);
      })
      .catch(() => {});
    request<Dashboard>(`${root}/dashboard`, {
      ...post({ filters: [] }),
      signal: controller.signal,
    })
      .then((result) => {
        if (!cancelled && !controller.signal.aborted) setDashboard(result);
      })
      .catch((cause: Error) => {
        if (!cancelled && !controller.signal.aborted) setError(cause.message);
      });
    return () => {
      cancelled = true;
      controller.abort();
      pending.current?.abort();
    };
  }, [root, request]);

  async function applyFilters(clear = false) {
    const kind = columns.find((column) => column.name === filterColumn)?.type;
    if (
      !clear &&
      filterColumn &&
      kind === "boolean" &&
      !["true", "false"].includes(filterValue)
    ) {
      setError("For a boolean column, enter true or false.");
      return;
    }
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true);
    setError("");
    try {
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
      const result = await request<Dashboard>(`${root}/dashboard`, {
        ...post({ filters: selected, template_id: template || null }),
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      setDashboard(result);
      setFilters(selected);
      setAppliedTemplate(template);
      if (clear) {
        setFilterColumn("");
        setFilterValue("");
      }
    } catch (cause) {
      if (!controller.signal.aborted)
        setError(
          cause instanceof Error ? cause.message : "Could not load dashboard.",
        );
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return (
    <section
      className={`panel dashboardPanel ${styles.dashboard}`}
      aria-label="Dataset dashboard"
      aria-busy={busy}
    >
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
            payload={{ filters, template_id: appliedTemplate || null }}
            name="dashboard configuration"
          />
        )}
      </details>
      <div
        className={styles.filterStrip}
        aria-label="Applied dashboard filters"
      >
        <span className={styles.filterCaption}>Viewing</span>
        {filters.length ? (
          filters.map((filter) => (
            <span className={styles.filterChip} key={filter.column}>
              {filter.column} = {String(filter.value)}
              <button
                type="button"
                aria-label="Remove dashboard filter"
                disabled={busy}
                onClick={() => void applyFilters(true)}
              >
                ×
              </button>
            </span>
          ))
        ) : (
          <span className={styles.allRows}>All source rows</span>
        )}
        {appliedTemplate && (
          <span className={styles.allRows}>
            {templates.find((item) => item.id === appliedTemplate)?.name ??
              appliedTemplate}
          </span>
        )}
        {busy && <span role="status">Updating calculations…</span>}
      </div>
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

export function DashboardPanel(props: { root: string; request: ApiRequest }) {
  return <DashboardContent key={props.root} {...props} />;
}
