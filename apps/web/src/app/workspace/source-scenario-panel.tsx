/* Use case: Guides explicit price, quantity and cost what-if comparisons.
What it does: Collects source mappings and assumptions, then displays only server-calculated private results. */

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import type { AnalysisOptions, AnalysisSummary } from "./decision-types";
import { AnswerVisualization } from "./answer-visualization";
import { ResultExportActions } from "./result-export-actions";
import { WorkspaceSelect } from "./workspace-select";
import { amountFields, amountLabels, blankSourceAlternative, driverLabels, scenarioDrivers, simulationDrivers, SOURCE_SCENARIO_METHOD, CONSTRAINED_SCENARIO_METHOD, isSourceScenarioMethod } from "./source-scenario-types";
import type { AmountField, ScenarioDriver, SourceAlternative, SourceScenarioBody, SourceScenarioRequest, ScenarioConstraint, TriangularRange } from "./source-scenario-types";
import styles from "./source-scenario-panel.module.css";

const blankRanges = (): Record<ScenarioDriver, TriangularRange> => ({ price: { low: "", likely: "", high: "" }, quantity: { low: "", likely: "", high: "" }, variable_cost: { low: "", likely: "", high: "" }, fixed_cost: { low: "", likely: "", high: "" } });
const showHistory = (values: AnalysisSummary[]) => values.filter(value => value.kind === "scenario_comparison" && isSourceScenarioMethod(value.method_version));

type Props = { root: string; request: ApiRequest; onReview: () => void };

