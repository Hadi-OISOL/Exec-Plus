/* Use case: Greets the user after upload with a "Your data is ready" card that feels like a team of analysts reporting back.
What it does: Shows file size and a plain summary with primary actions, the dataset purpose (when the server offers it), the top findings with their exact values, each analyst's own live result as it arrives (fetched in parallel), the Trends finding and clickable questions that open chat. */

"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { ApiRequest } from "../profile-panel";
import { Icon } from "../explore-components";
import { actionIntent, analystNames } from "./insights-model";
import type { ActionIntent, InsightCard, InsightsPayload } from "./insights-model";
import styles from "./data-ready.module.css";

type Words = (text: string) => string;
export type RequestStatus = "waiting" | "working" | "done" | "unavailable";
export type DatasetPurpose = {
  version: string;
  summary: string;
  benefits: string[];
  suggested_questions: { title: string; question: string }[];
  profile_question: { question: string; choices: string[] } | null;
};
export type PurposeState = { root: string; status: RequestStatus; payload?: DatasetPurpose };
export type TeamMember = { id: string; name: string; status: RequestStatus; detail: string };

export function purposePath(root: string): string | null {
  const match = /^(\/workspaces\/[^/]+)\/datasets\/[^/]+\/uploads\/([^/]+)$/.exec(root);
  return match ? `${match[1]}/uploads/${match[2]}/dataset-purpose` : null;
}

export async function loadPurpose(root: string, request: ApiRequest, signal?: AbortSignal): Promise<PurposeState> {
  const path = purposePath(root);
  if (!path) return { root, status: "unavailable" };
  try {
    const payload = await request<DatasetPurpose>(path, { signal });
    return payload?.version === "dataset-purpose-v1" ? { root, status: "done", payload: { ...payload, benefits: payload.benefits ?? [], suggested_questions: payload.suggested_questions ?? [] } } : { root, status: "unavailable" };
  } catch {
    return { root, status: "unavailable" };
  }
}

export function useDatasetPurpose(root: string, request: ApiRequest, enabled: boolean): PurposeState {
  const [state, setState] = useState<PurposeState | null>(null);
  useEffect(() => {
    const path = purposePath(root);
    if (!enabled || !path) return;
    const controller = new AbortController();
    void loadPurpose(root, request, controller.signal).then(next => { if (!controller.signal.aborted) setState(next); });
    return () => controller.abort();
  }, [root, request, enabled]);
  if (state?.root === root) return state;
  return { root, status: enabled && purposePath(root) ? "working" : "waiting" };
}

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;

export type AnalystReport = { version: string; analyst: string; insights: InsightCard[]; limitations?: string[] };
export type ReportState = { status: RequestStatus; payload?: AnalystReport };
export type Reports = Record<string, ReportState>;

export async function loadReport(root: string, analyst: string, request: ApiRequest, signal?: AbortSignal): Promise<ReportState> {
  try {
    const payload = await request<AnalystReport>(`${root}/analyst-overview?analyst=${encodeURIComponent(analyst)}`, { signal });
    return payload?.version === "insights-analyst-v1" ? { status: "done", payload: { ...payload, insights: payload.insights ?? [] } } : { status: "unavailable" };
  } catch {
    return { status: "unavailable" };
  }
}

export function useAnalystReports(root: string, request: ApiRequest, enabled: boolean): Reports {
  const [state, setState] = useState<{ root: string; reports: Reports } | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    for (const analyst of Object.keys(analystNames)) {
      void loadReport(root, analyst, request, controller.signal).then(report => {
        if (!controller.signal.aborted) setState(current => ({ root, reports: { ...(current?.root === root ? current.reports : {}), [analyst]: report } }));
      });
    }
    return () => controller.abort();
  }, [root, request, enabled]);
  return state?.root === root ? state.reports : {};
}

