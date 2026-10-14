/* Use case: Explores unusual values and explicitly constrained recommendations.
What it does: Shows private replayable evidence, assumptions and human review without executing actions. */
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import type { AllocationResult, AnalysisBody, AnalysisOptions, AnalysisSummary, AnomalyResult } from "./decision-types";
import { ScenarioPanel } from "./scenario-panel";
const post = (body: object): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export function DecisionPanel({ root, request, onReview, initialMethod, initialMetric = "", initialOperation }: {
    root: string;
    request: ApiRequest;
    onReview: () => void;
    initialMethod: "anomalies" | "allocations" | "scenarios";
    initialMetric?: string;
    initialOperation?: "daily_change";
}) {
    const datasetRoot = root.split("/uploads/")[0];
    const runsRoot = `${datasetRoot}/decision-analysis`;
    const [options, setOptions] = useState<AnalysisOptions | null>(null);
    const [history, setHistory] = useState<AnalysisSummary[]>([]);
    const [selected, setSelected] = useState<AnalysisBody | null>(null);
    const [kind, setKind] = useState<string>(initialMethod);
    const [name, setName] = useState("");
    const [metric, setMetric] = useState(initialMetric);
    const [entity, setEntity] = useState("");
    const [cost, setCost] = useState("");
    const [benefit, setBenefit] = useState("");
    const [segment, setSegment] = useState("");
    const [minimumSupport, setMinimumSupport] = useState("8");
    const [resource, setResource] = useState("");
    const [capacity, setCapacity] = useState("");
    const [threshold, setThreshold] = useState("3.5");
    const [materiality, setMateriality] = useState("0");
    const [budget, setBudget] = useState("");
    const [quantum, setQuantum] = useState("");
    const [quantity, setQuantity] = useState("1");
    const [confirmed, setConfirmed] = useState(false);
    const [bounds, setBounds] = useState<{
        candidate: string;
        minimum: string;
        maximum: string;
    }[]>([]);
    const [filter, setFilter] = useState("");
    const [filterValue, setFilterValue] = useState("");
    const [note, setNote] = useState("");
    const [target, setTarget] = useState("");
    const [feedback, setFeedback] = useState("investigate");
    const [pending, setPending] = useState("");
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");
    const operation = useRef<AbortController | null>(null);
    useEffect(() => {
        const controller = new AbortController();
        Promise.all([
            request<AnalysisOptions>(`${root}/decision-analysis/options`, { signal: controller.signal }),
            request<AnalysisSummary[]>(runsRoot, { signal: controller.signal }),
        ]).then(([value, saved]) => {
            if (controller.signal.aborted)
                return;
            setOptions(value);
            setHistory(saved);
        }).catch((cause) => {
            if (!controller.signal.aborted)
                setError(cause instanceof Error ? cause.message : "Could not load analysis options.");
        });
        return () => { controller.abort(); operation.current?.abort(); };
    }, [root, runsRoot, request]);
    async function work(label: string, action: (signal: AbortSignal) => Promise<void>) {
        if (operation.current)
            return;
        const controller = new AbortController();
        operation.current = controller;
        setPending(label);
        setError("");
        setMessage("");
        try {
            await action(controller.signal);
        }
        catch (cause) {
            if (!controller.signal.aborted)
                setError(cause instanceof Error ? cause.message : "Analysis could not complete.");
        }
        finally {
            if (!controller.signal.aborted)
                setPending("");
            if (operation.current === controller)
                operation.current = null;
        }
    }
    const metricName = metric || options?.metrics[0]?.name || "";
    const entityName = entity || options?.entities[0] || "";
    const costName = cost || options?.metrics[0]?.name || "";
    const benefitName = benefit || options?.metrics[1]?.name || "";
    async function create(event: FormEvent) {
        event.preventDefault();
        if (!options)
            return;
        await work("Calculating and preserving source evidence…", async (signal) => {
            const common = { name: name.trim() || (kind === "anomalies" ? "Unusual values" : "Budget allocation"), revision_id: options.revision_id, understanding_id: options.understanding_id, filters: filter ? [{ column: filter, operator: "eq", value: filterValue }] : [] };
            const declaredBounds = bounds.map((item) => ({ candidate: item.candidate, minimum: Number(item.minimum), maximum: Number(item.maximum) }));
            const body = kind === "anomalies" ? { ...common, metric: metricName, threshold, materiality, segment_column: segment || null, minimum_segment_size: Number(minimumSupport) } : {
                ...common, entity_column: entityName, cost_column: costName, benefit_column: benefitName,
                resource_column: resource || null, resource_capacity: resource ? capacity : null,
                budget, quantum, maximum_quantity: Number(quantity), bounds: declaredBounds, assumptions_confirmed: confirmed,
            };
            const value = await request<AnalysisBody>(`${root}/decision-analysis/${kind}`, { ...post(body), signal });
            const saved = await request<AnalysisSummary[]>(runsRoot, { signal });
            if (signal.aborted)
                return;
            setSelected(value);
            setHistory(saved);
            setNote("");
            setTarget("");
            setMessage("Saved privately with original source evidence.");
        });
    }
    async function open(id: string) {
        await work("Replaying original sources and checking the result…", async (signal) => {
            const value = await request<AnalysisBody>(`${runsRoot}/${id}`, { signal });
            if (!signal.aborted) {
                setSelected(value);
                setNote("");
                setTarget("");
                setMessage("Original source query and analysis reproduced.");
            }
        });
    }
    async function review(status: string) {
        if (!selected)
            return;
        await work("Verifying evidence and recording your review…", async (signal) => {
            const value = await request<AnalysisBody>(`${runsRoot}/${selected.run.id}/reviews`, {
                ...post({ target: selected.run.kind === "bounded_allocation" ? "decision" : target, status, note, expected_version: selected.review_version }), signal,
            });
            if (!signal.aborted) {
                setSelected(value);
                setNote("");
                setMessage("Review recorded. No external action was executed.");
            }
        });
    }
    const anomaly = selected?.run.kind === "robust_distribution" ? selected.run.result as AnomalyResult : null;
    const allocation = selected?.run.kind === "bounded_allocation" ? selected.run.result as AllocationResult : null;
    const selector = (label: string, value: string, change: (value: string) => void, items: string[]) => <label>{label}<select value={value} onChange={(e) => change(e.target.value)} required>{items.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>;
    if (kind === "scenarios") return <><label>Analysis method<select value={kind} onChange={e => setKind(e.target.value)}><option value="anomalies">Unusual values · snapshot distribution</option><option value="allocations">Recommendation · budget allocation</option><option value="scenarios">What-if · scenario comparison</option></select></label><ScenarioPanel initialMetric={initialMetric} initialOperation={initialOperation} root={root} request={request} onReview={onReview} /></>;
    return <section className="panel decisionPanel" aria-label="Anomalies and decisions">
    <header><p className="eyebrow">PRIVATE EVIDENCE · HUMAN REVIEW</p><h2>Find unusual values. Compare a declared decision.</h2>
      <p>Statistical findings need your context. Allocation benefits are conditional estimates from your declared inputs, never proven effects.</p></header>
    {error && <p role="alert" className="error">{error}</p>}
    {message && <p role="status">{message}</p>}
    {pending && <p role="status">{pending}</p>}
    {!options ? <p>Loading source options…</p> : options.state !== "ready" ? <div><h3>Review meanings and units before analysis</h3><p>Confirm the selected source and a fixed unit for every numerical measure.</p><button type="button" onClick={onReview}>Review data meanings</button></div> : <form onSubmit={create}>
      <div className="formGrid">
        <label>Analysis method<select value={kind} onChange={(e) => setKind(e.target.value)}><option value="anomalies">Unusual values · snapshot distribution</option><option value="allocations">Recommendation · budget allocation</option><option value="scenarios">What-if · scenario comparison</option></select></label>
        <label>Analysis name<input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} placeholder="Optional name"/></label>
        {kind === "anomalies" ? <>
          {selector("Measure to inspect", metricName, setMetric, options.metrics.map((m) => m.name))}
          <label>Compare within group<select value={segment} onChange={e => setSegment(e.target.value)}><option value="">Whole population</option>{options.entities.map(item => <option key={item}>{item}</option>)}</select></label>
          {segment && <label>Minimum complete records per group<input type="number" min={8} max={1000} step={1} required value={minimumSupport} onChange={e => setMinimumSupport(e.target.value)} /></label>}
          <label>Unusualness threshold · 3 to 10<input inputMode="decimal" required value={threshold} onChange={(e) => setThreshold(e.target.value)}/></label>
          <label>Minimum difference from median<input inputMode="decimal" required value={materiality} onChange={(e) => setMateriality(e.target.value)}/></label>
        </> : <>
          {selector("Candidate identifier", entityName, setEntity, options.entities)}
          {selector("Per-unit cost", costName, value => { setCost(value); if (resource === value) setResource(""); setConfirmed(false); }, options.metrics.map((m) => m.name))}
          {selector("Per-unit benefit", benefitName, value => { setBenefit(value); if (resource === value) setResource(""); setConfirmed(false); }, options.metrics.map((m) => m.name))}
          <label>Additional resource limit<select value={resource} onChange={e => { setResource(e.target.value); setConfirmed(false); }}><option value="">Budget only</option>{options.metrics.filter(m => m.name !== costName && m.name !== benefitName).map(m => <option key={m.name} value={m.name}>{m.name} · {m.unit}</option>)}</select></label>
          {resource && <label>Total additional resource available<input inputMode="decimal" required value={capacity} onChange={e => { setCapacity(e.target.value); setConfirmed(false); }} /></label>}
          <label>Total budget<input inputMode="decimal" required value={budget} onChange={(e) => setBudget(e.target.value)}/></label>
          <label>Budget quantum<input inputMode="decimal" required value={quantum} onChange={(e) => setQuantum(e.target.value)} placeholder="Example: 1 or 0.01"/></label>
          <label>Maximum quantity per candidate<input type="number" required min={0} max={10} step={1} value={quantity} onChange={(e) => setQuantity(e.target.value)}/></label>
        </>}
      </div>
      <details><summary>Limit the population or declare quantity bounds</summary>
        <div className="formGrid"><label>Population filter<select value={filter} onChange={(e) => setFilter(e.target.value)}><option value="">All rows</option>{options.entities.map((item) => <option key={item}>{item}</option>)}</select></label><label>Filter equals<input value={filterValue} onChange={(e) => setFilterValue(e.target.value)} required={Boolean(filter)}/></label></div>
        {kind === "allocations" && <div><h4>Optional candidate quantity limits</h4>
          <p>Each candidate needs one unique source row. Use at most 20 candidates, quantities 0–10 and at most 5,000 budget quantum units.</p>
          {bounds.map((item, index) => <div className="formGrid" key={index}>
            <label>Candidate name {index + 1}<input required maxLength={200} value={item.candidate} onChange={(e) => setBounds(bounds.map((row, i) => i === index ? { ...row, candidate: e.target.value } : row))}/></label>
            <label>Minimum quantity {index + 1}<input type="number" required min={0} max={10} step={1} value={item.minimum} onChange={(e) => setBounds(bounds.map((row, i) => i === index ? { ...row, minimum: e.target.value } : row))}/></label>
            <label>Maximum quantity {index + 1}<input type="number" required min={0} max={10} step={1} value={item.maximum} onChange={(e) => setBounds(bounds.map((row, i) => i === index ? { ...row, maximum: e.target.value } : row))}/></label>
            <button type="button" onClick={() => setBounds(bounds.filter((_, i) => i !== index))}>Remove quantity limit {index + 1}</button>
          </div>)}
          <button type="button" disabled={bounds.length >= 20} onClick={() => setBounds([...bounds, { candidate: "", minimum: "0", maximum: quantity }])}>Add a candidate quantity limit</button>
        </div>}
      </details>
      {kind === "anomalies" ? <p>At least eight complete values per evaluated group; at most 32 groups and 1,000 group/value pairs. Missing or undersized groups are excluded with visible coverage. No seasonal baseline, fraud probability or automatic correction.</p> : <>
        {resource && <p>The additional limit uses {options.metrics.find(m => m.name === resource)?.unit}. At most 100,000 quantity combinations; reduce candidate ranges if the calculation is refused.</p>}
        <p>Cost uses {options.metrics.find((m) => m.name === costName)?.unit}; benefit uses {options.metrics.find((m) => m.name === benefitName)?.unit}. Budget and quantum must use the cost unit. All costs must be exact multiples of the quantum.</p>
        <label className="checkLabel"><input type="checkbox" checked={confirmed} required onChange={(e) => setConfirmed(e.target.checked)}/>I confirm fixed per-unit costs and additive linear benefits in a common benefit unit. Any additional resource has fixed additive per-unit use. These are decision assumptions, not proven causal effects.</label>
      </>}
      <button disabled={Boolean(pending) || (kind === "allocations" && (!confirmed || !entityName || !benefitName || costName === benefitName))}>Calculate and save privately</button>
    </form>}
    <section aria-label="Private analysis history"><h3>Your saved analyses</h3><p>Only you can view these runs and reviews, including in a shared workspace.</p>
      {history.filter(item => item.kind !== "scenario_comparison").length ? <ul>{history.filter(item => item.kind !== "scenario_comparison").map((item) => <li key={item.id}><button type="button" disabled={Boolean(pending)} onClick={() => open(item.id)}>{item.name} · {item.kind === "robust_distribution" ? "Unusual values" : "Allocation"}</button></li>)}</ul> : <p>No saved analyses yet.</p>}
    </section>
    {selected && <section aria-label="Saved analysis result"><h3>{selected.run.name}</h3>
      <p>{selected.current ? "Current source and meanings." : "Historical source or meanings: review against current data before acting."} Method: {selected.run.method_version}.</p>
      <button type="button" disabled={Boolean(pending)} onClick={() => open(selected.run.id)}>Replay original evidence</button>
      {anomaly && <><p>{anomaly.flagged_records} of {anomaly.sample_count} records flagged. Median reference: {anomaly.baseline ?? "Separate baseline for each group"}. Method: {anomaly.method}.</p>
        {anomaly.groups && <><p>{anomaly.covered_records} records evaluated; {anomaly.excluded_records} excluded. Excluded records were not judged normal.</p><div className="tableWrap"><table aria-label="Group coverage"><thead><tr><th>Group</th><th>Status</th><th>Complete records</th><th>Missing measures</th><th>Median</th></tr></thead><tbody>{anomaly.groups.map((g, i) => <tr key={i}><td>{g.segment ?? "Missing group"}</td><td>{g.status.replaceAll("_", " ")}</td><td>{g.sample_count}</td><td>{g.missing_records}</td><td>{g.baseline ?? "Not evaluated"}</td></tr>)}</tbody></table></div></>}
        <p>Threshold: {anomaly.threshold}; minimum difference: {anomaly.materiality}. Findings show repeated values, not individual row identities.</p>
        <div className="tableWrap"><table><thead><tr>{anomaly.groups && <th>Group</th>}<th>Value</th><th>Records</th><th>Difference from median</th><th>Score · not probability</th></tr></thead><tbody>{anomaly.findings.map((f) => <tr key={f.id}>{anomaly.groups && <td>{f.segment}</td>}<td>{f.value}</td><td>{f.count}</td><td>{f.absolute_difference}</td><td>{f.score ?? "Unavailable · degenerate baseline"}</td></tr>)}</tbody></table></div>
        {!anomaly.findings.length && <p>No values flagged by this method. This does not prove the absence of other anomalies.</p>}
      </>}
      {allocation && <><p>Recommendation: {allocation.status}. Review: {selected.decision_status}; {selected.approval_effective ? "approval applies to the current source" : "no effective current approval"}.</p>
        <div className="tableWrap"><table><thead><tr><th>Alternative</th><th>Cost</th><th>Conditional benefit</th><th>Feasible</th></tr></thead><tbody><tr><td>Do nothing</td><td>{allocation.baseline.cost}</td><td>{allocation.baseline.benefit}</td><td>{allocation.baseline.feasible ? "Yes" : "No · mandatory minimums"}</td></tr><tr><td>Optimal declared allocation</td><td>{allocation.cost ?? "Unavailable"}</td><td>{allocation.benefit ?? "Unavailable"}</td><td>{allocation.status === "feasible" ? "Yes" : "No"}</td></tr></tbody></table></div>
        {allocation.resource_capacity !== undefined && <p>Additional resource used: {allocation.resource_used ?? "Unavailable"}; available: {allocation.resource_capacity}; remaining: {allocation.unused_resource ?? "Unavailable"}.</p>}
        {allocation.reason && <p>{allocation.reason}</p>}
        {allocation.unused_budget !== undefined && <p>Unused budget: {allocation.unused_budget}. Budget: {allocation.budget}; quantum: {allocation.quantum}.</p>}
        <div className="tableWrap"><table><thead><tr><th>Candidate</th><th>Quantity</th><th>Bounds</th><th>Cost</th><th>Conditional benefit</th>{allocation.resource_capacity !== undefined && <th>Additional resource</th>}</tr></thead><tbody>{allocation.allocations.map((a) => <tr key={a.candidate}><td>{a.candidate}</td><td>{a.quantity}</td><td>{a.minimum}–{a.maximum}</td><td>{a.cost}</td><td>{a.benefit}</td>{allocation.resource_capacity !== undefined && <td>{a.resource}</td>}</tr>)}</tbody></table></div>
        <ul>{allocation.assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
      </>}
      <ul>{selected.run.result.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      <details><summary>Source evidence and exact units</summary><dl>{Object.entries(selected.run.evidence.units).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}<dt>Query receipt</dt><dd>{selected.run.evidence.query_id}</dd><dt>Result checksum</dt><dd className="checksum">{selected.run.evidence.result_checksum}</dd></dl><p>Reopening reconstructs the original source bytes, confirmed meanings, query and analysis. A checksum alone is not independent proof.</p></details>
      {(allocation || anomaly?.findings.length) ? <form onSubmit={(e) => { e.preventDefault(); void review(allocation ? "approved" : feedback); }} aria-label="Human review">
        <h4>{allocation ? "Review recommendation" : "Review a finding"}</h4>
        {anomaly && <><label>Finding to review<select required value={target} onChange={(e) => setTarget(e.target.value)}><option value="">Select a finding</option>{anomaly.findings.map((f) => <option key={f.id} value={f.id}>{f.segment ? `${f.segment} · ` : ""}{f.value} · {f.count} records</option>)}</select></label>{selector("Finding feedback", feedback, setFeedback, ["investigate", "expected", "data_issue", "dismissed"])}</>}
        <label>Review note<textarea required maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)}/></label>
        {allocation ? <div className="buttonRow"><button type="submit" disabled={Boolean(pending) || !selected.current || allocation.status !== "feasible" || !note.trim()}>Approve recommendation</button><button type="button" disabled={Boolean(pending) || !note.trim()} onClick={() => review("rejected")}>Reject recommendation</button><button type="button" disabled={Boolean(pending) || !note.trim()} onClick={() => review("pending")}>Reopen for review</button></div> : <button disabled={Boolean(pending) || !target || !note.trim()}>Save finding feedback</button>}
        <p>Approval records your decision. It never spends money, changes source data or calls another system.</p>
      </form> : null}
      <h4>Immutable review history</h4>{selected.reviews.length ? <ol>{selected.reviews.map((r) => <li key={r.id}><strong>{r.status}</strong> · {r.target === "decision" ? "Recommendation" : "Finding"}<p>{r.note}</p><time>{r.created_at}</time></li>)}</ol> : <p>Not reviewed yet.</p>}
    </section>}
  </section>;
}
