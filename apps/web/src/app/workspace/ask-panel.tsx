/* Use case: Provides a conversation with grounded answers about the selected upload.
What it does: Keeps paired turns, renders exact results and record tables, and exposes execution evidence. */

import { useEffect, useImperativeHandle, useRef, useState } from "react";
import type { Ref } from "react";
import { Icon, RecordTable } from "./explore-components";
import type { Cell } from "./explore-components";
import { SaveControl } from "./saved-panel";
import type { ApiRequest } from "./profile-panel";
import { ConversationEvidence } from "./conversation-evidence";
import type { Citation } from "./conversation-evidence";
import { ConversationActivity } from "./conversation-activity";
import {
  isTerminalJob,
  mergeJobEvents,
  pollPause,
  reconcileJob,
} from "./conversation-job";
import type { ConversationJob, JobEvent, JobEvents } from "./conversation-job";

type Lineage = {
  query_id: string;
  metric: string;
  aggregation: string;
  records_analyzed: number;
  sql: string;
  filters: string[];
  model_route: string | null;
  receipt?: { sources: { revision_id: string; understanding_id?: string }[] };
};
type Answer = {
  kind?: string;
  message?: string;
  label?: string;
  value?: string | number;
  columns?: string[];
  rows?: Cell[][];
  records_analyzed?: number;
  matched_records?: number | null;
  lineage?: Lineage;
  data?: Answer | null;
  citations?: Citation[];
  limitations?: string[];
  coverage?: string;
  guidance?: {
    columns: string[];
    suggestions: string[];
    definition_state: string;
  };
  sources?: { revision_id: string; understanding_id?: string }[];
};
type Turn = {
  id: number | string;
  question: string;
  answer: Answer | null;
  message: string;
  failed?: boolean;
  requestId?: string;
  serverId?: string;
  status?: string;
  jobId?: string;
  job?: ConversationJob;
  events?: JobEvent[];
  unavailable?: boolean;
};
type History = { id: string; created_at: string };
type SavedTurn = {
  id: string;
  question: string;
  kind: string;
  message: string | null;
  request_id: string | null;
  status: string;
  job_id?: string | null;
};
type JobResult = { turn: SavedTurn; answer: Answer | null };
const flatten = (answer: Answer | null): Answer | null =>
  answer?.data ? { ...answer, ...answer.data, data: undefined } : answer;
