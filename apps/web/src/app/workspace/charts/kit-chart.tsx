/* Use case: Shows any exact chart specification as an accessible, animated, themed chart.
What it does: Hosts Apache ECharts with resize, theme and reduced-motion handling, keyboard item stepping, a donut centre total and exact legend, and a "View as table" toggle with the returned values. */

"use client";

import { useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { init, use as registerECharts } from "echarts/core";
import type { EChartsType, ECElementEvent } from "echarts/core";
import { BarChart, BoxplotChart, HeatmapChart, LineChart, PieChart, SankeyChart, ScatterChart, TreeChart, TreemapChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import { useDarkTheme } from "../../theme-control";
import { addExact, bucketSlices, chartSummary, readableMetric, shareText, specTable } from "./chart-values";
import type { ChartSpec, Slice } from "./chart-values";
import { kitItemCount, makeKitOption, sliceColor } from "./chart-options";
import { defaultTokens, readTokens } from "./chart-tokens";
import type { ChartTokens } from "./chart-tokens";
import styles from "./chart-kit.module.css";

registerECharts([PieChart, BarChart, LineChart, ScatterChart, HeatmapChart, BoxplotChart, TreemapChart, SankeyChart, TreeChart, GridComponent, LegendComponent, TooltipComponent, VisualMapComponent, SVGRenderer]);

function subscribeMotion(callback: () => void) {
  const query = window.matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

export function useReducedMotion() {
  return useSyncExternalStore(subscribeMotion, () => window.matchMedia("(prefers-reduced-motion: reduce)").matches, () => true);
}

function leafCount(node: { children?: unknown[] }): number {
  return node.children?.length ? (node.children as { children?: unknown[] }[]).reduce((total: number, child) => total + leafCount(child), 0) : 1;
}

export function kitHeight(spec: ChartSpec, width: number): number {
  switch (spec.kind) {
    case "donut": return width < 480 ? 220 : 240;
    case "bar": return (spec.horizontal ?? spec.series.length === 1) ? Math.max(160, Math.min(560, spec.categories.length * 34 + 24)) : 300;
    case "heatmap": return Math.max(240, spec.y.length * 44 + 130);
    case "tree": return Math.max(220, Math.min(720, leafCount(spec.root) * 30 + 40));
    case "sankey": return Math.max(240, spec.nodes.length * 28);
    default: return 280;
  }
}

export function ExactTable({ spec }: { spec: ChartSpec }) {
  const { columns, rows } = specTable(spec);
  return <div className={`tableScroll ${styles.table}`} role="region" tabIndex={0} aria-label={`Exact values for ${spec.title}`}>
    <table><thead><tr>{columns.map((column, index) => <th key={index} scope="col">{column}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, position) => <td key={position}>{cell}</td>)}</tr>)}</tbody></table>
  </div>;
}

function DonutLegend({ slices, total, unit, tokens, active, onFocus, onPick }: { slices: Slice[]; total: string | null; unit?: string; tokens: ChartTokens; active: number | null; onFocus: (index: number | null) => void; onPick?: (index: number) => void }) {
  return <ul className={styles.legend} aria-label="Groups and exact values">
    {slices.map((slice, index) => <li key={`${slice.label}-${index}`} data-active={active === index || undefined}>
      <button type="button" onMouseEnter={() => onFocus(index)} onMouseLeave={() => onFocus(null)} onFocus={() => onFocus(index)} onBlur={() => onFocus(null)} onClick={() => onPick?.(index)} title={slice.members ? slice.members.map(member => `${member.label}: ${member.value}`).join("\n") : `${slice.label}: ${slice.value}`}>
        <span className={styles.swatch} style={{ background: sliceColor(slice, index, tokens) }} aria-hidden="true" />
        <span className={styles.legendLabel}>{slice.label}</span>
        <span className={styles.legendValue}>{readableMetric(slice.value)}{unit ? ` ${unit}` : ""}</span>
        <span className={styles.legendShare}>{shareText(slice.value, total)}</span>
      </button>
    </li>)}
  </ul>;
}

