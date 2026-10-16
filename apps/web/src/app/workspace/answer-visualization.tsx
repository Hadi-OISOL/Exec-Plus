/* Use case: Explores an executed answer as an exact table or a bounded interactive chart.
What it does: Presents returned cells without aggregation, adds signed plots and modal expansion, and delegates every drill action to the caller. */

"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  chartEligible,
  displayMetric,
  exactCell,
  lineSegments,
  plotPoints,
  plotScale,
  plotBounds,
} from "./visualization-values";
import type { VisualizationCell } from "./visualization-values";
import styles from "./answer-visualization.module.css";

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

function Plot({
  props,
  chart,
}: {
  props: AnswerVisualizationProps;
  chart: "bar" | "line" | "dot";
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
  const bounds = plotBounds(points);
  const [active, setActive] = useState<number | null>(null);
  const chartArea = useRef<HTMLDivElement>(null);
  const [plotWidth, setPlotWidth] = useState(600);
  useEffect(() => {
    if (!chartArea.current) return;
    const observer = new ResizeObserver(entries => {
      const width = entries[0]?.contentRect.width;
      if (width && width > 0) setPlotWidth(width);
    });
    observer.observe(chartArea.current);
    return () => observer.disconnect();
  }, [chart]);
  const horizontal = (index: number) => 16 + (points.length < 2 ? 0.5 : index / (points.length - 1)) * (plotWidth - 32);
  const vertical = (value: number) => 22 + (100 - scale.position(value)) * 2.1;
  const selectedIndex = active !== null && active < points.length ? active : null;
  const selected = selectedIndex === null ? undefined : points[selectedIndex];
  return (
    <div className={styles.plot}>
      <div className={styles.plotHeading}>
        <p className={styles.axisLabel}>{columns[valueIndex]} <span>by {columns[categoryIndex]}</span></p>
        <span className={styles.plotEncoding}>{chart === "bar" ? "Length shows value · zero baseline" : chart === "dot" ? "Dot shows value · stem starts at zero" : connectLinePoints ? "One point per returned row" : "Observed points only"}</span>
      </div>
      {chart !== "line" ? (
        <>
        <div className={styles.barScale} aria-label="Chart value range">
          <span>{columns[categoryIndex]}</span>
          <div><span title={exactCell(bounds.minimum)}>{displayMetric(bounds.minimum)}</span><span title={exactCell(bounds.maximum)}>{displayMetric(bounds.maximum)}</span></div>
          <span>Exact value</span>
        </div>
        <ul className={`${styles.bars} ${chart === "dot" ? styles.dotPlot : ""} ${chartClassName}`} aria-label={title}>
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
                  {[0, 25, 50, 75, 100].map(position => <i key={position} className={styles.barGuide} style={{left: `${position}%`}} />)}
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
                  {chart === "bar" && point.value === 0 && <i className={styles.zeroMarker} style={{left: `${scale.zero}%`}} />}
                  {chart === "dot" && point.value !== null && <i className={`${styles.dotMarker} ${point.value < 0 ? styles.negativeDot : ""}`} style={{left: `${end}%`}} />}
                  {point.value === null && <i className={styles.missingMark}>No value</i>}
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
                    className={`${styles.barRow} barButton ${active === index ? styles.activeBar : ""}`}
                    type="button"
                    disabled={
                      selectionDisabled || point.row[categoryIndex] === null
                    }
                    onClick={() =>
                      onSelect(point.row[categoryIndex], point.row)
                    }
                    onFocus={() => setActive(index)}
                    onMouseEnter={() => setActive(index)}
                  >
                    {contents}
                  </button>
                ) : (
                  <div className={`${styles.barRow} ${active === index ? styles.activeBar : ""}`} tabIndex={0} role="img" aria-label={`${point.label}: ${exactCell(point.raw)}`} onFocus={() => setActive(index)} onMouseEnter={() => setActive(index)}>{contents}</div>
                )}
              </li>
            );
          })}
        </ul>
        </>
      ) : (
        <>
          <div className={styles.lineLayout}>
          <div className={styles.valueAxis} aria-label="Chart value range"><span title={exactCell(bounds.maximum)}>{displayMetric(bounds.maximum)}</span><span title={exactCell(bounds.minimum)}>{displayMetric(bounds.minimum)}</span></div>
          <div className={styles.lineArea} ref={chartArea}>
          <svg
            viewBox={`0 0 ${plotWidth} 254`}
            className={`trendSvg ${styles.lineChart}`}
            role="group"
            aria-label={`${title} ${connectLinePoints ? "line chart" : "observed points"}`}
            onPointerMove={event => {
              const box = event.currentTarget.getBoundingClientRect();
              const fraction = (event.clientX - box.left - 16) / Math.max(1, box.width - 32);
              setActive(Math.max(0, Math.min(points.length - 1, Math.round(fraction * (points.length - 1)))));
            }}
          >
            {[0, 25, 50, 75, 100].map((position) => (
              <line
                key={position}
                x1={16}
                x2={plotWidth - 16}
                y1={22 + position * 2.1}
                y2={22 + position * 2.1}
                className={styles.gridLine}
              />
            ))}
            <line
              x1={16}
              x2={plotWidth - 16}
              y1={vertical(0)}
              y2={vertical(0)}
              className={styles.zeroAxis}
            />
            {connectLinePoints &&
              segments.map((segment, index) => (
                <polyline
                  key={index}
                  points={segment
                    .map(
                      (point) => `${horizontal(point.index)},${22 + point.y * 2.1}`,
                    )
                    .join(" ")}
                  fill="none"
                  className={styles.line}
                />
              ))}
            {selectedIndex !== null && <line x1={horizontal(selectedIndex)} x2={horizontal(selectedIndex)} y1={12} y2={242} className={styles.crosshair} />}
            {segments.flat().map((coordinate) => {
              const point = points[coordinate.index];
              const selectable =
                onSelect &&
                !selectionDisabled &&
                point.row[categoryIndex] !== null;
              return (
                <g
                  key={coordinate.index}
                  transform={`translate(${horizontal(coordinate.index)},${22 + coordinate.y * 2.1})`}
                  className={`chartPoint ${styles.pointTarget} ${active === coordinate.index ? styles.activePoint : ""}`}
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
                  <circle r={22} className={styles.hitTarget} />
                  <circle r={active === coordinate.index ? 6 : 4} className={styles.point} />
                  <title>
                    {point.label}: {exactCell(point.raw)}
                  </title>
                </g>
              );
            })}
          </svg>
          <div className={styles.axisRange} aria-label="Chart category range"><span>{points[0]?.label}</span><span>{points.length > 1 ? points[points.length - 1]?.label : ""}</span></div>
          </div>
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
      <div className={`${chart === "line" ? "chartReadout" : "barReadout"} ${styles.readout}`} aria-live="polite" aria-label={`Exact chart detail for ${title}`}>
        {selected ? <><div><span>{columns[categoryIndex]}</span><strong>{selected.label}</strong></div><div><span>{columns[valueIndex]}</span><strong>{exactCell(selected.raw)}</strong></div></> : <><div><span>EXPLORE THE VALUES</span><strong>Hover or use Tab to inspect {chart === "bar" ? "a bar" : "a point"}.</strong></div><span className={styles.readoutHint}>Exact values, straight from this result</span></>}
      </div>
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
