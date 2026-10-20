/* Use case: Renders governed returned rows through bundled chart engines and attributed presets.
What it does: Connects Lieflat bars, documd lines and an ECharts dot view to exact inspection, bounded navigation and source-preserving drill actions. */

"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { init, use as registerECharts } from "echarts/core";
import type { EChartsCoreOption, EChartsType, ECElementEvent } from "echarts/core";
import { BarChart, LineChart, ScatterChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import { makeLieflatBarOption } from "./lieflat-chart-presets";
import { makeDocumdLineOption } from "./documd-chart-presets";
import { displayMetric, exactCell, plotBounds, plotNumber } from "./visualization-values";
import type { PlotPoint, VisualizationCell } from "./visualization-values";
import type { AnswerVisualizationProps } from "./answer-visualization";
import shared from "./answer-visualization.module.css";
import styles from "./echarts-answer-plot.module.css";
import { useDarkTheme } from "../theme-control";
import { chartTheme } from "./chart-theme";
import { defaultTokens, readTokens } from "./charts/chart-tokens";
import type { ChartTokens } from "./charts/chart-tokens";

registerECharts([BarChart, LineChart, ScatterChart, GridComponent, MarkLineComponent, TooltipComponent, DataZoomComponent, SVGRenderer]);

function subscribeMotion(callback: () => void) {
  const query = window.matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

function motionSnapshot() { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; }

export function makeDotOption(points: PlotPoint[], start: number, end: number, reducedMotion: boolean, width: number): EChartsCoreOption {
  const magnitude = Math.max(Number.MIN_VALUE, ...points.flatMap(point => point.value === null ? [] : [Math.abs(point.value)]));
  const values = points.map(point => point.value === null ? null : point.value / magnitude);
  const minimum = Math.min(0, ...values.flatMap(value => value === null ? [] : [value]));
  const maximum = Math.max(0, ...values.flatMap(value => value === null ? [] : [value]));
  return {
    animation: !reducedMotion,
    animationDuration: 350,
    animationDurationUpdate: 0,
    grid: { left: Math.min(112, width * .35), right: 24, top: 16, bottom: 18 },
    xAxis: { type: "value", min: minimum, max: maximum || (minimum === 0 ? 1 : 0), axisLabel: { show: false }, axisTick: { show: false }, axisLine: { show: false }, splitLine: { lineStyle: { color: "#e0e8e2" } } },
    yAxis: { type: "category", inverse: true, data: points.map((_, index) => String(index)), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#304c43", fontFamily: "Manrope, sans-serif", fontSize: 12, width: Math.min(100, width * .3), overflow: "truncate", formatter: (value: string) => points[Number(value)]?.label ?? "" } },
    dataZoom: [{ type: "inside", disabled: true, filterMode: "none", yAxisIndex: 0, startValue: start, endValue: end }],
    series: [{ type: "scatter", symbolSize: 12, data: points.map((point, index) => ({ value: [values[index], index], itemStyle: { color: point.value !== null && point.value < 0 ? "#a56730" : "#176b57" } })), emphasis: { itemStyle: { borderColor: "#213a32", borderWidth: 3 } } }],
  };
}

export function EChartsAnswerPlot({ props, kind }: { props: AnswerVisualizationProps; kind: "bar" | "line" | "dot" }) {
  const { title, rows, columns, categoryIndex = 0, valueIndex = 1, connectLinePoints = true, chartLimit = 30, onSelect, selectionDisabled } = props;
  const points = useMemo<PlotPoint[]>(() => rows.map(row => ({ row, label: exactCell(row[categoryIndex]), raw: row[valueIndex] ?? null, value: plotNumber(row[valueIndex]) })), [rows, categoryIndex, valueIndex]);
  const missingPoints = useMemo(() => points.filter(point => point.value === null), [points]);
  const initialSize = Math.max(1, Math.min(points.length, chartLimit, kind === "line" ? 30 : 8));
  const [windowRange, setWindowRange] = useState({ start: 0, end: initialSize - 1 });
  const start = Math.max(0, Math.min(windowRange.start, points.length - 1));
  const end = Math.max(start, Math.min(windowRange.end, points.length - 1));
  const size = end - start + 1;
  const [active, setActive] = useState(0);
  const [hovered, setHovered] = useState<number | null>(null);
  const selectedIndex = Math.max(0, Math.min(active, points.length - 1));
  const selected = points[selectedIndex];
  const inspectedIndex = hovered !== null && hovered >= 0 && hovered < points.length ? hovered : selectedIndex;
  const inspected = points[inspectedIndex];
  const host = useRef<HTMLDivElement>(null);
  const engine = useRef<EChartsType | null>(null);
  const [width, setWidth] = useState(480);
  const reducedMotion = useSyncExternalStore(subscribeMotion, motionSnapshot, () => true);
  const dark = useDarkTheme();
  const [tokens, setTokens] = useState<ChartTokens>(() => defaultTokens(false));
  const helpId = useId();
  const bounds = useMemo(() => plotBounds(points), [points]);
  const height = kind === "line" ? 300 : Math.max(260, Math.min(520, size * 46 + 32));
  const option = useMemo(() => {
    const input = { points, start, end, reducedMotion, width, connectLinePoints };
    return kind === "bar" ? makeLieflatBarOption(input) : kind === "line" ? makeDocumdLineOption(input) : makeDotOption(points, start, end, reducedMotion, width);
  }, [points, start, end, reducedMotion, width, connectLinePoints, kind]);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const chart = init(element, undefined, { renderer: "svg" });
    engine.current = chart;
    const observer = new ResizeObserver(entries => {
      const nextWidth = entries[0]?.contentRect.width;
      if (nextWidth && nextWidth > 0 && !chart.isDisposed()) {
        setWidth(nextWidth);
        chart.resize();
      }
    });
    observer.observe(element);
    return () => { observer.disconnect(); chart.dispose(); engine.current = null; };
  }, []);

  useEffect(() => {
    const chart = engine.current;
    if (!chart) return;
    chart.setOption(chartTheme(option, tokens), { notMerge: true });
    if (host.current) host.current.dataset.engineReady = "true";
  }, [option, tokens]);
  useEffect(() => { if (host.current) setTokens(readTokens(host.current, dark)); }, [dark]);

  useEffect(() => {
    const chart = engine.current;
    if (!chart) return;
    const preview = (event: ECElementEvent) => {
      if (event.componentType === "series" && Number.isInteger(event.dataIndex) && event.dataIndex >= 0 && event.dataIndex < points.length) setHovered(event.dataIndex);
    };
    const select = (event: ECElementEvent) => {
      const point = points[event.dataIndex];
      if (event.componentType !== "series" || !point) return;
      setActive(event.dataIndex);
      setHovered(null);
      if (onSelect && !selectionDisabled && point.row[categoryIndex] !== null) onSelect(point.row[categoryIndex], point.row);
    };
    const clearPreview = () => setHovered(null);
    chart.on("mouseover", preview);
    chart.on("globalout", clearPreview);
    chart.on("click", select);
    return () => { if (!chart.isDisposed()) { chart.off("mouseover", preview); chart.off("globalout", clearPreview); chart.off("click", select); } };
  }, [points, categoryIndex, onSelect, selectionDisabled]);

  useEffect(() => {
    const chart = engine.current;
    if (!chart) return;
    chart.dispatchAction({ type: "downplay" });
    chart.dispatchAction({ type: "highlight", seriesIndex: 0, dataIndex: inspectedIndex });
  }, [inspectedIndex, option]);

  const inspect = useCallback((index: number) => {
    const next = Math.max(0, Math.min(points.length - 1, index));
    setActive(next);
    setHovered(null);
    if (next < start || next > end) {
      const first = Math.max(0, Math.min(points.length - size, next - Math.floor(size / 2)));
      setWindowRange({ start: first, end: first + size - 1 });
    }
  }, [points.length, start, end, size]);

  function zoom(factor: number) {
    const nextSize = Math.max(1, Math.min(points.length, Math.round(size * factor)));
    const center = selectedIndex >= start && selectedIndex <= end ? selectedIndex : Math.floor((start + end) / 2);
    const first = Math.max(0, Math.min(points.length - nextSize, center - Math.floor(nextSize / 2)));
    setWindowRange({ start: first, end: first + nextSize - 1 });
  }

  function selectRow() {
    if (selected && onSelect && !selectionDisabled && selected.row[categoryIndex] !== null) onSelect(selected.row[categoryIndex] as VisualizationCell, selected.row);
  }

  return <div className={`${shared.plot} ${styles.plot}`} data-chart-template={kind === "bar" ? "lieflat-g10" : kind === "line" ? "documd-line" : "echarts-dots"}>
    <div className={shared.plotHeading}>
      <p className={shared.axisLabel}>{columns[valueIndex]} <span>by {columns[categoryIndex]}</span></p>
      <span className={shared.plotEncoding}>{kind === "bar" ? "Length shows value · zero baseline" : kind === "dot" ? "Position shows value · zero baseline" : connectLinePoints ? "One point per returned row" : "Observed points only"}</span>
    </div>
    <div className={styles.toolbar} role="group" aria-label={`${title} chart navigation`}>
      <span aria-live="polite">Viewing {start + 1}–{end + 1} of {points.length} returned rows</span>
      <div><button type="button" disabled={size <= 1} onClick={() => zoom(.5)}>Zoom in</button><button type="button" disabled={size >= points.length} onClick={() => zoom(2)}>Zoom out</button><button type="button" disabled={size === points.length} onClick={() => setWindowRange({ start: 0, end: points.length - 1 })}>Show all</button></div>
    </div>
    <div className={styles.range} aria-label="Chart value range"><span title={exactCell(bounds.minimum)}><small>Scale minimum</small>{displayMetric(bounds.minimum)}</span><span>Full result scale</span><span title={exactCell(bounds.maximum)}><small>Scale maximum</small>{displayMetric(bounds.maximum)}</span></div>
    <div className={styles.chart} role="group" tabIndex={0} aria-label={`${title} interactive chart`} aria-describedby={helpId} onMouseLeave={() => setHovered(null)} onKeyDown={event => {
      if (["ArrowLeft", "ArrowUp", "ArrowRight", "ArrowDown", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        inspect(event.key === "Home" ? 0 : event.key === "End" ? points.length - 1 : selectedIndex + (["ArrowLeft", "ArrowUp"].includes(event.key) ? -1 : 1));
      } else if ((event.key === "Enter" || event.key === " ") && onSelect) { event.preventDefault(); selectRow(); }
    }}>
      <div ref={host} data-chart-renderer="apache-echarts" data-chart-kind={kind} data-reduced-motion={String(reducedMotion)} aria-hidden="true" style={{ height }} />
    </div>
    <p id={helpId} className={styles.help}>Hover to inspect. Use arrow keys, Home or End on the chart to browse every returned row.{onSelect ? " Press Enter to open its records." : ""}</p>
    {missingPoints.length > 0 && <div className={styles.missing} aria-label="Rows without a value"><p><strong>Missing values · {missingPoints.length}</strong> These rows have no mark. A zero is a real value on the baseline.</p>{missingPoints.length <= 3 ? <ul>{missingPoints.map((point, index) => <li key={index}>{point.label}</li>)}</ul> : <details><summary>See rows without a value</summary><ul>{missingPoints.map((point, index) => <li key={index}>{point.label}</li>)}</ul></details>}</div>}
    {points.length > size && <label className={styles.windowControl}>Move through the result<input type="range" min={0} max={Math.max(0, points.length - size)} value={start} onChange={event => { const first = Number(event.target.value); setWindowRange({ start: first, end: first + size - 1 }); }} /></label>}
    <div className={styles.inspectionControls}>
      <label>Inspect a returned row<select aria-label={`Inspect returned row for ${title}`} value={selectedIndex} onChange={event => inspect(Number(event.target.value))}>{points.map((point, index) => <option key={index} value={index}>{index + 1}. {point.label}</option>)}</select></label>
      <div><button type="button" aria-label={`Previous chart row for ${title}`} disabled={selectedIndex === 0} onClick={() => inspect(selectedIndex - 1)}>←</button><button type="button" aria-label={`Next chart row for ${title}`} disabled={selectedIndex === points.length - 1} onClick={() => inspect(selectedIndex + 1)}>→</button></div>
    </div>
    <div className={`${kind === "line" ? "chartReadout" : "barReadout"} ${shared.readout}`} aria-live="polite" aria-label={`Exact chart detail for ${title}`}>
      <div><span>{columns[categoryIndex]}</span><strong>{inspected?.label ?? "Missing"}</strong></div><div><span>{columns[valueIndex]}</span><strong>{exactCell(inspected?.raw)}</strong></div>
    </div>
    {onSelect && <button className={styles.drill} type="button" disabled={selectionDisabled || !selected || selected.row[categoryIndex] === null} onClick={selectRow}>View records for {selected?.label}</button>}
    {kind === "line" && <p className={shared.note}>{connectLinePoints ? points.some(point => point.value === null) ? "Missing values remain gaps in the line. View the table for every period." : "Lines follow the returned order; they do not add new observations." : "Observed date points; no inferred values between dates."}</p>}
    <p className={shared.plotNote}>Plot positions are approximate. Full exact values remain in this inspector and Table. Zoom changes only the view.</p>
  </div>;
}
