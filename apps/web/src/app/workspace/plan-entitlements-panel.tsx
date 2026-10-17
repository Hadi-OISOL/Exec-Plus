/* Use case: Makes local product allowances and administrator assignments visible.
What it does: Shows actual remaining capacity and explicit no-payment assignments through protected APIs. */

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import { WorkspaceSelect } from "./workspace-select";
import styles from "./model-usage-panel.module.css";

type Assignment = { id: string; version: number; plan_key: string; starts_at: string; ends_at: string };
type Allowance = { used: number | null; limit: number | null; remaining: number | null; basis: string };
type Summary = { assignment: Assignment | null; active: boolean; allowances: Record<string, Allowance>; billing: string; counting: string };
type Catalog = { key: string; name: string; version: number; limits: Record<string, number | null> };
const labels: Record<string, string> = { seats: "Team seats", datasets: "Datasets", file_bytes: "Maximum file size", storage_bytes: "Retained upload storage", saved_studies: "Saved studies", processing: "Processing operations", exports: "Exports", forecasts: "Forecast operations", model_attempts: "AI attempts" };
const amount = (key: string, value: number) => key.endsWith("bytes") ? `${value.toLocaleString()} bytes` : value.toLocaleString();
const period = (value: Assignment) => `${new Date(value.starts_at).toUTCString()} to ${new Date(value.ends_at).toUTCString()}`;

export function PlanEntitlementsPanel({ workspaceId, request }: { workspaceId: string; request: ApiRequest }) {
  const [generation, setGeneration] = useState(0);
  return <AllowanceReport key={`${workspaceId}:${generation}`} workspaceId={workspaceId} request={request} refresh={() => setGeneration(value => value + 1)} />;
}

function AllowanceReport({ workspaceId, request, refresh }: { workspaceId: string; request: ApiRequest; refresh: () => void }) {
  const [report, setReport] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    request<Summary>(`/workspaces/${workspaceId}/plan`, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setReport(value); })
      .catch(cause => { if (!controller.signal.aborted) { setReport(null); setError(cause instanceof Error ? cause.message : "Allowances could not be loaded."); } })
      .finally(() => { if (!controller.signal.aborted) setPending(false); });
    return () => controller.abort();
  }, [workspaceId, request]);
  return <section className={`panel ${styles.panel}`} aria-label="Workspace allowances" aria-busy={pending}>
    <div className={styles.header}><div><p className="studioEyebrow">WORKSPACE OWNER</p><h2>Workspace allowances</h2><p>See how much room this workspace has for new work.</p></div><button type="button" disabled={pending} onClick={refresh}>Refresh allowances</button></div>
    {pending && <p role="status">Loading allowances…</p>}
    {error && <p role="alert" className="errorNotice">{error}</p>}
    {report && <>
      <p className={styles.notice}>{report.assignment ? `${report.assignment.plan_key} · ${report.active ? "Active" : "Not active — ask an administrator to review the period"}` : "No local plan assigned. Existing global safety limits still apply."}</p>
      {report.assignment && <p className={styles.caption}>{period(report.assignment)}</p>}
      <dl className={styles.allowance}>{Object.entries(report.allowances).map(([key, value]) => <div key={key}><dt>{labels[key] ?? key}</dt><dd>{value.basis === "per_file" ? value.limit === null ? "No plan limit" : amount(key, value.limit) : <>{value.remaining === null ? "No plan limit" : `${amount(key, value.remaining)} remaining`}<small>{value.used === null ? "No assigned reporting period" : `${amount(key, value.used)} used`}{value.limit !== null && ` of ${amount(key, value.limit)}`}</small></>}</dd></div>)}</dl>
      <p>{report.counting}</p><p className={styles.caption}>{report.billing} Existing work is retained when an allowance is reduced.</p>
    </>}
  </section>;
}

export function PlanAssignmentPanel({ workspaceId, request }: { workspaceId: string; request: ApiRequest }) {
  const [catalog, setCatalog] = useState<Catalog[]>([]);
  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [selected, setSelected] = useState("demo");
  const [days, setDays] = useState(30);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [generation, setGeneration] = useState(0);
  const operation = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([request<Catalog[]>("/plans", { signal: controller.signal }), request<Assignment | null>(`/admin/workspaces/${workspaceId}/plan`, { signal: controller.signal })])
      .then(([options, current]) => { if (!controller.signal.aborted) { setCatalog(options); setAssignment(current); setSelected(current?.plan_key ?? "demo"); setReady(true); } })
      .catch(cause => { if (!controller.signal.aborted) { setAssignment(null); setCatalog([]); setReady(false); setError(cause instanceof Error ? cause.message : "Local plans could not be loaded."); } });
    return () => controller.abort();
  }, [workspaceId, request, generation]);
  useEffect(() => () => operation.current?.abort(), []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !ready) return;
    setBusy(true); setError(""); setStatus("");
    const controller = new AbortController(); operation.current = controller;
    const start = new Date();
    try {
      const result = await request<Assignment>(`/admin/workspaces/${workspaceId}/plan`, { method: "PUT", headers: { "Content-Type": "application/json" }, signal: controller.signal, body: JSON.stringify({ expected_version: assignment?.version ?? 0, plan_key: selected, starts_at: start.toISOString(), ends_at: new Date(start.getTime() + days * 86400000).toISOString() }) });
      if (!controller.signal.aborted) { setAssignment(result); setStatus("Local allowance assigned. No payment or subscription was created."); }
    } catch (cause) { if (!controller.signal.aborted) { setAssignment(null); setCatalog([]); setError(cause instanceof Error ? cause.message : "The assignment could not be saved. Reload before retrying."); setReady(false); } }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  function reload() { setAssignment(null); setCatalog([]); setReady(false); setError(""); setStatus(""); setGeneration(value => value + 1); }
  return <section className={`panel ${styles.panel}`} aria-label="Assign local allowance">
    <h3>Assign a local allowance</h3><p>Administrator-controlled capacity only. There are no prices, payments or subscriptions.</p>
    {assignment && <p className={styles.caption}>Current: {assignment.plan_key}, version {assignment.version}. {period(assignment)}</p>}
    {!ready && !error && <p role="status">Loading available plans…</p>}
    {error && <p role="alert" className="errorNotice">{error}</p>}
    {status && <p role="status">{status}</p>}
    <form onSubmit={submit}><WorkspaceSelect label="Local plan" value={selected} onValueChange={setSelected} disabled={!ready || busy} options={catalog.map(item => ({ value: item.key, label: item.name }))} />
      <label className={styles.period}>Days from now<input type="number" min={1} max={366} required value={days} disabled={!ready || busy} onChange={event => setDays(Number(event.target.value))} /></label>
      <p className={styles.caption}>This starts a new explicit period. Existing events within that period count toward the allowance. No automatic renewal occurs.</p>
      <div className={styles.switch}><button type="submit" disabled={!ready || busy}>{busy ? "Saving allowance…" : "Assign local allowance"}</button><button type="button" onClick={reload} disabled={busy}>Reload assignment</button></div>
    </form>
  </section>;
}
