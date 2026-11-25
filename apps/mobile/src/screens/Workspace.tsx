/* Use case: Workspace pages of the phone app: private memory and activity history.
What it does: Shows and edits the user's private agent memory, and lists recent audited actions in the workspace from the live API. */

import { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { api } from "../api";
import { useNav } from "../nav";
import { color, font, space } from "../theme";
import { Button, Card, Chip, ErrorText, Field, H, Loading, P, Screen, s } from "../ui";

type Memory = {
  version: number;
  role: string;
  focus: string;
  explanation_style: "concise" | "step_by_step";
  profile: { preferred_name: string; answers: Record<string, unknown> };
};

export function MemoryScreen() {
  const nav = useNav();
  const path = `/workspaces/${nav.workspaceId}/agent-memory`;
  const [memory, setMemory] = useState<Memory | null>(null);
  const [role, setRole] = useState("");
  const [focus, setFocus] = useState("");
  const [style, setStyle] = useState<Memory["explanation_style"]>("concise");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () =>
    api<Memory>(path)
      .then((m) => {
        setMemory(m);
        setRole(m.role);
        setFocus(m.focus);
        setStyle(m.explanation_style);
      })
      .catch((e) => setNote(e.message));

  useEffect(() => {
    load();
  }, [path]);

  async function save() {
    if (!memory) return;
    setBusy(true);
    setNote("");
    try {
      await api(path, { method: "PUT", body: { expected_version: memory.version, role: role.trim(), focus: focus.trim(), explanation_style: style } });
      await load();
      setNote("Saved. Future answers will use this.");
    } catch (cause) {
      setNote(cause instanceof Error ? cause.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  async function forget() {
    setBusy(true);
    try {
      await api(path, { method: "DELETE" });
      await load();
      setNote("Forgotten. Old answers stay as they were.");
    } catch (cause) {
      setNote(cause instanceof Error ? cause.message : "Could not forget.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen kicker="Private to you" title="My memory" onBack={nav.back}>
      {!memory ? (
        <Loading label="Loading memory" />
      ) : (
        <>
          <P muted>Osalytix uses this only to word answers for you — never to change numbers.</P>
          <Field label="Your role" value={role} onChangeText={setRole} maxLength={300} placeholder="e.g. Farm manager" />
          <Field label="What you focus on" value={focus} onChangeText={setFocus} maxLength={500} multiline placeholder="e.g. Water use and crop yield" />
          <Text style={s.label}>How should answers be explained?</Text>
          <View style={s.row}>
            <Chip label="Short and clear" active={style === "concise"} onPress={() => setStyle("concise")} />
            <Chip label="Step by step" active={style === "step_by_step"} onPress={() => setStyle("step_by_step")} />
          </View>
          <Button label="Save" onPress={save} busy={busy} />
          {note ? <P muted>{note}</P> : null}
          {memory.profile.preferred_name ? (
            <Card>
              <Text style={s.muted}>Name Osalytix uses</Text>
              <Text style={{ fontFamily: font.serif, fontSize: 20, color: color.ink }}>{memory.profile.preferred_name}</Text>
            </Card>
          ) : null}
          <Button kind="secondary" label="Redo the get-to-know-you questions" onPress={() => nav.push({ name: "profile" })} />
          <Button kind="ghost" label="Forget my memory" onPress={forget} disabled={busy} />
        </>
      )}
    </Screen>
  );
}

type Event = { id: string; action: string; resource_type: string; created_at: string };

export function AuditScreen() {
  const nav = useNav();
  const [events, setEvents] = useState<Event[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ events: Event[] }>(`/workspaces/${nav.workspaceId}/audit-history`)
      .then((r) => setEvents(r.events))
      .catch((e) => setError(e.message));
  }, [nav.workspaceId]);

  return (
    <Screen kicker="Workspace" title="Activity history" onBack={nav.back}>
      <ErrorText text={error} />
      {!events && !error ? <Loading label="Loading activity" /> : null}
      {events?.length === 0 ? <P muted>No activity yet.</P> : null}
      {events && <H>Latest {events.length} actions</H>}
      {events?.map((e) => (
        <View key={e.id} style={{ paddingVertical: space(2.5), borderBottomWidth: 1, borderBottomColor: color.line }}>
          <Text style={{ color: color.ink, fontWeight: "600" }}>{e.action.replace(/[._]/g, " ")}</Text>
          <Text style={{ fontFamily: font.mono, fontSize: 11, color: color.muted }}>
            {e.resource_type} · {new Date(e.created_at).toLocaleString()}
          </Text>
        </View>
      ))}
    </Screen>
  );
}