export function analystTeam({ reading, insights, reports = {}, dashboard, purpose }: { reading: RequestStatus; insights: { status: RequestStatus; payload?: InsightsPayload }; reports?: Reports; dashboard: RequestStatus; purpose: RequestStatus }): TeamMember[] {
  const detail: Record<RequestStatus, string> = { waiting: "Waiting to start", working: "Working on it…", done: "Done", unavailable: "Not available right now" };
  const cards = insights.payload?.insights ?? [];
  return [
    { id: "reader", name: "File reader", status: reading, detail: reading === "done" ? "Read your columns and starting numbers" : reading === "working" ? "Reading your columns…" : detail[reading] },
    ...Object.entries(analystNames).map(([id, name]) => {
      const report = reports[id];
      const own = report?.status === "done" ? report.payload : undefined;
      const combined = id !== "trend" && insights.status === "done";
      const status: RequestStatus = own || combined ? "done" : report?.status ?? (insights.status === "waiting" ? "waiting" : "working");
      const found = own ? own.insights.length : cards.filter(card => card.analyst === id).length;
      const quiet = (id === "trend" && own?.limitations?.[0]) || "Nothing stood out";
      return { id, name, status, detail: status === "done" ? (found ? `Found ${plural(found, "thing")} worth a look` : quiet) : status === "working" ? "Checking your data…" : detail[status] };
    }),
    { id: "dashboard", name: "Dashboard builder", status: dashboard, detail: dashboard === "working" ? "Building your dashboard…" : dashboard === "done" ? "Your dashboard is ready" : detail[dashboard] },
    { id: "purpose", name: "Purpose guide", status: purpose, detail: purpose === "working" ? "Working out how this data can help you…" : purpose === "done" ? "Suggested how to use this data" : detail[purpose] },
  ];
}

export function topFindings(payload: InsightsPayload | undefined, reports: Reports = {}, limit = 4): InsightCard[] {
  if (!payload) return [];
  return [...(reports.trend?.payload?.insights ?? []), ...payload.insights].slice(0, limit);
}

export function profileAnswer(choice: string): string {
  return `I am ${/^[aeiou]/i.test(choice) ? "an" : "a"} ${choice}`;
}

export function questionChips(purpose: DatasetPurpose | undefined, fallback: string[]): { label: string; question: string }[] {
  const items = purpose?.suggested_questions.length ? purpose.suggested_questions.map(item => ({ label: item.title || item.question, question: item.question })) : fallback.map(question => ({ label: question, question }));
  return items.filter(item => item.question.trim()).slice(0, 6);
}

const statusLabel: Record<RequestStatus, string> = { waiting: "Waiting", working: "Working", done: "Done", unavailable: "Unavailable" };

export function AnalystTeam({ members }: { members: TeamMember[] }) {
  const finished = members.filter(member => member.status === "done" || member.status === "unavailable").length;
  return <section className={styles.team} aria-label="Your analyst team">
    <div className={styles.sectionHead}><h3>Your analyst team</h3><p>{finished === members.length ? "Everyone has reported back." : `${finished} of ${members.length} have reported back.`}</p></div>
    <ul>{members.map(member => <li key={member.id} data-status={member.status}>
      <span className={styles.dot} aria-hidden="true">{member.status === "done" ? <Icon name="check" size={12} /> : null}</span>
      <span className={styles.member}><strong>{member.name}</strong><span>{member.detail}</span></span>
      <span className={styles.state}>{statusLabel[member.status]}</span>
    </li>)}</ul>
  </section>;
}

function FindingRow({ card, index, words, onAction, onSee }: { card: InsightCard; index: number; words: Words; onAction: (intent: ActionIntent) => void; onSee: (id: string) => void }) {
  const evidence = card.evidence?.[0];
  const action = (card.actions ?? []).find(item => actionIntent(item));
  return <li>
    <span className={styles.rank} aria-hidden="true">{index + 1}</span>
    <div className={styles.finding}>
      <strong>{words(card.title)}</strong>
      <span>{words(card.summary)}</span>
      {evidence && <span className={styles.exact}>{words(evidence.label)}: <b>{evidence.value}{evidence.unit ? ` ${evidence.unit}` : ""}</b></span>}
      <div className={styles.findingActions}>
        {action && <button type="button" className={styles.chip} onClick={() => onAction(actionIntent(action)!)}>{words(action.label)}<Icon name="arrow" size={13} /></button>}
        <button type="button" className={styles.link} onClick={() => onSee(card.id)}>See the evidence</button>
      </div>
    </div>
  </li>;
}

