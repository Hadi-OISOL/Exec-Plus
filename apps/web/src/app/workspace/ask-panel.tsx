/* Use case: Lets a user ask a natural-language question and read an AI summary.
What it does: Routes questions through the intent router and requests a grounded
narrative, always showing a verified answer or a clear explanation, never a guess. */

import { useEffect, useState } from "react";

import type { ApiRequest } from "./profile-panel";

type Lineage = { metric: string; aggregation: string; records_analyzed: number };
type Answer = { label: string; value: number; lineage: Lineage };

const post = (body: object): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export function AskPanel({ root, request }: { root: string; request: ApiRequest }) {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState("");
  const [summaryError, setSummaryError] = useState("");
  const [summaryBusy, setSummaryBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    request<string[]>(`${root}/suggested-questions`)
      .then((result) => {
        if (!cancelled) setSuggestions(result);
      })
      .catch(() => {
        /* Suggestions are a convenience; a failure here should not block the panel. */
      });
    return () => {
      cancelled = true;
    };
  }, [root, request]);

  async function ask(text: string) {
    setBusy(true);
    setError("");
    setAnswer(null);
    try {
      setAnswer(await request<Answer>(`${root}/ask`, post({ question: text })));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not answer that question.");
    } finally {
      setBusy(false);
    }
  }

  async function generateSummary() {
    setSummaryBusy(true);
    setSummaryError("");
    setSummary("");
    try {
      const result = await request<{ summary: string }>(
        `${root}/dashboard/summary`,
        post({ filters: [] }),
      );
      setSummary(result.summary);
    } catch (cause) {
      setSummaryError(cause instanceof Error ? cause.message : "Could not generate a summary.");
    } finally {
      setSummaryBusy(false);
    }
  }

  return (
    <section className="panel askPanel" aria-label="Ask a question">
      <h2>5. Ask a question</h2>
      <p>
        Questions are answered only from executed results — never estimated by a model. An
        unclear or unsupported question is explained rather than guessed at.
      </p>
      {suggestions.length > 0 && (
        <div className="suggestionChips">
          {suggestions.map((item) => (
            <button
              key={item}
              type="button"
              disabled={busy}
              onClick={() => {
                setQuestion(item);
                void ask(item);
              }}
            >
              {item}
            </button>
          ))}
        </div>
      )}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void ask(question);
        }}
      >
        <label>
          Your question
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="e.g. What is total revenue?"
            required
            maxLength={500}
          />
        </label>
        <button disabled={busy || !question.trim()}>{busy ? "Thinking…" : "Ask"}</button>
      </form>
      {error && (
        <p role="alert" aria-label="Question error" className="errorNotice">
          {error}
        </p>
      )}
      {answer && (
        <div className="kpiCard answerCard">
          <span className="kpiLabel">{answer.label}</span>
          <strong className="kpiValue">{answer.value.toLocaleString()}</strong>
          <span className="kpiFootnote">
            {answer.lineage.aggregation} · verified from{" "}
            {answer.lineage.records_analyzed.toLocaleString()} records
          </span>
        </div>
      )}
      <div className="summaryBlock">
        <button type="button" disabled={summaryBusy} onClick={() => void generateSummary()}>
          {summaryBusy ? "Generating…" : "Generate AI summary"}
        </button>
        {summaryError && (
          <p role="alert" aria-label="Summary error" className="errorNotice">
            {summaryError}
          </p>
        )}
        {summary && <p className="summaryText">{summary}</p>}
      </div>
    </section>
  );
}
