/* Use case: Finds unusual values in the selected file with one click and no settings.
What it does: Runs the server's automatic MAD/IQR scan and lists each unusual row in plain language with exact values. */
import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiRequest } from "./profile-panel";

type Finding = {
  row: string;
  column: string;
  value: string;
  unit: string | null;
  direction: "high" | "low";
  compared_with: "file" | "group";
  group: { column: string; value: string } | null;
  median: string;
  usual_low: string;
  usual_high: string;
  score: string | null;
  explanation: string;
};
type Measure = { column: string; unit: string | null; checked: number; median: string; usual_low: string; usual_high: string; flagged: number };
export type UnusualScan =
  | { state: "needs_review" | "unavailable"; message: string }
  | {
      state: "ready";
      meaning: "confirmed" | "inferred";
      summary: string;
      rows: number;
      threshold: string;
      group_column: string | null;
      measures: Measure[];
      findings: Finding[];
      total_findings: number;
      closest: Finding[];
      exclusions: { column: string; reason: string }[];
      limitations: string[];
      query_id: string;
    };

export function UnusualValues({ root, request, onReview, autoRun = false }: { root: string; request: ApiRequest; onReview: () => void; autoRun?: boolean }) {
  const [scan, setScan] = useState<UnusualScan | null>(null);
  const [pending, setPending] = useState(autoRun);
  const [error, setError] = useState("");
  const active = useRef<AbortController | null>(null);
  const check = useCallback((controller: AbortController) => {
    active.current = controller;
    return request<UnusualScan>(`${root}/decision-analysis/unusual-values`, { method: "POST", signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) setScan(value); })
      .catch((cause) => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "The unusual-value check could not complete."); })
      .finally(() => {
        if (!controller.signal.aborted) setPending(false);
        if (active.current === controller) active.current = null;
      });
  }, [root, request]);
  useEffect(() => {
    const controller = new AbortController();
    if (autoRun) void check(controller);
    return () => controller.abort();
  }, [autoRun, check]);
  useEffect(() => () => active.current?.abort(), []);
  function run() {
    if (active.current) return;
    setPending(true);
    setError("");
    void check(new AbortController());
  }
  const ready = scan?.state === "ready" ? scan : null;
  return <section className="unusualValues" aria-label="Unusual values">
    <div className="unusualValuesIntro">
      <h3>Find unusual values</h3>
      <p>We check every measurement in this file and point out rows that stand far from the rest. No settings needed.</p>
      <button type="button" disabled={pending} onClick={run}>{scan ? "Check again" : "Find unusual values"}</button>
    </div>
    {pending && <p role="status">Checking every measurement…</p>}
    {error && <p role="alert" className="errorNotice">{error}</p>}
    {scan && scan.state !== "ready" && <div className="unusualValuesBlocked">
      <p>{scan.message}</p>
      {scan.state === "needs_review" && <button type="button" onClick={onReview}>Review data meanings</button>}
    </div>}
    {ready && <div className="unusualValuesResult">
      <p className="unusualValuesSummary" role="status">{ready.summary}</p>
      {ready.findings.length > 0 && <ol className="unusualValuesFindings" aria-label="Unusual values found">
        {ready.findings.map((item, index) => <li key={`${index}:${item.row}:${item.column}`} className={`unusualFinding unusualFinding-${item.direction}`}>
          <p>{item.explanation}</p>
          {item.score && <small>Robust score {item.score} · above {ready.threshold} counts as unusual</small>}
        </li>)}
      </ol>}
      {ready.total_findings > ready.findings.length && <p>Showing the {ready.findings.length} strongest of {ready.total_findings} unusual values.</p>}
      {ready.closest.length > 0 && <div className="unusualValuesClosest">
        <h4>Closest to unusual</h4>
        <ul>{ready.closest.map((item, index) => <li key={`${index}:${item.row}:${item.column}`}>{item.explanation}</li>)}</ul>
      </div>}
      <details className="unusualValuesDetails">
        <summary>What we checked ({ready.measures.length} measures, {ready.rows} rows)</summary>
        <div className="tableWrap"><table aria-label="Usual range of each measure">
          <thead><tr><th>Measure</th><th>Values checked</th><th>Middle value</th><th>Usual range</th><th>Unusual</th></tr></thead>
          <tbody>{ready.measures.map(item => <tr key={item.column}><td>{item.column}{item.unit ? ` · ${item.unit}` : ""}</td><td>{item.checked}</td><td>{item.median}</td><td>{item.usual_low} to {item.usual_high}</td><td>{item.flagged}</td></tr>)}</tbody>
        </table></div>
        {ready.group_column && <p>Each value was also compared with rows that share its {ready.group_column}.</p>}
        {ready.exclusions.length > 0 && <ul>{ready.exclusions.map(item => <li key={item.column}><strong>{item.column}</strong>: {item.reason}</li>)}</ul>}
      </details>
      <ul className="unusualValuesLimitations">{ready.limitations.map(item => <li key={item}>{item}</li>)}</ul>
      {ready.meaning === "inferred" && <button type="button" onClick={onReview}>Review data meanings</button>}
    </div>}
  </section>;
}
