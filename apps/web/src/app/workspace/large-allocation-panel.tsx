/* Use case: Compares larger declared resource allocations without executing actions.
What it does: Collects explicit assumptions, shows exact private outcomes and distinguishes proof from a timed feasible result. */
"use client";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import type { AllocationResult, AnalysisBody, AnalysisOptions, AnalysisSummary } from "./decision-types";
import { AnswerVisualization } from "./answer-visualization";
import { ResultExportActions } from "./result-export-actions";
import styles from "./large-allocation-panel.module.css";

export const LARGE_ALLOCATION_METHOD = "cp-sat-integer-allocation-v1";
type ResourceUse = { column: string; capacity: string; used: string | null; unused: string | null };
type LargeResult = Omit<AllocationResult, "quantum" | "solver_status" | "verification" | "allocations"> & {
  solver_status: "optimal" | "feasible" | "infeasible" | "unknown";
  resources: ResourceUse[];
  allocations: (AllocationResult["allocations"][number] & { resources: { column: string; per_unit: string; used: string }[] })[];
};
type LargeBody = Omit<AnalysisBody, "run"> & { run: Omit<AnalysisBody["run"], "result"> & {
  result: LargeResult; request: { benefit_column: string; cost_column: string; filters: object[] };
} };
type Bound = { candidate: string; minimum: string; maximum: string };
const post = (body: object): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export function LargeAllocationPanel({ root, request, onReview }: { root: string; request: ApiRequest; onReview: () => void }) {
  const datasetRoot = root.split("/uploads/")[0];
  const runsRoot = `${datasetRoot}/decision-analysis`;
  const [options, setOptions] = useState<AnalysisOptions | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [selected, setSelected] = useState<LargeBody | null>(null);
  const [name, setName] = useState("");
  const [entity, setEntity] = useState("");
  const [cost, setCost] = useState("");
  const [benefit, setBenefit] = useState("");
  const [budget, setBudget] = useState("");
  const [maximum, setMaximum] = useState("1");
  const [resources, setResources] = useState<{ id: string; column: string; capacity: string }[]>([]);
  const [bounds, setBounds] = useState<(Bound & { id: string })[]>([]);
  const [rules, setRules] = useState<{ id: string; kind: "requires" | "excludes"; first: string; second: string }[]>([]);
  const [filter, setFilter] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const operation = useRef<AbortController | null>(null);
  const entityName = entity || options?.entities[0] || "";
  const costName = cost || options?.metrics[0]?.name || "";
  const benefitName = benefit || options?.metrics[1]?.name || "";
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([request<AnalysisOptions>(`${root}/decision-analysis/options`, { signal: controller.signal }), request<AnalysisSummary[]>(runsRoot, { signal: controller.signal })])
      .then(([next, saved]) => { if (!controller.signal.aborted) { setOptions(next); setHistory(saved); } })
      .catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load allocation options."); });
    return () => { controller.abort(); operation.current?.abort(); };
  }, [root, request, runsRoot]);
  async function work(label: string, action: (signal: AbortSignal) => Promise<void>) {
    if (operation.current) return;
    const controller = new AbortController(); operation.current = controller;
    setPending(label); setError(""); setMessage("");
    try { await action(controller.signal); }
    catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "This allocation could not complete."); }
    finally { if (!controller.signal.aborted) setPending(""); if (operation.current === controller) operation.current = null; }
  }
  async function reload() {
    await work("Reloading source options and private history…", async signal => {
      const [next, saved] = await Promise.all([request<AnalysisOptions>(`${root}/decision-analysis/options`, { signal }), request<AnalysisSummary[]>(runsRoot, { signal })]);
      if (!signal.aborted) { setOptions(next); setHistory(saved); setConfirmed(false); }
    });
  }
  async function create(event: FormEvent) {
    event.preventDefault(); if (!options || !confirmed) return;
    await work("Checking exact inputs and searching within the declared limits…", async signal => {
      const body = { name: name.trim() || "Larger resource allocation", revision_id: options.revision_id, understanding_id: options.understanding_id,
        entity_column: entityName, cost_column: costName, benefit_column: benefitName, budget, maximum_quantity: Number(maximum),
        resources: resources.map(item => ({ column: item.column, capacity: item.capacity })),
        bounds: bounds.map(item => ({ candidate: item.candidate, minimum: Number(item.minimum), maximum: Number(item.maximum) })),
        prerequisites: rules.filter(item => item.kind === "requires").map(item => ({ candidate: item.first, requires: item.second })),
        exclusions: rules.filter(item => item.kind === "excludes").map(item => ({ first: item.first, second: item.second })),
        filters: filter ? [{ column: filter, operator: "eq", value: filterValue }] : [], assumptions_confirmed: confirmed };
      const value = await request<LargeBody>(`${root}/decision-analysis/large-allocations`, { ...post(body), signal });
      if (signal.aborted) return;
      setSelected(value); setConfirmed(false); setMessage("Saved privately. No source values or external actions changed.");
      try { const saved = await request<AnalysisSummary[]>(runsRoot, { signal }); if (!signal.aborted) setHistory(saved); }
      catch (cause) { if (!signal.aborted) throw new Error(`Your result is saved. History could not reload: ${cause instanceof Error ? cause.message : "Try Reload saved results."}`); }
    });
  }
  async function open(id: string) {
    await work("Verifying original source evidence and retained quantities…", async signal => {
      const value = await request<LargeBody>(`${runsRoot}/${id}`, { signal });
      if (!signal.aborted) { setSelected(value); setMessage("Saved quantities and original source evidence verified. The search was not rerun."); }
    });
  }
  async function review(status: string, note: string) {
    if (!selected) return;
    await work("Recording your private review…", async signal => {
      const value = await request<LargeBody>(`${runsRoot}/${selected.run.id}/reviews`, { ...post({ target: "decision", status, note, expected_version: selected.review_version }), signal });
      if (!signal.aborted) { setSelected(value); setMessage("Review recorded. No external action was executed."); }
    });
  }
  const choices = options?.metrics || [];
  const measureOptions = choices.map(item => <option key={item.name} value={item.name}>{item.name} · {item.unit}</option>);
  const saved = history.filter(item => item.method_version === LARGE_ALLOCATION_METHOD);
  return <section className={`panel ${styles.panel}`} aria-label="Larger allocation">
    <header><p className="eyebrow">DECLARED INPUTS · PRIVATE DECISION</p><h2>Choose actions within several limits</h2><p>Compare up to 50 actions using a budget and three extra resources. Enter fixed per-unit costs and benefits. The result is conditional on those inputs.</p><p>The search has a short time limit. We clearly show whether the best answer was proved or only a usable answer was found.</p></header>
    {error && <p role="alert" className="error">{error}</p>}{pending && <p role="status">{pending}</p>}{message && <p role="status">{message}</p>}
    {!options ? <p>Loading allocation options…</p> : options.state !== "ready" ? <div className={styles.notice}><p>Confirm the source meaning and fixed measurement units first.</p><button onClick={onReview}>Review data meanings</button></div> : !options.large_allocations?.available ? <p>The larger solver is unavailable in this environment. The original budget allocation remains available.</p> : <form className={styles.form} onSubmit={create} onInvalidCapture={event => { const disclosure = (event.target as HTMLElement).closest("details"); if (disclosure) disclosure.open = true; }} onChange={event => { if (!(event.target instanceof HTMLInputElement) || event.target.name !== "allocation-confirmation") setConfirmed(false); }}>
      <fieldset disabled={Boolean(pending)}><legend>1. Identify each action and its benefit</legend><div className={styles.grid}>
        <label>Analysis name<input maxLength={100} value={name} onChange={event => setName(event.target.value)} placeholder="Optional name" /></label>
        <label>Action identifier<select required value={entityName} onChange={event => setEntity(event.target.value)}>{options.entities.map(item => <option key={item}>{item}</option>)}</select></label>
        <label>Per-unit cost<select required value={costName} onChange={event => setCost(event.target.value)}>{measureOptions}</select></label>
        <label>Per-unit benefit<select required value={benefitName} onChange={event => setBenefit(event.target.value)}>{measureOptions}</select></label>
      </div><p>One source row must represent one unique action. Costs must be positive; benefits and extra resource use must be nonnegative.</p></fieldset>
      <fieldset disabled={Boolean(pending)}><legend>2. Set resource and quantity limits</legend><div className={styles.grid}>
        <label>Available budget · {choices.find(item => item.name === costName)?.unit}<input required inputMode="decimal" value={budget} onChange={event => setBudget(event.target.value)} /></label>
        <label>Maximum units per action<input required type="number" min={0} max={100} step={1} value={maximum} onChange={event => setMaximum(event.target.value)} /></label>
      </div><p>Exact decimals are kept. There is no rounding to budget steps. If the exact integer scale is too large, the request is refused.</p>
        {resources.map((item, index) => <div className={styles.row} key={item.id}><label>Resource {index + 1}<select required value={item.column} onChange={event => setResources(items => items.map(row => row.id === item.id ? { ...row, column: event.target.value } : row))}><option value="">Choose a separate measure</option>{measureOptions}</select></label><label>Resource {index + 1} capacity<input required inputMode="decimal" value={item.capacity} onChange={event => setResources(items => items.map(row => row.id === item.id ? { ...row, capacity: event.target.value } : row))} /></label><button type="button" onClick={() => { setResources(items => items.filter(row => row.id !== item.id)); setConfirmed(false); }}>Remove resource {index + 1}</button></div>)}
        <button type="button" disabled={resources.length >= 3} onClick={() => { setResources(items => [...items, { id: crypto.randomUUID(), column: "", capacity: "" }]); setConfirmed(false); }}>Add resource limit</button>
        <details><summary>Different limits for particular actions</summary><p>Type the exact action identifier from your file. Other actions use zero minimum and the maximum above.</p>{bounds.map((item, index) => <div className={styles.row} key={item.id}><label>Action {index + 1} name<input required maxLength={200} value={item.candidate} onChange={event => setBounds(items => items.map(row => row.id === item.id ? { ...row, candidate: event.target.value } : row))} /></label>{(["minimum", "maximum"] as const).map(field => <label key={field}>Action {index + 1} {field}<input required type="number" min={0} max={100} step={1} value={item[field]} onChange={event => setBounds(items => items.map(row => row.id === item.id ? { ...row, [field]: event.target.value } : row))} /></label>)}<button type="button" onClick={() => { setBounds(items => items.filter(row => row.id !== item.id)); setConfirmed(false); }}>Remove action limit {index + 1}</button></div>)}<button type="button" disabled={bounds.length >= 50} onClick={() => { setBounds(items => [...items, { id: crypto.randomUUID(), candidate: "", minimum: "0", maximum }]); setConfirmed(false); }}>Add action limit</button></details>
      </fieldset><fieldset disabled={Boolean(pending)}><legend>3. Add any selection rules</legend><p>“Requires” means at least one unit of the named action is needed. “Cannot go with” prevents both actions from being selected. These are selection rules, not schedules.</p>
        {rules.map((item, index) => <div className={styles.row} key={item.id}><label>Rule {index + 1} action<input required maxLength={200} value={item.first} onChange={event => setRules(items => items.map(row => row.id === item.id ? { ...row, first: event.target.value } : row))} /></label><label>Rule {index + 1} relationship<select value={item.kind} onChange={event => setRules(items => items.map(row => row.id === item.id ? { ...row, kind: event.target.value as "requires" | "excludes" } : row))}><option value="requires">Requires</option><option value="excludes">Cannot go with</option></select></label><label>Rule {index + 1} other action<input required maxLength={200} value={item.second} onChange={event => setRules(items => items.map(row => row.id === item.id ? { ...row, second: event.target.value } : row))} /></label><button type="button" onClick={() => { setRules(items => items.filter(row => row.id !== item.id)); setConfirmed(false); }}>Remove rule {index + 1}</button></div>)}
        <button type="button" disabled={rules.length >= 80} onClick={() => { setRules(items => [...items, { id: crypto.randomUUID(), kind: "requires", first: "", second: "" }]); setConfirmed(false); }}>Add selection rule</button>
        <details><summary>Optional population filter</summary><div className={styles.grid}><label>Include only this group<select value={filter} onChange={event => setFilter(event.target.value)}><option value="">All permitted rows</option>{options.entities.map(item => <option key={item}>{item}</option>)}</select></label><label>Group equals<input required={Boolean(filter)} value={filterValue} onChange={event => setFilterValue(event.target.value)} /></label></div></details>
        <label className="checkLabel"><input name="allocation-confirmation" type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />I confirm each row is one action, resources are per unit and fixed, and benefits add together. This model does not prove real-world effects.</label>
      </fieldset><button disabled={Boolean(pending) || !confirmed || costName === benefitName}>Calculate and save privately</button>
    </form>}
    <section className={styles.history} aria-label="Saved larger allocations"><h3>Your saved larger allocations</h3><button type="button" disabled={Boolean(pending)} onClick={reload}>Reload saved results</button>{saved.length ? <ul>{saved.map(item => <li key={item.id}><button type="button" disabled={Boolean(pending)} onClick={() => open(item.id)}>{item.name}</button></li>)}</ul> : <p>No saved larger allocation yet.</p>}</section>
    {selected && <LargeAllocationResult key={selected.run.id} body={selected} datasetRoot={datasetRoot} pending={Boolean(pending)} onReplay={() => open(selected.run.id)} onReview={review} />}
  </section>;
}

