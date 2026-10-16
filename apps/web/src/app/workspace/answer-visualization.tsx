/* Use case: Explores an executed answer as an exact table or a bounded interactive chart.
What it does: Presents returned cells without aggregation, adds signed plots and modal expansion, and delegates every drill action to the caller. */

"use client";

import { useId, useRef, useState } from "react";
import {
  chartEligible,
  exactCell,
} from "./visualization-values";
import type { VisualizationCell } from "./visualization-values";
import styles from "./answer-visualization.module.css";
import { EChartsAnswerPlot } from "./echarts-answer-plot";

export type { VisualizationCell } from "./visualization-values";
export type AnswerVisualizationProps = {
  title: string;
  columns: string[];
  rows: VisualizationCell[][];
  initialMode?: "chart" | "table";
  initialChart?: "bar" | "line" | "dot";
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
  const chart = !allowLine && preferredChart === "line" ? "bar" : preferredChart;
  const dialog = useRef<HTMLDialogElement>(null);
  const [expanded, setExpanded] = useState(false);
  const id = useId();
  function content(expanded = false) {
    return (
      <>
        <header className={styles.header}>
          <div>
            <span className={styles.eyebrow}>{mode === "table" ? "THE RETURNED VALUES" : chart === "line" ? "FOLLOW THE SERIES" : "COMPARE THE CATEGORIES"}</span>
            <h3 id={`${id}-${expanded ? "expanded" : "inline"}`}>{title}</h3>
            {mode === "table" && <p className={styles.fieldCaption}>{columns.join(" · ")}</p>}
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
        {mode === "chart" && (
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
            <button type="button" aria-pressed={chart === "dot"} onClick={() => setChart("dot")}>Dots</button>
            {allowLine &&
            <button
              type="button"
              aria-pressed={chart === "line"}
              onClick={() => setChart("line")}
            >
              {connectLinePoints ? "Line" : "Observed points"}
            </button>}
          </div>
        )}
        {mode === "chart" ? (
          <EChartsAnswerPlot
            key={chart}
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
            kind={chart}
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
