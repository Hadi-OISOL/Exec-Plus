/* Use case: Chat with Osalytix about one data file from the phone.
What it does: Creates or reopens a private thread, sends questions to the live /ask endpoint and shows each answer as a receipt with exact tables, bars, clarification choices and follow-up questions. */

import { useEffect, useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, ScrollViewInstance, Text, TextInput, View } from "react-native";
import { api, newRequestId, rootOf, Source } from "../api";
import { useNav } from "../nav";
import { color, font, space } from "../theme";
import { Bars, Button, Chip, ErrorText, Loading, P, Receipt, Screen, Table, s } from "../ui";

type Answer = {
  kind?: string;
  message?: string;
  columns?: string[];
  rows?: unknown[][];
  value?: unknown;
  records_analyzed?: number;
  presentation?: { chart?: { type: string } | null; follow_ups?: string[] };
  narrative?: { segments: { text: string }[] };
  guidance?: { suggestions?: string[] };
};
type Turn = {
  id: string;
  question: string;
  kind: string;
  status: string;
  message: string | null;
  clarification?: { choices: string[] } | null;
  answer?: Answer | null;
};

function bodyOf(answer: unknown): Answer | null {
  if (!answer || typeof answer !== "object") return null;
  const value = answer as { answer?: Answer };
  return value.answer && typeof value.answer === "object" ? value.answer : (answer as Answer);
}

export function ChatScreen({
  workspaceId,
  source,
  threadId: initialThread,
  question: firstQuestion,
}: {
  workspaceId: string;
  source?: Source;
  threadId?: string;
  question?: string;
}) {
  const nav = useNav();
  const [threadId, setThreadId] = useState(initialThread ?? "");
  const [title, setTitle] = useState(source?.datasetName ?? "Conversation");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(!!initialThread);
  const [text, setText] = useState("");
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const scroll = useRef<ScrollViewInstance>(null);
  const asked = useRef(false);

  useEffect(() => {
    if (!initialThread) return;
    (async () => {
      try {
        const thread = await api<{ title: string; turns: Turn[] }>(`/workspaces/${workspaceId}/threads/${initialThread}`);
        if (thread.title) setTitle(thread.title);
        const loaded = await Promise.all(
          thread.turns.map(async (turn) => {
            try {
              const answer = await api(`/workspaces/${workspaceId}/threads/${initialThread}/turns/${turn.id}/answer`);
              return { ...turn, answer: bodyOf(answer) };
            } catch {
              return turn;
            }
          }),
        );
        setTurns(loaded);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Could not open this chat.");
      } finally {
        setLoading(false);
      }
    })();
  }, [initialThread, workspaceId]);

  useEffect(() => {
    if (firstQuestion && !asked.current) {
      asked.current = true;
      send(firstQuestion);
    }
  }, [firstQuestion]);

  async function send(question: string) {
    const q = question.trim();
    if (!q || pending) return;
    setError("");
    setText("");
    setPending(q);
    try {
      let tid = threadId;
      if (!tid) {
        if (!source) throw new Error("Open a file first.");
        tid = (await api<{ id: string }>(`${rootOf(source)}/threads`, { method: "POST" })).id;
        setThreadId(tid);
      }
      const result = await api<{ turn: Turn; answer: Answer | null }>(`/workspaces/${workspaceId}/threads/${tid}/ask`, {
        body: { question: q.slice(0, 500), request_id: newRequestId() },
      });
      setTurns((all) => [...all, { ...result.turn, answer: result.answer }]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The question could not be answered.");
      setText(q);
    } finally {
      setPending("");
      setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 100);
    }
  }

  const starters = ["What is this file about?", "Which group is the biggest?", "Find anything unusual", "What should I do next?"];

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: color.field }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <Screen kicker="Ask Osalytix" title={title} onBack={nav.back} scroll={false}>
        <ScrollView ref={scroll} contentContainerStyle={{ gap: space(4), paddingBottom: space(6) }} keyboardShouldPersistTaps="handled">
          {loading && <Loading label="Opening your chat…" />}
          {!loading && turns.length === 0 && !pending && (
            <>
              <P muted>Ask in your own words, in any language. Numbers are always calculated from your file.</P>
              <View style={s.row}>
                {starters.map((item) => (
                  <Chip key={item} label={item} onPress={() => send(item)} />
                ))}
              </View>
            </>
          )}
          {turns.map((turn) => (
            <TurnView key={turn.id} turn={turn} onAsk={send} />
          ))}
          {pending ? (
            <>
              <Question text={pending} />
              <Loading label="Planning, calculating and checking…" />
            </>
          ) : null}
          <ErrorText text={error} />
        </ScrollView>
        <View style={{ flexDirection: "row", gap: space(2), alignItems: "flex-end", paddingTop: space(2), paddingBottom: space(4) }}>
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder="Ask a question…"
            placeholderTextColor={color.muted}
            multiline
            style={[s.input, { flex: 1, maxHeight: 120 }]}
            accessibilityLabel="Your question"
          />
          <Button label="Ask" onPress={() => send(text)} busy={!!pending} disabled={!text.trim()} style={{ minWidth: 72 }} />
        </View>
      </Screen>
    </KeyboardAvoidingView>
  );
}

