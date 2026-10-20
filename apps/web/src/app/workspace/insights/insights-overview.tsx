/* Use case: Tells the reader what the analyst team found right after upload, like a Liveboard.
What it does: Loads the insights-v1 overview, shows exact KPI tiles, double-checked insight cards with kit charts and evidence, and proposed action buttons that open chat, data preparation, unusual-value checks, what-ifs or meaning review. */

"use client";

import { useEffect, useId, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import type { ApiRequest } from "../profile-panel";
import { Icon } from "../explore-components";
import { KitChart, useReducedMotion } from "../charts/kit-chart";
import { humanizeFields, humanizeSpec, readableMetric } from "../charts/chart-values";
import { StatTile } from "../charts/stat-tile";
import { actionIntent, analystNames, chartSpecFromInsight, insightFields } from "./insights-model";
import type { ActionIntent, InsightAction, InsightCard, InsightsPayload } from "./insights-model";
import styles from "./insights.module.css";

type Words = (text: string) => string;
const plain: Words = text => text;

export function KpiRow({ kpis, words = plain }: { kpis: InsightsPayload["kpis"]; words?: Words }) {
  return <div className={styles.kpis} aria-label="Key figures for this file">
    {kpis.map(kpi => <StatTile key={kpi.id} label={words(kpi.label)} value={readableMetric(kpi.value)} exact={kpi.value} unit={kpi.unit ?? undefined} caption={kpi.detail ? words(kpi.detail) : undefined} />)}
  </div>;
}

function ActionButton({ action, onAction, words }: { action: InsightAction; onAction: (intent: ActionIntent) => void; words: Words }) {
  const intent = actionIntent(action);
  if (!intent) return null;
  return <button type="button" className={styles.action} onClick={() => onAction(intent)}>
    <span>{words(action.label)}</span><Icon name="arrow" size={14} />
  </button>;
}

function DoubleChecked({ card }: { card: InsightCard }) {
  if (card.cross_check?.status !== "verified" || !card.cross_check.checks.every(check => check.agrees)) return null;
  const detail = card.cross_check.checks.map(check => `${check.label}: ${check.primary} = ${check.secondary}`).join("\n");
  return <span className={styles.badge} title={detail}><Icon name="check" size={13} />Double-checked</span>;
}

export function InsightCardView({ card, index, onAction, fields = [] }: { card: InsightCard; index: number; onAction: (intent: ActionIntent) => void; fields?: string[] }) {
  const words: Words = text => humanizeFields(text, fields);
  const mapped = chartSpecFromInsight(card.chart);
  const spec = mapped && { ...humanizeSpec(mapped, fields), subtitle: undefined };
  const actions = (card.actions ?? []).filter(action => actionIntent(action));
  return <article className={styles.card} style={{ "--i": Math.min(index, 6) } as CSSProperties} data-insight={card.id} data-analyst={card.analyst} tabIndex={-1} aria-labelledby={`insight-${card.id}`}>
    <header className={styles.cardHeader}>
      <span className={styles.kind} data-tone={kindTone(card.analyst)}><Icon name={kindIcon(card.analyst)} size={13} />{analystNames[card.analyst] ?? card.analyst}</span>
      <DoubleChecked card={card} />
    </header>
    <h3 className={styles.cardTitle} id={`insight-${card.id}`} title={card.title}>{words(card.title)}</h3>
    <p className={styles.summary}>{words(card.summary)}</p>
    {spec && <KitChart spec={spec} centerLabel={words(card.chart?.y.label || "Total")} />}
    {Boolean(card.evidence?.length) && <ul className={styles.evidence} aria-label="Evidence">
      {card.evidence!.map((item, position) => <li key={position} title={`${item.label}: ${item.value}${item.unit ? ` ${item.unit}` : ""}`}><span>{words(item.label)}</span><strong>{words(readableMetric(item.value))}{item.unit ? ` ${item.unit}` : ""}</strong></li>)}
    </ul>}
    {actions.length > 0 && <div className={styles.cardActions}>{actions.slice(0, 3).map(action => <ActionButton key={action.id} action={action} onAction={onAction} words={words} />)}</div>}
    {Boolean(card.cross_check?.checks.length || (card.statements?.length ?? 0) > 1) && <details className={styles.details}>
      <summary>Why this?</summary>
      {(card.statements?.length ?? 0) > 1 && <ul>{card.statements!.map((statement, position) => <li key={position}>{words(statement)}</li>)}</ul>}
      {Boolean(card.cross_check?.checks.length) && <div className="tableScroll" role="region" tabIndex={0} aria-label={`Cross-checks for ${card.title}`}><table>
        <thead><tr><th scope="col">Check</th><th scope="col">First calculation</th><th scope="col">Independent check</th><th scope="col">Method</th></tr></thead>
        <tbody>{card.cross_check!.checks.map((check, position) => <tr key={position}><td>{check.label}</td><td>{check.primary}</td><td>{check.secondary}</td><td>{check.method}{check.query_id ? ` · ${check.query_id}` : ""}</td></tr>)}</tbody>
      </table></div>}
    </details>}
  </article>;
}

const kindIcon = (analyst: string) => ({ quality: "prepare", composition: "overview", distribution: "usage", segment: "studies", relationship: "patterns", outlier: "search" })[analyst] ?? "sparkle";
const kindTone = (analyst: string) => (analyst === "outlier" || analyst === "quality" ? "watch" : analyst === "relationship" || analyst === "segment" ? "notable" : "info");

const sections: [string, string, string[]][] = [
  ["composition", "Composition", ["composition"]],
  ["segment", "Group comparisons", ["segment"]],
  ["distribution", "Distributions", ["distribution", "outlier"]],
  ["relationship", "Relationships", ["relationship"]],
  ["quality", "Data quality", ["quality"]],
];

function FindingsStrip({ cards, words, onReveal }: { cards: InsightCard[]; words: Words; onReveal: (card: InsightCard) => void }) {
  return <ol className={styles.strip} aria-label="Top findings">
    {cards.map((card, index) => <li key={card.id} style={{ "--i": index } as CSSProperties}>
      <a href={`#insight-${card.id}`} onClick={event => { event.preventDefault(); onReveal(card); }}><span className={styles.kind} data-tone={kindTone(card.analyst)}><Icon name={kindIcon(card.analyst)} size={13} />{analystNames[card.analyst] ?? card.analyst}</span>
        <strong>{words(card.title)}</strong><span className={styles.stripSummary}>{words(card.summary)}</span><span className={styles.stripLink}>See the chart and evidence<Icon name="arrow" size={13} /></span></a>
    </li>)}
  </ol>;
}

export type ProposedItem = { key: string; label: string; reason?: string; group: string; run: () => void };

export function proposedFromInsights(actions: InsightAction[], onAction: (intent: ActionIntent) => void, words: Words = plain): ProposedItem[] {
  return actions.flatMap(action => {
    const intent = actionIntent(action);
    return intent ? [{ key: action.id, label: words(action.label), group: actionGroups[intent.type], run: () => onAction(intent) }] : [];
  });
}

const actionGroups: Record<ActionIntent["type"], string> = { ask: "Ask", prepare: "Prepare", anomalies: "Check", scenario: "What-if", review: "Confirm" };

export function ProposedActions({ items }: { items: ProposedItem[] }) {
  if (!items.length) return null;
  return <section className={styles.proposed} aria-label="Proposed actions">
    <div><span className={styles.overline}>Proposed actions</span><h3>What to do next</h3><p>Each action opens a governed check, question or what-if. Results show their own evidence and assumptions; suggestions are not findings.</p></div>
    <div className={styles.proposedGrid}>{items.map((item, index) => <button key={item.key} type="button" className={`${styles.proposedItem} ${index === 0 ? styles.proposedLead : ""}`} style={{ "--i": Math.min(index, 6) } as CSSProperties} onClick={item.run}>
      <strong>{item.label}<Icon name="arrow" size={14} /></strong>
      <span className={styles.proposedGroup}>{item.group}</span>
      {item.reason && <span>{item.reason}</span>}
    </button>)}</div>
  </section>;
}

export function InsightsSkeleton() {
  return <div className={styles.grid} aria-hidden="true">
    {[0, 1, 2, 3].map(item => <div key={item} className={`${styles.card} ${styles.skeleton}`}><span /><span /><span /><span /></div>)}
  </div>;
}

export type InsightsState = { root: string; payload?: InsightsPayload; error?: string } | null;

export function useInsights(root: string, request: ApiRequest, enabled: boolean): [InsightsState, () => void] {
  const [state, setState] = useState<InsightsState>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    request<InsightsPayload>(`${root}/analyst-overview`, { signal: controller.signal })
      .then(payload => setState({ root, payload: payload?.version === "insights-v1" ? payload : undefined }))
      .catch(cause => { if (!controller.signal.aborted) setState({ root, error: cause instanceof Error ? cause.message : "The analyst overview could not load." }); });
    return () => controller.abort();
  }, [root, request, attempt, enabled]);
  return [state?.root === root ? state : null, () => { setState(null); setAttempt(value => value + 1); }];
}