export function DataReady({ fileName, rows, columns, seconds, summary, confirmed, purpose, insights, reports = {}, team, questions, words, onAsk, onDashboard, onReview, onQuestion, onAction, onSee, checks }: {
  fileName: string; rows: number; columns: number; seconds: string | null; summary: string; confirmed: boolean;
  purpose?: DatasetPurpose; insights: { status: RequestStatus; payload?: InsightsPayload }; reports?: Reports; team: TeamMember[]; questions: { label: string; question: string }[];
  words: Words; onAsk: () => void; onDashboard: () => void; onReview: () => void; onQuestion: (question: string) => void; onAction: (intent: ActionIntent) => void; onSee: (id: string) => void; checks?: ReactNode;
}) {
  const findings = topFindings(insights.payload, reports);
  const analysts = team.filter(member => member.id in analystNames);
  const reported = analysts.filter(member => member.status === "done" || member.status === "unavailable").length;
  return <div className={styles.ready}>
    <header className={styles.hero}>
      <span className={styles.mark} aria-hidden="true"><Icon name="check" size={20} /></span>
      <div className={styles.heroText}>
        <span className={styles.overline}>Your data is ready</span>
        <h2 className="discoveryFilename">{fileName}</h2>
        <p className={styles.meta}>{rows.toLocaleString()} rows × {columns.toLocaleString()} columns{seconds ? ` · first reading in ${seconds} s` : ""} · {confirmed ? "meanings confirmed" : "meanings not confirmed yet"}</p>
        <p className={styles.summary}>{words(purpose?.summary || summary)}</p>
      </div>
      <div className={styles.actions}>
        <button type="button" className={styles.primary} onClick={onAsk}><Icon name="chat" size={16} />Ask Syntelio</button>
        <button type="button" className={styles.secondary} onClick={onDashboard}><Icon name="studies" size={16} />See dashboard</button>
        <button type="button" className={styles.secondary} onClick={onReview}><Icon name="check" size={16} />Review meanings</button>
      </div>
    </header>
    {purpose && (purpose.benefits.length > 0 || purpose.profile_question) && <section className={styles.purpose} aria-label="How this data can help you">
      {purpose.benefits.length > 0 && <><h3>How this data can help you</h3><ul>{purpose.benefits.map((item, index) => <li key={index}>{words(item)}</li>)}</ul></>}
      {Boolean(purpose.profile_question?.choices?.length) && purpose.profile_question && <div className={styles.profile} role="group" aria-label={purpose.profile_question.question}>
        <p>{purpose.profile_question.question}</p>
        <div className={styles.chips}>{purpose.profile_question.choices.map(choice => <button key={choice} type="button" className={styles.chip} onClick={() => onQuestion(profileAnswer(choice))}>{choice}</button>)}</div>
      </div>}
    </section>}
    <div className={styles.columns}>
      <div className={styles.main}>
        <section className={styles.know} aria-label="What you should know" aria-busy={insights.status === "working"}>
          <div className={styles.sectionHead}><h3>What you should know</h3><p>{insights.status === "working" ? `${reported} of ${analysts.length} analysts have reported. The most important findings appear here once all are in, each double-checked.` : findings.length ? "The most important findings, each recalculated by an independent check." : insights.status === "done" ? "Nothing stood out strongly yet. Ask a question to dig deeper." : "Findings are not available right now. The numbers below still come from your file."}</p></div>
          {findings.length > 0 && <ol>{findings.map((card, index) => <FindingRow key={card.id} card={card} index={index} words={words} onAction={onAction} onSee={onSee} />)}</ol>}
        </section>
        {checks}
        {questions.length > 0 && <section className={styles.questions} aria-label="Questions you could ask">
          <h3>Questions you could ask</h3>
          <div className={styles.chips}>{questions.map(item => <button key={item.question} type="button" className={styles.chip} title={item.question} onClick={() => onQuestion(item.question)}>{words(item.label)}<Icon name="arrow" size={13} /></button>)}</div>
        </section>}
      </div>
      <AnalystTeam members={team} />
    </div>
  </div>;
}
