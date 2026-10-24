/* Use case: Lets platform administrators see which workspaces are closest to their allowances.
What it does: Lists exact period operation counts per assigned workspace, ranked by the highest share of any limit. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import { usedShare } from "./usage-values";
import styles from "./model-usage-panel.module.css";

type Operation = { used: number; limit: number | null; state: "ok" | "near" | "reached" };
type Row = { workspace_id: string; name: string; plan_key: string; active: boolean; operations: Record<string, Operation>; highest: string | null; highest_percent: number };
const kinds = [["processing", "Processing"], ["exports", "Exports"], ["forecasts", "Forecasts"], ["model_attempts", "AI attempts"]] as const;

export function UsageRanking({ request }: { request: ApiRequest }) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [generation, setGeneration] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    request<{ workspaces: Row[]; total: number }>("/admin/usage/workspaces?limit=100", { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) { setRows(value.workspaces); setTotal(value.total); setError(""); } })
      .catch(cause => { if (!controller.signal.aborted) { setRows(null); setError(cause instanceof Error ? cause.message : "Usage could not be loaded."); } });
    return () => controller.abort();
  }, [request, generation]);
  return <section className={`panel ${styles.panel}`} aria-label="Workspace usage ranking" aria-busy={rows === null && !error}>
    <div className={styles.header}><div><h2>Usage by workspace</h2><p>Exact admitted operations in each workspace&apos;s current allowance period, highest share of a limit first. Stored data is not opened.</p></div><button type="button" onClick={() => { setRows(null); setError(""); setGeneration(value => value + 1); }}>Refresh usage</button></div>
    {rows === null && !error && <p role="status">Loading usage…</p>}
    {error && <p role="alert" className="errorNotice">{error}</p>}
    {rows && (rows.length ? <div className={styles.tableScroll}><table aria-label="Workspaces by usage"><thead><tr><th scope="col">Workspace</th><th scope="col">Plan</th>{kinds.map(([key, label]) => <th scope="col" key={key}>{label}</th>)}<th scope="col">Closest limit</th></tr></thead>
      <tbody>{rows.map(row => <tr key={row.workspace_id}><th scope="row">{row.name}</th><td>{row.plan_key}{row.active ? "" : " (inactive)"}</td>
        {kinds.map(([key]) => { const value = row.operations[key]; return <td key={key}>{value.used.toLocaleString()}{value.limit === null ? "" : ` / ${value.limit.toLocaleString()}`}{value.state === "ok" ? "" : value.state === "near" ? " · near" : " · reached"}</td>; })}
        <td>{row.highest ? `${usedShare(row.operations[row.highest].used, row.operations[row.highest].limit)} of ${row.highest.replace("_", " ")}` : "No limits"}</td></tr>)}</tbody></table></div>
      : <p>No workspace has a local allowance yet.</p>)}
    {rows && total > rows.length && <p className={styles.caption}>Showing the first {rows.length} of {total} workspaces.</p>}
  </section>;
}