export function SourceScenarioPanel({ root, request, onReview }: Props) {
  const droot = root.split("/uploads/")[0];
  const runsRoot = `${droot}/decision-analysis`;
  const [options, setOptions] = useState<AnalysisOptions | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [selected, setSelected] = useState<SourceScenarioBody | null>(null);
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [basis, setBasis] = useState<"per_unit" | "row_totals">("per_unit");
  const [quantity, setQuantity] = useState("");
  const [sales, setSales] = useState("");
  const [cost, setCost] = useState("");
  const [fixed, setFixed] = useState("");
  const [filter, setFilter] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [inheritedFilters, setInheritedFilters] = useState<SourceScenarioRequest["filters"] | null>(null);
  const [reload, setReload] = useState(0);
  const [alternatives, setAlternatives] = useState<SourceAlternative[]>([blankSourceAlternative(1)]);
  const [sensitivity, setSensitivity] = useState(false);
  const [driver, setDriver] = useState<ScenarioDriver>("price");
  const [levels, setLevels] = useState("-10, 0, 10");
  const [simulate, setSimulate] = useState(false);
  const [ranges, setRanges] = useState(blankRanges);
  const [seed, setSeed] = useState("20261024");
  const [targetField, setTargetField] = useState<AmountField>("remaining");
  const [targetDirection, setTargetDirection] = useState<"above" | "below">("above");
  const [targetValue, setTargetValue] = useState("");
  const [limits, setLimits] = useState<(Omit<ScenarioConstraint, "unit"> & { id: string })[]>([]);
  const [parent, setParent] = useState<string | null>(null);
  const [rowConfirmed, setRowConfirmed] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const operation = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([request<AnalysisOptions>(`${root}/decision-analysis/options`, { signal: controller.signal }), request<AnalysisSummary[]>(runsRoot, { signal: controller.signal })])
      .then(([value, saved]) => { if (!controller.signal.aborted) { setOptions(value); setHistory(showHistory(saved)); } })
      .catch(cause => { if (!controller.signal.aborted) { setOptions(null); setHistory([]); setSelected(null); setError(cause instanceof Error ? cause.message : "Could not load this source."); } });
    return () => { controller.abort(); operation.current?.abort(); };
  }, [root, runsRoot, request, reload]);
  async function work(action: (signal: AbortSignal) => Promise<void>) {
    if (operation.current) return;
    const controller = new AbortController(); operation.current = controller;
    setBusy(true); setError(""); setMessage("");
    try { await action(controller.signal); }
    catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "The comparison could not complete."); }
    finally { if (!controller.signal.aborted) setBusy(false); if (operation.current === controller) operation.current = null; }
  }
  function changed(mapping = false) { setConfirmed(false); if (mapping) setRowConfirmed(false); }
  function editAlternative(index: number, patch: Partial<SourceAlternative>) {
    setAlternatives(values => values.map((value, position) => position === index ? { ...value, ...patch } : value)); changed();
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (step < 2) { setStep(step + 1); return; }
    if (!options || !confirmed || !rowConfirmed) return;
    await work(async signal => {
      const body = {
        name: name.trim() || "Price, quantity and cost comparison", model: limits.length ? CONSTRAINED_SCENARIO_METHOD : SOURCE_SCENARIO_METHOD, basis,
        constraints: limits.length ? limits.map(({ field, operator, value }) => ({ field, operator, value, unit: limitUnit(field) })) : null,
        quantity_column: quantity, sales_column: sales, cost_column: cost, fixed_cost_column: fixed || null,
        filters: inheritedFilters ?? (filter ? [{ column: filter, operator: "eq", value: filterValue }] : []), alternatives,
        sensitivity: sensitivity ? { driver, percent_changes: levels.split(",").map(value => value.trim()) } : null,
        simulation: simulate ? { drivers: simulationDrivers(ranges), draws: 10000, seed: Number(seed), target: targetValue.trim() ? { field: targetField, direction: targetDirection, value: targetValue.trim() } : null } : null,
        assumptions_confirmed: confirmed, row_basis_confirmed: rowConfirmed, parent_run_id: parent,
        revision_id: options.revision_id, understanding_id: options.understanding_id,
      };
      const saved = await request<SourceScenarioBody>(`${root}/decision-analysis/source-scenarios`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
      if (signal.aborted) return;
      setSelected(saved); setParent(null); setConfirmed(false); setMessage("Comparison saved privately. Your original data is unchanged.");
      const listed = await request<AnalysisSummary[]>(runsRoot, { signal });
      if (!signal.aborted) setHistory(showHistory(listed));
    });
  }
  async function open(id: string) {
    await work(async signal => {
      setSelected(null);
      const saved = await request<SourceScenarioBody>(`${runsRoot}/${id}`, { signal });
      if (!isSourceScenarioMethod(saved.run.result.version)) throw new Error("Open this earlier method under One measure instead.");
      if (!signal.aborted) { setSelected(saved); setMessage("All source rows and saved calculations were replayed."); }
    });
  }
  function successor() {
    if (!selected) return;
    const saved: SourceScenarioRequest = selected.run.request;
    setName(`${selected.run.name} · next`.slice(0, 100)); setBasis(saved.basis);
    setQuantity(saved.quantity_column); setSales(saved.sales_column); setCost(saved.cost_column); setFixed(saved.fixed_cost_column || "");
    setInheritedFilters(saved.filters.map(value => ({ ...value }))); setFilter(""); setFilterValue("");
    setAlternatives(saved.alternatives.map(value => ({ ...value })));
    setLimits((saved.constraints || []).map(({ field, operator, value }) => ({ field, operator, value, id: crypto.randomUUID() })));
    setSensitivity(Boolean(saved.sensitivity)); setDriver(saved.sensitivity?.driver || "price"); setLevels(saved.sensitivity?.percent_changes.join(", ") || "-10, 0, 10");
    const savedSimulation = saved.simulation;
    setSimulate(Boolean(savedSimulation)); setRanges({ ...blankRanges(), ...(savedSimulation?.drivers || {}) }); setSeed(String(savedSimulation?.seed ?? 20261024));
    setTargetValue(savedSimulation?.target?.value || ""); setTargetField(savedSimulation?.target?.field || "remaining"); setTargetDirection(savedSimulation?.target?.direction || "above");
    setParent(selected.run.id); setRowConfirmed(false); setConfirmed(false); setStep(0);
  }
  const columns = options?.source_scenarios?.columns || [];
  const money = columns.filter(value => value.currency);
  const quantities = columns.filter(value => !value.currency && value.unit);
  const limitUnit = (field: AmountField) => field === "margin_percent" ? "%" : field === "quantity" ? columns.find(value => value.name === quantity)?.unit || "" : columns.find(value => value.name === sales)?.currency || "";
  const eligible = options?.state === "ready" && ["record", "order", "order_item", "other"].includes(options.source_scenarios?.grain || "") && money.some(column => money.filter(value => value.currency === column.currency).length >= 2) && quantities.length > 0;
  const populationDescription = inheritedFilters !== null ? (inheritedFilters.length ? inheritedFilters.map(value => `${value.column} ${value.operator} ${String(value.value)}`).join("; ") : "All eligible rows, with the saved measure filters applied.") : filter ? `Rows where ${filter} equals ${filterValue}.` : "All eligible rows, with the saved measure filters applied.";
  const mapOptions = (values: typeof columns) => <><option value="">Choose a column</option>{values.map(value => <option key={value.name} value={value.name}>{value.name} · {value.currency || value.unit}</option>)}</>;
  return <section className={`panel ${styles.panel}`} aria-label="Source-derived scenarios">
    <span className="analysisEyebrow">YOUR CHANGES · EXACT CALCULATIONS</span>
    <h2>What if price, quantity or costs change?</h2>
    <p>Choose the matching columns, then enter your assumptions. We show sales, included costs and the amount left. We do not guess how customers will respond.</p>
    {error && <><p className="error" role="alert">{error}</p><button type="button" disabled={busy} onClick={() => { setError(""); setConfirmed(false); setRowConfirmed(false); setStep(0); setReload(value => value + 1); }}>Reload source options</button></>}{message && <p role="status">{message}</p>}{busy && <p role="status">Checking the source and calculating your comparison…</p>}
    {!options ? <p>{error ? "Source options could not be loaded." : "Loading source options…"}</p> : !eligible ? <div className={styles.note}><h3>Review the inputs first</h3><p>This model needs a quantity with a fixed unit and two separate money columns with the same confirmed currency. Confirm that each row is a transaction or a non-overlapping period; stock snapshots are not eligible.</p><button type="button" onClick={onReview}>Review data meanings</button></div> : <>
      <ol className={styles.steps} aria-label="Scenario steps">{["1. Choose inputs", "2. Set changes", "3. Review and run"].map((label, index) => <li key={label} aria-current={step === index ? "step" : undefined}>{label}</li>)}</ol>
      <form onSubmit={submit} className={styles.form}>
        {step === 0 && <fieldset disabled={busy}><legend>1. What does each column mean?</legend>
          <p>Use transactions or non-overlapping periods. Do not add repeated stock snapshots or repeat the same fixed cost on several rows.</p>
          <div className={styles.grid}>
            <label>Comparison name<input value={name} maxLength={100} onChange={event => setName(event.target.value)} placeholder="Optional name" /></label>
            <label>How sales and costs are stored<select value={basis} onChange={event => { setBasis(event.target.value as typeof basis); changed(true); }}><option value="per_unit">Price and variable cost per unit</option><option value="row_totals">Sales and variable cost totals per row</option></select></label>
            <label>Quantity column<select required value={quantity} onChange={event => { setQuantity(event.target.value); changed(true); }}>{mapOptions(quantities)}</select></label>
            <label>{basis === "per_unit" ? "Price per unit column" : "Sales total column"}<select required value={sales} onChange={event => { setSales(event.target.value); changed(true); }}>{mapOptions(money)}</select></label>
            <label>{basis === "per_unit" ? "Variable cost per unit column" : "Variable cost total column"}<select required value={cost} onChange={event => { setCost(event.target.value); changed(true); }}>{mapOptions(money)}</select></label>
            <label>Fixed cost allocated per row<select value={fixed} onChange={event => { setFixed(event.target.value); if (!event.target.value) { setAlternatives(values => values.map(value => ({ ...value, fixed_cost: "0" }))); if (driver === "fixed_cost") setDriver("price"); } changed(true); }}><option value="">No fixed costs included</option>{money.map(value => <option key={value.name} value={value.name}>{value.name} · {value.currency}</option>)}</select></label>
          </div>
          <details><summary>Choose a row group (optional)</summary>{inheritedFilters !== null ? <><p>Saved population: {populationDescription}</p><button type="button" onClick={() => { setInheritedFilters(null); setParent(null); changed(true); }}>Choose a different row group for a new comparison</button></> : <div className={styles.grid}><label>Population field<select value={filter} onChange={event => { setFilter(event.target.value); changed(true); }}><option value="">All eligible rows</option>{options.entities.map(value => <option key={value}>{value}</option>)}</select></label><label>Population value<input value={filterValue} required={Boolean(filter)} onChange={event => { setFilterValue(event.target.value); changed(true); }} /></label></div>}</details>
          <label className={styles.check}><input type="checkbox" required checked={rowConfirmed} onChange={event => { setRowConfirmed(event.target.checked); setConfirmed(false); }} />Each row contributes once. Sales and variable costs match this quantity unit; included fixed costs are allocated once. The chosen periods do not overlap.</label>
        </fieldset>}
        {step === 1 && <fieldset disabled={busy}><legend>2. Enter the changes you want to compare</legend>
          <p>Use percentages from −100 to 10,000. Zero keeps that input unchanged. Quantity changes independently of price; it is your assumption.</p>
          <p>You can name alternatives Conservative or Optimistic. Their changes are your assumptions, not probabilities.</p>
          <div className={styles.alternatives}>{alternatives.map((alternative, index) => <fieldset key={index}><legend>Alternative {index + 1}</legend><label>Alternative name {index + 1}<input value={alternative.name} required maxLength={100} onChange={event => editAlternative(index, { name: event.target.value })} /></label><div className={styles.grid}>{scenarioDrivers.map(key => <label key={key}>{driverLabels[key]} change {index + 1} (%)<input required inputMode="decimal" maxLength={100} value={alternative[key]} disabled={key === "fixed_cost" && !fixed} onChange={event => editAlternative(index, { [key]: event.target.value })} /></label>)}</div>{alternatives.length > 1 && <button type="button" onClick={() => { setAlternatives(values => values.filter((_, position) => position !== index)); changed(); }}>Remove alternative {index + 1}</button>}</fieldset>)}</div>
          <div className={styles.actions}><button type="button" disabled={alternatives.length >= 5} onClick={() => { setAlternatives(values => [...values, blankSourceAlternative(values.length + 1)]); changed(); }}>Add alternative</button></div>
          <details><summary>Explore one change across several values</summary><label className={styles.check}><input type="checkbox" checked={sensitivity} onChange={event => { setSensitivity(event.target.checked); changed(); }} />Include a sensitivity comparison</label>{sensitivity && <div className={styles.grid}><label>Sensitivity driver<select value={driver} onChange={event => { setDriver(event.target.value as ScenarioDriver); changed(); }}>{scenarioDrivers.filter(value => value !== "fixed_cost" || fixed).map(value => <option key={value} value={value}>{driverLabels[value]}</option>)}</select></label><label>Percentages, separated by commas<input required value={levels} maxLength={2100} onChange={event => { setLevels(event.target.value); changed(); }} /><small>Two to 21 increasing values. Every other change stays at zero.</small></label></div>}</details>
          <details><summary>Simulate uncertain changes (low / likely / high)</summary>
            <label className={styles.check}><input type="checkbox" checked={simulate} onChange={event => { setSimulate(event.target.checked); changed(); }} />Include a simulation of 10,000 seeded draws</label>
            {simulate && <>
              <p>For each change you are unsure about, give a lowest, most likely and highest percentage. Leave a row blank to keep it at zero. Each draw runs the same exact calculation; the result is a simulation under your ranges, not a forecast.</p>
              <div className="tableWrap"><table aria-label="Simulation ranges"><thead><tr><th>Change</th><th>Low (%)</th><th>Likely (%)</th><th>High (%)</th></tr></thead><tbody>{scenarioDrivers.filter(key => key !== "fixed_cost" || fixed).map(key => <tr key={key}><th scope="row">{driverLabels[key]}</th>{(["low", "likely", "high"] as const).map(bound => <td key={bound}><input aria-label={`${driverLabels[key]} ${bound} (%)`} inputMode="decimal" maxLength={100} value={ranges[key][bound]} onChange={event => { const value = event.target.value; setRanges(items => ({ ...items, [key]: { ...items[key], [bound]: value } })); changed(); }} /></td>)}</tr>)}</tbody></table></div>
              <div className={styles.grid}>
                <label>Simulation seed<input required inputMode="numeric" pattern="[0-9]+" maxLength={10} value={seed} onChange={event => { setSeed(event.target.value); changed(); }} /><small>The same seed always gives the same draws.</small></label>
                <WorkspaceSelect label="Target outcome" value={targetField} disabled={busy} options={amountFields.map(field => ({ value: field, label: amountLabels[field] }))} onValueChange={field => { setTargetField(field as AmountField); changed(); }} />
                <WorkspaceSelect label="Target direction" value={targetDirection} disabled={busy} options={[{ value: "above", label: "Above" }, { value: "below", label: "Below" }]} onValueChange={value => { setTargetDirection(value as "above" | "below"); changed(); }} />
                <label>Target value · {limitUnit(targetField)} · optional<input inputMode="decimal" maxLength={100} value={targetValue} onChange={event => { setTargetValue(event.target.value); changed(); }} /></label>
              </div>
            </>}
          </details>
          <section aria-label="Declared scenario limits"><h4>Keep outcomes within your limits</h4><p>Optional: check a minimum or maximum for sales, quantity, costs or margin. A passing check only means your stated limit was met.</p>
            {limits.map((limit, index) => <fieldset key={limit.id}><legend>Limit {index + 1}</legend><div className={styles.grid}>
              <WorkspaceSelect label={`Limit ${index + 1} amount`} value={limit.field} disabled={busy} options={amountFields.map(field => ({ value: field, label: amountLabels[field] }))} onValueChange={field => { setLimits(items => items.map(item => item.id === limit.id ? { ...item, field: field as AmountField } : item)); changed(); }} />
              <WorkspaceSelect label={`Limit ${index + 1} boundary`} value={limit.operator} disabled={busy} options={[{ value: "minimum", label: "At least" }, { value: "maximum", label: "At most" }]} onValueChange={operator => { setLimits(items => items.map(item => item.id === limit.id ? { ...item, operator: operator as "minimum" | "maximum" } : item)); changed(); }} />
              <label>Limit {index + 1} value · {limitUnit(limit.field)}<input required inputMode="decimal" maxLength={100} value={limit.value} onChange={event => { setLimits(items => items.map(item => item.id === limit.id ? { ...item, value: event.target.value } : item)); changed(); }} /></label>
              <button type="button" onClick={() => { setLimits(items => items.filter(item => item.id !== limit.id)); changed(); }}>Remove limit {index + 1}</button>
            </div></fieldset>)}
            <button type="button" disabled={limits.length >= 12} onClick={() => { setLimits(items => [...items, { id: crypto.randomUUID(), field: "remaining", operator: "minimum", value: "" }]); changed(); }}>Add outcome limit</button>
          </section>
        </fieldset>}
        {step === 2 && <fieldset disabled={busy}><legend>3. Review your assumptions</legend>
          <div className={styles.note}><p><strong>{basis === "per_unit" ? "Per-unit inputs" : "Recorded row totals"}</strong></p><p>Quantity: {quantity}. Sales: {sales}. Variable cost: {cost}. Fixed cost: {fixed || "not included"}.</p><p>{populationDescription}</p><p>Sales scale with price × quantity. Variable costs scale with cost per unit × quantity. Fixed costs use only their own change.</p></div>
          <div className="tableWrap" tabIndex={0} role="region" aria-label="Declared scenario changes table"><table><thead><tr><th>Alternative</th>{scenarioDrivers.map(value => <th key={value}>{driverLabels[value]} (%)</th>)}</tr></thead><tbody>{alternatives.map((value, index) => <tr key={index}><td>{value.name}</td>{scenarioDrivers.map(key => <td key={key}>{value[key]}</td>)}</tr>)}</tbody></table></div>
          {sensitivity && <p>Sensitivity: {driverLabels[driver]} at {levels}%, with every other change at zero.</p>}
          {simulate && <p>Simulation: {Object.entries(simulationDrivers(ranges)).map(([key, value]) => `${driverLabels[key as ScenarioDriver]} ${value.low}/${value.likely}/${value.high}%`).join("; ") || "no complete ranges yet"} · seed {seed}{targetValue.trim() ? ` · target ${amountLabels[targetField].toLowerCase()} ${targetDirection} ${targetValue} ${limitUnit(targetField)}` : ""}.</p>}
          {limits.length > 0 && <ul aria-label="Review declared limits">{limits.map(limit => <li key={limit.id}>{amountLabels[limit.field]}: {limit.operator === "minimum" ? "at least" : "at most"} {limit.value} {limitUnit(limit.field)}.</li>)}</ul>}
          {parent && <p>This creates a successor and keeps the earlier comparison. <button type="button" onClick={() => setParent(null)}>Make an independent comparison</button></p>}
          <label className={styles.check}><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />I confirm these changes and the fixed row mix are my assumptions. The result is not a forecast, a causal effect or audited net profit.</label>
        </fieldset>}
        <div className={styles.actions}>{step > 0 && <button type="button" disabled={busy} onClick={() => setStep(step - 1)}>Back</button>}<button type="submit" disabled={busy || (step === 2 && (!confirmed || !rowConfirmed))}>{step === 2 ? "Calculate and save source comparison" : "Continue"}</button></div>
      </form>
    </>}
    <section aria-label="Private source scenario history"><h3>Your saved source comparisons</h3>{history.length ? <ul>{history.map(value => <li key={value.id}><button type="button" disabled={busy} onClick={() => void open(value.id)}>{value.name}</button></li>)}</ul> : <p>No source comparisons saved yet.</p>}</section>
    {selected && <SourceScenarioResult value={selected} droot={droot} busy={busy} onReplay={() => void open(selected.run.id)} onSuccessor={successor} />}
  </section>;
}

