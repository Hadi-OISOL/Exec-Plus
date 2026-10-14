/* Use case: Shows what the model understood about a new upload and asks its owner to confirm or correct it.
What it does: Presents one question at a time, saves verified meaning through the understanding API and keeps free-text answers as private notes. */

import { useEffect, useRef, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import styles from "./data-brief-review.module.css";

type Definition = {
  description: string;
  grain: string;
  columns: {
    name: string;
    role: string;
    unit: string;
    meaning: string;
    [key: string]: unknown;
  }[];
  [key: string]: unknown;
};
type BriefColumn = {
  name: string;
  type: string;
  role: string;
  meaning: string;
  unit: string;
  uncertain: boolean;
  question: string;
};
type Brief = {
  source: "model" | "profile";
  summary: string;
  grain: string;
  columns: BriefColumn[];
  questions: string[];
  state: string;
  revision_id: string;
  version: number;
  can_edit: boolean;
  definition: Definition;
  already_confirmed: boolean;
  model_route: string | null;
  notice: string;
  sampled: boolean;
  model_enabled: boolean;
  review_mode?: "missing";
};
type Card = {
  id: string;
  kind: "summary" | "grain" | "column" | "general";
  title: string;
  facts: string[];
  quote: string;
  column?: BriefColumn;
  openByDefault: boolean;
};
type Answer = {
  text: string;
  role: string;
  unit: string;
  grain: string;
  edited: boolean;
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
const maxRetries = 6;

const post = (body: object): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

function wait(milliseconds: number) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function buildCards(brief: Brief): Card[] {
  const cards: Card[] = brief.review_mode === "missing" ? [] : [
    {
      id: "summary",
      kind: "summary",
      title: "Here is what I think this data is about. Is that right?",
      facts: [],
      quote: brief.summary,
      openByDefault: false,
    },
    {
      id: "grain",
      kind: "grain",
      title:
        brief.grain === "unknown"
          ? "What does one row in this file represent?"
          : `I think each row is ${grainNames[brief.grain]?.toLowerCase() ?? "a record"}. Is that right?`,
      facts: [],
      quote: "",
      openByDefault: brief.grain === "unknown",
    },
  ];
  if (brief.review_mode === "missing" && brief.grain === "unknown") cards.push({
    id: "grain", kind: "grain", title: "What does one row in this file represent?",
    facts: [], quote: "", openByDefault: true,
  });
  for (const column of brief.columns) {
    const saved = brief.definition.columns.find(item => item.name === column.name);
    const missingUnit = column.role === "metric" && !(column.unit || saved?.currency || saved?.unit_column);
    cards.push({
      id: `column:${column.name}`,
      kind: "column",
      title: missingUnit
        ? `${column.question || `What unit does "${column.name}" use?`} Use "unitless" if it has no unit.`
        : column.uncertain
        ? `I am not sure about "${column.name}". ${column.question}`
        : `I understood "${column.name}" as ${column.meaning || "a column I could not describe"}. Is that right?`,
      facts: [
        `Type: ${column.type}`,
        `Seen as: ${roleNames[column.role] ?? column.role}`,
        ...(column.unit ? [`Unit: ${column.unit}`] : []),
      ],
      quote: "",
      column,
      openByDefault: missingUnit || column.uncertain || !column.meaning,
    });
  }
  brief.questions.forEach((question, position) =>
    cards.push({
      id: `general:${position}`,
      kind: "general",
      title: question,
      facts: [],
      quote: "",
      openByDefault: true,
    }),
  );
  return cards;
}

function suggestion(brief: Brief, card: Card): Answer {
  return {
    text:
      card.kind === "summary"
        ? brief.summary
        : card.kind === "column"
          ? (card.column?.meaning ?? "")
          : "",
    role: card.column?.role ?? "",
    unit: card.column?.unit ?? "",
    grain: brief.grain,
    edited: false,
  };
}

function noteLines(cards: Card[], answers: Record<string, Answer>): string[] {
  const lines: string[] = [];
  for (const card of cards) {
    const answer = answers[card.id];
    const text = answer?.text.trim();
    if (!answer?.edited || !text) continue;
    if (card.kind === "summary") lines.push(`- About this data: ${text}`);
    if (card.kind === "column")
      lines.push(
        `- Column "${card.column?.name}"${answer.unit.trim() ? ` (${answer.unit.trim()})` : ""}: ${text}`,
      );
    if (card.kind === "general") lines.push(`- ${card.title} ${text}`);
  }
  return lines;
}

export function DataBriefReview({
  root,
  request,
  manual = false,
  onClose,
  onUnavailable,
}: {
  root: string;
  request: ApiRequest;
  manual?: boolean;
  onClose: (changed: boolean, finished: boolean) => void;
  onUnavailable: (reason: string) => void;
}) {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [draft, setDraft] = useState<Answer | null>(null);
  const [editing, setEditing] = useState(false);
  const [phase, setPhase] = useState<
    "loading" | "asking" | "review" | "saving" | "done" | "confirmed"
  >("loading");
  const [share, setShare] = useState(false);
  const [results, setResults] = useState<string[]>([]);
  const [changed, setChanged] = useState(false);
  const closeRef = useRef(onClose);
  const unavailableRef = useRef(onUnavailable);
  useEffect(() => {
    closeRef.current = onClose;
    unavailableRef.current = onUnavailable;
  });

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      let lastError = "Your file is still being prepared.";
      for (let attempt = 0; attempt < maxRetries; attempt += 1) {
        try {
          const value = await request<Brief>(`${root}/data-brief${manual ? "?review_missing=true" : ""}`, {
            method: "POST",
            signal: controller.signal,
          });
          if (controller.signal.aborted) return;
          if (value.already_confirmed) {
            if (manual) setPhase("confirmed");
            else closeRef.current(false, true);
            return;
          }
          if (value.source !== "model" && value.review_mode !== "missing") {
            unavailableRef.current(value.model_enabled ? value.notice : "");
            return;
          }
          const built = buildCards(value);
          setBrief(value);
          setCards(built);
          if (built.length) {
            setDraft(suggestion(value, built[0]));
            setEditing(built[0].openByDefault);
          }
          setPhase(built.length ? "asking" : "review");
          return;
        } catch (cause) {
          if (controller.signal.aborted) return;
          lastError = cause instanceof Error ? cause.message : lastError;
          await wait(1000);
        }
      }
      if (!controller.signal.aborted) {
        unavailableRef.current("The data reading could not be loaded.");
      }
    }
    load();
    return () => controller.abort();
  }, [root, request, manual]);

  function goTo(position: number, next: Record<string, Answer>) {
    if (!brief) return;
    if (position >= cards.length) {
      setPhase("review");
      return;
    }
    const card = cards[position];
    setIndex(position);
    setDraft(next[card.id] ?? suggestion(brief, card));
    setEditing(card.openByDefault);
  }

  function record(card: Card, answer: Answer | null) {
    const next = { ...answers };
    if (answer) next[card.id] = answer;
    else delete next[card.id];
    setAnswers(next);
    goTo(index + 1, next);
  }

  async function save() {
    if (!brief) return;
    setPhase("saving");
    const done: string[] = [];
    let didChange = false;
    const summaryAnswer = answers.summary;
    const grainAnswer = answers.grain;
    const nextGrain = grainAnswer ? grainAnswer.grain : brief.definition.grain;
    const answered = Object.keys(answers).length;
    const fullyReviewed = nextGrain !== "unknown" && (
      brief.state === "confirmed" || (brief.review_mode === "missing"
        ? brief.columns.every(column => Boolean(answers[`column:${column.name}`]))
        : brief.definition.columns.every(column => Boolean(answers[`column:${column.name}`])))
    );
    if ((answered || brief.review_mode === "missing") && brief.can_edit) {
        const definition: Definition = {
          ...brief.definition,
          description: summaryAnswer?.text.trim()
            ? summaryAnswer.text.trim().slice(0, 500)
            : brief.definition.description,
          grain: nextGrain,
          columns: brief.definition.columns.map((column) => {
            const reply = answers[`column:${column.name}`];
            if (!reply) return column;
            return {
              ...column,
              role: reply.role || column.role,
              unit: reply.unit.trim(),
              meaning: reply.text.trim().slice(0, 200) || column.meaning,
            };
          }),
        };
        try {
          await request(
            `${root}/understanding`,
            post({
              revision_id: brief.revision_id,
              expected_version: brief.version,
              state: fullyReviewed ? "confirmed" : "needs_review",
              definition,
            }),
          );
          didChange = true;
          done.push(
            fullyReviewed
              ? "Saved. This reading is now context for answers about this data."
              : "Your answers are saved as a draft. Finish the skipped fields before confirming the whole dataset.",
          );
        } catch (cause) {
          done.push(
            `The shared meaning was not changed: ${cause instanceof Error ? cause.message : "the save failed."}`,
          );
        }
    } else if (answered) {
      done.push(
        "Only the dataset creator or a workspace owner/admin can change the shared meaning, so your answers were kept as notes.",
      );
    }
    const lines = noteLines(cards, answers);
    if (lines.length) {
      const dataset = root.replace(/\/uploads\/[^/]+$/, "");
      const name = `data-reading-${root.split("/").pop()?.slice(0, 8) ?? "upload"}.md`;
      const text = `# What the owner told ExecPlus about this data\n\n${lines.join("\n")}\n`;
      try {
        await request(
          `${dataset}/documents?name=${encodeURIComponent(name)}&shared=${share}`,
          { method: "POST", headers: { "Content-Type": "text/plain" }, body: text },
        );
        didChange = true;
        done.push(
          `${lines.length} note${lines.length === 1 ? "" : "s"} added to your knowledge base${share ? " and shared with the workspace" : " (private to you)"}.`,
        );
      } catch (cause) {
        done.push(
          `The notes were not saved: ${cause instanceof Error ? cause.message : "the save failed."}`,
        );
      }
    }
    if (!done.length) done.push("Nothing was changed.");
    setResults(done);
    setChanged(didChange);
    setPhase("done");
  }

  const heading = (title: string, text: string) => (
    <div className={styles.header}>
      <div>
        <h2>{title}</h2>
        <p>{text}</p>
      </div>
    </div>
  );

  if (phase === "loading")
    return (
      <section className={styles.brief} aria-label="Data reading" aria-busy="true">
        {heading(
          "Reading your data",
          "I am working out what this file is about so I can check it with you…",
        )}
      </section>
    );

  if (phase === "saving")
    return (
      <section className={styles.brief} aria-label="Data reading" aria-busy="true">
        {heading("Saving what you confirmed", "One moment…")}
      </section>
    );

  if (phase === "confirmed")
    return (
      <section className={styles.brief} aria-label="Data reading">
        {heading(
          "This data's meaning is already confirmed",
          "Answers about this data already use it. You can change it under Data understanding.",
        )}
        <div className={styles.nav}>
          <span className={styles.spacer} />
          <button type="button" onClick={() => onClose(false, true)}>
            Close
          </button>
        </div>
      </section>
    );

  if (phase === "done")
    return (
      <section className={styles.brief} aria-label="Data reading">
        {heading(
          "Review save results",
          "Check what was saved below, including anything that still needs review.",
        )}
        <ul className={styles.summaryList}>
          {results.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <div className={styles.nav}>
          <span className={styles.spacer} />
          <button type="button" onClick={() => onClose(changed, true)}>
            Continue to my insights
          </button>
        </div>
      </section>
    );

  if (!brief || !draft) return null;

  if (phase === "review") {
    const lines = noteLines(cards, answers);
    return (
      <section className={styles.brief} aria-label="Data reading">
        {heading(
          "Review before saving",
          brief.can_edit
            ? "Reviewed fields become shared meaning. Skipped fields keep a new review as a draft; your notes stay private unless you choose to share."
            : "You can save your notes. Only an owner or admin can change the shared meaning.",
        )}
        <ul className={styles.summaryList}>
          <li>
            {Object.keys(answers).length} of {cards.length} questions answered.
          </li>
          <li>
            {lines.length} free-text note{lines.length === 1 ? "" : "s"} will be
            kept in your knowledge base.
          </li>
        </ul>
        {lines.length > 0 && (
          <div className={styles.explain}>
            <label className={styles.share}>
              <input
                type="checkbox"
                checked={share}
                onChange={(event) => setShare(event.target.checked)}
              />
              Share my notes with everyone in this workspace
            </label>
          </div>
        )}
        <div className={styles.nav}>
          <button
            type="button"
            className={styles.link}
            onClick={() => goTo(cards.length - 1, answers)}
          >
            ← Back
          </button>
          <span className={styles.spacer} />
          <button
            type="button"
            className={styles.secondary}
            onClick={() => onClose(false, false)}
          >
            Skip without saving
          </button>
          <button type="button" onClick={save}>
            Save as context for this data
          </button>
        </div>
      </section>
    );
  }

  const card = cards[index];
  const progress = Math.round((index / cards.length) * 100);
  const numeric = card.column
    ? card.column.type === "integer" || card.column.type === "decimal"
    : false;
  const roles = Object.keys(roleNames).filter(
    (item) => item !== "metric" || numeric,
  );
  const canUse =
    card.kind === "grain"
      ? draft.grain !== "unknown"
      : card.kind === "column"
        ? Boolean(draft.text.trim() || draft.role === "ignored")
        : Boolean(draft.text.trim());

  return (
    <section className={styles.brief} aria-label="Data reading">
      <div className={styles.header}>
        <div>
          <h2>Let me check I understood your data</h2>
          <p>
            Confirm or correct what I read. What you confirm becomes context for
            later answers.
          </p>
        </div>
        <button
          type="button"
          className={styles.secondary}
          onClick={() => onClose(false, false)}
        >
          Skip for now
        </button>
      </div>
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
      {card.quote && <p className={styles.quote}>{card.quote}</p>}
      {card.kind !== "general" && (
        <p className={styles.caption}>
          {brief.review_mode === "missing"
            ? "Your previous answers are saved. Only missing meanings or units are shown here."
            : brief.sampled
            ? "Suggested by the language model from your file's structure and a small sample of its values. Identifiers and personal columns are withheld."
            : "Suggested by the language model from your file's structure. It has not seen your row values."}
        </p>
      )}
      {card.facts.length > 0 && (
        <ul className={styles.peek} aria-label="What I can see">
          {card.facts.map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      )}

      {!editing && (
        <div className={styles.choices}>
          <button
            type="button"
            onClick={() =>
              record(card, suggestion(brief, card))
            }
          >
            Yes, that&apos;s right
          </button>
          <button
            type="button"
            className={styles.secondary}
            onClick={() => setEditing(true)}
          >
            No, let me edit
          </button>
        </div>
      )}

      {editing && (
        <div className={styles.explain}>
          {card.kind === "grain" && (
            <label>
              What does one row represent?
              <select
                value={draft.grain}
                onChange={(event) => setDraft({ ...draft, grain: event.target.value })}
              >
                {Object.entries(grainNames).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          )}
          {card.kind === "column" && (
            <>
              <label>
                What is this column really?
                <select
                  value={draft.role}
                  onChange={(event) => setDraft({ ...draft, role: event.target.value })}
                >
                  {roles.map((value) => (
                    <option key={value} value={value}>
                      {roleNames[value]}
                    </option>
                  ))}
                </select>
              </label>
              {draft.role === "metric" && (
                <label>
                  Unit, if you know it
                  <input
                    value={draft.unit}
                    maxLength={40}
                    onChange={(event) => setDraft({ ...draft, unit: event.target.value })}
                  />
                </label>
              )}
            </>
          )}
          {card.kind !== "grain" && (
            <label>
              {card.kind === "summary"
                ? "What is this data about?"
                : card.kind === "column"
                  ? "What does this column mean?"
                  : "Your answer"}
              <textarea
                value={draft.text}
                maxLength={card.kind === "summary" ? 300 : 200}
                onChange={(event) => setDraft({ ...draft, text: event.target.value })}
              />
            </label>
          )}
          <div className={styles.choices}>
            <button type="button" disabled={!canUse} onClick={() => record(card, { ...draft, edited: true })}>
              Use my answer
            </button>
            {!card.openByDefault && (
              <button
                type="button"
                className={styles.secondary}
                onClick={() => {
                  setDraft(suggestion(brief, card));
                  setEditing(false);
                }}
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      )}

      <div className={styles.nav}>
        <button
          type="button"
          className={styles.link}
          onClick={() => goTo(index - 1, answers)}
          disabled={index === 0}
        >
          ← Back
        </button>
        <span className={styles.spacer} />
        <button type="button" className={styles.link} onClick={() => record(card, null)}>
          Skip this question →
        </button>
      </div>
    </section>
  );
}
