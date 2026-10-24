/* Use case: Builds explicit, source-backed investigations of a recorded change.
What it does: Collects two populations without guessing their meaning, then shows
server-calculated contributions, coverage, exact fractions and supporting records. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import { WorkspaceSelect } from "./workspace-select";
import { RecordTable, type Cell } from "./explore-components";
import { addsBack, monthWindows, type MonthComparison } from "./change-helpers";
import styles from "./contribution.module.css";

export type ContributionViews = {
  state: string;
  revision_id: string;
  understanding_id: string;
  columns?: { name: string; role: string }[];
  date_columns?: string[];
};
type Named = { id: string; name: string };
type Upload = { id: string; filename: string; created_at: string };
type Fields = { column: string; segment: string; quantity_column: string; dimensions: string[] };
const blankFields = (): Fields => ({ column: "", segment: "", quantity_column: "", dimensions: [] });
const options = (values: string[]) => values.map(value => ({ value, label: value }));

function FieldChoices({ title, views, fields, setFields, decompose, disabled }: {
  title: string; views: ContributionViews; fields: Fields; setFields: (fields: Fields) => void;
  decompose: boolean; disabled: boolean;
}) {
  const metrics = views.columns?.filter(c => c.role === "metric").map(c => c.name) ?? [];
  const categories = views.columns?.filter(c => ["dimension", "ordinal"].includes(c.role)).map(c => c.name) ?? [];
  return <fieldset className={styles.fields} disabled={disabled}>
    <legend>{title}</legend>
    <WorkspaceSelect label={`${title} amount`} value={fields.column} onValueChange={column => setFields({ ...fields, column })} options={options(metrics)} disabled={disabled} />
    <WorkspaceSelect label={`${title} category`} value={fields.segment} onValueChange={segment => setFields({ ...fields, segment, dimensions: fields.dimensions.filter(name => name !== segment) })} options={options(categories)} disabled={disabled} />
    {decompose && <WorkspaceSelect label={`${title} quantity`} value={fields.quantity_column} onValueChange={quantity_column => setFields({ ...fields, quantity_column })} options={options(metrics.filter(c => c !== fields.column))} disabled={disabled} />}
    {fields.segment && [0, 1, 2].filter(i => i <= fields.dimensions.length).map(i => <WorkspaceSelect key={i} label={`${title} also rank by ${i + 1}`} value={fields.dimensions[i] ?? "none"}
      onValueChange={value => setFields({ ...fields, dimensions: value === "none" ? fields.dimensions.slice(0, i) : [...fields.dimensions.slice(0, i), value] })}
      options={[{ value: "none", label: "Not used" }, ...options(categories.filter(c => c !== fields.segment && !fields.dimensions.slice(0, i).includes(c)))]} disabled={disabled} />)}
  </fieldset>;
}

export function ContributionForm({ root, request, views, busy, blocked, onCreate }: {
  root: string; request: ApiRequest; views: ContributionViews; busy: boolean; blocked: boolean;
  onCreate: (method: { kind: string; [key: string]: unknown }, question: string) => Promise<void>;
}) {
  const workspacePath = root.split("/datasets/")[0];
  const locked = busy || blocked;
  const [mode, setMode] = useState("period");
  const [datasets, setDatasets] = useState<Named[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [uploadId, setUploadId] = useState("");
  const [otherViews, setOtherViews] = useState<ContributionViews | null>(null);
  const [left, setLeft] = useState<Fields>(blankFields);
  const [right, setRight] = useState<Fields>(blankFields);
  const [dateColumn, setDateColumn] = useState("");
  const [dates, setDates] = useState(["", "", "", ""]);
  const [month, setMonth] = useState("");
  const [against, setAgainst] = useState<MonthComparison>("previous");
  const pickMonth = (value: string, base: MonthComparison) => { setMonth(value); setAgainst(base); const windows = monthWindows(value, base); if (windows) setDates(windows); };
  const [decompose, setDecompose] = useState(false);
  const [additive, setAdditive] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (mode !== "dataset") return;
    let active = true;
    request<Named[]>(`${workspacePath}/datasets`).then(value => { if (active) setDatasets(value); })
      .catch((cause: Error) => { if (active) setError(cause.message); });
    return () => { active = false; };
  }, [mode, workspacePath, request]);
  useEffect(() => {
    if (!datasetId) return;
    let active = true;
    request<Upload[]>(`${workspacePath}/datasets/${datasetId}/uploads`).then(value => { if (active) setUploads(value); })
      .catch((cause: Error) => { if (active) setError(cause.message); });
    return () => { active = false; };
  }, [datasetId, workspacePath, request]);
  useEffect(() => {
    if (!datasetId || !uploadId) return;
    let active = true;
    request<ContributionViews>(`${workspacePath}/datasets/${datasetId}/uploads/${uploadId}/adaptive-views`)
      .then(value => { if (active) setOtherViews(value); })
      .catch((cause: Error) => { if (active) setError(cause.message); });
    return () => { active = false; };
  }, [datasetId, uploadId, workspacePath, request]);
  const validFields = (fields: Fields) => fields.column && fields.segment && (!decompose || (fields.quantity_column && fields.quantity_column !== fields.column));
  const ready = additive && validFields(left) && (mode === "period"
    ? dateColumn && dates.every(Boolean) && dates[0] <= dates[1] && dates[1] < dates[2] && dates[2] <= dates[3]
    : otherViews?.state === "ready" && validFields(right) && right.dimensions.length === left.dimensions.length);
  const selectedFields = (fields: Fields) => ({ column: fields.column, segment: fields.segment,
    ...(decompose ? { quantity_column: fields.quantity_column } : {}),
    ...(fields.dimensions.length ? { dimensions: fields.dimensions } : {}) });
  return <details className={styles.builder}>
    <summary>Explain a change</summary>
    <p>Compare recorded totals and see which categories contributed. Start with two date ranges or choose another confirmed file.</p>
    <form onSubmit={event => {
      event.preventDefault();
      if (!ready || locked) return;
      const selected = mode === "period" ? views : otherViews!;
      const period = mode === "period";
      const method = {
        kind: "contribution", mode, additive_rows_confirmed: true, decompose,
        baseline: { ...selectedFields(left), ...(period ? { date_column: dateColumn, start: dates[0], end: dates[1] } : {}) },
        comparison: { ...selectedFields(period ? left : right), dataset_id: period ? root.split("/")[4] : datasetId,
          upload_id: period ? root.split("/")[6] : uploadId, revision_id: selected.revision_id,
          understanding_id: selected.understanding_id, ...(period ? { date_column: dateColumn, start: dates[2], end: dates[3] } : {}) },
      };
      void onCreate(method, `What contributed to the change in ${left.column} by ${left.segment}?`);
    }}>
      <WorkspaceSelect label="Compare populations" value={mode} onValueChange={value => { setMode(value); setError(""); }} options={[
        { value: "period", label: "Two date ranges", description: "Same file, separate inclusive date windows" },
        { value: "dataset", label: "Two file snapshots", description: "Map explicitly selected fields with matching units" },
      ]} disabled={locked} />
      <label className={styles.check}><input type="checkbox" checked={decompose} disabled={locked} onChange={e => setDecompose(e.target.checked)} /> Also separate volume, product mix and revenue per unit</label>
      {decompose && <p>Needs currency revenue, positive quantities and the same quantity unit on both sides. Revenue per unit is observed; it is not a proven price effect.</p>}
      <div className={styles.grid}>
        <FieldChoices title="Baseline" views={views} fields={left} setFields={setLeft} decompose={decompose} disabled={locked} />
        {mode === "period" ? <fieldset className={styles.fields} disabled={locked}>
          <legend>Date windows</legend>
          <WorkspaceSelect label="Comparison date field" value={dateColumn} onValueChange={setDateColumn} options={options(views.date_columns ?? [])} disabled={locked} />
          {!views.date_columns?.length && <p>This file has no date field. Choose two file snapshots instead.</p>}
          <div className={styles.dates}>
            <label>Quick month<input type="month" value={month} onChange={e => pickMonth(e.target.value, against)} /></label>
            <WorkspaceSelect label="Compare that month with" value={against} onValueChange={value => pickMonth(month, value as MonthComparison)} options={[
              { value: "previous", label: "The month before" }, { value: "year", label: "Same month last year" }]} disabled={locked} />
          </div>
          <div className={styles.dates}>{["Baseline start", "Baseline end", "Comparison start", "Comparison end"].map((label, i) => <label key={label}>{label}<input type="date" value={dates[i]} onChange={e => setDates(dates.map((v, j) => j === i ? e.target.value : v))} required /></label>)}</div>
          <p>The comparison must start after the baseline ends. Dates include both endpoints; absent periods are not filled.</p>
        </fieldset> : <div className={styles.fields}>
          <WorkspaceSelect label="Comparison dataset" value={datasetId} onValueChange={value => { setDatasetId(value); setUploads([]); setUploadId(""); setOtherViews(null); setRight(blankFields()); setError(""); }} options={datasets.map(value => ({ value: value.id, label: value.name }))} disabled={locked} />
          <WorkspaceSelect label="Comparison snapshot" value={uploadId} onValueChange={value => { setUploadId(value); setOtherViews(null); setRight(blankFields()); setError(""); }} options={uploads.map(value => ({ value: value.id, label: `${value.filename} · ${new Date(value.created_at).toLocaleString()}` }))} disabled={locked || !datasetId} />
          {otherViews?.state === "ready" && <FieldChoices title="Comparison" views={otherViews} fields={right} setFields={setRight} decompose={decompose} disabled={locked} />}
          {otherViews && otherViews.state !== "ready" && <p>Confirm the meaning of this snapshot in Prepare before comparing it.</p>}
        </div>}
      </div>
      <label className={styles.check}><input type="checkbox" checked={additive} disabled={locked} onChange={e => setAdditive(e.target.checked)} /> These amounts can be added across rows, and each side represents its intended population without duplicate totals.</label>
      {mode === "dataset" && right.dimensions.length !== left.dimensions.length && <p>Choose the same number of “also rank by” fields on both sides.</p>}
      <p>Optional “also rank by” fields (up to three) show which field concentrates the change and drill into its top member. That is accounting attribution, not a cause.</p>
      <p>Confirmed required filters and current permissions apply. Up to 10,000 matching records per side and 128 categories; larger populations need an explicitly filtered comparison.</p>
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={locked || !ready}>{busy ? "Calculating…" : "Calculate & save comparison"}</button>
    </form>
  </details>;
}

type Exact = { display: string; numerator: string; denominator: string; display_exact: boolean };
type Coverage = { present: boolean; rows: number; measured: number; missing: number; total: Exact | null };
export type Contribution = {
  baseline_total: Exact | null; comparison_total: Exact | null; net_change: Exact | null; reconciled: boolean;
  rows: { segment: string | null; baseline: Coverage; comparison: Coverage; delta: Exact | null; percent_of_net: Exact | null; status: string }[];
  pvm: { order: string; state: string; limitation: string; totals: Record<string, Exact>; components: { segment: string | null; volume: Exact; mix: Exact; unit_revenue: Exact }[]; reconciled: boolean } | null;
  root_cause?: RootCause;
};
export type RootCause = {
  method: string; state: string; limitation: string;
  fields: { field: string; members: number; state: string; top_member?: string | null; top_delta?: Exact; concentration?: Exact; top_share_of_net?: Exact | null }[];
  drilldown: { within_field: string; within_member: string | null; field: string; concentration: Exact; rows: { member: string | null; delta: Exact }[]; reconciled: boolean } | null;
};
export type ContributionRecords = { columns: string[]; rows: Cell[][]; records_analyzed: number };
const shown = (value: Exact | null) => value?.display ?? "Not defined";
const exact = (value: Exact) => `${value.numerator}/${value.denominator}`;

export function ContributionSummary({ value, unit }: { value: Contribution; unit: string }) {
  return <div className={styles.summary} aria-label="Recorded comparison totals">
    {[["Baseline", value.baseline_total], ["Comparison", value.comparison_total], ["Recorded change", value.net_change]].map(([label, amount]) => <div key={String(label)}><span>{String(label)}</span><strong>{shown(amount as Exact | null)}</strong><small>{unit}</small></div>)}
    <p>{value.reconciled ? "The category contributions add up exactly to the recorded change." : "Missing measurements prevent a complete reconciliation. Undefined amounts stay visible."} These are observed contributions, not proven causes.</p>
  </div>;
}

const member = (value: string | null | undefined) => value ?? "Missing value";
const fieldState: Record<string, string> = { no_movement: "No change in this field", too_many_groups: "More than 128 members; not ranked" };

export function RootCauseDetails({ value, unit }: { value: RootCause; unit: string }) {
  const drill = value.drilldown;
  const top = value.fields[0];
  const checked = drill && top?.top_delta ? addsBack(drill.rows.map(row => row.delta), top.top_delta) : null;
  return <section className={styles.rootCause} aria-label="Where the change is concentrated">
    <h4>Where the change is concentrated</h4>
    <p className={styles.label}>Accounting attribution, not cause</p>
    {value.state === "undefined_missing_values" ? <p>Some amounts are missing, so fields cannot be ranked without guessing. Fill or filter the missing amounts and compare again.</p>
      : value.state === "no_change" ? <p>No field shows any recorded movement between the two populations.</p> : <>
      <RecordTable data={{ columns: ["Rank", "Field", "Top member", `Top member change (${unit})`, "Concentration", "Exact concentration", "Share of net change"], records_analyzed: value.fields.length,
        rows: value.fields.map((field, index) => field.state === "ranked"
          ? [index + 1, field.field, member(field.top_member), shown(field.top_delta ?? null), shown(field.concentration ?? null), field.concentration ? exact(field.concentration) : null, shown(field.top_share_of_net ?? null)]
          : [null, field.field, fieldState[field.state] ?? field.state, null, null, null, null]) }} />
      <p>Concentration is the top member’s absolute change divided by all absolute movement in that field. 1 means one member holds all the movement.</p>
      {drill && <>
        <h5>Inside {drill.within_field} = {member(drill.within_member)}, by {drill.field}</h5>
        <RecordTable data={{ columns: [drill.field, `Change (${unit})`, "Exact change"], records_analyzed: drill.rows.length, rows: drill.rows.map(row => [member(row.member), row.delta.display, exact(row.delta)]) }} />
        <p role="status">{drill.reconciled && checked ? `Adds back exactly: these ${drill.rows.length} members sum to ${top?.top_delta?.display} ${unit}, the change in ${member(drill.within_member)}. Checked on the server and again in your browser.` : "These members do not add back to the top member’s change. Treat this drilldown as incomplete."}</p>
      </>}
    </>}
    <p>{value.limitation}</p>
  </section>;
}

export function ContributionDetails({ value, results }: { value: Contribution; results: ContributionRecords[] }) {
  const [category, setCategory] = useState("all");
  const selected = category === "all" ? null : value.rows[Number(category)].segment;
  return <div className={styles.detail}>
    <details><summary>Contributions, coverage and exact values</summary>
      <RecordTable data={{ columns: ["Category", "Baseline", "Comparison", "Change", "% of net", "Status", "Baseline measured / rows", "Comparison measured / rows", "Exact change"], rows: value.rows.map(row => [row.segment, shown(row.baseline.total), shown(row.comparison.total), shown(row.delta), shown(row.percent_of_net), row.status, `${row.baseline.measured} / ${row.baseline.rows}`, `${row.comparison.measured} / ${row.comparison.rows}`, row.delta ? exact(row.delta) : null]), records_analyzed: value.rows.length }} />
      <p>An absent category has no records on that side. A present category with only missing amounts remains undefined. Percentage contributions use the signed net change and can exceed 100%; they are unavailable when the net change is zero.</p>
    </details>
    {value.pvm && <details><summary>Volume, mix and revenue per unit</summary>
      <p>Order: {value.pvm.order}. {value.pvm.limitation}</p>
      {value.pvm.state === "no_matched_products" && <p>No category appears on both sides. Only observed entries and exits can be compared.</p>}
      <RecordTable data={{ columns: ["Component", "Recorded contribution", "Exact fraction", "Display"], rows: Object.entries(value.pvm.totals).map(([name, amount]) => [name.replaceAll("_", " "), amount.display, exact(amount), amount.display_exact ? "Exact" : "Rounded"]), records_analyzed: Object.keys(value.pvm.totals).length }} />
      <RecordTable data={{ columns: ["Category", "Volume", "Mix", "Revenue per unit"], rows: value.pvm.components.map(row => [row.segment, exact(row.volume), exact(row.mix), exact(row.unit_revenue)]), records_analyzed: value.pvm.components.length }} />
      <p>For matched categories, p = revenue / quantity, Q = total quantity, and s = category quantity / Q. Volume = (Q₁ − Q₀) × s₀ × p₀; mix = Q₁ × (s₁ − s₀) × p₀; unit revenue = q₁ × (p₁ − p₀). New and departed categories use their recorded revenue separately.</p>
    </details>}
    <details><summary>Inspect supporting records</summary>
      <WorkspaceSelect label="Supporting category" value={category} onValueChange={setCategory} options={[{ value: "all", label: "All selected records" }, ...value.rows.map((row, index) => ({ value: String(index), label: row.segment ?? "Missing category" }))]} />
      {results.map((result, index) => {
        const rows = result.rows.filter(row => category === "all" || (row[0] === null ? null : String(row[0])) === selected);
        return <section key={index}><h4>{index === 0 ? "Baseline records" : "Comparison records"}</h4><RecordTable data={{ columns: result.columns, rows, records_analyzed: rows.length }} /></section>;
      })}
    </details>
  </div>;
}
