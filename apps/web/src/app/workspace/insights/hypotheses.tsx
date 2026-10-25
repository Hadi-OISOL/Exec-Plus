/* Use case: Shows "Things we checked for you": candidate statements the server tested on the upload.
What it does: Loads hypotheses-v1, lists supported checks first with their exact figures, an "Ask about this" question and a private useful/not-useful vote (clicking the same vote again clears it), and keeps the rest in a collapsed list. */

"use client";

import { useCallback, useEffect, useState } from "react";
import type { ApiRequest } from "../profile-panel";
import shared from "./data-ready.module.css";
import styles from "./hypotheses.module.css";

type Words = (text: string) => string;
export type Vote = "like" | "dislike";
export type Reason = "too_obvious" | "not_relevant" | "wrong_measure";
export type Hypothesis = {
  id: string; kind: string; origin: string; statement: string; status: "supported" | "not_supported" | "not_enough_data";
  finding: string; evidence: Record<string, string | null>; question: string; feedback: Vote | null;
};
export type HypothesesPayload = { version: string; items: Hypothesis[]; limitations: string[] };
export type HypothesesState = { root: string; status: "working" | "done" | "unavailable"; payload?: HypothesesPayload };

const hidden = new Set(["rule", "note", "query_id"]);
const reasons: { id: Reason; label: string }[] = [
  { id: "too_obvious", label: "Too obvious" },
  { id: "not_relevant", label: "Not relevant" },
  { id: "wrong_measure", label: "Wrong measure" },
];

export function hypothesesPath(root: string): { list: string; feedback: string } | null {
  const match = /^(\/workspaces\/[^/]+)\/datasets\/[^/]+\/uploads\/([^/]+)$/.exec(root);
  return match ? { list: `${match[1]}/uploads/${match[2]}/hypotheses`, feedback: `${match[1]}/hypothesis-feedback` } : null;
}

export async function loadHypotheses(root: string, request: ApiRequest, signal?: AbortSignal): Promise<HypothesesState> {
  const path = hypothesesPath(root);
  if (!path) return { root, status: "unavailable" };
  try {
    const payload = await request<HypothesesPayload>(path.list, { signal });
    return payload?.version === "hypotheses-v1" ? { root, status: "done", payload: { ...payload, items: payload.items ?? [], limitations: payload.limitations ?? [] } } : { root, status: "unavailable" };
  } catch {
    return { root, status: "unavailable" };
  }
}

export function withVote(items: Hypothesis[], kind: string, vote: Vote | null): Hypothesis[] {
  const rank = (item: Hypothesis) => (item.feedback === "like" ? 0 : item.feedback === "dislike" ? 2 : 1);
  return items.map(item => (item.kind === kind ? { ...item, feedback: vote } : item)).map((item, index) => ({ item, index }))
    .sort((a, b) => rank(a.item) - rank(b.item) || a.index - b.index).map(entry => entry.item);
}

export function evidenceRows(item: Hypothesis): [string, string][] {
  return Object.entries(item.evidence).filter((entry): entry is [string, string] => !hidden.has(entry[0]) && typeof entry[1] === "string" && entry[1] !== "")
    .map(([key, value]) => [key.replaceAll("_", " "), value]);
}

function Check({ item, words, onQuestion, onVote }: { item: Hypothesis; words: Words; onQuestion: (question: string) => void; onVote: (item: Hypothesis, vote: Vote, reason?: Reason) => void }) {
  const [asking, setAsking] = useState(false);
  const vote = (next: Vote) => { onVote(item, next); setAsking(next === "dislike" && item.feedback !== "dislike"); };
  return <li data-status={item.status}>
    <strong>{words(item.statement)}</strong>
    <span>{words(item.finding)}</span>
    <dl className={styles.evidence}>{evidenceRows(item).map(([label, value]) => <div key={label}><dt>{words(label)}</dt><dd>{value}</dd></div>)}</dl>
    {item.evidence.rule && <small className={styles.rule}>{words(item.evidence.rule)}</small>}
    <div className={shared.findingActions}>
      <button type="button" className={shared.chip} onClick={() => onQuestion(item.question)}>Ask about this</button>
      <span className={styles.votes} role="group" aria-label="Is this check useful?">
        <button type="button" className={styles.vote} aria-pressed={item.feedback === "like"} onClick={() => vote("like")}>Useful</button>
        <button type="button" className={styles.vote} aria-pressed={item.feedback === "dislike"} onClick={() => vote("dislike")}>Not useful</button>
      </span>
    </div>
    {asking && <div className={styles.reasons} role="group" aria-label="Why is this not useful?">
      <span>Why?</span>
      {reasons.map(reason => <button key={reason.id} type="button" className={shared.chip} onClick={() => { onVote(item, "dislike", reason.id); setAsking(false); }}>{reason.label}</button>)}
    </div>}
  </li>;
}

export function HypothesisList({ items, limitations, words, onQuestion, onVote }: { items: Hypothesis[]; limitations: string[]; words: Words; onQuestion: (question: string) => void; onVote: (item: Hypothesis, vote: Vote, reason?: Reason) => void }) {
  const supported = items.filter(item => item.status === "supported");
  const rest = items.filter(item => item.status !== "supported");
  return <section className={shared.know} aria-label="Things we checked for you">
    <div className={shared.sectionHead}><h3>Things we checked for you</h3><p>{supported.length ? "These held up when we tested them on your rows. A pattern here is not proof of a cause." : "None of the ideas we tested held up clearly in your rows."}</p></div>
    {supported.length > 0 && <ul className={styles.list}>{supported.map(item => <Check key={item.id} item={item} words={words} onQuestion={onQuestion} onVote={onVote} />)}</ul>}
    {rest.length > 0 && <details className={styles.rest}>
      <summary>Not supported or not enough data ({rest.length})</summary>
      <ul className={styles.list}>{rest.map(item => <Check key={item.id} item={item} words={words} onQuestion={onQuestion} onVote={onVote} />)}</ul>
    </details>}
    {limitations.length > 0 && <p className={styles.rule}>{limitations.map(words).join(" ")}</p>}
  </section>;
}

export function HypothesisChecks({ root, request, enabled, words, onQuestion }: { root: string; request: ApiRequest; enabled: boolean; words: Words; onQuestion: (question: string) => void }) {
  const [state, setState] = useState<HypothesesState | null>(null);
  useEffect(() => {
    if (!enabled || !hypothesesPath(root)) return;
    const controller = new AbortController();
    void loadHypotheses(root, request, controller.signal).then(next => { if (!controller.signal.aborted) setState(next); });
    return () => controller.abort();
  }, [root, request, enabled]);
  const vote = useCallback((item: Hypothesis, next: Vote, reason?: Reason) => {
    const path = hypothesesPath(root);
    if (!path) return;
    const cleared = !reason && item.feedback === next;
    setState(current => current?.payload ? { ...current, payload: { ...current.payload, items: withVote(current.payload.items, item.kind, cleared ? null : next) } } : current);
    void request(path.feedback, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: item.kind, vote: next, ...(reason ? { reason } : {}) }) }).catch(() => undefined);
  }, [root, request]);
  const current = state?.root === root ? state : null;
  if (!current?.payload || current.payload.items.length === 0) return null;
  return <HypothesisList items={current.payload.items} limitations={current.payload.limitations} words={words} onQuestion={onQuestion} onVote={vote} />;
}