export function KitChart({ spec, onItem, className, centerLabel = "Total", defaultView = "chart", bare = false }: { spec: ChartSpec; onItem?: (index: number) => void; className?: string; centerLabel?: string; defaultView?: "chart" | "table"; bare?: boolean }) {
  const [view, setView] = useState(defaultView);
  const host = useRef<HTMLDivElement>(null);
  const engine = useRef<EChartsType | null>(null);
  const [width, setWidth] = useState(560);
  const [tokens, setTokens] = useState<ChartTokens>(() => defaultTokens(false));
  const [active, setActive] = useState<number | null>(null);
  const reducedMotion = useReducedMotion();
  const dark = useDarkTheme();
  const helpId = useId();
  const option = useMemo(() => makeKitOption(spec, tokens, { reducedMotion, width }), [spec, tokens, reducedMotion, width]);
  const count = kitItemCount(spec);
  const slices = useMemo(() => (spec.kind === "donut" ? bucketSlices(spec.slices, spec.maxSlices) : []), [spec]);
  const total = spec.kind === "donut" ? spec.total ?? addExact(spec.slices.map(slice => slice.value)) : null;

  useEffect(() => {
    const element = host.current;
    if (view !== "chart" || !element) return;
    const chart = init(element, undefined, { renderer: "svg" });
    engine.current = chart;
    const observer = new ResizeObserver(entries => {
      const next = entries[0]?.contentRect.width;
      if (next && !chart.isDisposed()) { setWidth(next); chart.resize(); }
    });
    observer.observe(element);
    return () => { observer.disconnect(); chart.dispose(); engine.current = null; };
  }, [view]);

  useEffect(() => { if (host.current) setTokens(readTokens(host.current, dark)); }, [dark, view]);

  useEffect(() => {
    const chart = engine.current;
    if (!chart) return;
    chart.setOption(option, { notMerge: true });
    if (host.current) host.current.dataset.engineReady = "true";
    const click = (event: ECElementEvent) => { if (event.componentType === "series" && Number.isInteger(event.dataIndex)) onItem?.(event.dataIndex); };
    chart.on("click", click);
    return () => { if (!chart.isDisposed()) chart.off("click", click); };
  }, [option, onItem]);

  useEffect(() => {
    const chart = engine.current;
    if (!chart || chart.isDisposed()) return;
    chart.dispatchAction({ type: "downplay", seriesIndex: 0 });
    if (active === null) { chart.dispatchAction({ type: "hideTip" }); return; }
    chart.dispatchAction({ type: "highlight", seriesIndex: 0, dataIndex: active });
    if (spec.kind !== "donut") chart.dispatchAction({ type: "showTip", seriesIndex: 0, dataIndex: active });
  }, [active, option, spec.kind]);

  function step(event: React.KeyboardEvent) {
    if (!count) return;
    const keys: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    if (event.key === "Escape") { setActive(null); return; }
    if (event.key === "Home" || event.key === "End") { event.preventDefault(); setActive(event.key === "Home" ? 0 : count - 1); return; }
    if (event.key === "Enter" && active !== null) { onItem?.(active); return; }
    if (!(event.key in keys)) return;
    event.preventDefault();
    setActive(current => current === null ? 0 : (current + keys[event.key] + count) % count);
  }

  const height = kitHeight(spec, width);
  const activeSlice = active !== null ? slices[active] : null;
  return <figure className={`${styles.frame} ${className ?? ""}`} data-kit-chart={spec.kind}>
    {bare ? <figcaption className={styles.hidden}>{spec.title}</figcaption> : <div className={styles.header}>
      <div><figcaption className={styles.title}>{spec.title}</figcaption>{spec.subtitle && <p className={styles.subtitle}>{spec.subtitle}</p>}</div>
      <button type="button" className={styles.toggle} aria-pressed={view === "table"} onClick={() => setView(view === "table" ? "chart" : "table")}>{view === "table" ? "View as chart" : "View as table"}</button>
    </div>}
    {view === "table" ? <ExactTable spec={spec} /> : <div className={spec.kind === "donut" ? styles.donutLayout : undefined}>
      <div className={styles.canvasWrap}>
        <div ref={host} className={styles.canvas} style={{ height }} role="img" tabIndex={0} aria-label={chartSummary(spec)} aria-describedby={helpId} onKeyDown={step} onBlur={() => setActive(null)} data-chart-renderer="apache-echarts" data-reduced-motion={String(reducedMotion)} />
        {spec.kind === "donut" && <div className={styles.center} aria-hidden="true">
          <span>{activeSlice ? activeSlice.label : centerLabel}</span>
          <strong title={(activeSlice ? activeSlice.value : total) ?? undefined}>{readableMetric(activeSlice ? activeSlice.value : total)}</strong>
          {activeSlice ? <small>{shareText(activeSlice.value, total)}</small> : spec.unit ? <small>{spec.unit}</small> : null}
        </div>}
      </div>
      {spec.kind === "donut" && <DonutLegend slices={slices} total={total} unit={spec.unit} tokens={tokens} active={active} onFocus={setActive} onPick={onItem} />}
    </div>}
    <p id={helpId} className={styles.note}>{view === "chart" ? "Shapes are approximate; labels, legend and table show the exact returned values." : "Exact returned values."}</p>
  </figure>;
}
