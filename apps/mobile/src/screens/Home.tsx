/* Use case: The phone app's home page after sign-in.
What it does: Greets the user by name and shows quick actions, the latest files, recent chats and this month's AI usage from the live API. */

import { useCallback, useEffect, useState } from "react";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { api, listFiles, Source } from "../api";
import { useNav } from "../nav";
import { color, font, space } from "../theme";
import { Button, Card, H, Loading, P, Screen, s } from "../ui";

type Thread = { id: string; title: string; dataset_name: string; turn_count: number };
type Usage = { allowances: Record<string, { limit: number | null; used: number }> };

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
}

export function HomeScreen() {
  const nav = useNav();
  const wid = nav.workspaceId;
  const [name, setName] = useState("");
  const [files, setFiles] = useState<Source[] | null>(null);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    const [profile, me] = await Promise.all([
      api<{ preferred_name: string }>("/me/profile").catch(() => ({ preferred_name: "" })),
      api<{ display_name: string }>("/auth/me").catch(() => ({ display_name: "" })),
    ]);
    setName(profile.preferred_name || me.display_name.split(" ")[0]);
    setFiles(await listFiles(wid).catch(() => []));
    setThreads(await api<Thread[]>(`/workspaces/${wid}/threads`).catch(() => []));
    setUsage(await api<Usage>(`/workspaces/${wid}/plan-usage`).catch(() => null));
  }, [wid]);

  useEffect(() => {
    load();
  }, [load]);

  const latest = files?.[0];
  const ai = usage?.allowances.model_attempts;
  const actions = [
    { label: "Upload a file", glyph: "↑", go: () => nav.tab({ name: "files" }) },
    { label: "Try a sample", glyph: "✦", go: () => nav.tab({ name: "files" }) },
    { label: "Your chats", glyph: "❝", go: () => nav.tab({ name: "chats" }) },
    { label: "Account", glyph: "◉", go: () => nav.tab({ name: "account" }) },
  ];

  return (
    <Screen kicker={greeting()} title={name ? `Hello, ${name}.` : "Hello."} scroll={false}>
      <ScrollView
        contentContainerStyle={{ gap: space(4), paddingBottom: space(24) }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
      >
        {files === null ? (
          <Loading label="Getting your workspace ready" />
        ) : latest ? (
          <Card style={{ backgroundColor: color.field, borderColor: color.field }}>
            <Text style={{ color: color.mint, fontSize: 11, fontWeight: "700", letterSpacing: 1.4 }}>PICK UP WHERE YOU LEFT OFF</Text>
            <Text style={{ color: color.paper, fontFamily: font.serif, fontSize: 22, marginTop: space(1) }} numberOfLines={2}>
              {latest.datasetName}
            </Text>
            <Text style={{ color: color.mint, marginTop: 2, marginBottom: space(4), fontFamily: font.mono, fontSize: 12 }}>
              {latest.upload.row_count ?? "?"} rows · {latest.upload.column_count ?? "?"} columns
            </Text>
            <Button label="Ask about this file" onPress={() => nav.push({ name: "chat", workspaceId: wid, source: latest })} />
            <Button kind="ghost" label="Open insights ›" onPress={() => nav.push({ name: "file", source: latest })} style={{ marginTop: space(1) }} />
          </Card>
        ) : (
          <Card style={{ backgroundColor: color.field, borderColor: color.field }}>
            <Text style={{ color: color.paper, fontFamily: font.serif, fontSize: 22 }}>Start with one file.</Text>
            <Text style={{ color: color.mint, marginTop: space(1), marginBottom: space(4), lineHeight: 20 }}>
              Upload a spreadsheet or try a sample. Osalytix reads it, asks a few questions and then answers in plain words.
            </Text>
            <Button label="Add your first file" onPress={() => nav.tab({ name: "files" })} />
          </Card>
        )}

        <View style={[s.row, { gap: space(3) }]}>
          {actions.map((a) => (
            <Pressable key={a.label} onPress={a.go} accessibilityRole="button" style={{ width: "47%" }}>
              {({ pressed }) => (
                <Card style={{ alignItems: "flex-start", gap: space(2), opacity: pressed ? 0.85 : 1 }}>
                  <Text style={{ fontSize: 20, color: color.saffronInk }}>{a.glyph}</Text>
                  <Text style={{ fontWeight: "700", color: color.ink }}>{a.label}</Text>
                </Card>
              )}
            </Pressable>
          ))}
        </View>

        {files && files.length > 1 && (
          <>
            <H>Recent files</H>
            {files.slice(0, 3).map((f) => (
              <Pressable key={f.upload.id} onPress={() => nav.push({ name: "file", source: f })} accessibilityRole="button">
                <Card>
                  <Text style={{ fontFamily: font.serif, fontSize: 17, color: color.ink }} numberOfLines={1}>
                    {f.datasetName}
                  </Text>
                  <Text style={s.muted} numberOfLines={1}>
                    {f.upload.filename}
                  </Text>
                </Card>
              </Pressable>
            ))}
          </>
        )}

        {threads.length > 0 && (
          <>
            <H>Recent chats</H>
            {threads.slice(0, 3).map((t) => (
              <Pressable key={t.id} onPress={() => nav.push({ name: "chat", workspaceId: wid, threadId: t.id })} accessibilityRole="button">
                <Card>
                  <Text style={{ color: color.ink, fontWeight: "600" }} numberOfLines={2}>
                    {t.title || "Untitled chat"}
                  </Text>
                  <Text style={s.muted} numberOfLines={1}>
                    {t.dataset_name} · {t.turn_count} {t.turn_count === 1 ? "question" : "questions"}
                  </Text>
                </Card>
              </Pressable>
            ))}
          </>
        )}

        {ai && (
          <P muted>
            AI requests this month: {ai.used} of {ai.limit ?? "unlimited"}
          </P>
        )}
      </ScrollView>
    </Screen>
  );
}
