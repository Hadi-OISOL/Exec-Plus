/* Use case: Asks the file's open questions on the phone before any analytics are shown.
What it does: Turns the live data-brief into one-question-at-a-time cards (summary, row meaning, units, unclear columns), offers suggested units and saves the reviewed meaning through /understanding. */

import { useState } from "react";
import { Text, View } from "react-native";
import { api } from "../api";
import { color, font, space } from "../theme";
import { Button, Chip, ErrorText, Field, H, P, Receipt, Screen, s } from "../ui";
import { unitChoices } from "../unit-choices";

type Column = { name: string; type: string; role: string; meaning: string; unit: string; uncertain: boolean; question: string };
type DefColumn = { name: string; role: string; unit: string; meaning: string; currency?: string; unit_column?: string; [k: string]: unknown };
export type Brief = {
  source: string;
  summary: string;
  grain: string;
  columns: Column[];
  revision_id: string;
  version: number;
  can_edit: boolean;
  definition: { description: string; grain: string; columns: DefColumn[]; [k: string]: unknown };
  already_confirmed: boolean;
  model_enabled: boolean;
  review_mode?: string;
};
type Answer = { role: string; unit: string; text: string; grain: string };
type Card = { id: string; kind: "summary" | "grain" | "column"; title: string; column?: Column; needsUnit?: boolean };

const ROLES: Record<string, string> = {
  metric: "Measure (number)",
  dimension: "Category",
  identifier: "Identifier",
  ordinal: "Rating / level",
  ignored: "Ignore",
};
const GRAINS: Record<string, string> = {
  record: "A general record",
  order: "An order",
  order_item: "An order item",
  customer: "A customer",
  inventory_snapshot: "An inventory snapshot",
  survey_response: "A survey response",
  other: "Something else",
  unknown: "I am not sure",
};

function cardsFor(brief: Brief): Card[] {
  const cards: Card[] = [
    { id: "summary", kind: "summary", title: "Here is what I think this file is about. Is that right?" },
    {
      id: "grain",
      kind: "grain",
      title: brief.grain === "unknown" ? "What does one row in this file represent?" : `I think each row is ${GRAINS[brief.grain]?.toLowerCase() ?? "a record"}. Right?`,
    },
  ];
  for (const column of brief.columns) {
    const saved = brief.definition.columns.find((c) => c.name === column.name);
    const needsUnit = column.role === "metric" && !(column.unit || saved?.currency || saved?.unit_column);
    if (!needsUnit && !column.uncertain) continue;
    cards.push({
      id: `column:${column.name}`,
      kind: "column",
      column,
      needsUnit,
      title: needsUnit ? `What unit does "${column.name}" use?` : `I am not sure about "${column.name}". ${column.question}`,
    });
  }
  return cards;
}

function suggestion(brief: Brief, card: Card): Answer {
  return {
    role: card.column?.role ?? "",
    unit: card.column?.unit ?? "",
    text: card.kind === "summary" ? brief.summary : card.column?.meaning ?? "",
    grain: brief.grain,
  };
}

