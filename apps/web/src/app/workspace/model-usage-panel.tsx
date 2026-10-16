/* Use case: Shows a workspace owner recorded AI usage and configured allowances.
What it does: Separates reported amounts, unknown costs and reserved exposure without inventing a bill. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import styles from "./model-usage-panel.module.css";

type UsageSummary = {
  starts_at: string;
  ends_at: string;
  counts: { attempts: number; released_before_dispatch: number; in_flight: number; unknown_cost_attempts: number };
  costs: { currency: string | null; known_cost: string | null; held_exposure: string; priced_attempts: number; unknown_attempts: number }[];
  tokens: {
    input_tokens: string | null;
    output_tokens: string | null;
    cached_input_tokens: string | null;
    input_tokens_reported_attempts: number;
    output_tokens_reported_attempts: number;
    cached_input_tokens_reported_attempts: number;
  };
  allowance: null | {
    id: string;
    version: number;
    plan_key: string;
    starts_at: string;
    ends_at: string;
    max_attempts: number | null;
    max_in_flight: number | null;
    currency: string | null;
    spend_limit: string | null;
    reservation_per_attempt: string | null;
    current_totals: { attempts: number; in_flight: number; known_cost: string; held_exposure: string; unknown_attempts: number };
    availability: { can_start_next: boolean; code: string | null };
  };
  limitation: string;
};

const reasons: Record<string, string> = {
  usage_window: "The allowance period is not active.",
  usage_attempt_limit: "This workspace has used its request allowance.",
  usage_concurrency: "The allowed number of requests is already running. Try again when they finish.",
  usage_spend_limit: "Recorded costs and money reserved for requests have reached the configured limit.",
  usage_unresolved: "Earlier costs need review before this spending allowance can be used.",
};
const amount = (value: string | null, currency: string | null) =>
  value === null ? "Unknown" : `${value}${currency ? ` ${currency}` : ""}`;
const timestamp = (value: string) => `${value.slice(0, 19).replace("T", " ")} UTC`;

export function ModelUsagePanel({ workspaceId, request }: { workspaceId: string; request: ApiRequest }) {
  const [days, setDays] = useState(30);
  const [generation, setGeneration] = useState(0);
  return <UsageReport key={`${workspaceId}:${days}:${generation}`} workspaceId={workspaceId}
    request={request} days={days} setDays={setDays} refresh={() => setGeneration(value => value + 1)} />;
}

function UsageReport({ workspaceId, request, days, setDays, refresh }: {
  workspaceId: string; request: ApiRequest; days: number; setDays: (days: number) => void; refresh: () => void;
}) {
  const [report, setReport] = useState<UsageSummary | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    request<UsageSummary>(`/workspaces/${workspaceId}/model-usage?days=${days}`, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setReport(value); })
      .catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "AI usage could not be loaded. Please try again."); })
      .finally(() => { if (!controller.signal.aborted) setPending(false); });
    return () => controller.abort();
  }, [workspaceId, request, days]);
  return <section className={`panel ${styles.panel}`} aria-label="AI usage">
    <div className={styles.header}>
      <div><p className="studioEyebrow">WORKSPACE OWNER</p><h2>AI usage</h2>
        <p>See recorded requests, known costs and the allowance set for this workspace.</p></div>
      <button type="button" onClick={refresh} disabled={pending}>Refresh AI usage</button>
    </div>
    <label className={styles.period}>Reporting window<select value={days} disabled={pending} onChange={event => setDays(Number(event.target.value))}>
      {[7, 30, 90].map(value => <option key={value} value={value}>Last {value} days</option>)}
    </select></label>
    {pending && <p role="status">Loading recorded AI usage…</p>}
    {error && <p role="alert" className="errorNotice">{error}</p>}
    {report && <>
      <p className={styles.caption}>{timestamp(report.starts_at)} to {timestamp(report.ends_at)}</p>
      <dl className={styles.metrics}>
        <div><dt>Recorded attempts</dt><dd>{report.counts.attempts}</dd></div>
        <div><dt>Requests still active</dt><dd>{report.counts.in_flight}</dd></div>
        <div><dt>Attempts with unknown cost</dt><dd>{report.counts.unknown_cost_attempts}</dd></div>
      </dl>
      {report.counts.attempts === 0 && <p className={styles.notice}>No AI attempts were recorded in this window. Ask ExecPlus a question, then refresh this view.</p>}
      <p className={styles.caption}>One question can need several attempts, including retries. {report.counts.released_before_dispatch} attempts stopped before a request was sent.</p>
      <section className={styles.block} aria-label="Recorded model costs">
        <h3>Recorded costs</h3><p>These amounts use reported usage and configured rates. They are not an invoice. Unknown costs are not treated as free.</p>
        {report.costs.length ? <div className={styles.costs}>{report.costs.map((cost, index) => <section className={styles.cost} key={`${cost.currency}:${index}`}>
          <h4>{cost.currency ?? "Unpriced requests"}</h4>
          <dl><div><dt>Known subtotal</dt><dd>{amount(cost.known_cost, cost.currency)}</dd></div>
            <div><dt>Reserved, not a recorded charge</dt><dd>{amount(cost.held_exposure, cost.currency)}</dd></div>
            <div><dt>Attempts with a known price</dt><dd>{cost.priced_attempts}</dd></div>
            <div><dt>Attempts with unknown cost</dt><dd>{cost.unknown_attempts}</dd></div></dl>
        </section>)}</div> : <p>No cost records in this window.</p>}
        <p className={styles.caption}>Reserved amounts hold space in a configured allowance while a request or its final cost is unresolved. Different currencies stay separate.</p>
      </section>
      <section className={styles.block} aria-label="Current AI allowance">
        <h3>Current allowance</h3>
        {report.allowance ? <>
          <p className={styles.notice}>{report.allowance.availability.can_start_next
            ? "The current allowance has room for another request."
            : reasons[report.allowance.availability.code ?? ""] ?? "New requests are paused by the current allowance."}</p>
          <p className={styles.caption}>Allowance period: {timestamp(report.allowance.starts_at)} to {timestamp(report.allowance.ends_at)}. These totals use that period, independently of the reporting window above.</p>
          <dl className={styles.allowance}>
            <div><dt>Request attempts</dt><dd>{report.allowance.current_totals.attempts} / {report.allowance.max_attempts ?? "No configured limit"}</dd></div>
            <div><dt>Active requests</dt><dd>{report.allowance.current_totals.in_flight} / {report.allowance.max_in_flight ?? "No configured limit"}</dd></div>
            <div><dt>Spending limit</dt><dd>{report.allowance.spend_limit === null ? "No configured limit" : amount(report.allowance.spend_limit, report.allowance.currency)}</dd></div>
            <div><dt>Known cost in allowance period</dt><dd>{amount(report.allowance.current_totals.known_cost, report.allowance.currency)}</dd></div>
            <div><dt>Reserved in allowance period</dt><dd>{amount(report.allowance.current_totals.held_exposure, report.allowance.currency)}</dd></div>
            <div><dt>Attempts still awaiting a known cost</dt><dd>{report.allowance.current_totals.unknown_attempts}</dd></div>
          </dl>
        </> : <p>No workspace allowance has been configured. Recorded usage still appears here.</p>}
      </section>
      <details className={styles.details}><summary>Reported tokens and counting details</summary>
        <p>Tokens are the pieces of text the model receives or generates. Coverage shows how many attempts actually reported each count.</p>
        <dl className={styles.allowance}>
          {([
            ["Input tokens", report.tokens.input_tokens, report.tokens.input_tokens_reported_attempts],
            ["Output tokens", report.tokens.output_tokens, report.tokens.output_tokens_reported_attempts],
            ["Cached input tokens", report.tokens.cached_input_tokens, report.tokens.cached_input_tokens_reported_attempts],
          ] as const).map(([label, value, coverage]) => <div key={label}><dt>{label}</dt><dd>{value ?? "Unknown"}<small>Reported by {coverage} {coverage === 1 ? "attempt" : "attempts"}</small></dd></div>)}
        </dl><p>{report.limitation}</p>
      </details>
    </>}
  </section>;
}