export function useInsightWords(payload: InsightsPayload | undefined, known: string[]): [string[], Words] {
  const fields = useMemo(() => [...known, ...(payload ? insightFields(payload) : [])], [payload, known]);
  return [fields, (text: string) => humanizeFields(text, fields)];
}

export function insightTabs(cards: InsightCard[]): { key: string; title: string; cards: InsightCard[] }[] {
  const grouped = sections.map(([key, title, analysts]) => ({ key, title, cards: cards.filter(card => analysts.includes(card.analyst)) }));
  const other = cards.filter(card => !sections.some(([, , analysts]) => analysts.includes(card.analyst)));
  return [{ key: "highlights", title: "Highlights", cards: cards.slice(0, 4) }, ...grouped, { key: "more", title: "More", cards: other }].filter(tab => tab.key === "highlights" || tab.cards.length);
}

function CardGrid({ cards, onAction, fields }: { cards: InsightCard[]; onAction: (intent: ActionIntent) => void; fields: string[] }) {
  return <div className={styles.grid}>{cards.map((card, index) => <InsightCardView key={card.id} card={card} index={index} onAction={onAction} fields={fields} />)}</div>;
}

function InsightsBoard({ payload, onAction, fields, words }: { payload: InsightsPayload; onAction: (intent: ActionIntent) => void; fields: string[]; words: Words }) {
  const tabs = useMemo(() => insightTabs(payload.insights), [payload]);
  const [selected, setSelected] = useState("highlights");
  const [pending, setPending] = useState({ id: "", tick: 0 });
  const reducedMotion = useReducedMotion();
  const baseId = useId();
  const active = tabs.find(tab => tab.key === selected) ?? tabs[0];
  const kpis = payload.kpis;
  useEffect(() => {
    if (!pending.id) return;
    const card = document.querySelector<HTMLElement>(`[data-insight="${CSS.escape(pending.id)}"]`);
    if (!card) return;
    card.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
    card.focus({ preventScroll: true });
    card.dataset.highlight = "true";
    const timer = window.setTimeout(() => { delete card.dataset.highlight; }, 1600);
    return () => { window.clearTimeout(timer); delete card.dataset.highlight; };
  }, [pending, reducedMotion]);
  function choose(key: string, focus = false) {
    setSelected(key);
    if (focus) document.getElementById(`${baseId}-tab-${key}`)?.focus();
  }
  function keys(event: React.KeyboardEvent) {
    const index = tabs.findIndex(tab => tab.key === active.key);
    const next = event.key === "ArrowRight" ? index + 1 : event.key === "ArrowLeft" ? index - 1 : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null;
    if (next === null) return;
    event.preventDefault();
    choose(tabs[(next + tabs.length) % tabs.length].key, true);
  }
  function reveal(card: InsightCard) {
    const home = tabs.find(tab => tab.key !== "highlights" && tab.cards.some(item => item.id === card.id)) ?? tabs[0];
    setSelected(home.key);
    setPending(current => ({ id: card.id, tick: current.tick + 1 }));
  }
  return <>
    <div className={styles.tabs} role="tablist" aria-label="Analyst overview sections" onKeyDown={keys}>
      {tabs.map(tab => <button key={tab.key} id={`${baseId}-tab-${tab.key}`} type="button" role="tab" aria-selected={tab.key === active.key} aria-controls={`${baseId}-panel`} tabIndex={tab.key === active.key ? 0 : -1} onClick={() => choose(tab.key)}>
        {tab.title}{tab.key !== "highlights" && <span className={styles.tabCount}>{tab.cards.length}</span>}
      </button>)}
    </div>
    <div className={styles.panel} id={`${baseId}-panel`} role="tabpanel" aria-labelledby={`${baseId}-tab-${active.key}`} data-insight-tab={active.key}>
      {active.key === "highlights" ? <>
        {payload.insights.length > 0 && <FindingsStrip cards={payload.insights.slice(0, 3)} words={words} onReveal={reveal} />}
        {kpis.length > 0 && <KpiRow kpis={kpis} words={words} />}
        {active.cards.length > 0 && <CardGrid cards={active.cards} onAction={onAction} fields={fields} />}
        <p className={styles.tabHint}>Every finding was recalculated by an independent check before being shown.{payload.definition_state !== "confirmed" ? " Meanings are inferred until you confirm them." : ""}{payload.insights.length - active.cards.length > 0 ? ` ${payload.insights.length - active.cards.length} more findings are grouped in the tabs above.` : ""}</p>
      </> : <CardGrid cards={active.cards} onAction={onAction} fields={fields} />}
    </div>
  </>;
}