export function FileQuestions({ brief, root, title, onDone }: { brief: Brief; root: string; title: string; onDone: (saved: boolean) => void }) {
  const [cards] = useState(() => cardsFor(brief));
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [draft, setDraft] = useState<Answer>(() => suggestion(brief, cards[0]));
  const [phase, setPhase] = useState<"asking" | "review" | "saving">("asking");
  const [error, setError] = useState("");

  const card = cards[index];
  const go = (next: number, saved = answers) => {
    if (next >= cards.length) return setPhase("review");
    setIndex(next);
    setDraft(saved[cards[next].id] ?? suggestion(brief, cards[next]));
  };
  const record = (value: Answer | null) => {
    const next = { ...answers };
    if (value) next[card.id] = value;
    else delete next[card.id];
    setAnswers(next);
    go(index + 1, next);
  };

  async function save(acceptRest: boolean) {
    setPhase("saving");
    setError("");
    const grain = answers.grain?.grain ?? brief.definition.grain;
    const columns = brief.definition.columns.map((column) => {
      const reply = answers[`column:${column.name}`];
      if (!reply) return column;
      return { ...column, role: reply.role || column.role, unit: reply.unit.trim(), meaning: reply.text.trim().slice(0, 200) || column.meaning };
    });
    const asked = new Set(cards.filter((c) => c.kind === "column").map((c) => c.id));
    const skippedAsked = [...asked].some((id) => !answers[id]);
    const confirmed = acceptRest && !skippedAsked && grain !== "unknown";
    try {
      await api(`${root}/understanding`, {
        body: {
          revision_id: brief.revision_id,
          expected_version: brief.version,
          state: confirmed ? "confirmed" : "needs_review",
          definition: {
            ...brief.definition,
            description: answers.summary?.text.trim().slice(0, 500) || brief.definition.description,
            grain,
            columns,
          },
        },
      });
      onDone(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save your answers.");
      setPhase("review");
    }
  }

  if (phase !== "asking") {
    const asked = new Set(cards.map((c) => c.column?.name));
    const rest = brief.columns.filter((c) => !asked.has(c.name));
    return (
      <Screen kicker="Last step" title="Review before saving" onBack={() => { setPhase("asking"); setIndex(cards.length - 1); }}>
        <P>{Object.keys(answers).length} of {cards.length} questions answered.</P>
        {rest.length > 0 && (
          <Receipt title="The other columns" stamp="CHECK">
            {rest.map((c) => (
              <Text key={c.name} style={{ color: color.ink, marginBottom: space(1.5), lineHeight: 20 }}>
                <Text style={{ fontFamily: font.mono, fontWeight: "700" }}>{c.name}</Text>
                {` — ${c.meaning || "no description"} (${ROLES[c.role] ?? c.role}${c.unit ? `, ${c.unit}` : ""})`}
              </Text>
            ))}
          </Receipt>
        )}
        <ErrorText text={error} />
        {brief.can_edit ? (
          <>
            <Button label="These look right — save" onPress={() => save(true)} busy={phase === "saving"} />
            <Button kind="secondary" label="Save my answers only" onPress={() => save(false)} disabled={phase === "saving"} />
          </>
        ) : (
          <P muted>Only the file owner or an admin can save meanings for everyone.</P>
        )}
        <Button kind="ghost" label="Skip for now" onPress={() => onDone(false)} />
      </Screen>
    );
  }

  return (
    <Screen
      kicker={`Let's understand ${title}`}
      title="One small question at a time."
      right={<Button kind="ghost" label="Skip for now" onPress={() => onDone(false)} style={{ minHeight: 32 }} />}
    >
      <Text style={{ fontFamily: font.mono, color: color.saffronInk, fontSize: 12 }}>
        QUESTION {index + 1} OF {cards.length}
      </Text>
      <View style={{ height: 6, backgroundColor: "#e5dabf", borderRadius: 3 }}>
        <View style={{ height: 6, width: `${((index + 1) / cards.length) * 100}%`, backgroundColor: color.saffron, borderRadius: 3 }} />
      </View>
      <H>{card.title}</H>
      {card.kind === "summary" && <Field label="What is this data about?" value={draft.text} onChangeText={(text) => setDraft({ ...draft, text })} multiline />}
      {card.kind === "grain" && (
        <View style={s.row}>
          {Object.entries(GRAINS).map(([key, label]) => (
            <Chip key={key} label={label} active={draft.grain === key} onPress={() => setDraft({ ...draft, grain: key })} />
          ))}
        </View>
      )}
      {card.kind === "column" && card.column && (
        <>
          <View style={s.row}>
            <Text style={s.muted}>Type: {card.column.type}</Text>
            <Text style={s.muted}>· Seen as: {ROLES[card.column.role] ?? card.column.role}</Text>
          </View>
          {draft.role === "metric" && (
            <View style={{ gap: space(2) }}>
              <Text style={s.label}>{card.needsUnit ? "Unit (required)" : "Unit, if you know it"}</Text>
              <View style={s.row}>
                {unitChoices(card.column.name, card.column.unit).map((unit) => (
                  <Chip key={unit} label={unit} active={draft.unit === unit} onPress={() => setDraft({ ...draft, unit })} />
                ))}
              </View>
              <Field label="Or type a unit" value={draft.unit} onChangeText={(unit) => setDraft({ ...draft, unit })} maxLength={40} autoCapitalize="none" />
            </View>
          )}
          <Text style={s.label}>What is this column really?</Text>
          <View style={s.row}>
            {Object.entries(ROLES).map(([key, label]) => (
              <Chip key={key} label={label} active={draft.role === key} onPress={() => setDraft({ ...draft, role: key })} />
            ))}
          </View>
          <Field label="What does this column mean?" value={draft.text} onChangeText={(text) => setDraft({ ...draft, text })} maxLength={200} />
        </>
      )}
      <P muted>Suggested by reading your file's structure. Your answers make every later answer more exact.</P>
      <Button
        label={card.kind === "column" ? "Use my answer" : "Yes, that's right"}
        onPress={() => record(draft)}
        disabled={card.kind === "column" && !!card.needsUnit && draft.role === "metric" && !draft.unit.trim()}
      />
      <View style={[s.row, { justifyContent: "space-between" }]}>
        <Button kind="ghost" label="‹ Back" onPress={() => go(Math.max(0, index - 1))} disabled={index === 0} />
        <Button kind="ghost" label="Skip this question ›" onPress={() => record(null)} />
      </View>
    </Screen>
  );
}
