/* Use case: Asks a few short questions about this file after it is read, so the next answers follow what the person cares about.
What it does: Shows the server's dataset-focus-v1 questions as clickable choices or short text, saves the private answers (or a skip) and then shows them back as a small receipt with a way to change them. */

"use client";

import { useState } from "react";
import type { ApiRequest } from "../profile-panel";
import styles from "./data-ready.module.css";

type Words = (text: string) => string;
export type FollowUpQuestion = { id: string; prompt: string; kind: "single" | "text"; options: string[]; hint?: string };
export type FollowUp = { version: string; questions: FollowUpQuestion[]; answers: Record<string, string>; status: "pending" | "completed" | "skipped" };

export function focusPath(root: string): string | null {
  const match = /^(\/workspaces\/[^/]+)\/datasets\/[^/]+\/uploads\/([^/]+)$/.exec(root);
  return match ? `${match[1]}/uploads/${match[2]}/dataset-focus` : null;
}

export function validAnswers(followUp: FollowUp, answers: Record<string, string> = followUp.answers): Record<string, string> {
  const kept: Record<string, string> = {};
  for (const question of followUp.questions) {
    const value = answers[question.id]?.trim();
    if (value && (question.kind === "text" || question.options.includes(value))) kept[question.id] = value;
  }
  return kept;
}

export function answeredRows(followUp: FollowUp): { prompt: string; value: string }[] {
  const answers = validAnswers(followUp);
  return followUp.questions.filter(question => answers[question.id]).map(question => ({ prompt: question.prompt, value: answers[question.id] }));
}

export function FollowUpQuestions({ followUp, root, request, words, onSaved }: { followUp: FollowUp; root: string; request: ApiRequest; words: Words; onSaved: (saved: FollowUp) => void }) {
  const [answers, setAnswers] = useState<Record<string, string>>(() => validAnswers(followUp));
  const [editing, setEditing] = useState(followUp.status === "pending");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const path = focusPath(root);
  if (!path || !followUp.questions.length) return null;
  const rows = answeredRows(followUp);

  async function save(status: "completed" | "skipped") {
    setBusy(true);
    setError("");
    try {
      const saved = await request<FollowUp>(path!, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers: status === "completed" ? validAnswers(followUp, answers) : validAnswers(followUp), status }) });
      setEditing(false);
      onSaved(saved);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Your answers could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  const set = (id: string, value: string) => setAnswers(current => ({ ...current, [id]: current[id] === value ? "" : value }));
  if (!editing) {
    return <section className={styles.followUp} aria-label="Your focus for this file">
      <div className={styles.sectionHead}><h3>Your focus for this file</h3><p>{rows.length ? "Insights, suggested questions and the dashboard follow these answers. Only you can see them." : "You skipped the questions. Answers stay as they were before."}</p></div>
      {rows.length > 0 && <dl className={styles.focusRows}>{rows.map(row => <div key={row.prompt}><dt>{row.prompt}</dt><dd>{words(row.value)}</dd></div>)}</dl>}
      <div><button type="button" className={styles.link} onClick={() => { setAnswers(validAnswers(followUp)); setEditing(true); }}>{rows.length ? "Change answers" : "Answer the questions"}</button></div>
    </section>;
  }
  return <section className={styles.followUp} aria-label="A few questions about this file">
    <div className={styles.sectionHead}><h3>A few questions about this file</h3><p>So the next answers follow what matters to you. Skip any of them; your answers stay private to you.</p></div>
    <ol className={styles.askList}>{followUp.questions.map((question, index) => <li key={question.id}>
      <span className={styles.rank} aria-hidden="true">{index + 1}</span>
      <div className={styles.ask} role="group" aria-label={question.prompt}>
        <p>{question.prompt}</p>
        {question.kind === "text" && <input className={styles.answerInput} aria-label={question.prompt} value={answers[question.id] ?? ""} maxLength={120} placeholder={question.hint || "Type a short answer"} onChange={event => setAnswers(current => ({ ...current, [question.id]: event.target.value }))} />}
        {question.options.length > 0 && <div className={styles.chips}>{question.options.map(option => <button key={option} type="button" className={styles.chip} aria-pressed={answers[question.id] === option} onClick={() => set(question.id, option)}>{words(option)}</button>)}</div>}
      </div>
    </li>)}</ol>
    {error && <p className={styles.error} role="alert">{error}</p>}
    <div className={styles.actions}>
      <button type="button" className={styles.primary} disabled={busy} onClick={() => void save("completed")}>{busy ? "Saving…" : "Save my answers"}</button>
      <button type="button" className={styles.secondary} disabled={busy} onClick={() => void save("skipped")}>Skip for now</button>
    </div>
  </section>;
}