function requestIdentifier(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20),
  ].join("-");
}
export type ChatHandle = { ask: (question: string) => void; focus: () => void };
const post = (body: object): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export function AskPanel({
  root,
  request,
  filename,
  starterQuestions = [],
  expert = false,
  ref,
}: {
  root: string;
  request: ApiRequest;
  filename: string;
  starterQuestions?: string[];
  expert?: boolean;
  ref?: Ref<ChatHandle>;
}) {
  const [threadId, setThreadId] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<History[]>([]);
  const [selectedThread, setSelectedThread] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [activeJob, setActiveJob] = useState<ConversationJob | null>(null);
  const [activityEvents, setActivityEvents] = useState<JobEvent[]>([]);
  const [cancelPending, setCancelPending] = useState(false);
  const [cancelError, setCancelError] = useState("");
  const serial = useRef(0);
  const inFlight = useRef(false);
  const operation = useRef<AbortController | null>(null);
  const lastActivity = useRef<{
    job: ConversationJob;
    events: JobEvent[];
  } | null>(null);
  const conversation = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const workspaceRoot = root.split("/datasets/")[0];

  useEffect(() => () => operation.current?.abort(), [root, request]);

  function beginOperation() {
    const controller = new AbortController();
    operation.current = controller;
    inFlight.current = true;
    lastActivity.current = null;
    setBusy(true);
    setCancelError("");
    setCancelPending(false);
    return controller;
  }

  function finishOperation(controller: AbortController) {
    if (controller.signal.aborted || operation.current !== controller) return;
    controller.abort();
    operation.current = null;
    inFlight.current = false;
    setBusy(false);
    setPending("");
    setActiveJob(null);
    setCancelPending(false);
    input.current?.focus({ preventScroll: true });
  }

  async function observeJob(
    initial: ConversationJob,
    turn: Turn,
    controller: AbortController,
  ) {
    let events: JobEvent[] = [];
    let sequence = 0;
    setActiveJob(initial);
    setActivityEvents(events);
    lastActivity.current = { job: initial, events };
    const path = `${workspaceRoot}/jobs/${initial.id}`;
    while (!controller.signal.aborted) {
      const [observedJob, activity] = await Promise.all([
        request<ConversationJob>(path, { signal: controller.signal }),
        request<JobEvents>(`${path}/events?after=${sequence}`, {
          signal: controller.signal,
        }),
      ]);
      if (controller.signal.aborted) return;
      const job = reconcileJob(lastActivity.current?.job, observedJob);
      events = mergeJobEvents(events, activity.events);
      sequence = Math.max(sequence, activity.next_sequence);
      lastActivity.current = { job, events };
      setActiveJob(job);
      setActivityEvents(events);
      if (isTerminalJob(job)) {
        const finalActivity = await request<JobEvents>(
          `${path}/events?after=${sequence}`,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        events = mergeJobEvents(events, finalActivity.events);
        lastActivity.current = { job, events };
        const result = await request<JobResult>(`${path}/result`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setTurns((previous) => [
          ...previous.filter((item) => item.id !== turn.id),
          {
            ...turn,
            serverId: result.turn.id,
            status: result.turn.status,
            answer: flatten(result.answer),
            message: result.turn.message ?? "",
            failed: ["failed", "expired"].includes(job.status),
            jobId: job.id,
            job,
            events,
          },
        ]);
        return;
      }
      await pollPause(controller.signal, document.hidden ? 3000 : 1000);
    }
  }

  function interruptedTurn(turn: Turn, cause: unknown) {
    const status = (cause as { status?: number })?.status;
    const unavailable = status === 401 || status === 403 || status === 404;
    const activity = lastActivity.current;
    setTurns((previous) => [
      ...previous.filter((item) => item.id !== turn.id),
      {
        ...turn,
        failed: true,
        unavailable,
        jobId: activity?.job.id ?? turn.jobId,
        job: activity?.job,
        events: activity?.events,
        message:
          unavailable || (status && !activity)
            ? cause instanceof Error
              ? cause.message
              : "This request is unavailable."
            : "The connection was interrupted. Your request may still be running. Resume or check the same request before starting another.",
      },
    ]);
  }

  async function cancelJob() {
    const job = activeJob;
    const controller = operation.current;
    if (!job || !controller || cancelPending || isTerminalJob(job)) return;
    setCancelPending(true);
    setCancelError("");
    try {
      const result = await request<ConversationJob>(
        `${workspaceRoot}/jobs/${job.id}/cancel`,
        {
          method: "POST",
          signal: controller.signal,
        },
      );
      if (!controller.signal.aborted) {
        const current = reconcileJob(lastActivity.current?.job, result);
        lastActivity.current = {
          job: current,
          events: lastActivity.current?.events ?? [],
        };
        setActiveJob(current);
      }
    } catch (cause) {
      if (!controller.signal.aborted) {
        setCancelPending(false);
        setCancelError(
          cause instanceof Error
            ? cause.message
            : "Cancellation could not be requested. The request may still be running.",
        );
      }
    }
  }

  useEffect(() => {
    let active = true;
    request<History[]>(`${root}/threads`)
      .then((items) => {
        if (active) setHistory(items);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [root, request, threadId]);

  async function openHistory() {
    if (!selectedThread || inFlight.current) return;
    const controller = beginOperation();
    setHistoryError("");
    try {
      const result = await request<{ turns: SavedTurn[] }>(
        `${workspaceRoot}/threads/${selectedThread}`,
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      setThreadId(selectedThread);
      const savedTurns: Turn[] = result.turns.map((turn) => ({
        id: turn.id,
        serverId: turn.id,
        requestId: turn.request_id ?? undefined,
        status: turn.status,
        jobId: turn.job_id ?? undefined,
        question: turn.question,
        answer: null,
        failed: turn.status === "failed",
        message:
          turn.message ??
          (turn.status === "running"
            ? "This request is still running."
            : "Saved answer — load its evidence below."),
      }));
      setTurns(savedTurns);
      const running = savedTurns.find(
        (turn) => turn.status === "running" && turn.jobId,
      );
      if (running) {
        setPending(running.question);
        setTurns(savedTurns.filter((turn) => turn.id !== running.id));
        try {
          const job = await request<ConversationJob>(
            `${workspaceRoot}/jobs/${running.jobId}`,
            { signal: controller.signal },
          );
          if (!controller.signal.aborted)
            await observeJob(job, running, controller);
        } catch (cause) {
          if (!controller.signal.aborted) interruptedTurn(running, cause);
        }
      }
    } catch (cause) {
      if (!controller.signal.aborted)
        setHistoryError(
          cause instanceof Error ? cause.message : "Conversation unavailable.",
        );
    } finally {
      finishOperation(controller);
    }
  }

  async function loadAnswer(turn: Turn) {
    if (!turn.serverId || inFlight.current) return;
    const controller = beginOperation();
    try {
      const answer = await request<Answer | null>(
        `${workspaceRoot}/threads/${threadId}/turns/${turn.serverId}/answer`,
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      const activity = turn.jobId
        ? await request<JobEvents>(
            `${workspaceRoot}/jobs/${turn.jobId}/events?after=0`,
            { signal: controller.signal },
          )
        : null;
      const job = turn.jobId
        ? await request<ConversationJob>(
            `${workspaceRoot}/jobs/${turn.jobId}`,
            { signal: controller.signal },
          )
        : null;
      if (controller.signal.aborted) return;
      setTurns((items) =>
        items.map((item) =>
          item.id === turn.id
            ? {
                ...item,
                answer: flatten(answer),
                job: job ?? undefined,
                events: activity?.events,
                message: answer
                  ? "Reopened historical evidence. A follow-up will check for source changes."
                  : item.message,
              }
            : item,
        ),
      );
    } catch (cause) {
      if (controller.signal.aborted) return;
      setTurns((items) =>
        items.map((item) =>
          item.id === turn.id
            ? {
                ...item,
                failed: true,
                message:
                  cause instanceof Error
                    ? cause.message
                    : "The evidence is unavailable.",
              }
            : item,
        ),
      );
    } finally {
      finishOperation(controller);
    }
  }

  useEffect(() => {
    if (conversation.current)
      conversation.current.scrollTop = conversation.current.scrollHeight;
  }, [turns, pending]);

  async function ask(text: string, retry?: Turn) {
    if (inFlight.current || !text.trim()) return;
    const controller = beginOperation();
    setPending(text);
    setQuestion("");
    const id = retry?.id ?? ++serial.current;
    const requestId = retry?.requestId ?? requestIdentifier();
    const turn: Turn = {
      id,
      question: text,
      requestId,
      answer: null,
      message: "",
      jobId: retry?.jobId,
    };
    if (retry) setTurns((items) => items.filter((item) => item.id !== id));
    try {
      if (retry?.jobId) {
        const job = await request<ConversationJob>(
          `${workspaceRoot}/jobs/${retry.jobId}`,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted) await observeJob(job, turn, controller);
        return;
      }
      const thread =
        threadId ||
        (
          await request<{ id: string }>(`${root}/threads`, {
            method: "POST",
            signal: controller.signal,
          })
        ).id;
      if (controller.signal.aborted) return;
      setThreadId(thread);
      const job = await request<ConversationJob>(
        `${workspaceRoot}/threads/${thread}/jobs`,
        {
          ...post({ question: text, request_id: requestId }),
          signal: controller.signal,
        },
      );
      if (!controller.signal.aborted) await observeJob(job, turn, controller);
    } catch (cause) {
      if (controller.signal.aborted) return;
      interruptedTurn(turn, cause);
      setQuestion(text);
    } finally {
      finishOperation(controller);
    }
  }
  useImperativeHandle(ref, () => ({
    focus: () => {
      input.current?.scrollIntoView({
        block: "center",
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
      input.current?.focus({ preventScroll: true });
    },
    ask: (text) => {
      input.current?.scrollIntoView({
        block: "center",
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
      void ask(text);
    },
  }));

  async function generateSummary() {
    if (inFlight.current) return;
    const controller = beginOperation();
    setPending("Summarize the verified insights");
    const id = ++serial.current;
    try {
      const result = await request<{ summary: string }>(
        `${root}/dashboard/summary`,
        { ...post({ filters: [] }), signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      setTurns((previous) => [
        ...previous,
        {
          id,
          question: "Summarize the verified insights",
          answer: null,
          message: result.summary,
        },
      ]);
    } catch (cause) {
      if (controller.signal.aborted) return;
      setTurns((previous) => [
        ...previous,
        {
          id,
          question: "Summarize the verified insights",
          answer: null,
          message:
            cause instanceof Error
              ? cause.message
              : "Could not generate a summary.",
          failed: true,
        },
      ]);
    } finally {
      finishOperation(controller);
    }
  }

  return (
    <section className="panel askPanel" aria-label="Ask a question">
      <header className="chatHeader">
        <div className="assistantAvatar">
          <Icon name="sparkle" />
        </div>
        <div>
          <h2>Ask ExecPlus</h2>
          <span>Your data, in conversation</span>
        </div>
        <button
          className="quietButton"
          type="button"
          title="Start a new conversation"
          disabled={busy}
          onClick={() => {
            setThreadId("");
            setTurns([]);
            setQuestion("");
          }}
        >
          New conversation
        </button>
      </header>
      <details className="conversationHistory">
        <summary>Private conversation history</summary>
        <p>
          Only your conversations for this upload appear here. Reopened answers
          retain their original sources and definitions.
        </p>
        <label>
          Saved conversation
          <select
            value={selectedThread}
            onChange={(event) => setSelectedThread(event.target.value)}
          >
            <option value="">Choose a conversation</option>
            {history.map((item) => (
              <option key={item.id} value={item.id}>
                {new Date(item.created_at).toLocaleString()}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={busy || !selectedThread}
          onClick={() => void openHistory()}
        >
          Open conversation
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            request<History[]>(`${root}/threads`)
              .then(setHistory)
              .catch((cause) => setHistoryError(cause.message))
          }
        >
          Refresh history
        </button>
        {historyError && <p role="alert">{historyError}</p>}
      </details>
      <div className="chatSource">
        <span className="liveDot" />
        <span>{filename}</span>
        <span>Selected file</span>
      </div>
      <div
        className="conversationLog"
        ref={conversation}
        role="log"
        aria-label="Conversation"
        aria-live="polite"
        aria-relevant="additions text"
      >
        <div className="assistantMessage welcomeMessage">
          <span className="messageAuthor">ExecPlus</span>
          <h3>What would you like to discover?</h3>
          <p>
            You’re exploring <strong>{filename}</strong>. Ask what a column
            means, find specific records, or explore one of the findings
            alongside this conversation.
          </p>
          <p className="chatHint">
            You don’t need to know the right query. Start with what you want to
            understand.
          </p>
        </div>
        {!turns.length && (
          <div className="suggestionChips">
            {[
              ...new Set([
                "Help me understand my data",
                ...starterQuestions.slice(0, 2),
                "Show the first 10 records",
              ]),
            ].map((item) => (
              <button
                type="button"
                key={item}
                disabled={busy}
                onClick={() => void ask(item)}
              >
                {item}
                <Icon name="arrow" size={14} />
              </button>
            ))}
          </div>
        )}
        {turns.map((turn) => (
          <article className="conversationTurn" key={turn.id}>
            <div className="userMessage">
              <span className="messageAuthor">You</span>
              <p>{turn.question}</p>
            </div>
            <div className="assistantMessage">
              <span className="messageAuthor">
                ExecPlus{" "}
                {turn.answer?.lineage && (
                  <span className="verifiedBadge">
                    <Icon name="check" size={12} /> Verified
                  </span>
                )}
              </span>
              {turn.answer?.guidance ? (
                <div className="datasetGuidance" aria-label="Data explanation">
                  {turn.answer.message
                    ?.split("\n\n")
                    .map((paragraph, index) => (
                      <p key={index}>{paragraph}</p>
                    ))}
                  <div
                    className="suggestionChips"
                    aria-label="Explore this explanation"
                  >
                    {turn.answer.guidance.suggestions.map((suggestion) => (
                      <button
                        key={suggestion}
                        type="button"
                        disabled={busy}
                        onClick={() => void ask(suggestion)}
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                  <details className="answerEvidence" open={expert}>
                    <summary>What this explanation is based on</summary>
                    <p>
                      Selected-file profile and saved workspace definitions.
                      Naming-based interpretations are tentative.
                    </p>
                    <p>
                      Definition status:{" "}
                      {turn.answer.guidance.definition_state.replaceAll(
                        "_",
                        " ",
                      )}
                    </p>
                    {turn.answer.sources?.map((source) => (
                      <p key={source.revision_id}>
                        Source revision: {source.revision_id}
                        {source.understanding_id
                          ? ` · Definition version: ${source.understanding_id}`
                          : ""}
                      </p>
                    ))}
                  </details>
                </div>
              ) : turn.answer?.message ? (
                <p>{turn.answer.message}</p>
              ) : (
                turn.message && (
                  <p
                    role={turn.failed ? "alert" : undefined}
                    className={turn.failed ? "errorNotice" : undefined}
                  >
                    {turn.message}
                  </p>
                )
              )}
              {turn.answer?.value !== undefined && (
                <div className="answerCard">
                  <span className="kpiLabel">{turn.answer.label}</span>
                  <strong className="kpiValue">
                    {String(turn.answer.value).replace(
                      /(\.\d*?[1-9])0+$|\.0+$/,
                      "$1",
                    )}
                  </strong>
                </div>
              )}
              {turn.status === "partial" && (
                <p role="status" className="errorNotice">
                  Partial answer — review the limitations below.
                </p>
              )}
              {turn.answer?.citations && (
                <ConversationEvidence
                  citations={turn.answer.citations}
                  limitations={turn.answer.limitations ?? []}
                  coverage={turn.answer.coverage ?? "missing"}
                  request={request}
                />
              )}
              {turn.serverId &&
                !turn.answer &&
                ["complete", "partial"].includes(turn.status ?? "") && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void loadAnswer(turn)}
                  >
                    Load saved answer
                  </button>
                )}
              {turn.failed &&
                !turn.unavailable &&
                turn.requestId &&
                (!turn.job || !isTerminalJob(turn.job)) && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void ask(turn.question, turn)}
                  >
                    {turn.jobId
                      ? "Resume activity"
                      : "Check or retry this request"}
                  </button>
                )}
              {turn.failed &&
                turn.job &&
                isTerminalJob(turn.job) &&
                !turn.unavailable && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void ask(turn.question)}
                  >
                    Try as a new request
                  </button>
                )}
              {turn.answer?.rows && (
                <>
                  <p>
                    {turn.answer.lineage?.aggregation === "rows"
                      ? "Here are the matching records."
                      : "Here's the breakdown."}
                  </p>
                  <RecordTable
                    data={{
                      columns: turn.answer.columns ?? [],
                      rows: turn.answer.rows,
                      records_analyzed: turn.answer.records_analyzed ?? 0,
                      matched_records: turn.answer.matched_records,
                    }}
                  />
                </>
              )}
              {turn.answer?.lineage && (
                <>
                  <span className="kpiFootnote">
                    Checked against{" "}
                    {turn.answer.lineage.records_analyzed.toLocaleString()}{" "}
                    source records
                  </span>
                  <details className="answerEvidence" open={expert}>
                    <summary>How this answer was verified</summary>
                    <p>
                      {turn.answer.lineage.filters.length
                        ? turn.answer.lineage.filters.join("; ")
                        : "All source records included."}
                    </p>
                    <code>{turn.answer.lineage.sql}</code>
                    <p>
                      Model route:{" "}
                      {turn.answer.lineage.model_route ?? "Structured query"}
                    </p>
                    {turn.answer.lineage.receipt?.sources.map((source) => (
                      <p key={source.revision_id}>
                        Source revision: {source.revision_id}
                        {source.understanding_id
                          ? ` · Confirmed definition: ${source.understanding_id}`
                          : " · Profile-based interpretation"}
                      </p>
                    ))}
                    <SaveControl
                      root={root}
                      request={request}
                      kind="analysis"
                      payload={{ query_id: turn.answer.lineage.query_id }}
                      name="conversation result"
                    />
                  </details>
                </>
              )}
              {turn.job && (
                <details className="answerEvidence" open={expert}>
                  <summary>Request activity</summary>
                  <ConversationActivity
                    job={turn.job}
                    events={turn.events ?? []}
                    expert={expert}
                  />
                </details>
              )}
              <details className="saveQuestion">
                <summary>Save question</summary>
                <SaveControl
                  root={root}
                  request={request}
                  kind="question"
                  payload={{ question: turn.question }}
                  name="question"
                />
              </details>
            </div>
          </article>
        ))}
        {pending && (
          <>
            <div className="userMessage">
              <span className="messageAuthor">You</span>
              <p>{pending}</p>
            </div>
            {!activeJob && (
              <p className="requestPending" role="status">
                {pending === "Summarize the verified insights"
                  ? "Requesting a summary of verified insights…"
                  : "Submitting your request…"}
              </p>
            )}
          </>
        )}
      </div>
      {activeJob && (
        <ConversationActivity
          job={activeJob}
          events={activityEvents}
          expert={expert}
          cancelPending={cancelPending}
          error={cancelError}
          onCancel={() => void cancelJob()}
        />
      )}
      <div className="chatComposer">
        <button
          className="summaryAction"
          type="button"
          disabled={busy}
          onClick={() => void generateSummary()}
        >
          <Icon name="sparkle" size={14} /> Generate AI summary
        </button>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void ask(question);
          }}
        >
          <label className="srOnly" htmlFor="chat-question">
            Your question
          </label>
          <textarea
            id="chat-question"
            ref={input}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask anything about this dataset…"
            required
            maxLength={500}
            rows={2}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault();
                void ask(question);
              }
            }}
          />
          <button
            type="submit"
            aria-label="Ask"
            disabled={busy || !question.trim()}
          >
            <Icon name="arrow" />
          </button>
        </form>
        <small>
          Answers use your selected file. Unclear questions get a clarification.
        </small>
      </div>
    </section>
  );
}