function SourceScenarioResult({ value, droot, busy, onReplay, onSuccessor }: { value: SourceScenarioBody; droot: string; busy: boolean; onReplay: () => void; onSuccessor: () => void }) {
  const result = value.run.result;
  const currency = value.run.evidence.units[value.run.request.sales_column];
  const quantityUnit = value.run.evidence.units[value.run.request.quantity_column];
  const columns = [{ name: "Source baseline", values: result.baseline }, ...result.alternatives.map(alternative => ({ name: alternative.name, values: alternative.result }))];
  const unit = (field: AmountField) => field === "quantity" ? quantityUnit : field === "margin_percent" ? "%" : currency;
  return <section className={styles.result} aria-label="Saved source scenario result">
    <span className="analysisEyebrow">PRIVATE · HYPOTHETICAL OUTCOMES</span><h3>{value.run.name}</h3>
    <p>{value.current ? "Current source and meanings." : "Historical source or meanings. A successor uses the current source."} {result.sample_count} complete matched rows.</p>
    <p className={styles.note}>These amounts include only your selected costs. No customer response or future demand was predicted.</p>
    <div className={styles.actions}><button type="button" disabled={busy} onClick={onReplay}>Replay source comparison</button><button type="button" disabled={busy} onClick={onSuccessor}>Create source successor</button></div>
    <ResultExportActions path={`${droot}/analyses/${value.run.id}/export?kind=scenario`} charts={["Remaining amount under declared assumptions", ...(result.sensitivity ? ["Single-driver sensitivity"] : [])]} />
    <h4>Starting amounts from your source</h4><dl className={styles.cards}>{(["revenue", "total_cost", "remaining"] as const).map(field => <div key={field}><dt>{amountLabels[field]}</dt><dd>{result.baseline[field]}</dd><small>{currency}</small></div>)}</dl>
    <AnswerVisualization title="Remaining amount under declared assumptions" columns={["Alternative", `Remaining (${currency})`]} rows={columns.map(column => [column.name, column.values.remaining])} recordsAnalyzed={result.sample_count} chartLimit={6} />
    <h4>Every calculated amount</h4><p>Exact returned values; a negative amount is kept. {result.constraints ? "Margin needs positive sales. Limit checks use the exact ratio, before display rounding." : "Margin is unavailable when sales are zero."}</p>
    <div className="tableWrap" tabIndex={0} role="region" aria-label="Every calculated amount table"><table><thead><tr><th>Measure</th><th>Unit</th>{columns.map((column, index) => <th key={index}>{column.name}</th>)}</tr></thead><tbody>{amountFields.map(field => <tr key={field}><th scope="row">{amountLabels[field]}</th><td>{unit(field)}</td>{columns.map((column, index) => <td key={index}>{column.values[field] ?? (result.constraints ? "Unavailable · sales are not positive" : "Unavailable · zero sales")}</td>)}</tr>)}</tbody></table></div>
    {result.constraints && <section aria-label="Scenario limit checks"><h4>Which outcomes meet your limits?</h4><p>Passed means the declared boundary was met. It does not prove that the plan is practical. Unavailable margins need positive sales.</p>
      <AnswerVisualization title="Exact scenario limit checks" chartAllowed={false} initialMode="table" columns={["Outcome", "Amount", "Boundary", "Threshold", "Unit", "Actual display", "Exact ratio", "Check"]} rows={[
        { name: "Source baseline", checks: result.baseline_constraints || [] },
        ...result.alternatives.map(item => ({ name: item.name, checks: item.constraints || [] })),
        ...(result.sensitivity?.points.map(point => ({ name: `Sensitivity ${point.percent_change}%`, checks: point.constraints || [] })) || []),
      ].flatMap(item => item.checks.map(check => [item.name, amountLabels[check.field], check.operator, check.value, check.unit, check.actual, check.exact_actual ? `${check.exact_actual.numerator}/${check.exact_actual.denominator}` : "Unavailable", check.status]))} />
    </section>}
    <h4>Change in the remaining amount</h4><ul>{result.alternatives.map(alternative => <li key={alternative.name}>{alternative.name}: {alternative.difference.remaining} {currency} versus the source baseline.</li>)}</ul>
    {result.sensitivity && <section aria-label="Single-driver sensitivity"><h4>What changes when only {driverLabels[result.sensitivity.driver].toLowerCase()} changes?</h4><p>Each point starts from the original source. Every other change is zero. This range is not a probability or a confidence interval.</p><AnswerVisualization title="Single-driver sensitivity" columns={[`${driverLabels[result.sensitivity.driver]} change (%)`, `Remaining (${currency})`]} rows={result.sensitivity.points.map(point => [point.percent_change, point.result.remaining])} recordsAnalyzed={result.sample_count} chartLimit={21} /><details className={styles.evidence}><summary>All exact sensitivity values</summary><div className="tableWrap" tabIndex={0} role="region" aria-label="Exact sensitivity values table"><table><thead><tr><th>Change (%)</th>{amountFields.map(field => <th key={field}>{amountLabels[field]} ({unit(field)})</th>)}</tr></thead><tbody>{result.sensitivity.points.map(point => <tr key={point.percent_change}><td>{point.percent_change}</td>{amountFields.map(field => <td key={field}>{point.result[field] ?? "Unavailable"}</td>)}</tr>)}</tbody></table></div></details></section>}
    {result.simulation && <section aria-label="Simulation under stated ranges"><h4>Simulation under your stated ranges</h4><p className={styles.note}>{result.simulation.label} {result.simulation.draws.toLocaleString()} draws · seed {result.simulation.seed}. P10 means one draw in ten was lower.</p>
      {result.simulation.target_probability && <p><strong>{result.simulation.target_probability.share}</strong> of draws had {amountLabels[result.simulation.target_probability.field].toLowerCase()} {result.simulation.target_probability.direction} {result.simulation.target_probability.value} {unit(result.simulation.target_probability.field)} ({result.simulation.target_probability.draws_beating} draws; simulation error ± {result.simulation.target_probability.monte_carlo_standard_error}).</p>}
      <div className="tableWrap" tabIndex={0} role="region" aria-label="Simulation percentiles table"><table><thead><tr><th>Measure</th><th>Unit</th><th>P10</th><th>P50</th><th>P90</th></tr></thead><tbody>{amountFields.map(field => { const row = result.simulation?.percentiles[field]; return <tr key={field}><th scope="row">{amountLabels[field]}</th><td>{unit(field)}</td><td>{row?.p10 ?? "Unavailable"}</td><td>{row?.p50 ?? "Unavailable"}</td><td>{row?.p90 ?? "Unavailable"}</td></tr>; })}</tbody></table></div>
      <details className={styles.evidence}><summary>Simulation assumptions</summary><ul>{Object.entries(result.simulation.drivers).map(([key, value]) => <li key={key}>{driverLabels[key as ScenarioDriver]}: low {value.low}%, likely {value.likely}%, high {value.high}%</li>)}{[...result.simulation.assumptions, ...result.simulation.limitations].map(item => <li key={item}>{item}</li>)}</ul></details>
    </section>}
    {result.warnings.map(warning => <p className={styles.note} key={warning}>{warning}</p>)}
    <details className={styles.evidence}><summary>Assumptions, limits and source evidence</summary><h4>Your declared changes</h4><ul>{result.alternatives.map(alternative => <li key={alternative.name}>{alternative.name}: {scenarioDrivers.map(driver => `${driverLabels[driver]} ${alternative.assumptions[driver]}%`).join("; ")}</li>)}</ul><ul>{[...result.assumptions, ...result.limitations].map(item => <li key={item}>{item}</li>)}</ul><p>Method: {result.version}. One complete ordered source projection is independently replayed.</p><p>Query receipt: {value.run.evidence.query_id}</p><p>Result checksum: {value.run.evidence.result_checksum}</p>{result.parent_run_id && <p>Prior comparison: {result.parent_run_id}</p>}</details>
  </section>;
}