function Question({ text }: { text: string }) {
  return (
    <View style={{ alignSelf: "flex-end", maxWidth: "85%", backgroundColor: color.field, borderRadius: 16, borderBottomRightRadius: 4, padding: space(3) }}>
      <Text style={{ color: color.paper, fontSize: 15, lineHeight: 21 }}>{text}</Text>
    </View>
  );
}

function TurnView({ turn, onAsk }: { turn: Turn; onAsk: (q: string) => void }) {
  const a = turn.answer ?? {};
  const columns = a.columns ?? [];
  const rows = a.rows ?? [];
  const numeric = turn.kind === "numerical" && rows.length > 0;
  const bars =
    numeric && columns.length === 2 && rows.length > 1 && rows.every((r) => Number.isFinite(Number(r[1])))
      ? rows.map((r) => ({ label: String(r[0]), value: r[1] }))
      : null;
  const message = turn.message || a.message || "";
  const chips = [...(turn.clarification?.choices ?? []), ...(a.presentation?.follow_ups ?? []), ...(a.guidance?.suggestions ?? [])];
  return (
    <View style={{ gap: space(2) }}>
      <Question text={turn.question} />
      <Receipt title={numeric ? "Answer" : turn.kind === "ambiguous" ? "Quick question" : "Osalytix"} stamp={numeric ? "VERIFIED" : undefined}>
        {numeric && rows.length === 1 && columns.length === 1 ? (
          <Text style={{ fontFamily: font.serif, fontSize: 34, color: color.field }}>{String(rows[0][0])}</Text>
        ) : null}
        {(a.narrative?.segments ?? []).slice(0, 3).map((seg) => (
          <Text key={seg.text} style={[s.p, { marginBottom: space(1) }]}>
            {seg.text}
          </Text>
        ))}
        {message
          ? message.split("\n").filter(Boolean).map((line, i) => (
              <Text key={i} style={[s.p, { marginBottom: space(1.5) }, line.length < 48 && !/[.?!]$/.test(line) && { fontFamily: font.serif, fontSize: 17 }]}>
                {line}
              </Text>
            ))
          : null}
        {bars ? <Bars rows={bars} /> : null}
        {numeric && !(rows.length === 1 && columns.length === 1) ? <Table columns={columns} rows={rows} /> : null}
        {a.records_analyzed ? (
          <Text style={{ fontFamily: font.mono, fontSize: 11, color: color.muted, marginTop: space(3) }}>
            CALCULATED FROM {a.records_analyzed} RECORDS
          </Text>
        ) : null}
        {turn.status === "failed" ? <ErrorText text="This question could not be answered." /> : null}
      </Receipt>
      {chips.length > 0 && (
        <View style={s.row}>
          {chips.slice(0, 5).map((c) => (
            <Chip key={c} label={c} onPress={() => onAsk(c)} />
          ))}
        </View>
      )}
    </View>
  );
}
