/* Use case: Shows the dashboard Syntelio built for this dataset before anything else on the overview.
What it does: Loads the auto-dashboard-v1 version, renders KPI tiles and kit charts with exact values, explains why the tiles were chosen, and lets the owner edit, share, rebuild or save a tile as a pinnable study. */

"use client";

import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import type { ApiRequest } from "../profile-panel";
import { Icon } from "../explore-components";
import { KitChart } from "../charts/kit-chart";
import { humanizeFields, humanizeSpec, readableMetric } from "../charts/chart-values";
import { StatTile } from "../charts/stat-tile";
import { chartSpecFromInsight } from "./insights-model";
import { selectionNote, studyMethod } from "./auto-dashboard-model";
import type { AutoDashboard, AutoDashboardResponse, DashboardTile } from "./auto-dashboard-model";
import styles from "./insights.module.css";
import board from "./auto-dashboard.module.css";

type Words = (text: string) => string;
type State = { root: string; data?: AutoDashboardResponse; error?: string } | null;

function Tile({ tile, index, words, onSave, saved }: { tile: DashboardTile; index: number; words: Words; onSave?: () => void; saved?: string }) {
  const mapped = chartSpecFromInsight(tile.chart);
  const fields = tile.columns;
  const spec = mapped && { ...humanizeSpec(mapped, fields), subtitle: undefined };
  return <article className={`${styles.card} ${board.tile}`} style={{ "--i": Math.min(index, 8) } as CSSProperties} data-tile={tile.id} data-kind={tile.kind}>
    <h3 className={styles.cardTitle}>{words(tile.title)}</h3>
    {tile.kpi ? <StatTile label={words(tile.reason)} value={readableMetric(tile.kpi.value)} exact={tile.kpi.value} unit={tile.kpi.unit ?? undefined} /> : <p className={styles.summary}>{words(tile.summary || tile.reason)}</p>}
    {spec && <KitChart spec={spec} centerLabel={words(tile.chart?.y.label || "Total")} />}
    {onSave && <div className={styles.cardActions}>
      <button type="button" className={styles.action} onClick={onSave} disabled={Boolean(saved)}><span>{saved || "Save as study to pin"}</span><Icon name="studies" size={14} /></button>
    </div>}
  </article>;
}

