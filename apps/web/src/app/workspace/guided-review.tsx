/* Use case: Walks a user through what ExecPlus understood about a new upload, one question at a time.
What it does: Builds review cards from the stored profile, saves explicit draft corrections and keeps user-reported notes private unless sharing is chosen. */

import { useEffect, useRef, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import styles from "./guided-review.module.css";

type ProfileColumn = {
  name: string;
  type: string;
  missing: number;
  distinct_count: number;
  date_min: string | null;
  date_max: string | null;
};
type Profile = { row_count: number; columns: ProfileColumn[] };
type Revision = { profile: Profile };
type DefinitionColumn = {
  name: string;
  role: string;
  unit: string;
  currency: string;
  unit_column: string;
  meaning: string;
  [key: string]: unknown;
};
type Definition = {
  grain: string;
  columns: DefinitionColumn[];
  [key: string]: unknown;
};
type Understanding = {
  revision_id: string;
  version: number;
  state: string;
  definition: Definition;
  can_edit: boolean;
  unit_suggestions?: { column: string; unit: string }[];
};
type Card = {
  id: string;
  kind: "grain" | "column";
  column: string;
  title: string;
  facts: string[];
  numeric: boolean;
};
type Answer = {
  agreed: boolean;
  role: string;
  grain: string;
  unit: string;
  note: string;
  meaning: string;
};

const roleWords: Record<string, string> = {
  metric: "a number that is added up or averaged",
  dimension: "a category or label used to group rows",
  identifier: "an identifier that names a record",
  ordinal: "an ordered rating or level",
  ignored: "something that can be left out of analysis",
};
const roleNames: Record<string, string> = {
  metric: "Measure (number)",
  dimension: "Category",
  identifier: "Identifier",
  ordinal: "Rating / level",
  ignored: "Ignore",
};
const grainNames: Record<string, string> = {
  unknown: "I am not sure",
  record: "A general record",
  order: "An order",
  order_item: "An order item",
  customer: "A customer",
  inventory_snapshot: "An inventory snapshot",
  survey_response: "A survey response",
  other: "Something else",
};
const rolePriority = ["metric", "identifier", "dimension", "ordinal", "ignored"];
const maxColumnCards = 10;

const post = (body: object): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

function buildCards(definition: Definition, profile: Profile): Card[] {
  const cards: Card[] = [
    {
      id: "grain",
      kind: "grain",
      column: "",
      title:
        definition.grain === "unknown"
          ? "What does one row in this file represent?"
          : `I think each row is ${grainNames[definition.grain]?.toLowerCase() ?? "a record"}. Is that right?`,
      facts: [`${profile.row_count.toLocaleString()} rows`, `${profile.columns.length} columns`],
      numeric: false,
    },
  ];
  const known = new Map(profile.columns.map((item) => [item.name, item]));
  const ordered = definition.columns
    .filter((item) => known.has(item.name))
    .sort(
      (a, b) =>
        rolePriority.indexOf(a.role) - rolePriority.indexOf(b.role) ||
        a.name.localeCompare(b.name),
    )
    .slice(0, maxColumnCards);
  for (const column of ordered) {
    const source = known.get(column.name)!;
    const dated = source.date_min && source.date_max;
    const facts = [
      `Type: ${source.type}`,
      `${source.distinct_count.toLocaleString()} different values`,
      source.missing ? `${source.missing.toLocaleString()} missing` : "No missing values",
    ];
    if (dated) facts.push(`Dates ${source.date_min} to ${source.date_max}`);
    if (column.currency || column.unit) facts.push(`Unit: ${column.currency || column.unit}`);
    if (column.unit_column) facts.push(`Per-row units: ${column.unit_column}`);
    cards.push({
      id: `column:${column.name}`,
      kind: "column",
      column: column.name,
      title: `I think "${column.name}" is ${roleWords[column.role] ?? "a column"}. Is that right?`,
      facts,
      numeric: source.type === "integer" || source.type === "decimal",
    });
  }
  return cards;
}

function suggestedUnit(context: Understanding, card: Card): string {
  return context.unit_suggestions?.find((item) => item.column === card.column)?.unit ?? "";
}

function emptyAnswer(context: Understanding, card: Card): Answer {
  const definition = context.definition;
  const column = definition.columns.find((item) => item.name === card.column);
  return {
    agreed: true,
    role: column?.role ?? "",
    grain: definition.grain,
    unit: column?.unit || (column?.currency ? "" : suggestedUnit(context, card)),
    note: "",
    meaning: column?.meaning ?? "",
  };
}

function noteLines(
  cards: Card[],
  answers: Record<string, Answer>,
  definition: Definition,
): string[] {
  const lines: string[] = [];
  for (const card of cards) {
    const answer = answers[card.id];
    if (!answer) continue;
    const subject = card.kind === "grain" ? "Each row" : `Column "${card.column}"`;
    const original = definition.columns.find((item) => item.name === card.column);
    if (answer.agreed && !answer.note.trim() && answer.unit === (original?.unit ?? "")) continue;
    const parts = [
      card.kind === "grain" &&
      answer.grain !== "unknown" &&
      answer.grain !== definition.grain
        ? `represents ${grainNames[answer.grain]?.toLowerCase()}`
        : "",
      card.kind === "column" && answer.role && answer.role !== original?.role
        ? `is ${roleWords[answer.role]}`
        : "",
      answer.unit.trim() ? `measured in ${answer.unit.trim()}` : "",
      answer.note.trim() ? `Reviewer note: ${answer.note.trim()}` : "",
    ].filter(Boolean);
    if (parts.length) lines.push(`- ${subject} ${parts.join(". ")}`);
  }
  return lines;
}

export function GuidedReview({
  root,
  request,
  onClose,
  onReview,
}: {
  root: string;
  request: ApiRequest;
  onClose: (changed: boolean) => void;
  onReview: () => void;
}) {
  const [context, setContext] = useState<Understanding | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [explaining, setExplaining] = useState(false);
  const [phase, setPhase] = useState<"loading" | "asking" | "review" | "done">(
    "loading",
  );
  const [share, setShare] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState<string[]>([]);

  const [totalColumns, setTotalColumns] = useState(0);
  const [loadVersion, setLoadVersion] = useState(0);
  const [draftSaved, setDraftSaved] = useState(false);
  const [notesSaved, setNotesSaved] = useState(false);
  const [pending, setPending] = useState("");
  const operation = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      request<Understanding>(`${root}/understanding`, { signal: controller.signal }),
      request<Revision>(`${root}/profile`, { signal: controller.signal }),
    ]).then(([understanding, revision]) => {
      if (controller.signal.aborted) return;
      setContext(understanding);
      setCards(buildCards(understanding.definition, revision.profile));
      setTotalColumns(revision.profile.columns.length);
      setPhase("asking");
      setError("");
    }).catch(cause => {
      if (controller.signal.aborted) return;
      setError(cause instanceof Error ? cause.message : "Could not load this review.");
      setPhase("done");
    });
    return () => { controller.abort(); operation.current?.abort(); };
  }, [root, request, loadVersion]);

  const card = cards[index];
  const answer =
    card && context
      ? (answers[card.id] ?? emptyAnswer(context, card))
      : null;

  function update(patch: Partial<Answer>) {
    if (!card || !answer) return;
    setAnswers({ ...answers, [card.id]: { ...answer, ...patch } });
  }

  function advance(next: Answer | null) {
    const updated = { ...answers };
    if (card && next) updated[card.id] = next;
    else if (card) delete updated[card.id];
    setAnswers(updated);
    setExplaining(false);
    if (index + 1 >= cards.length) {
      finish(updated);
    } else {
      setIndex(index + 1);
    }
  }

  function back() {
    setExplaining(false);
    setIndex(Math.max(0, index - 1));
  }

  function finish(finalAnswers: Record<string, Answer>) {
    setAnswers(finalAnswers);
    setPhase("review");
  }

  const nextDefinition: Definition | null = context ? {
    ...context.definition,
    grain: answers.grain && !answers.grain.agreed ? answers.grain.grain : context.definition.grain,
    columns: context.definition.columns.map(column => {
      const reply = answers[`column:${column.name}`];
      if (!reply) return column;
      return {
        ...column,
        role: reply.agreed ? column.role : reply.role || column.role,
        unit: column.currency || column.unit_column ? column.unit : reply.unit.trim(),
        meaning: reply.agreed ? column.meaning : reply.meaning.trim(),
      };
    }),
  } : null;
  const definitionChanged = Boolean(context && nextDefinition && JSON.stringify(nextDefinition) !== JSON.stringify(context.definition));
  const lines = context ? noteLines(cards, answers, context.definition) : [];

  async function save(kind: "draft" | "notes") {
    if (!context || operation.current) return;
    const controller = new AbortController(); operation.current = controller;
    setPending(kind); setError("");
    try {
      if (kind === "draft") {
        if (!context.can_edit || !definitionChanged || draftSaved) return;
        await request(`${root}/understanding`, {
          ...post({ revision_id: context.revision_id, expected_version: context.version, state: "needs_review", definition: nextDefinition }),
          signal: controller.signal,
        });
        if (!controller.signal.aborted) {
          setDraftSaved(true); setContextChanged(true);
          setResults(previous => [...previous, "Shared corrections saved as a draft. Review all meanings before confirming calculations."]);
        }
      } else {
        if (!lines.length || notesSaved) return;
        const dataset = root.replace(/\/uploads\/[^/]+$/, "");
        const name = `review-notes-${context.revision_id}.md`;
        await request(`${dataset}/documents?name=${encodeURIComponent(name)}&shared=${share}`, {
          method: "POST", headers: { "Content-Type": "text/plain" }, signal: controller.signal,
          body: `# User-reported data notes\n\nThese are reviewer statements, not confirmed definitions or calculated facts.\n\n${lines.join("\n")}\n`,
        });
        if (!controller.signal.aborted) {
          setNotesSaved(true); setContextChanged(true);
          setResults(previous => [...previous, share ? "Notes saved and explicitly shared with this workspace." : "Notes saved privately to your documents."]);
        }
      }
    } catch (cause) {
      if (!controller.signal.aborted) setError(`${kind === "draft" ? "Draft" : "Notes"} save did not confirm success: ${cause instanceof Error ? cause.message : "request failed"}. Other successful saves are preserved. After a connection failure, check history before retrying.`);
    } finally {
      if (!controller.signal.aborted) setPending("");
      if (operation.current === controller) operation.current = null;
    }
  }

  const [contextChanged, setContextChanged] = useState(false);

  if (phase === "loading") {
    return (
      <section className={styles.guided} aria-label="Guided data review" aria-busy="true">
        <div className={styles.header}>
          <div>
            <h2>Getting to know your data</h2>
            <p>Reading your file so I can ask a few quick questions…</p>
          </div>
        </div>
      </section>
    );
  }

  if (phase === "review" && context) return (
    <section className={styles.guided} aria-label="Guided data review" aria-busy={Boolean(pending)}>
      <h2>Review your answers before saving</h2>
      <p>This focused review covered at most {Math.min(totalColumns, maxColumnCards)} of {totalColumns} columns. It never confirms the entire dataset.</p>
      {!context.can_edit && <p>You can save personal notes. Only the dataset creator or workspace owner/admin can edit shared meanings.</p>}
      <details open><summary>Proposed shared draft corrections</summary>
        <p>Row meaning: {nextDefinition?.grain}. Current state: {draftSaved ? "needs_review" : context.state}.</p>
        <ul>{cards.filter(c => c.kind === "column" && answers[c.id]).map(c => {
          const column = nextDefinition?.columns.find(item => item.name === c.column);
          return <li key={c.id}>{c.column}: {roleNames[column?.role ?? ""] ?? column?.role}; unit {column?.currency || column?.unit || column?.unit_column || "not declared"}; meaning {column?.meaning || "not declared"}</li>;
        })}</ul>
        <button disabled={Boolean(pending) || !context.can_edit || !definitionChanged || draftSaved} onClick={() => save("draft")}>Save draft meanings</button>
        {!definitionChanged && <p>No structured corrections were proposed.</p>}
      </details>
      <details open><summary>Your separate data notes</summary>
        {lines.length ? <ul>{lines.map(line => <li key={line}>{line}</li>)}</ul> : <p>No personal notes were proposed.</p>}
        <label className={styles.share}><input type="checkbox" checked={share} disabled={Boolean(pending) || notesSaved} onChange={e => setShare(e.target.checked)} />Share my notes with everyone in this workspace</label>
        <button disabled={Boolean(pending) || !lines.length || notesSaved} onClick={() => save("notes")}>Save my data notes</button>
      </details>
      {pending && <p role="status">Saving {pending === "draft" ? "draft meanings" : "data notes"}…</p>}
      {error && <p role="alert" className={styles.error}>{error}</p>}
      {results.length > 0 && <ul role="status">{results.map(item => <li key={item}>{item}</li>)}</ul>}
      <div className={styles.nav}>
        <button disabled={Boolean(pending)} onClick={onReview}>Review and confirm full meanings</button>
        <button disabled={Boolean(pending)} onClick={() => onClose(contextChanged)}>Continue to my insights</button>
      </div>
      <p>Draft meanings need full confirmation. Saving notes alone never changes shared definitions. Unsaved answers are discarded when you continue.</p>
    </section>
  );

  if (phase === "done") {
    return (
      <section className={styles.guided} aria-label="Guided data review">
        <div className={styles.header}>
          <div>
            <h2>{error ? "Guided review unavailable" : "Thanks — that helps"}</h2>
            <p>
              {error
                ? "You can still ask questions or open Data understanding."
                : "Your review is optional."}
            </p>
          </div>
        </div>
        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : (
          <ul className={styles.summary}>
            {results.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
        <div className={styles.nav}>
          {error && <button onClick={() => { setPhase("loading"); setLoadVersion(n => n + 1); }}>Retry loading review</button>}
          <span className={styles.spacer} />
          <button type="button" onClick={() => onClose(contextChanged)}>
            Continue to my insights
          </button>
        </div>
      </section>
    );
  }

  if (!card || !answer || !context) return null;

  const progress = Math.round((index / cards.length) * 100);
  const roles = Object.keys(roleNames).filter(
    (item) => item !== "metric" || card.numeric,
  );

  return (
    <section className={styles.guided} aria-label="Guided data review">
      <div className={styles.header}>
        <div>
          <h2>Let&apos;s check I understood your data</h2>
          <p>
            Answer a few quick questions. Corrections make future answers more
            clearer. Nothing is saved until you review and choose an action.
          </p>
        </div>
        <button type="button" className={styles.secondary} onClick={() => onClose(false)}>
          Skip for now
        </button>
      </div>
      <p>Focused review: up to {maxColumnCards} columns. Full confirmation stays in Data understanding.</p>
      <div className={styles.progressRow}>
        <span>
          Question {index + 1} of {cards.length}
        </span>
        <div
          className={styles.track}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
        >
          <div className={styles.fill} style={{ width: `${progress}%` }} />
        </div>
      </div>
      <p className={styles.question}>{card.title}</p>
      <ul className={styles.peek} aria-label="What I can see">
        {card.facts.map((fact) => (
          <li key={fact}>{fact}</li>
        ))}
      </ul>

      {!explaining && card.kind === "column" && card.numeric && answer.role === "metric" && !context.definition.columns.find(c => c.name === card.column)?.currency && !context.definition.columns.find(c => c.name === card.column)?.unit_column && (
        <label className={styles.unit}>
          Unit, if you know it (for example PKR, kg, units){answer.unit && answer.unit === suggestedUnit(context, card) && !context.definition.columns.find(c => c.name === card.column)?.unit ? " · suggested from column name" : ""}
          <input
            value={answer.unit}
            maxLength={40}
            onChange={(event) => update({ unit: event.target.value })}
          />
        </label>
      )}

      {!explaining && (
        <div className={styles.choices}>
          <button type="button" onClick={() => advance({ ...answer, agreed: true })}>
            Yes, that&apos;s right
          </button>
          <button
            type="button"
            className={styles.secondary}
            onClick={() => {
              update({ agreed: false });
              setExplaining(true);
            }}
          >
            No, let me explain
          </button>
        </div>
      )}

      {explaining && (
        <div className={styles.explain}>
          {card.kind === "grain" ? (
            <label>
              What does one row represent?
              <select
                value={answer.grain}
                onChange={(event) => update({ grain: event.target.value, agreed: false })}
              >
                {Object.entries(grainNames).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <>
              <label>
                What is this column really?
                <select
                  value={answer.role}
                  onChange={(event) => update({ role: event.target.value, agreed: false })}
                >
                  {roles.map((value) => (
                    <option key={value} value={value}>
                      {roleNames[value]}
                    </option>
                  ))}
                </select>
              </label>
              {answer.role === "metric" && !context.definition.columns.find(c => c.name === card.column)?.currency && !context.definition.columns.find(c => c.name === card.column)?.unit_column && (
                <label>
                  Unit, if you know it
                  <input
                    value={answer.unit}
                    maxLength={40}
                    onChange={(event) => update({ unit: event.target.value, agreed: false })}
                  />
                </label>
              )}
            </>
          )}
          {card.kind === "column" && context.can_edit && <label>Column meaning for the shared draft<input maxLength={200} value={answer.meaning} onChange={e => update({ meaning: e.target.value, agreed: false })} /></label>}
          <label>
            Personal data note (optional)
            <textarea
              value={answer.note}
              maxLength={400}
              placeholder="For example: status 3 means refunded"
              onChange={(event) => update({ note: event.target.value, agreed: false })}
            />
          </label>
          <div className={styles.choices}>
            <button type="button" onClick={() => advance({ ...answer, agreed: false })}>
              Use this answer and continue
            </button>
            <button
              type="button"
              className={styles.secondary}
              onClick={() => {
                update(emptyAnswer(context, card));
                setExplaining(false);
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className={styles.nav}>
        <button type="button" className={styles.link} onClick={back} disabled={index === 0}>
          ← Back
        </button>
        <span className={styles.spacer} />
        <button type="button" className={styles.link} onClick={() => advance(null)}>
          Skip this question →
        </button>
      </div>
    </section>
  );
}
