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
};
type History = { id: string; created_at: string };
type SavedTurn = {
  id: string;
  question: string;
  kind: string;
  message: string | null;
  request_id: string;
  status: string;
};
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
export type ChatHandle = { ask: (question: string) => void };
const post = (body: object): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export function AskPanel({
  root,
  request,
  filename,
  ref,
}: {
  root: string;
  request: ApiRequest;
  filename: string;
  ref?: Ref<ChatHandle>;
}) {
  const [threadId, setThreadId] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<History[]>([]);
  const [selectedThread, setSelectedThread] = useState("");
  const [historyError, setHistoryError] = useState("");
  const serial = useRef(0);
  const inFlight = useRef(false);
  const conversation = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let cancelled = false;
    request<string[]>(`${root}/suggested-questions`)
      .then((result) => {
        if (!cancelled) setSuggestions(result);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [root, request]);

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
    setBusy(true);
    setHistoryError("");
    inFlight.current = true;
    try {
      const result = await request<{ turns: SavedTurn[] }>(
        `${root.split("/datasets/")[0]}/threads/${selectedThread}`,
      );
      setThreadId(selectedThread);
      setTurns(
        result.turns.map((turn) => ({
          id: turn.id,
          serverId: turn.id,
          requestId: turn.request_id,
          status: turn.status,
          question: turn.question,
          answer: null,
          failed: turn.status === "failed",
          message:
            turn.message ??
            (turn.status === "running"
              ? "This request is still running. Reopen this conversation shortly."
              : "Saved answer — load its evidence below."),
        })),
      );
    } catch (cause) {
      setHistoryError(
        cause instanceof Error ? cause.message : "Conversation unavailable.",
      );
    } finally {
      setBusy(false);
      inFlight.current = false;
    }
  }

  async function loadAnswer(turn: Turn) {
    if (!turn.serverId || inFlight.current) return;
    setBusy(true);
    inFlight.current = true;
    try {
      const answer = await request<Answer | null>(
        `${root.split("/datasets/")[0]}/threads/${threadId}/turns/${turn.serverId}/answer`,
      );
      setTurns((items) =>
        items.map((item) =>
          item.id === turn.id
            ? {
                ...item,
                answer: flatten(answer),
                message: answer
                  ? "Reopened historical evidence. A follow-up will check for source changes."
                  : item.message,
              }
            : item,
        ),
      );
    } catch (cause) {
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
      setBusy(false);
      inFlight.current = false;
    }
  }

  useEffect(() => {
    if (conversation.current)
      conversation.current.scrollTop = conversation.current.scrollHeight;
  }, [turns, pending]);

  async function ask(text: string, retry?: Turn) {
    if (inFlight.current || !text.trim()) return;
    inFlight.current = true;
    setBusy(true);
    setPending(text);
    setQuestion("");
    const id = retry?.id ?? ++serial.current;
    const requestId = retry?.requestId ?? requestIdentifier();
    if (retry) setTurns((items) => items.filter((item) => item.id !== id));
    try {
      const thread =
        threadId ||
        (await request<{ id: string }>(`${root}/threads`, { method: "POST" }))
          .id;
      setThreadId(thread);
      const result = await request<{
        answer: Answer | null;
        turn: {
          id: string;
          message: string | null;
          kind: string;
          status: string;
        };
      }>(
        `${root.split("/datasets/")[0]}/threads/${thread}/ask`,
        post({ question: text, request_id: requestId }),
      );
      setTurns((previous) => [
        ...previous,
        {
          id,
          question: text,
          answer: flatten(result.answer),
          message: result.turn.message ?? "",
          serverId: result.turn.id,
          status: result.turn.status,
        },
      ]);
    } catch (cause) {
      setTurns((previous) => [
        ...previous,
        {
          id,
          question: text,
          answer: null,
          message:
            cause instanceof Error
              ? cause.message
              : "Could not answer. Please try again.",
          failed: true,
          requestId,
        },
      ]);
      setQuestion(text);
    } finally {
      inFlight.current = false;
      setBusy(false);
      setPending("");
      input.current?.focus({ preventScroll: true });
    }
  }
  useImperativeHandle(ref, () => ({
    ask: (text) => {
      void ask(text);
    },
  }));

  async function generateSummary() {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setPending("Summarize the verified insights");
    const id = ++serial.current;
    try {
      const result = await request<{ summary: string }>(
        `${root}/dashboard/summary`,
        post({ filters: [] }),
      );
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
      inFlight.current = false;
      setBusy(false);
      setPending("");
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
        <span>Connected</span>
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
            I can find records, calculate totals and break results down by
            category, and find supporting document passages. Ask a follow-up to
            keep exploring.
          </p>
          <p className="chatHint">
            Try “show all records of Karachi” when your file has a city column.
          </p>
        </div>
        {!turns.length && (
          <div className="suggestionChips">
            {[...suggestions.slice(0, 3), "Show the first 10 records"].map(
              (item) => (
                <button
                  type="button"
                  key={item}
                  disabled={busy}
                  onClick={() => void ask(item)}
                >
                  {item}
                  <Icon name="arrow" size={14} />
                </button>
              ),
            )}
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
              {turn.answer?.message ? (
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
                turn.status !== "running" &&
                turn.status !== "failed" && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void loadAnswer(turn)}
                  >
                    Load saved answer
                  </button>
                )}
              {turn.failed && turn.requestId && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void ask(turn.question, turn)}
                >
                  Check or retry this request
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
                  <details className="answerEvidence">
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
            <div className="thinkingFlow" aria-busy="true">
              <span className="thinkingDots">
                <i />
                <i />
                <i />
              </span>
              <p>Planning and checking your request…</p>
              <div>
                <span>Question</span>
                <Icon name="arrow" size={14} />
                <span>Data + documents</span>
                <Icon name="arrow" size={14} />
                <span>Evidence</span>
              </div>
            </div>
          </>
        )}
      </div>
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