export function AutoDashboardView({ root, request, enabled, fields = [], onReview }: { root: string; request: ApiRequest; enabled: boolean; fields?: string[]; onReview: () => void }) {
  const [state, setState] = useState<State>(null);
  const [attempt, setAttempt] = useState(0);
  const [editing, setEditing] = useState<string[] | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [saved, setSaved] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    request<AutoDashboardResponse>(`${root}/auto-dashboard`, { signal: controller.signal })
      .then(data => setState({ root, data: data?.dashboard?.version === "auto-dashboard-v1" ? data : undefined }))
      .catch(cause => { if (!controller.signal.aborted) setState({ root, error: cause instanceof Error ? cause.message : "The dashboard could not load." }); });
    return () => controller.abort();
  }, [root, request, attempt, enabled]);
  if (!enabled) return null;
  const current = state?.root === root ? state : null;
  const dashboard = current?.data?.dashboard;
  const words: Words = text => humanizeFields(text, [...fields, ...(dashboard?.candidates.flatMap(item => item.columns) ?? [])]);
  const workspace = root.split("/datasets/")[0];

  function replace(next: AutoDashboard) {
    setState(value => value?.data ? { ...value, data: { ...value.data, dashboard: next } } : value);
  }
  async function run(label: string, work: () => Promise<AutoDashboard>) {
    setBusy(label);
    setNotice("");
    try { replace(await work()); setEditing(null); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : "That change did not save."); }
    finally { setBusy(""); }
  }
  const patch = (body: Record<string, unknown>) => run("save", () => request<AutoDashboard>(`${workspace}/auto-dashboards/${dashboard!.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_number: dashboard!.number, ...body }) }));
  async function save(tile: DashboardTile) {
    const method = studyMethod(tile);
    const source = dashboard?.sources[0];
    if (!method || !source?.understanding_id) return;
    try {
      await request(`${root}/studies`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: tile.title.slice(0, 100), question: `${tile.title.slice(0, 480)}?`, method, revision_id: source.revision_id, understanding_id: source.understanding_id }) });
      setSaved(value => ({ ...value, [tile.id]: "Saved — pin it in Studies & dashboards" }));
    } catch (cause) { setNotice(cause instanceof Error ? cause.message : "The study could not be saved."); }
  }

  if (!current) return <section className={styles.overview} aria-label="Your dashboard" aria-busy="true">
    <div className={styles.heading}><span className={styles.overline}>Your dashboard</span><h3>Building a dashboard for this data…</h3></div>
    <div className={styles.grid} aria-hidden="true">{[0, 1, 2].map(item => <div key={item} className={`${styles.card} ${styles.skeleton}`}><span /><span /><span /><span /></div>)}</div>
  </section>;
  if (current.error || !dashboard) return <section className={styles.overview} aria-label="Your dashboard">
    <div className={styles.notice} role="status"><p><strong>The automatic dashboard is unavailable right now.</strong> The analyst overview below still comes from your file.</p>
      <button type="button" className={styles.action} onClick={() => { setState(null); setAttempt(value => value + 1); }}>Try again</button></div>
  </section>;
  const kpis = dashboard.tiles.filter(tile => tile.kpi);
  const charts = dashboard.tiles.filter(tile => !tile.kpi);
  const confirmed = dashboard.definition_state === "confirmed";
  return <section className={`${styles.overview} ${board.board}`} aria-label="Your dashboard" data-dashboard={dashboard.id} data-version={dashboard.number}>
    <div className={board.header}>
      <div className={styles.heading}>
        <span className={styles.overline}>Your dashboard · version {dashboard.number}{dashboard.owned ? "" : " · shared with you"}</span>
        <h3>Built for {dashboard.dataset_name}</h3>
      </div>
      {dashboard.owned && <div className={board.controls}>
        <button type="button" className={styles.action} disabled={Boolean(busy)} aria-pressed={editing !== null} onClick={() => setEditing(editing ? null : dashboard.tiles.map(tile => tile.id))}><span>{editing ? "Cancel editing" : "Edit tiles"}</span></button>
        <button type="button" className={styles.action} disabled={Boolean(busy)} aria-pressed={dashboard.shared} onClick={() => patch({ shared: !dashboard.shared })}><span>{dashboard.shared ? "Shared with workspace" : "Private — share"}</span></button>
        <button type="button" className={styles.action} disabled={Boolean(busy)} onClick={() => run("rebuild", () => request<AutoDashboard>(`${root}/auto-dashboard/rebuild`, { method: "POST" }))}><span>{busy === "rebuild" ? "Rebuilding…" : "Rebuild dashboard"}</span></button>
      </div>}
    </div>
    {notice && <p role="alert" className={board.alert}>{notice}</p>}
    {dashboard.needs_confirmation && <div className={styles.notice}><p><strong>Confirm meanings for more.</strong> Totals, averages, trends and rankings of your measures appear once their meaning and units are confirmed.</p>
      <button type="button" className={styles.action} onClick={onReview}><span>Review data meaning</span><Icon name="arrow" size={14} /></button></div>}
    {editing && <fieldset className={board.editor}>
      <legend>Choose up to nine tiles</legend>
      {dashboard.candidates.map(item => <label key={item.id}><input type="checkbox" checked={editing.includes(item.id)} disabled={!editing.includes(item.id) && editing.length >= 9} onChange={event => setEditing(value => (value ?? []).filter(key => key !== item.id).concat(event.target.checked ? [item.id] : []))} />{words(item.title)}</label>)}
      <button type="button" className={styles.primaryAction} disabled={!editing.length || Boolean(busy)} onClick={() => patch({ tiles: editing })}><span>{busy === "save" ? "Saving…" : "Save tiles"}</span></button>
    </fieldset>}
    {kpis.length > 0 && <div className={styles.kpis} aria-label="Key figures">{kpis.map(tile => <div key={tile.id} data-tile={tile.id} data-kind="kpi" title={tile.reason}><StatTile label={words(tile.title)} value={readableMetric(tile.kpi!.value)} exact={tile.kpi!.value} unit={tile.kpi!.unit ?? undefined} caption={words(tile.reason)} /></div>)}</div>}
    {charts.length > 0 && <div className={styles.grid}>{charts.map((tile, index) => <Tile key={tile.id} tile={tile} index={index} words={words} saved={saved[tile.id]} onSave={dashboard.owned && confirmed && studyMethod(tile) ? () => save(tile) : undefined} />)}</div>}
    {!dashboard.tiles.length && <p className={styles.tabHint}>No tiles could be built for this file yet. Confirm its meaning or ask a question.</p>}
    <details className={styles.details}>
      <summary>Why this dashboard</summary>
      <p>{selectionNote(dashboard)} Built from a {dashboard.brief_summary.rows}-row brief of this file{dashboard.brief_summary.date_coverage ? `, dated ${dashboard.brief_summary.date_coverage.min} to ${dashboard.brief_summary.date_coverage.max} (${words(dashboard.brief_summary.date_coverage.column)})` : ", with no date field"}.</p>
      <ul>{dashboard.tiles.map(tile => <li key={tile.id}><strong>{words(tile.title)}:</strong> {words(tile.reason)}{tile.query_ids.length ? ` · ${tile.query_ids.length} receipt${tile.query_ids.length > 1 ? "s" : ""}` : ""}</li>)}</ul>
      <ul>{dashboard.limitations.map((item, index) => <li key={index}>{words(item)}</li>)}</ul>
    </details>
  </section>;
}
