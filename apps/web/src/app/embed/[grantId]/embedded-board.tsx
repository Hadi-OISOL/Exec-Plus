/* Use case: Presents an authorized saved dashboard without exposing workspace controls.
What it does: Accepts one origin-checked parent message, keeps credentials in memory and clears displayed results on expiry or revoked access. */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnswerVisualization, type VisualizationCell } from "../../workspace/answer-visualization";
import styles from "./embedded-board.module.css";

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Board = {
  board: { name: string; version: number };
  studies: { study: { id: string; name: string }; version: { question: string; method: { column: string; aggregation?: string }; evidence: { component?: string } }; display: { columns: string[]; rows: VisualizationCell[][]; coverage?: { columns: string[]; rows: VisualizationCell[][] } }; results: unknown[]; unit: string; sample_count: number; limitations: string[] }[];
};

export function EmbeddedBoard({ grantId, hostOrigin }: { grantId: string; hostOrigin: string }) {
  const [board, setBoard] = useState<Board | null>(null);
  const [message, setMessage] = useState("Waiting for the approved host to open this private dashboard.");
  const [busy, setBusy] = useState(false);
  const [expiresAt, setExpiresAt] = useState(0);
  const session = useRef("");
  const mounted = useRef(true);
  const controller = useRef<AbortController | null>(null);

  const load = useCallback(async (secret: string, signal: AbortSignal) => {
    const response = await fetch(`${api}/embed/session/board`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_secret: secret, host_origin: hostOrigin }), cache: "no-store", signal });
    if (!response.ok) throw new Error("This private view is no longer available. Ask the owner for a new view.");
    const value: Board = await response.json();
    if (!signal.aborted && mounted.current) { setBoard(value); setMessage(""); }
  }, [hostOrigin]);

  useEffect(() => {
    mounted.current = true;
    let accepted = false;
    const pending = new AbortController();
    controller.current = pending;
    const listener = async (event: MessageEvent) => {
      const value = event.data;
      if (accepted || event.source !== window.parent || event.origin !== hostOrigin || !value || value.type !== "execplus:open" || value.grantId !== grantId || typeof value.secret !== "string" || !/^epb_[A-Za-z0-9_-]{43}$/.test(value.secret)) return;
      accepted = true;
      setBusy(true);
      setMessage("Checking access to this saved dashboard…");
      try {
        const response = await fetch(`${api}/embed/${grantId}/exchange`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ bootstrap_secret: value.secret, host_origin: hostOrigin }), signal: pending.signal, cache: "no-store" });
        if (!response.ok) throw new Error("This one-use link has expired or was already opened. Ask the owner for a new view.");
        const result = await response.json();
        session.current = result.session_secret;
        setExpiresAt(Date.parse(result.expires_at));
        await load(session.current, pending.signal);
      } catch (error) {
        if (!pending.signal.aborted) { session.current = ""; setBoard(null); setMessage(error instanceof Error ? error.message : "This private dashboard could not load."); }
      } finally { if (!pending.signal.aborted) setBusy(false); }
    };
    window.addEventListener("message", listener);
    if (window.parent !== window && hostOrigin) window.parent.postMessage({ type: "execplus:ready", grantId }, hostOrigin);
    return () => { mounted.current = false; pending.abort(); controller.current?.abort(); session.current = ""; window.removeEventListener("message", listener); };
  }, [grantId, hostOrigin, load]);

  useEffect(() => {
    if (!expiresAt) return;
    const timer = window.setTimeout(() => {
      controller.current?.abort(); session.current = ""; setBoard(null); setBusy(false);
      setMessage("This private view has expired. Ask the owner for a new view.");
    }, Math.max(0, expiresAt - Date.now()));
    return () => window.clearTimeout(timer);
  }, [expiresAt]);

  async function refresh() {
    if (!session.current || busy) return;
    setBusy(true);
    const pending = new AbortController();
    controller.current?.abort(); controller.current = pending;
    try { await load(session.current, pending.signal); }
    catch (error) { if (!pending.signal.aborted) { setBoard(null); session.current = ""; setMessage(error instanceof Error ? error.message : "Access could not be checked."); } }
    finally { if (!pending.signal.aborted && mounted.current) setBusy(false); }
  }

  return <main className={styles.frame} aria-busy={busy}>
    <header className={styles.header}><div><p className={styles.eyebrow}>ExecPlus · Private dashboard</p><h1>{board?.board.name ?? "Your saved dashboard"}</h1></div>{board && <button disabled={busy} onClick={() => void refresh()}>{busy ? "Checking access…" : "Refresh access & results"}</button>}</header>
    {message && <p role="status" className={styles.notice}>{message}</p>}
    {board && <><p className={styles.context}>Saved version {board.board.version} · View expires at {new Date(expiresAt).toLocaleTimeString()}. Existing results are shown with their original evidence.</p><div className={styles.cards}>{board.studies.map(value => <section key={value.study.id} className={styles.card}>
      <p className={styles.eyebrow}>Saved study · {value.unit || "Unit not declared"}</p><h2>{value.study.name}</h2><p>{value.version.question}</p>
      <AnswerVisualization title={value.study.name} columns={value.display.columns.map(column => column === "__value" ? `${value.version.method.column} · ${value.unit}` : column)} rows={value.display.rows} initialMode={value.version.evidence.component === "table" ? "table" : "chart"} initialChart={value.version.evidence.component === "line" ? "line" : "bar"} recordsAnalyzed={value.sample_count} />
      {value.limitations.length > 0 && <ul className={styles.notes}>{value.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>}
      {value.display.coverage && <details><summary>Coverage for this study</summary><AnswerVisualization title="Study coverage" {...value.display.coverage} initialMode="table" chartAllowed={false} /></details>}
      <details><summary>Exact calculation evidence</summary><pre className={styles.evidence}>{JSON.stringify(value.results, null, 2)}</pre></details>
    </section>)}</div></>}
  </main>;
}