export function InsightsOverview({ state, retry, onAction, fields: knownFields, words: knownWords }: { state: InsightsState; retry: () => void; onAction: (intent: ActionIntent) => void; fields?: string[]; words?: Words }) {
  if (!state) return <section className={styles.overview} aria-label="Analyst overview" aria-busy="true">
    <div className={styles.heading}><span className={styles.overline}>Analyst overview</span><h3>Checking your data from several angles…</h3></div>
    <InsightsSkeleton />
  </section>;
  if (state.error) return <section className={styles.overview} aria-label="Analyst overview">
    <div className={styles.notice} role="status"><p><strong>The analyst overview is unavailable right now.</strong> The calculated starting points below still come from your file.</p>
      <button type="button" className={styles.action} onClick={retry}>Try again</button></div>
  </section>;
  const payload = state.payload;
  if (!payload) return null;
  const fields = knownFields ?? insightFields(payload);
  const words = knownWords ?? ((text: string) => humanizeFields(text, fields));
  return <section className={styles.overview} aria-label="Analyst overview">
    <div className={styles.heading}>
      <span className={styles.overline}>Analyst overview</span>
      <h3>{payload.insights.length ? "What stands out in your data" : "No standout findings yet"}</h3>
      {!payload.insights.length && <p>Nothing passed the checks strongly enough to highlight. Ask a question or explore the calculated starting points below.{payload.definition_state !== "confirmed" ? " Meanings are inferred until you confirm them." : ""}</p>}
    </div>
    {payload.insights.length > 0 ? <InsightsBoard payload={payload} onAction={onAction} fields={fields} words={words} /> : payload.kpis.length > 0 && <KpiRow kpis={payload.kpis} words={words} />}
    {Boolean(payload.limitations?.length) && <details className={styles.details}><summary>Limits of this overview</summary><ul>{payload.limitations!.map((item, index) => <li key={index}>{words(item)}</li>)}</ul></details>}
  </section>;
}
