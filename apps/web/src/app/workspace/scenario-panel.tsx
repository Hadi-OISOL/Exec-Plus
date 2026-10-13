/* Use case: Explores conditional aggregate changes while preserving original records.
What it does: Shows exact scenario comparisons, private successors and evidence replay. */
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import type { AnalysisOptions, AnalysisSummary } from "./decision-types";

type Alternative = { name: string; operation: "replace" | "percent_change"; value: string };
type ScenarioBody = {
  current: boolean;
  run: AnalysisSummary & {
    request: { metric: string; aggregation: "sum" | "avg"; filters: { column: string; operator: string; value: string }[]; alternatives: Alternative[] };
    result: { baseline: string; sample_count: number; metric: string; aggregation: string; parent_run_id: string | null; limitations: string[]; alternatives: (Alternative & { result: string; difference: string; percentage_difference: string | null })[] };
    evidence: { query_id: string; coverage_query_ids: string[]; units: Record<string, string>; result_checksum: string };
  };
};

export function ScenarioPanel({ root, request, onReview }: { root: string; request: ApiRequest; onReview: () => void }) {
  const runsRoot = `${root.split("/uploads/")[0]}/decision-analysis`;
  const [options, setOptions] = useState<AnalysisOptions | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [selected, setSelected] = useState<ScenarioBody | null>(null);
  const [name, setName] = useState("");
  const [metric, setMetric] = useState("");
  const [aggregation, setAggregation] = useState<"sum" | "avg">("sum");
  const [filter, setFilter] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [alternatives, setAlternatives] = useState<Alternative[]>([{ name: "Alternative 1", operation: "percent_change", value: "10" }]);
  const [confirmed, setConfirmed] = useState(false);
  const [parent, setParent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const operation = useRef<AbortController | null>(null);
  useEffect(() => {
    const c = new AbortController();
    Promise.all([request<AnalysisOptions>(`${root}/decision-analysis/options`, { signal: c.signal }), request<AnalysisSummary[]>(runsRoot, { signal: c.signal })])
      .then(([value, saved]) => { if (!c.signal.aborted) { setOptions(value); setHistory(saved.filter(r => r.kind === "scenario_comparison")); } })
      .catch(e => { if (!c.signal.aborted) setError(e instanceof Error ? e.message : "Could not load comparisons."); });
    return () => { c.abort(); operation.current?.abort(); };
  }, [root, request, runsRoot]);
  async function work(action: (signal: AbortSignal) => Promise<void>) {
    if (operation.current) return;
    const c = new AbortController(); operation.current = c; setBusy(true); setError(""); setMessage("");
    try { await action(c.signal); }
    catch (e) { if (!c.signal.aborted) setError(e instanceof Error ? e.message : "Comparison could not complete."); }
    finally { if (!c.signal.aborted) setBusy(false); if (operation.current === c) operation.current = null; }
  }
  async function create(e: FormEvent) {
    e.preventDefault(); if (!options) return;
    await work(async signal => {
      const body = { name: name.trim() || "What-if comparison", metric: metric || options.metrics[0]?.name, aggregation, revision_id: options.revision_id, understanding_id: options.understanding_id, filters: filter ? [{ column: filter, operator: "eq", value: filterValue }] : [], alternatives, assumptions_confirmed: confirmed, parent_run_id: parent };
      const value = await request<ScenarioBody>(`${root}/decision-analysis/scenarios`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
      const saved = await request<AnalysisSummary[]>(runsRoot, { signal });
      if (!signal.aborted) { setSelected(value); setHistory(saved.filter(r => r.kind === "scenario_comparison")); setParent(null); setMessage("Comparison saved privately. Original data is unchanged."); }
    });
  }
  async function open(id: string) {
    await work(async signal => {
      const value = await request<ScenarioBody>(`${runsRoot}/${id}`, { signal });
      if (!signal.aborted) { setSelected(value); setMessage("Baseline, coverage and alternatives reproduced from original evidence."); }
    });
  }
  function successor() {
    if (!selected) return;
    setParent(selected.run.id); setName(`${selected.run.name} · next`.slice(0, 100));
    setMetric(selected.run.request.metric); setAggregation(selected.run.request.aggregation);
    const savedFilter = selected.run.request.filters[0];
    setFilter(savedFilter?.column || ""); setFilterValue(savedFilter?.value || "");
    setAlternatives(selected.run.request.alternatives.map(a => ({ ...a }))); setConfirmed(false);
  }
  function edit(index: number, patch: Partial<Alternative>) { setAlternatives(items => items.map((item, i) => i === index ? { ...item, ...patch } : item)); }
  const result = selected?.run.result;
  const points = result ? [{ name: "Observed baseline", value: result.baseline }, ...result.alternatives.map(a => ({ name: a.name, value: a.result }))] : [];
  const maximum = Math.max(1, ...points.map(p => Math.abs(Number(p.value))));
  return <section className="panel decisionPanel" aria-label="Scenario comparisons">
    <h2>What if your assumptions change?</h2><p>Compare explicit changes to one confirmed total or average. These are hypothetical aggregate values, not predicted demand or proven effects.</p>
    {error && <p role="alert" className="error">{error}</p>}{message && <p role="status">{message}</p>}{busy && <p role="status">Calculating and checking original evidence…</p>}
    {!options ? <p>Loading source options…</p> : options.state !== "ready" ? <><p>Confirm meanings and fixed units before comparing scenarios.</p><button onClick={onReview}>Review data meanings</button></> : <form onSubmit={create}>
      <fieldset disabled={busy}><legend>1. Choose the observed baseline</legend><div className="formGrid">
        <label>Comparison name<input maxLength={100} value={name} onChange={e => setName(e.target.value)} placeholder="Optional name" /></label>
        <label>Scenario measure<select required value={metric || options.metrics[0]?.name || ""} onChange={e => setMetric(e.target.value)}>{options.metrics.map(m => <option key={m.name} value={m.name}>{m.name} · {m.unit}</option>)}</select></label>
        <label>Baseline calculation<select value={aggregation} onChange={e => setAggregation(e.target.value as "sum" | "avg")}><option value="sum">Sum · where confirmed meaning permits</option><option value="avg">Average · where confirmed meaning permits</option></select></label>
        <label>Scenario population<select value={filter} onChange={e => setFilter(e.target.value)}><option value="">All eligible rows</option>{options.entities.map(item => <option key={item}>{item}</option>)}</select></label>
        <label>Scenario filter equals<input value={filterValue} required={Boolean(filter)} onChange={e => setFilterValue(e.target.value)} /></label>
      </div></fieldset>
      <fieldset disabled={busy}><legend>2. Declare up to five alternatives</legend>
        {alternatives.map((a, index) => <div className="formGrid" key={index}>
          <label>Alternative name {index + 1}<input required maxLength={100} value={a.name} onChange={e => edit(index, { name: e.target.value })} /></label>
          <label>Change type {index + 1}<select value={a.operation} onChange={e => edit(index, { operation: e.target.value as Alternative["operation"] })}><option value="percent_change">Change baseline by percent</option><option value="replace">Replace hypothetical aggregate</option></select></label>
          <label>Assumed value {index + 1}<input required inputMode="decimal" maxLength={100} value={a.value} onChange={e => edit(index, { value: e.target.value })} /></label>
          <button type="button" disabled={alternatives.length === 1} onClick={() => setAlternatives(items => items.filter((_, i) => i !== index))}>Remove alternative {index + 1}</button>
        </div>)}
        <button type="button" disabled={alternatives.length >= 5} onClick={() => setAlternatives([...alternatives, { name: `Alternative ${alternatives.length + 1}`, operation: "percent_change", value: "0" }])}>Add alternative</button>
      </fieldset>
      <fieldset disabled={busy}><legend>3. Confirm assumptions and compare</legend>
        <p>Replacement values use the measure unit; percentage changes use percent. Missing measures and unsupported aggregations are refused.</p>
        {parent && <p>Saving a successor preserves the original comparison. <button type="button" onClick={() => setParent(null)}>Start an independent comparison</button></p>}
        <label className="checkLabel"><input type="checkbox" required checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />I confirm these are hypothetical aggregate changes, not forecasts or causal business effects.</label>
        <button disabled={!confirmed || busy}>Calculate and save comparison</button>
      </fieldset>
    </form>}
    <section aria-label="Private scenario history"><h3>Your saved comparisons</h3>{history.length ? <ul>{history.map(r => <li key={r.id}><button disabled={busy} onClick={() => open(r.id)}>{r.name}</button></li>)}</ul> : <p>No saved comparisons yet.</p>}</section>
    {selected && result && <section aria-label="Saved scenario result"><h3>{selected.run.name}</h3>
      <p>{selected.current ? "Current source and meanings." : "Historical source or meanings; create a new comparison against current data."} {result.sample_count} complete records. Baseline {result.aggregation} of {result.metric}: {result.baseline} {selected.run.evidence.units[result.metric]}.</p>
      <div className="buttonRow"><button disabled={busy} onClick={() => open(selected.run.id)}>Replay comparison evidence</button><button disabled={busy} onClick={successor}>Create successor comparison</button></div>
      {result.parent_run_id && <p>Successor of your saved comparison. <button disabled={busy} onClick={() => open(result.parent_run_id!)}>Open prior comparison</button></p>}
      <div className="tableWrap"><svg role="img" aria-label="Conditional scenario comparison plot with approximate coordinates" viewBox={`0 0 640 ${points.length * 48 + 30}`} style={{ width: "100%", minWidth: 640, maxWidth: 640 }}><line x1="400" x2="400" y1="0" y2={points.length * 48} stroke="currentColor" />{points.map((p, i) => <g key={i}><text x="0" y={i * 48 + 25} fill="currentColor">{p.name.slice(0, 20)}</text><circle cx={400 + Number(p.value) / maximum * 200} cy={i * 48 + 20} r="5" fill="currentColor" /></g>)}</svg></div>
      <p>Plot coordinates are approximate. The table preserves returned numerical strings.</p>
      <div className="tableWrap"><table><thead><tr><th>Alternative</th><th>Declared assumption</th><th>Conditional value</th><th>Difference</th><th>Percent difference</th></tr></thead><tbody><tr><td>Observed baseline</td><td>Original source</td><td>{result.baseline}</td><td>0</td><td>{/^[-+]?0(?:\.0*)?$/.test(result.baseline) ? "Unavailable · zero baseline" : "0"}</td></tr>{result.alternatives.map(a => <tr key={a.name}><td>{a.name}</td><td>{a.operation === "replace" ? "Replacement" : "Percent change"}: {a.value}</td><td>{a.result}</td><td>{a.difference}</td><td>{a.percentage_difference ?? "Unavailable · zero baseline"}</td></tr>)}</tbody></table></div>
      <ul>{result.limitations.map(item => <li key={item}>{item}</li>)}</ul>
      <details><summary>Baseline and coverage evidence</summary><p>Three independently replayed source queries calculate the baseline, present measures and population count.</p><ul>{[selected.run.evidence.query_id, ...selected.run.evidence.coverage_query_ids].map(id => <li key={id}>{id}</li>)}</ul><p className="checksum">Result checksum: {selected.run.evidence.result_checksum}</p></details>
    </section>}
  </section>;
}
