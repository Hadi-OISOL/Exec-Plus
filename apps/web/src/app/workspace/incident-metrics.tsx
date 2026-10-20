/* Use case: Explains recorded service outcomes and explicit local alert thresholds.
What it does: Separates failures from rejected requests, uses accessible existing controls,
and keeps incomplete observations and response-header timing limits visible. */

import { useState } from "react";
import { WorkspaceSelect } from "./workspace-select";
import styles from "./incident-panel.module.css";

export type AlertPolicy = {
  category: string; version: number; enabled: boolean; window_minutes: number;
  minimum_requests: number; minimum_failures: number; failure_basis_points: number;
};
export type RequestMetric = {
  category: string; title: string; policy: AlertPolicy;
  state: "disabled" | "insufficient_data" | "alert" | "below_threshold";
  window_start: string; window_end: string; requests: number; failed: number;
  rejected: number; successful: number;
  failure_rate: { numerator: string; denominator: string; percent_display: string | null };
  mean_response_start_ms: string | null; maximum_response_start_ms: number | null;
};
const labels = { disabled: "Alert off", insufficient_data: "Not enough requests", alert: "Above chosen limit", below_threshold: "Below chosen limit" };

function ThresholdForm({ policy, title, busy, save }: { policy: AlertPolicy; title: string; busy: boolean; save: (value: AlertPolicy) => Promise<void> }) {
  const [draft, setDraft] = useState(policy);
  const [percent, setPercent] = useState((policy.failure_basis_points / 100).toFixed(2));
  return <form className={styles.threshold} onSubmit={event => {
    event.preventDefault();
    const basisPoints = Math.round(Number(percent) * 100);
    if (Number.isInteger(basisPoints) && basisPoints >= 0 && basisPoints <= 10_000) void save({ ...draft, failure_basis_points: basisPoints });
  }} aria-label={`${title} alert settings`}>
    <label className={styles.check}><input type="checkbox" checked={draft.enabled} disabled={busy} onChange={event => setDraft({ ...draft, enabled: event.target.checked })} />Enable this in-app alert</label>
    <label>Look back (completed minutes)<input type="number" min="1" max="60" step="1" required disabled={busy} value={draft.window_minutes} onChange={event => setDraft({ ...draft, window_minutes: Number(event.target.value) })} /></label>
    <label>Minimum recorded requests<input type="number" min="1" max="1000000" step="1" required disabled={busy} value={draft.minimum_requests} onChange={event => setDraft({ ...draft, minimum_requests: Number(event.target.value) })} /></label>
    <label>Minimum server failures<input type="number" min="1" max="1000000" step="1" required disabled={busy} value={draft.minimum_failures} onChange={event => setDraft({ ...draft, minimum_failures: Number(event.target.value) })} /></label>
    <label>Failure rate limit (%)<input type="number" min="0" max="100" step="0.01" required disabled={busy} value={percent} onChange={event => setPercent(event.target.value)} /></label>
    <p>The alert appears when all three limits are met: enough requests, enough failures, and the chosen failure rate. Rejected requests (4xx) are shown separately from server failures (5xx).</p>
    <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save alert settings"}</button>
  </form>;
}

export function IncidentMetrics({ values, busy, save }: { values: RequestMetric[]; busy: boolean; save: (value: AlertPolicy) => Promise<void> }) {
  const [category, setCategory] = useState("ingestion");
  const selected = values.find(value => value.category === category);
  return <section className={styles.metrics} aria-label="Recorded request outcomes">
    <h3>Recorded request outcomes</h3>
    <p>Counts cover completed minutes and include only requests this application recorded. Health probes and admin polling are excluded. Pending collection, outages or a process crash can leave gaps; these counts do not prove complete service health.</p>
    <div className={styles.cards}>{values.map(value => <article className={styles.card} key={value.category} aria-label={`${value.title} outcomes`}>
      <div className={styles.cardHeading}><h4>{value.title}</h4><strong className={value.state === "alert" ? styles.error : undefined}>{labels[value.state]}</strong></div>
      <dl><div><dt>Recorded requests · last {value.policy.window_minutes} completed minutes</dt><dd>{value.requests.toLocaleString()}</dd></div>
        <div><dt>Server failures / recorded requests</dt><dd>{value.failure_rate.numerator} / {value.failure_rate.denominator}{value.failure_rate.percent_display !== null ? ` (${value.failure_rate.percent_display}%)` : " · No rate yet"}</dd></div>
        <div><dt>Rejected inputs or access</dt><dd>{value.rejected.toLocaleString()}</dd></div>
        <div><dt>Mean time to response headers</dt><dd>{value.mean_response_start_ms !== null ? `${value.mean_response_start_ms} ms` : "No measurement yet"}</dd></div></dl>
    </article>)}</div>
    <details className={styles.details}><summary>Adjust local alert limits</summary><p>These limits control this screen only. They do not send email, page staff or change the work itself. Timing ends when response headers are ready; it is not download time or background-job duration.</p>
      <WorkspaceSelect label="Request category" value={category} disabled={busy} onValueChange={setCategory} options={values.map(value => ({ value: value.category, label: value.title }))} />
      {selected && <ThresholdForm key={`${selected.category}-${selected.policy.version}`} title={selected.title} policy={selected.policy} busy={busy} save={save} />}
    </details>
  </section>;
}
