/* Use case: Displays a source-bound map of the fields in a dataset.
What it does: Uses the bundled ECharts tree renderer, themed and animated through the shared chart kit tokens, for declared membership edges and keeps every supplied field available as accessible exact text. */

import { useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { useDarkTheme } from "../theme-control";
import { defaultTokens, readTokens } from "./charts/chart-tokens";
import type { ChartTokens } from "./charts/chart-tokens";
import { init, use as registerECharts } from "echarts/core";
import type { EChartsCoreOption, EChartsType, ECElementEvent } from "echarts/core";
import { TreeChart } from "echarts/charts";
import { SVGRenderer } from "echarts/renderers";
import styles from "./diagram-results.module.css";

registerECharts([TreeChart, SVGRenderer]);

export type DiagramNode = {
  id: string;
  kind: "dataset" | "group" | "field";
  label: string;
  data_type: string;
  role: string;
  meaning: string;
  unit: string;
  currency: string;
  unit_column?: string;
};
export type DatasetDiagram = {
  version: "dataset-structure-v1" | "dataset-structure-v2";
  title: string;
  description: string;
  row_meaning: string;
  definition_state: string;
  scope: "all_fields" | "selected_fields";
  total_fields: number;
  shown_fields: number;
  nodes: DiagramNode[];
  edges: { source: string; target: string; relation: "contains" }[];
  limitations: string[];
};

function subscribeMotion(callback: () => void) {
  const query = window.matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

export function makeDiagramOption(diagram: DatasetDiagram, branch: string, first: number, width: number, reducedMotion: boolean, tokens: ChartTokens = defaultTokens(false)): EChartsCoreOption {
  const root = diagram.nodes.find(node => node.kind === "dataset");
  const groups = diagram.nodes.filter(node => node.kind === "group" && diagram.edges.some(edge => edge.source === root?.id && edge.target === node.id));
  const group = groups.find(node => node.id === branch);
  const fields = group ? diagram.nodes.filter(node => node.kind === "field" && diagram.edges.some(edge => edge.source === group.id && edge.target === node.id)).slice(first, first + 10) : [];
  const narrow = width < 500;
  const tone = (node: DiagramNode) => tokens.series[Math.max(0, groups.findIndex(item => item.id === node.id || diagram.edges.some(edge => edge.source === item.id && edge.target === node.id))) % tokens.series.length];
  const pill = (color: string) => ({ backgroundColor: tokens.surface, borderColor: color, borderWidth: 1, borderRadius: 6, padding: [4, 8], color: tokens.ink });
  const leaf = (node: DiagramNode) => {
    const color = tone(node);
    const isGroup = node.kind === "group";
    return { id: node.id, name: node.label, symbolSize: isGroup ? 14 : 9, itemStyle: { color, borderColor: tokens.surface, borderWidth: 2 },
      label: { position: "right", align: "left", width: narrow ? 105 : 180, overflow: "truncate", ...pill(isGroup ? color : tokens.grid), fontWeight: isGroup ? 600 : 400 } };
  };
  const groupTree = group ? { ...leaf(group), label: { position: "top", align: "center", distance: 10, width: narrow ? 120 : 160, overflow: "truncate", ...pill(tone(group)), fontWeight: 600 }, children: fields.map(leaf) } : null;
  const rootNode = { id: root?.id, name: root?.label ?? "This file", symbolSize: 18, itemStyle: { color: tokens.ink, borderColor: tokens.surface, borderWidth: 3 }, label: { position: "top", align: "center", distance: 10, width: narrow ? 110 : 150, overflow: "truncate", fontWeight: 650, ...pill(tokens.ink) } };
  const tree = groupTree && narrow ? groupTree : { ...rootNode, children: groupTree ? [groupTree] : groups.map(leaf) };
  return {
    animation: !reducedMotion,
    animationDuration: reducedMotion ? 0 : 600,
    animationEasing: "cubicOut",
    animationDurationUpdate: reducedMotion ? 0 : 300,
    series: [{
      type: "tree", data: [tree], orient: "LR", top: 36, bottom: 24,
      left: narrow ? 64 : 100, right: narrow ? 130 : 210,
      symbol: "circle", symbolSize: 12, edgeShape: "curve",
      initialTreeDepth: -1, expandAndCollapse: false, roam: false,
      itemStyle: { color: tokens.series[0], borderColor: tokens.surface, borderWidth: 2 },
      lineStyle: { color: tokens.grid, width: 1.5, curveness: 0.5 },
      label: { position: "top", align: "left", color: tokens.ink, fontFamily: tokens.font, fontSize: 12, width: narrow ? 100 : 150, overflow: "truncate" },
      emphasis: { focus: "ancestor", lineStyle: { color: tokens.muted, width: 2 } },
    }],
  };
}

export function DiagramResults({ diagram, sources = [] }: { diagram: DatasetDiagram; sources?: { revision_id: string; understanding_id?: string }[] }) {
  const [selectedId, setSelectedId] = useState(diagram.nodes[0]?.id ?? "");
  const [branch, setBranch] = useState(() => { const groups = diagram.nodes.filter(node => node.kind === "group"); return groups.length === 1 ? groups[0].id : ""; });
  const [first, setFirst] = useState(0);
  const [width, setWidth] = useState(640);
  const host = useRef<HTMLDivElement>(null);
  const engine = useRef<EChartsType | null>(null);
  const dark = useDarkTheme();
  const [tokens, setTokens] = useState<ChartTokens>(() => defaultTokens(false));
  const inspectorId = useId();
  const reducedMotion = useSyncExternalStore(subscribeMotion, () => window.matchMedia("(prefers-reduced-motion: reduce)").matches, () => true);
  const selected = diagram.nodes.find(node => node.id === selectedId) ?? diagram.nodes[0];
  const groups = diagram.nodes.filter(node => node.kind === "group");
  const members = useMemo(() => diagram.nodes.filter(node => node.kind === "field" && diagram.edges.some(edge => edge.source === branch && edge.target === node.id)), [diagram, branch]);
  const option = useMemo(() => makeDiagramOption(diagram, branch, first, width, reducedMotion, tokens), [diagram, branch, first, width, reducedMotion, tokens]);
  const height = branch ? Math.max(300, Math.min(10, members.length) * 44 + 80) : Math.max(300, groups.length * 54 + 80);

  function inspect(id: string) {
    const node = diagram.nodes.find(item => item.id === id);
    if (!node) return;
    setSelectedId(id);
    if (node.kind === "dataset") { setBranch(""); setFirst(0); }
    if (node.kind === "group") { setBranch(id); setFirst(0); }
    if (node.kind === "field") {
      const parent = diagram.edges.find(edge => edge.target === id)?.source ?? "";
      const siblings = diagram.nodes.filter(item => item.kind === "field" && diagram.edges.some(edge => edge.source === parent && edge.target === item.id));
      setBranch(parent); setFirst(Math.max(0, Math.floor(siblings.findIndex(item => item.id === id) / 10) * 10));
    }
  }

  useEffect(() => {
    if (!host.current) return;
    const chart = init(host.current, undefined, { renderer: "svg" });
    engine.current = chart;
    const observer = new ResizeObserver(entries => {
      if (entries[0]?.contentRect.width > 0 && !chart.isDisposed()) { setWidth(entries[0].contentRect.width); chart.resize(); }
    });
    observer.observe(host.current);
    return () => { observer.disconnect(); chart.dispose(); engine.current = null; };
  }, []);
  useEffect(() => {
    const chart = engine.current;
    if (!chart) return;
    chart.clear();
    chart.setOption(option, { notMerge: true });
    if (host.current) host.current.dataset.engineReady = "true";
  }, [option]);
  useEffect(() => { if (host.current) setTokens(readTokens(host.current, dark)); }, [dark]);
  useEffect(() => {
    const chart = engine.current;
    if (!chart) return;
    const click = (event: ECElementEvent) => { const node = event.data as { id?: string }; if (node?.id) inspect(node.id); };
    chart.on("click", click);
    return () => { if (!chart.isDisposed()) chart.off("click", click); };
  });

  return <section className={styles.panel} aria-label="Data organisation diagram">
    <header><span className={styles.eyebrow}>YOUR DATA, MAPPED</span><h3>{diagram.title}</h3><p>This map shows which fields belong to your file. Lines show membership, not causes or data joins.</p></header>
    {diagram.version === "dataset-structure-v1" && <p className={styles.legacy}>This earlier map uses analysis groups. Ask again for a map of your saved field roles.</p>}
    {diagram.description && <p className={styles.description}>{diagram.description}</p>}
    <div className={styles.facts}><span>{diagram.shown_fields} of {diagram.total_fields} fields included</span><span>{diagram.definition_state === "confirmed" ? "Saved definitions" : "Definitions need review"}</span>{diagram.row_meaning && <span>One row: {diagram.row_meaning.replaceAll("_", " ")}</span>}</div>
    <label className={styles.branch}>Diagram view<select value={branch} onChange={event => { setBranch(event.target.value); setFirst(0); setSelectedId(event.target.value || diagram.nodes.find(node => node.kind === "dataset")?.id || ""); }}><option value="">Whole file · field groups</option>{groups.map(group => <option key={group.id} value={group.id}>{group.label}</option>)}</select></label>
    <div className={styles.chips} role="group" aria-label="Field groups">{groups.map((group, index) => <button key={group.id} type="button" aria-pressed={branch === group.id} onClick={() => inspect(branch === group.id ? diagram.nodes.find(node => node.kind === "dataset")?.id ?? group.id : group.id)}><span style={{ background: tokens.series[index % tokens.series.length] }} aria-hidden="true" />{group.label}<small>{diagram.edges.filter(edge => edge.source === group.id).length}</small></button>)}</div>
    <p className={styles.caption}>{branch ? `${groups.find(group => group.id === branch)?.label ?? "Selected group"} · fields ${members.length ? first + 1 : 0}–${Math.min(first + 10, members.length)} of ${members.length}.` : "Select a group to see its fields."}</p>
    <div ref={host} className={styles.canvas} style={{ height }} data-diagram-renderer="apache-echarts-tree" data-reduced-motion={String(reducedMotion)} aria-hidden="true" />
    {branch && members.length > 10 && <div className={styles.navigation}><button type="button" disabled={first === 0} onClick={() => setFirst(value => Math.max(0, value - 10))}>Previous diagram fields</button><button type="button" disabled={first + 10 >= members.length} onClick={() => setFirst(value => value + 10)}>Next diagram fields</button></div>}
    <label className={styles.inspector} htmlFor={inspectorId}>Inspect a field or group<select id={inspectorId} value={selected?.id ?? ""} onChange={event => inspect(event.target.value)}>{diagram.nodes.map(node => <option key={node.id} value={node.id}>{node.label}</option>)}</select></label>
    {selected && <div className={styles.detail} aria-label="Diagram item details" aria-live="polite"><h4>{selected.label}</h4><dl><div><dt>Part of the map</dt><dd>{selected.kind}</dd></div>{selected.data_type && <div><dt>Stored type</dt><dd>{selected.data_type}</dd></div>}{selected.role && <div><dt>{diagram.version === "dataset-structure-v1" ? "Earlier analysis role" : "Saved role"}</dt><dd>{selected.role.replaceAll("_", " ")}</dd></div>}{selected.unit && <div><dt>Unit</dt><dd>{selected.unit}</dd></div>}{selected.currency && <div><dt>Currency</dt><dd>{selected.currency}</dd></div>}{selected.unit_column && <div><dt>Unit for each row is in</dt><dd>{selected.unit_column}</dd></div>}</dl>{selected.meaning && <p>{selected.meaning}</p>}{selected.kind === "field" && !selected.meaning && <p>No confirmed description for this field.</p>}</div>}
    {diagram.limitations.length > 0 && <ul className={styles.limitations}>{diagram.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>}
    <details className={styles.evidence}><summary>All included fields & source</summary>{groups.map(group => <section key={group.id}><h4>{group.label}</h4><ul>{diagram.nodes.filter(node => node.kind === "field" && diagram.edges.some(edge => edge.source === group.id && edge.target === node.id)).map(node => <li key={node.id}><strong>{node.label}</strong>{node.meaning && <span>{node.meaning}</span>}{(node.unit || node.currency) && <span>{[node.unit, node.currency].filter(Boolean).join(" · ")}</span>}</li>)}</ul></section>)}{sources.map(source => <p key={source.revision_id}>Source revision: {source.revision_id}{source.understanding_id ? ` · Definition: ${source.understanding_id}` : ""}</p>)}</details>
  </section>;
}
