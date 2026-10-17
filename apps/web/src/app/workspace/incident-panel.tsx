/* Use case: Lets staff administrators review redacted internal service incidents.
What it does: Shows real collector health, exact occurrence counts and explicit optimistic acknowledgement or resolution without displaying customer content. */

import { useEffect, useRef, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import { IncidentMetrics, type AlertPolicy, type RequestMetric } from "./incident-metrics";
import styles from "./incident-panel.module.css";

type Incident = { id: string; title: string; code: string; component: string; severity: string; status: string; version: number; occurrences: number; first_seen: string; last_seen: string };
type IncidentReport = { incidents: Incident[]; metrics: RequestMetric[]; collector: { running: boolean; last_success: string | null; last_failure: string | null; pending: number; overflow_pending: number; storage_failures_pending: number; capacity_limited: boolean; poll_seconds: number; metric_pending_buckets: number; metric_dropped_or_expired_requests: number; metric_capacity_limited: boolean; metric_last_gap: string | null } };

function time(value: string | null) { return value ? new Date(value).toLocaleString() : "No completed collection yet"; }

export function IncidentPanel({ request }: { request: ApiRequest }) {
  const [report, setReport] = useState<IncidentReport | null>(null);
  const [filter, setFilter] = useState("active");
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const mutation = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let reading = false;
    async function read() {
      if (reading || mutation.current) return;
      reading = true;
      try {
        const value = await request<IncidentReport>(`/admin/incidents?status=${filter}`, { signal: controller.signal });
        if (!controller.signal.aborted) { setReport(value); setError(""); setLoading(false); }
      } catch (cause) {
        if (!controller.signal.aborted) { setReport(null); setLoading(false); setError(cause instanceof Error ? cause.message : "Service alerts could not be loaded. Try again."); }
      } finally { reading = false; }
    }
    void read();
    const interval = setInterval(() => { void read(); }, 30_000);
    return () => { controller.abort(); clearInterval(interval); };
  }, [request, filter, reload]);
  useEffect(() => () => mutation.current?.abort(), []);
  async function update(value: Incident, status: "acknowledged" | "resolved") {
    if (busy) return;
    const controller = new AbortController(); mutation.current = controller;
    setBusy(true); setError(""); setMessage("");
    try {
      await request(`/admin/incidents/${value.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_version: value.version, status }), signal: controller.signal });
      if (!controller.signal.aborted) { setMessage(status === "resolved" ? "Incident resolved. A new failure will open it again." : "Incident acknowledged. New failures are still counted."); setReload(previous => previous + 1); }
    } catch (cause) {
      if (!controller.signal.aborted) { setReport(null); setError(cause instanceof Error ? cause.message : "The incident could not be updated. Reload it and try again."); }
    } finally { if (!controller.signal.aborted) { mutation.current = null; setBusy(false); } }
  }
  async function saveThreshold(value: AlertPolicy) {
    if (busy) return;
    const controller = new AbortController(); mutation.current = controller;
    setBusy(true); setError(""); setMessage("");
    try {
      await request(`/admin/incidents/thresholds/${value.category}`, { method: "PUT", headers: { "Content-Type": "application/json" }, signal: controller.signal, body: JSON.stringify({ expected_version: value.version, enabled: value.enabled, window_minutes: value.window_minutes, minimum_requests: value.minimum_requests, minimum_failures: value.minimum_failures, failure_basis_points: value.failure_basis_points }) });
      if (!controller.signal.aborted) { setMessage("Alert settings saved. The next view uses the new limits."); setReload(previous => previous + 1); }
    } catch (cause) {
      if (!controller.signal.aborted) { setReport(null); setError(cause instanceof Error ? cause.message : "Alert settings could not be saved. Reload and try again."); }
    } finally { if (!controller.signal.aborted) { mutation.current = null; setBusy(false); } }
  }
  const unhealthy = report && (!report.collector.running || !report.collector.last_success || report.collector.storage_failures_pending > 0 || report.collector.capacity_limited || report.collector.metric_capacity_limited);
  return <section className={`panel ${styles.panel}`} aria-label="Internal service alerts">
    <div className={styles.heading}><div><p className="eyebrow">SERVICE HEALTH</p><h2>Internal alerts</h2></div><button type="button" disabled={busy || loading} onClick={() => { setLoading(true); setReload(value => value + 1); }}>Refresh alerts</button></div>
    <p>Server errors and failed analysis, refresh and scheduled-report work appear here. Only fixed error categories, counts and times are kept. Customer questions, files and tokens are excluded.</p>
    <div className={styles.filter}><label>Show incidents<select value={filter} disabled={busy} onChange={event => { setFilter(event.target.value); setLoading(true); setReport(null); setMessage(""); }}><option value="active">Open & acknowledged</option><option value="open">Open</option><option value="acknowledged">Acknowledged</option><option value="resolved">Resolved</option><option value="all">All retained incidents</option></select></label></div>
    {loading && <p role="status">Loading service alerts…</p>}{error && <p role="alert" className={styles.error}>{error}</p>}{message && <p role="status">{message}</p>}
    {report && <>
      <div className={styles.health} role={unhealthy ? "alert" : undefined}><strong>{unhealthy ? "Collection needs attention" : "Collector is running"}</strong><span>Last successful collection: {time(report.collector.last_success)}</span><span>{report.collector.pending} queued request errors · {report.collector.overflow_pending} overflow events awaiting recording</span>{report.collector.storage_failures_pending > 0 && <span>Incident storage is unavailable. Pending events will retry; this screen cannot confirm complete service health.</span>}{report.collector.capacity_limited && <span>The 100,000 occurrence-key bound was reached. Durable failures remain queued at their source; request-error collection may be incomplete.</span>}</div>
      <p>{report.collector.metric_pending_buckets} minute/category counts awaiting collection in this process. {report.collector.metric_dropped_or_expired_requests} request observations dropped or expired in this process.{report.collector.metric_capacity_limited && " Metric storage reached its bound; the pending batch will retry."}</p>
      <IncidentMetrics values={report.metrics} busy={busy} save={saveThreshold} />
      {!report.incidents.length && <p>No retained incidents match this filter. This does not prove that every service is healthy.</p>}
      <div className={styles.cards}>{report.incidents.map(value => <article key={value.id} className={styles.card} aria-label={value.title}>
        <div className={styles.cardHeading}><span>{value.component} · {value.severity}</span><strong>{value.status}</strong></div><h3>{value.title}</h3>
        <dl><div><dt>Recorded occurrences</dt><dd>{value.occurrences.toLocaleString()}</dd></div><div><dt>First seen</dt><dd>{time(value.first_seen)}</dd></div><div><dt>Last seen</dt><dd>{time(value.last_seen)}</dd></div></dl>
        {value.code === "queue_overflow" && <p>Some request errors could not enter the bounded queue. The count records dropped entries, not complete request diagnostics.</p>}
        {value.status !== "resolved" && <div className={styles.actions}>{value.status === "open" && <button type="button" disabled={busy} onClick={() => void update(value, "acknowledged")}>Acknowledge</button>}<button type="button" disabled={busy} onClick={() => void update(value, "resolved")}>Mark resolved</button></div>}
      </article>)}</div>
    </>}
    <details className={styles.details}><summary>Collection limits</summary><p>Durable failures are checked about every 30 seconds while the API runs. Occurrence keys are retained for 30 days, with a 100,000-key bound. Resolved incidents older than 30 days are removed. The request-error queue holds 256 entries in this process; a process crash can lose pending request events. There is no external paging or email alert.</p><p>Acknowledging or resolving an alert changes its review status only. It does not repair or retry the failed work. Every administrator action is audited.</p></details>
  </section>;
}
