/* Use case: Asks a new Osalytix user the short get-to-know-you questions on the phone.
What it does: Loads the live 18-question profile, shows one skippable question at a time and saves or skips it through /me/profile. */

import { useEffect, useState } from "react";
import { View } from "react-native";
import { api } from "../api";
import { space } from "../theme";
import { Button, Chip, ErrorText, Field, H, Loading, P, Screen, s } from "../ui";

type Question = { id: string; prompt: string; kind: "text" | "single" | "multi"; options: string[]; hint: string };
type Profile = { version: number; preferred_name: string; answers: Record<string, unknown>; status: string; questionnaire: Question[] };

export function ProfileScreen({ onDone }: { onDone: () => void }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Profile>("/me/profile")
      .then((value) => {
        setProfile(value);
        setAnswers({ ...value.answers, preferred_name: value.preferred_name });
      })
      .catch((cause) => setError(cause.message));
  }, []);

  async function finish(status: "completed" | "skipped") {
    if (!profile) return;
    setBusy(true);
    setError("");
    const { preferred_name, ...rest } = answers;
    const kept = Object.fromEntries(
      Object.entries(rest).filter(([, v]) => (Array.isArray(v) ? v.length : typeof v === "string" ? v.trim() : v)),
    );
    try {
      await api("/me/profile", {
        method: "PUT",
        body: {
          expected_version: profile.version,
          preferred_name: String(preferred_name ?? "").trim(),
          answers: status === "completed" ? kept : {},
          status,
        },
      });
      onDone();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save.");
      setBusy(false);
    }
  }

  if (!profile)
    return (
      <Screen title="A few questions about you">
        {error ? <ErrorText text={error} /> : <Loading label="Loading questions" />}
        {error ? <Button label="Continue" onPress={onDone} /> : null}
      </Screen>
    );

  const questions = profile.questionnaire;
  const q = questions[index];
  const value = answers[q.id];
  const set = (v: unknown) => setAnswers({ ...answers, [q.id]: v });
  const last = index === questions.length - 1;
  const next = () => (last ? finish("completed") : setIndex(index + 1));

  return (
    <Screen
      kicker={`Question ${index + 1} of ${questions.length}`}
      title="Let's get to know you."
      right={<Button kind="ghost" label="Skip all" onPress={() => finish("skipped")} style={{ minHeight: 32 }} />}
    >
      <View style={{ height: 6, backgroundColor: "#e5dabf", borderRadius: 3 }}>
        <View style={{ height: 6, width: `${((index + 1) / questions.length) * 100}%`, backgroundColor: "#ff9f1c", borderRadius: 3 }} />
      </View>
      <H>{q.prompt}</H>
      {q.hint ? <P muted>{q.hint}</P> : null}
      {q.kind === "text" ? (
        <Field label="Your answer" value={String(value ?? "")} onChangeText={set} onSubmitEditing={next} />
      ) : (
        <View style={s.row}>
          {q.options.map((option) => {
            const list = Array.isArray(value) ? (value as string[]) : [];
            const active = q.kind === "single" ? value === option : list.includes(option);
            return (
              <Chip
                key={option}
                label={option}
                active={active}
                onPress={() =>
                  q.kind === "single"
                    ? set(active ? undefined : option)
                    : set(active ? list.filter((x) => x !== option) : [...list, option])
                }
              />
            );
          })}
        </View>
      )}
      <P muted>Your answers only change how Osalytix words things for you — never the numbers.</P>
      <ErrorText text={error} />
      <Button label={last ? "Finish" : "Next"} onPress={next} busy={busy} />
      <View style={[s.row, { justifyContent: "space-between" }]}>
        <Button kind="ghost" label="‹ Back" onPress={() => setIndex(Math.max(0, index - 1))} disabled={index === 0} />
        <Button kind="ghost" label="Skip this question ›" onPress={() => { set(undefined); next(); }} />
      </View>
      <View style={{ height: space(4) }} />
    </Screen>
  );
}
