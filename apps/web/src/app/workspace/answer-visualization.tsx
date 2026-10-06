/* Use case: Explores an executed answer as an exact table or a bounded interactive chart.
What it does: Presents returned cells without aggregation, adds signed plots and modal expansion, and delegates every drill action to the caller. */

"use client";

import { useId, useRef, useState } from "react";
import {
  chartEligible,
  exactCell,
  lineSegments,
  plotPoints,
  plotScale,
} from "./visualization-values";
import type { VisualizationCell } from "./visualization-values";
import styles from "./answer-visualization.module.css";

export type { VisualizationCell } from "./visualization-values";
export type AnswerVisualizationProps = {
  title: string;
  columns: string[];
  rows: VisualizationCell[][];
  initialMode?: "chart" | "table";
  initialChart?: "bar" | "line";
  categoryIndex?: number;
  valueIndex?: number;
  allowLine?: boolean;
  connectLinePoints?: boolean;
  chartAllowed?: boolean;
  recordsAnalyzed?: number | string;
  matchedRecords?: number | string | null;
  onSelect?: (value: VisualizationCell, row: VisualizationCell[]) => void;
  selectionDisabled?: boolean;
  compact?: boolean;
  chartLimit?: number;
  chartClassName?: string;
};

function ExactTable({
  columns,
  rows,
  title,
}: Pick<AnswerVisualizationProps, "columns" | "rows" | "title">) {
  const [requestedPage, setPage] = useState(0);
  const page = Math.min(
    requestedPage,
    Math.max(0, Math.ceil(rows.length / 20) - 1),
  );
  const start = page * 20;
  return (
    <div className={styles.tableView}>
      <div
        className={`tableScroll ${styles.tableScroll}`}
        role="region"
        tabIndex={0}
        aria-label={`Exact values for ${title}`}
      >
        <table>
          <thead>
            <tr>
              {columns.map((column, index) => (
                <th scope="col" key={`${column}-${index}`}>
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(start, start + 20).map((row, index) => (
              <tr key={start + index}>
                {columns.map((_, cell) => (
                  <td key={cell}>{exactCell(row[cell])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length && (
        <p className={styles.empty}>No returned values for this result.</p>
      )}
      <div className={styles.pagination}>
        <span>
          {rows.length
            ? `${start + 1}–${Math.min(start + 20, rows.length)}`
            : "0"}{" "}
          of {rows.length.toLocaleString()} returned rows
        </span>
        {rows.length > 20 && (
          <div>
            <button
              type="button"
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
              aria-label="Previous result rows"
            >
              ←
            </button>
            <button
              type="button"
              disabled={start + 20 >= rows.length}
              onClick={() => setPage(page + 1)}
              aria-label="Next result rows"
            >
              →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Plot({
  props,
  chart,
}: {
  props: AnswerVisualizationProps;
  chart: "bar" | "line";
}) {
  const {
    title,
    rows,
    columns,
    categoryIndex = 0,
    valueIndex = 1,
    chartLimit = 30,
    onSelect,
    selectionDisabled,
    chartClassName = "",
    connectLinePoints = true,
  } = props;
  const points = plotPoints(rows, categoryIndex, valueIndex, chartLimit);
  const scale = plotScale(points);
  const segments = lineSegments(points);
  const [active, setActive] = useState<number | null>(null);
  return (
    <div className={styles.plot}>
      <p className={styles.axisLabel}>
        {columns[valueIndex]} <span>by {columns[categoryIndex]}</span>
      </p>
      {chart === "bar" ? (
        <ul className={`${styles.bars} ${chartClassName}`} aria-label={title}>
          {points.map((point, index) => {
            const end =
              point.value === null ? scale.zero : scale.position(point.value);
            const contents = (
              <>
                <span className={`discoveryBarLabel ${styles.barLabel}`}>
                  {point.label}
                </span>
                <span
                  className={`discoveryBarTrack ${styles.barTrack}`}
                  aria-hidden="true"
                >
                  <i
                    className={styles.zeroLine}
                    style={{ left: `${scale.zero}%` }}
                  />
                  <span
                    className={`${styles.barFill} ${point.value !== null && point.value < 0 ? styles.negative : ""}`}
                    style={{
                      left: `${Math.min(end, scale.zero)}%`,
                      width: `${Math.abs(end - scale.zero)}%`,
                      minWidth:
                        point.value === null || point.value === 0 ? 0 : 2,
                    }}
                  />
                </span>
                <strong className={styles.barValue}>
                  {exactCell(point.raw)}
                </strong>
              </>
            );
            return (
              <li key={index}>
                {onSelect ? (
                  <button
                    className={`${styles.barRow} barButton`}
                    type="button"
                    disabled={
                      selectionDisabled || point.row[categoryIndex] === null
                    }
                    onClick={() =>
                      onSelect(point.row[categoryIndex], point.row)
                    }
                  >
                    {contents}
                  </button>
                ) : (
                  <div className={styles.barRow}>{contents}</div>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <>
          <svg
            viewBox="0 0 600 240"
            className={`trendSvg ${styles.lineChart}`}
            role="group"
            aria-label={`${title} ${connectLinePoints ? "line chart" : "observed points"}`}
          >
            {[0, 25, 50, 75, 100].map((position) => (
              <line
                key={position}
                x1={18}
                x2={582}
                y1={18 + position * 1.9}
                y2={18 + position * 1.9}
                className={styles.gridLine}
              />
            ))}
            <line
              x1={18}
              x2={582}
              y1={18 + (100 - scale.zero) * 1.9}
              y2={18 + (100 - scale.zero) * 1.9}
              className={styles.zeroAxis}
            />
            {connectLinePoints &&
              segments.map((segment, index) => (
                <polyline
                  key={index}
                  points={segment
                    .map(
                      (point) => `${18 + point.x * 5.64},${18 + point.y * 1.9}`,
                    )
                    .join(" ")}
                  fill="none"
                  className={styles.line}
                />
              ))}
            {segments.flat().map((coordinate) => {
              const point = points[coordinate.index];
              const selectable =
                onSelect &&
                !selectionDisabled &&
                point.row[categoryIndex] !== null;
              return (
                <circle
                  key={coordinate.index}
                  cx={18 + coordinate.x * 5.64}
                  cy={18 + coordinate.y * 1.9}
                  r={active === coordinate.index ? 5 : 3.5}
                  className={`chartPoint ${styles.point}`}
                  tabIndex={0}
                  role={selectable ? "button" : "img"}
                  aria-label={`${point.label}: ${exactCell(point.raw)}`}
                  onFocus={() => setActive(coordinate.index)}
                  onMouseEnter={() => setActive(coordinate.index)}
                  onClick={() => {
                    setActive(coordinate.index);
                    if (selectable)
                      onSelect(point.row[categoryIndex], point.row);
                  }}
                  onKeyDown={(event) => {
                    if (
                      selectable &&
                      (event.key === "Enter" || event.key === " ")
                    ) {
                      event.preventDefault();
                      onSelect(point.row[categoryIndex], point.row);
                    }
                  }}
                >
                  <title>
                    {point.label}: {exactCell(point.raw)}
                  </title>
                </circle>
              );
            })}
            <text x={18} y={235} className={styles.axisText}>
              {points[0]?.label}
            </text>
            <text x={582} y={235} textAnchor="end" className={styles.axisText}>
              {points.length > 1 ? points[points.length - 1]?.label : ""}
            </text>
          </svg>
          <div className={`chartReadout ${styles.readout}`} aria-live="polite">
            <span>
              {active === null
                ? "Hover or focus a point to explore"
                : points[active]?.label}
            </span>
            <strong>
              {active === null ? "" : exactCell(points[active]?.raw)}
            </strong>
          </div>
          {!connectLinePoints && (
            <p className={styles.note}>
              Observed date points; no inferred values between dates.
            </p>
          )}
          {connectLinePoints &&
            points.some((point) => point.value === null) && (
              <p className={styles.note}>
                Missing values remain gaps in the line. View the table for every
                period.
              </p>
            )}
        </>
      )}
      {rows.length > points.length && (
        <p className={styles.note}>
          Showing {points.length} of {rows.length} returned groups. All returned
          values are available in Table.
        </p>
      )}
      <p className={styles.plotNote}>
        Plot positions are approximate; labels and table values are exact.
      </p>
    </div>
  );
}

export function AnswerVisualization(props: AnswerVisualizationProps) {
  const {
    title,
    columns,
    rows,
    initialMode = "chart",
    initialChart = "bar",
    categoryIndex = 0,
    valueIndex = 1,
    allowLine = false,
    connectLinePoints = true,
    chartAllowed = true,
    recordsAnalyzed,
    matchedRecords,
    compact = false,
  } = props;
  const eligible =
    chartAllowed && chartEligible(columns, rows, categoryIndex, valueIndex);
  const [preferredMode, setMode] = useState(initialMode);
  const [preferredChart, setChart] = useState(initialChart);
  const mode = eligible ? preferredMode : "table";
  const chart = allowLine ? preferredChart : "bar";
  const dialog = useRef<HTMLDialogElement>(null);
  const [expanded, setExpanded] = useState(false);
  const id = useId();
  function content(expanded = false) {
    return (
      <>
        <header className={styles.header}>
          <div>
            <h3 id={`${id}-${expanded ? "expanded" : "inline"}`}>{title}</h3>
            <p className={styles.fieldCaption}>{columns.join(" · ")}</p>
          </div>
          <div className={styles.actions}>
            {eligible && (
              <div
                className={styles.segmented}
                role="group"
                aria-label={`${title} view`}
              >
                <button
                  type="button"
                  aria-pressed={mode === "chart"}
                  onClick={() => setMode("chart")}
                >
                  Chart
                </button>
                <button
                  type="button"
                  aria-pressed={mode === "table"}
                  onClick={() => setMode("table")}
                >
                  Table
                </button>
              </div>
            )}
            {!expanded && (
              <button
                type="button"
                className={styles.expandButton}
                aria-label={`Expand ${title}`}
                onClick={() => {
                  setExpanded(true);
                  dialog.current?.showModal();
                }}
              >
                <svg
                  viewBox="0 0 20 20"
                  width="16"
                  height="16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  aria-hidden="true"
                >
                  <path d="M7 3H3v4M13 3h4v4M17 13v4h-4M3 13v4h4" />
                </svg>
              </button>
            )}
            {expanded && (
              <button
                type="button"
                autoFocus
                onClick={() => dialog.current?.close()}
              >
                Close
              </button>
            )}
          </div>
        </header>
        {mode === "chart" && allowLine && (
          <div
            className={styles.chartChoice}
            role="group"
            aria-label={`${title} chart type`}
          >
            <button
              type="button"
              aria-pressed={chart === "bar"}
              onClick={() => setChart("bar")}
            >
              Bars
            </button>
            <button
              type="button"
              aria-pressed={chart === "line"}
              onClick={() => setChart("line")}
            >
              {connectLinePoints ? "Line" : "Observed points"}
            </button>
          </div>
        )}
        {mode === "chart" ? (
          <Plot
            props={
              expanded && props.onSelect
                ? {
                    ...props,
                    onSelect: (value, row) => {
                      dialog.current?.close();
                      props.onSelect?.(value, row);
                    },
                  }
                : props
            }
            chart={chart}
          />
        ) : (
          <ExactTable title={title} columns={columns} rows={rows} />
        )}
        {(recordsAnalyzed !== undefined || matchedRecords != null) && (
          <div className={styles.sourceCount}>
            {rows.length.toLocaleString()} returned rows
            {matchedRecords != null
              ? ` · ${String(matchedRecords)} matching source records`
              : ""}
            {recordsAnalyzed !== undefined
              ? ` · ${String(recordsAnalyzed)} source records analyzed`
              : ""}
          </div>
        )}
      </>
    );
  }
  return (
    <div
      className={`${styles.visualization} ${compact ? styles.compact : ""}`}
      data-visualization={title}
    >
      {content()}
      <dialog
        ref={dialog}
        className={styles.dialog}
        onClose={() => setExpanded(false)}
        aria-labelledby={`${id}-expanded`}
        onClick={(event) => {
          if (event.target === event.currentTarget) {
            const box = event.currentTarget.getBoundingClientRect();
            if (
              event.clientX < box.left ||
              event.clientX > box.right ||
              event.clientY < box.top ||
              event.clientY > box.bottom
            )
              event.currentTarget.close();
          }
        }}
      >
        {expanded && content(true)}
      </dialog>
    </div>
  );
}
