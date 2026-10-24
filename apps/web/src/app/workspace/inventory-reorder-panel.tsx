/* Use case: Plans exact inventory reorder quantities from a confirmed demand history.
What it does: Collects stock, reorder point, lead time and cost inputs, then shows the saved private plan with review and downloads. */
"use client";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import type { AnalysisBody, AnalysisOptions, AnalysisSummary } from "./decision-types";
import { ResultExportActions } from "./result-export-actions";
import { REORDER_METHOD, reorderInputs, reorderItems, reorderLabels, serviceLevels, type ReorderInput, type ReorderResult, type TypedItem } from "./inventory-reorder-types";

type Body = Omit<AnalysisBody, "run"> & { run: AnalysisSummary & { result: ReorderResult; evidence: AnalysisBody["run"]["evidence"] } };
const post = (body: object): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const blankItem = (): TypedItem => ({ item: "", stock: "", reorder_point: "", lead_time_days: "", unit_cost: "" });
const columnKey: Record<ReorderInput, string> = { stock: "stock_column", reorder_point: "reorder_point_column", lead_time_days: "lead_time_column", unit_cost: "unit_cost_column" };

export function InventoryReorderPanel({ root, request, onReview }: { root: string; request: ApiRequest; onReview: () => void }) {
  const datasetRoot = root.split("/uploads/")[0], runsRoot = `${datasetRoot}/decision-analysis`;
  const [options, setOptions] = useState<AnalysisOptions | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [selected, setSelected] = useState<Body | null>(null);
  const [name, setName] = useState("");
  const [dateColumn, setDateColumn] = useState(""); const [itemColumn, setItemColumn] = useState(""); const [demandColumn, setDemandColumn] = useState("");
  const [columns, setColumns] = useState<Partial<Record<ReorderInput, string>>>({});
  const [items, setItems] = useState<TypedItem[]>([]);
  const [defaultLead, setDefaultLead] = useState("");
  const [level, setLevel] = useState<string>("0.95");
  const [budget, setBudget] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [note, setNote] = useState("");
  const [pending, setPending] = useState(""); const [error, setError] = useState(""); const [message, setMessage] = useState("");
  const operation = useRef<AbortController | null>(null);
  const source = options?.inventory_reorder;
  const date = dateColumn || source?.dates[0] || "", itemChoices = source?.items.filter(value => !source.dates.includes(value)) ?? [], item = itemColumn || itemChoices[0] || "", demand = demandColumn || options?.metrics[0]?.name || "";
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([request<AnalysisOptions>(`${root}/decision-analysis/options`, { signal: controller.signal }), request<AnalysisSummary[]>(runsRoot, { signal: controller.signal })])
      .then(([value, saved]) => { if (!controller.signal.aborted) { setOptions(value); setHistory(saved); } })
      .catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load analysis options."); });
    return () => { controller.abort(); operation.current?.abort(); };
  }, [root, runsRoot, request]);
  async function work(label: string, action: (signal: AbortSignal) => Promise<void>) {
    if (operation.current) return;
    const controller = new AbortController(); operation.current = controller; setPending(label); setError(""); setMessage("");
    try { await action(controller.signal); }
    catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "The reorder plan could not complete."); }
    finally { if (!controller.signal.aborted) setPending(""); if (operation.current === controller) operation.current = null; }
  }
  async function create(event: FormEvent) {
    event.preventDefault(); if (!options || !confirmed) return;
    await work("Reading the demand history and checking every quantity…", async signal => {
      const body = {
        name: name.trim() || "Reorder plan", revision_id: options.revision_id, understanding_id: options.understanding_id, filters: [],
        date_column: date, item_column: item, demand_column: demand,
        ...Object.fromEntries(reorderInputs.map(key => [columnKey[key], columns[key] || null])),
        default_lead_time_days: !columns.lead_time_days && defaultLead.trim() ? Number(defaultLead) : null,
        items: reorderItems(items, columns), service_level: level, budget: budget.trim() || null, assumptions_confirmed: true,
      };
      const value = await request<Body>(`${root}/decision-analysis/inventory-reorders`, { ...post(body), signal });
      if (signal.aborted) return;
      setSelected(value); setConfirmed(false); setHistory(previous => [value.run, ...previous.filter(run => run.id !== value.run.id)]);
      setMessage("Saved privately. No order was placed.");
    });
  }
  async function open(id: string) {
    await work("Replaying the original history and checking the plan…", async signal => {
      const value = await request<Body>(`${runsRoot}/${id}`, { signal });
      if (!signal.aborted) { setSelected(value); setMessage("Original history and plan reproduced."); }
    });
  }
  async function review(status: string) {
    if (!selected) return;
    await work("Recording your review…", async signal => {
      const value = await request<Body>(`${runsRoot}/${selected.run.id}/reviews`, { ...post({ target: "decision", status, note, expected_version: selected.review_version }), signal });
      if (!signal.aborted) { setSelected(value); setNote(""); setMessage("Review recorded. No order was placed."); }
    });
  }
  const typed = reorderInputs.filter(key => !columns[key]);
  const saved = history.filter(run => run.method_version === REORDER_METHOD);
  const result = selected?.run.result;
  return <section className="panel decisionPanel" aria-label="Inventory reorder plan">
    <header><p className="eyebrow">PRIVATE PLAN · HUMAN REVIEW</p><h2>How much should I reorder?</h2><p>Uses your dated demand history to add lead-time demand and safety stock to each reorder point. Items with the fewest days of stock come first.</p></header>
    {error && <p role="alert" className="error">{error}</p>}{message && <p role="status">{message}</p>}{pending && <p role="status">{pending}</p>}
    {!options ? <p>Loading source options…</p> : options.state !== "ready" || !source?.dates.length || !itemChoices.length ? <div><p>Confirm a complete date column, an item field and a demand quantity with a fixed unit first.</p><button type="button" onClick={onReview}>Review data meanings</button></div> : <form onSubmit={create} onChange={event => { if (!(event.target instanceof HTMLInputElement) || event.target.name !== "reorder-confirmation") setConfirmed(false); }}>
      <div className="formGrid">
        <label>Plan name<input maxLength={100} value={name} onChange={event => setName(event.target.value)} placeholder="Optional name" /></label>
        <label>History date<select value={date} onChange={event => setDateColumn(event.target.value)}>{source.dates.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Item<select value={item} onChange={event => setItemColumn(event.target.value)}>{itemChoices.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Demand quantity<select value={demand} onChange={event => setDemandColumn(event.target.value)}>{options.metrics.map(value => <option key={value.name} value={value.name}>{value.name} · {value.unit}</option>)}</select></label>
        {reorderInputs.map(key => <label key={key}>{reorderLabels[key]} from<select value={columns[key] || ""} onChange={event => setColumns(previous => ({ ...previous, [key]: event.target.value }))}><option value="">Typed per item below</option>{options.metrics.filter(value => value.name !== demand).map(value => <option key={value.name} value={value.name}>{value.name} · {value.unit}</option>)}</select></label>)}
        {!columns.lead_time_days && <label>Default lead time (days)<input type="number" min={1} max={365} step={1} value={defaultLead} onChange={event => setDefaultLead(event.target.value)} placeholder="Optional" /></label>}
        <label>Service level<select value={level} onChange={event => setLevel(event.target.value)}>{serviceLevels.map(value => <option key={value} value={value}>{Number(value) * 100}%</option>)}</select></label>
        <label>Budget · optional<input inputMode="decimal" maxLength={100} value={budget} onChange={event => setBudget(event.target.value)} placeholder="No budget limit" /></label>
      </div>
      <fieldset><legend>Items and typed values</legend>
        <p>List items to plan (at most 50), or leave empty to plan every item in the history. Column values use each item&apos;s latest dated row.</p>
        {items.map((row, index) => <div className="formGrid" key={index}>
          <label>Item {index + 1}<input required maxLength={200} value={row.item} onChange={event => setItems(items.map((value, at) => at === index ? { ...value, item: event.target.value } : value))} /></label>
          {typed.map(key => <label key={key}>{reorderLabels[key]} {index + 1}<input inputMode="decimal" maxLength={100} value={row[key]} onChange={event => setItems(items.map((value, at) => at === index ? { ...value, [key]: event.target.value } : value))} /></label>)}
          <button type="button" onClick={() => setItems(items.filter((_, at) => at !== index))}>Remove item {index + 1}</button>
        </div>)}
        <button type="button" disabled={items.length >= 50} onClick={() => setItems([...items, blankItem()])}>Add an item</button>
      </fieldset>
      <label className="checkLabel"><input name="reorder-confirmation" type="checkbox" checked={confirmed} required onChange={event => setConfirmed(event.target.checked)} />I confirm the history, stock, reorder points, lead times and costs are my assumptions. The plan is a recommendation, not an order.</label>
      <button disabled={Boolean(pending) || !confirmed}>Plan reorder quantities</button>
    </form>}
    <section aria-label="Saved reorder plans"><h3>Your saved reorder plans</h3>{saved.length ? <ul>{saved.map(run => <li key={run.id}><button type="button" disabled={Boolean(pending)} onClick={() => open(run.id)}>{run.name}</button></li>)}</ul> : <p>No saved reorder plans yet.</p>}</section>
    {selected && result && <section aria-label="Saved reorder result"><h3>{selected.run.name}</h3>
      <ResultExportActions path={`${datasetRoot}/analyses/${selected.run.id}/export?kind=allocation`} charts={[]} />
      <p>{selected.current ? "Current source and meanings." : "Historical source or meanings: review against current data before acting."} History {result.history.start} to {result.history.end} ({result.history.calendar_days} days).</p>
      <p>{result.reason} {result.items_to_order} items to order{result.cost !== null ? ` · total cost ${result.cost}` : ""}{result.budget !== null ? ` · budget ${result.budget}` : ""}{result.unused_budget !== null ? ` · unused ${result.unused_budget}` : ""}.</p>
      <div className="tableWrap" tabIndex={0} role="region" aria-label="Reorder quantities table"><table><thead><tr><th>Priority</th><th>Item</th><th>Stock</th><th>Reorder point</th><th>Days of cover</th><th>Average daily demand</th><th>Safety stock</th><th>Target level</th><th>Needed</th><th>Order</th><th>Cost</th></tr></thead><tbody>{result.allocations.map(row => <tr key={row.candidate}><td>{row.rank}</td><td>{row.candidate}</td><td>{row.stock}</td><td>{row.reorder_point}</td><td>{row.days_of_cover ?? "No demand"}</td><td>{row.mean_daily_demand}</td><td>{row.safety_stock}</td><td>{row.target_level}</td><td>{row.recommended_quantity}</td><td>{row.quantity}</td><td>{row.cost ?? "—"}</td></tr>)}</tbody></table></div>
      <details><summary>Assumptions and checks</summary><ul>{[...result.assumptions, ...result.limitations].map(text => <li key={text}>{text}</li>)}</ul><dl>{Object.entries(result.verification).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{value}</dd></div>)}</dl><p>Receipt: {selected.run.evidence.query_id}.</p></details>
      <button type="button" disabled={Boolean(pending)} onClick={() => open(selected.run.id)}>Replay original evidence</button>
      <form onSubmit={event => { event.preventDefault(); void review("approved"); }} aria-label="Review reorder plan"><label>Review note<textarea required maxLength={1000} value={note} onChange={event => setNote(event.target.value)} /></label>
        <div className="buttonRow"><button disabled={Boolean(pending) || !selected.current || result.status !== "feasible" || !note.trim()}>Approve plan</button><button type="button" disabled={Boolean(pending) || !note.trim()} onClick={() => review("rejected")}>Reject plan</button></div>
        <p>Review: {selected.decision_status}. Approval records your decision; it never places an order.</p></form>
    </section>}
  </section>;
}
