/* Use case: The phone app's chat history.
What it does: Lists the user's private conversations in the workspace from the live API and reopens one to continue it. */

import { useCallback, useEffect, useState } from "react";
import { Pressable, RefreshControl, ScrollView, Text } from "react-native";
import { api } from "../api";
import { useNav } from "../nav";
import { color, font, space } from "../theme";
import { Card, ErrorText, Loading, P, Screen, s } from "../ui";

type Thread = { id: string; title: string; dataset_name: string; filename: string; last_activity: string; turn_count: number };

function when(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short" }) + " · " + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function ChatsScreen() {
  const nav = useNav();
  const [threads, setThreads] = useState<Thread[] | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setThreads(await api<Thread[]>(`/workspaces/${nav.workspaceId}/threads`));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load chats.");
      setThreads([]);
    }
  }, [nav.workspaceId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Screen kicker="Your conversations" title="Chats" scroll={false}>
      <ScrollView
        contentContainerStyle={{ gap: space(3), paddingBottom: space(24) }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
      >
        <ErrorText text={error} />
        {threads === null ? (
          <Loading label="Loading chats" />
        ) : threads.length === 0 ? (
          <P muted>No chats yet. Open a file and ask a question.</P>
        ) : (
          threads.map((t) => (
            <Pressable key={t.id} accessibilityRole="button" onPress={() => nav.push({ name: "chat", workspaceId: nav.workspaceId, threadId: t.id })}>
              {({ pressed }) => (
                <Card style={{ opacity: pressed ? 0.85 : 1 }}>
                  <Text style={{ fontFamily: font.serif, fontSize: 17, color: color.ink }} numberOfLines={2}>
                    {t.title || "Untitled chat"}
                  </Text>
                  <Text style={[s.muted, { marginTop: 2 }]} numberOfLines={1}>
                    {t.dataset_name} · {t.turn_count} {t.turn_count === 1 ? "question" : "questions"}
                  </Text>
                  <Text style={{ fontFamily: font.mono, fontSize: 11, color: color.saffronInk, marginTop: space(1) }}>{when(t.last_activity)}</Text>
                </Card>
              )}
            </Pressable>
          ))
        )}
      </ScrollView>
    </Screen>
  );
}