function LargeAllocationResult({ body, datasetRoot, pending, onReplay, onReview }: { body: LargeBody; datasetRoot: string; pending: boolean; onReplay: () => void; onReview: (status: string, note: string) => Promise<void> }) {
  const [note, setNote] = useState("");
  const result = body.run.result;
  const title = { optimal: "Best declared benefit proved", feasible: "Usable selection · best benefit not proved", infeasible: "No selection meets every declared limit", unknown: "Search ended without a usable answer" }[result.solver_status];
  return <section className={styles.result} aria-label="Saved larger allocation"><h3>{body.run.name}</h3><p className={styles.notice}><strong>{title}</strong><br />{result.reason}</p><p>{body.current ? "Current source and meanings." : "Historical source or meanings; approval does not apply to the current source."} Review: {body.decision_status}. {body.approval_effective ? "Approval is effective for this declared model." : "No effective current approval."}</p>
    <ResultExportActions path={`${datasetRoot}/analyses/${body.run.id}/export?kind=allocation`} charts={result.allocations.length ? ["Declared benefit by selected candidate"] : []} /><button type="button" disabled={pending} onClick={onReplay}>Verify saved allocation evidence</button>
    <dl className={styles.cards}><div><dt>Conditional benefit · {body.run.evidence.units[body.run.request.benefit_column]}</dt><dd>{result.benefit ?? "No selection"}</dd></div><div><dt>Cost · {body.run.evidence.units[body.run.request.cost_column]}</dt><dd>{result.cost ?? "No selection"}</dd></div><div><dt>Do-nothing baseline</dt><dd>{result.baseline.feasible ? "Feasible · benefit 0" : "Fails required minimum quantities"}</dd></div></dl>
    <div className="tableWrap" tabIndex={0} role="region" aria-label="Exact resource limits"><table><thead><tr><th>Resource</th><th>Unit</th><th>Available</th><th>Used</th><th>Remaining</th></tr></thead><tbody>{result.resources.map(item => <tr key={item.column}><th>{item.column}</th><td>{body.run.evidence.units[item.column]}</td><td>{item.capacity}</td><td>{item.used ?? "No selection"}</td><td>{item.unused ?? "No selection"}</td></tr>)}</tbody></table></div>
    {result.allocations.length > 0 && <><AnswerVisualization title="Conditional benefit by action" columns={["Action", `Benefit (${body.run.evidence.units[body.run.request.benefit_column]})`, "Quantity", "Cost", "Minimum", "Maximum"]} rows={result.allocations.map(item => [item.candidate, item.benefit, item.quantity, item.cost, item.minimum, item.maximum])} initialChart="bar" /><details><summary>Every exact resource contribution</summary><AnswerVisualization title="Per-action resource use" initialMode="table" chartAllowed={false} columns={["Action", "Quantity", "Resource", "Unit", "Per unit", "Used"]} rows={result.allocations.flatMap(item => item.resources.map(resource => [item.candidate, item.quantity, resource.column, body.run.evidence.units[resource.column], resource.per_unit, resource.used]))} /></details></>}
    <details><summary>Saved assumptions, rules and limits</summary><ul>{[...result.assumptions, ...result.limitations].map(item => <li key={item}>{item}</li>)}</ul><ul>{result.selection_rules?.prerequisites.map((item, index) => <li key={`p-${index}`}>{item.candidate} requires {item.requires}.</li>)}{result.selection_rules?.exclusions.map((item, index) => <li key={`e-${index}`}>{item.first} cannot go with {item.second}.</li>)}</ul><p>Filters: {body.run.request.filters.length ? JSON.stringify(body.run.request.filters) : "All permitted rows; confirmed required filters also apply."}</p><p>Private source receipt: {body.run.evidence.query_id}</p><p>Result checksum: {body.run.evidence.result_checksum}</p></details>
    <form className={styles.form} onSubmit={event => { event.preventDefault(); void onReview("approved", note); }}><label>Reason for your review<textarea required maxLength={1000} value={note} onChange={event => setNote(event.target.value)} /></label><p>Approval records your decision. It does not execute any action or turn assumptions into proven outcomes.</p><div className="buttonRow"><button disabled={pending || !body.current || result.status !== "feasible" || !note.trim()}>Approve recommendation</button><button type="button" disabled={pending || !note.trim()} onClick={() => onReview("rejected", note)}>Reject recommendation</button><button type="button" disabled={pending || !note.trim()} onClick={() => onReview("pending", note)}>Reopen for review</button></div></form>
    <details><summary>Private review history ({body.reviews.length})</summary>{body.reviews.map(item => <p key={item.id}>{item.sequence}. {item.status} · {item.note}</p>)}</details>
  </section>;
}
