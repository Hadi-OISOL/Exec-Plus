/* Use case: The phone app's More menu listing every Osalytix feature.
What it does: Opens each analysis for the chosen file, the workspace pages, and the website for features that are web-only for now. */

import * as WebBrowser from "expo-web-browser";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { listFiles, SITE, Source } from "../api";
import { useNav } from "../nav";
import { color, font, space } from "../theme";
import { Chip, H, Loading, P, Screen, s } from "../ui";
import { FILE_TABS } from "./File";

type Item = { label: string; hint: string; go: () => void };

function Row({ item }: { item: Item }) {
  return (
    <Pressable onPress={item.go} accessibilityRole="button">
      {({ pressed }) => (
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            paddingVertical: space(3.5),
            borderBottomWidth: 1,
            borderBottomColor: color.line,
            opacity: pressed ? 0.6 : 1,
          }}
        >
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 16, fontWeight: "600", color: color.ink }}>{item.label}</Text>
            <Text style={s.muted}>{item.hint}</Text>
          </View>
          <Text style={{ fontSize: 22, color: color.saffronInk }}>›</Text>
        </View>
      )}
    </Pressable>
  );
}

const HINTS: Record<string, string> = {
  insights: "Key numbers and analyst findings",
  dashboard: "Charts built for this file",
  findings: "First exact facts and good questions",
  checks: "Ideas tested against your rows",
  unusual: "Values far from the rest",
  forecast: "Predict the next days or months",
  quality: "Missing, repeated and mixed values",
  about: "What this data is for, and your goals",
};

export function MoreScreen() {
  const nav = useNav();
  const [files, setFiles] = useState<Source[] | null>(null);
  const [chosen, setChosen] = useState<Source | null>(null);

  useEffect(() => {
    listFiles(nav.workspaceId)
      .then((list) => {
        setFiles(list);
        setChosen(list[0] ?? null);
      })
      .catch(() => setFiles([]));
  }, [nav.workspaceId]);

  const web = (path: string) => () => WebBrowser.openBrowserAsync(`${SITE}${path}`);
  const ask = (question: string) => () => chosen && nav.push({ name: "chat", workspaceId: nav.workspaceId, source: chosen, question });

  const analyses: Item[] = chosen
    ? [
        ...FILE_TABS.map(([tab, label]) => ({ label, hint: HINTS[tab], go: () => nav.push({ name: "file", source: chosen, tab }) })),
        { label: "Patterns", hint: "Which measures move together", go: ask("Find patterns in my data") },
        { label: "What should I do next?", hint: "Next steps from your real figures", go: ask("What should I do next?") },
        { label: "What changed?", hint: "Root cause of a change", go: ask("What changed the most between periods, and where did it come from?") },
      ]
    : [];
  const workspace: Item[] = [
    { label: "Files", hint: "Upload and manage your data", go: () => nav.tab({ name: "files" }) },
    { label: "Chats", hint: "Your conversation history", go: () => nav.tab({ name: "chats" }) },
    { label: "My memory", hint: "What Osalytix remembers about you", go: () => nav.push({ name: "memory" }) },
    { label: "Activity history", hint: "Who did what and when", go: () => nav.push({ name: "audit" }) },
    { label: "Plan and usage", hint: "Your plan, limits and account", go: () => nav.push({ name: "account" }) },
  ];
  const website: Item[] = [
    { label: "What-if scenarios", hint: "Change assumptions and compare", go: web("/workspace") },
    { label: "Recommendations", hint: "Best actions within a budget", go: web("/workspace") },
    { label: "Studies and boards", hint: "Saved studies and pinned dashboards", go: web("/workspace") },
    { label: "Clean and prepare data", hint: "Fix issues, version history", go: web("/workspace") },
    { label: "Connectors and refresh", hint: "Google Sheets, databases, scheduled refresh", go: web("/workspace") },
    { label: "Team", hint: "Invite people and set roles", go: web("/workspace") },
    { label: "Exports, API and embeds", hint: "PDF, Excel, API keys, embedded dashboards", go: web("/workspace") },
    { label: "Help and support", hint: "Send a request to the team", go: web("/workspace") },
  ];

  return (
    <Screen kicker="Everything in Osalytix" title="More">
      {files === null ? (
        <Loading label="Loading" />
      ) : (
        <>
          <H>Analyse a file</H>
          {files.length === 0 ? (
            <P muted>Add a file first to see its analyses.</P>
          ) : (
            <>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space(2) }}>
                {files.slice(0, 8).map((f) => (
                  <Chip key={f.upload.id} label={f.datasetName} active={f.upload.id === chosen?.upload.id} onPress={() => setChosen(f)} />
                ))}
              </ScrollView>
              <View>{analyses.map((item) => <Row key={item.label} item={item} />)}</View>
            </>
          )}
        </>
      )}
      <H>Your workspace</H>
      <View>{workspace.map((item) => <Row key={item.label} item={item} />)}</View>
      <H>On the website</H>
      <P muted>These open Osalytix in the browser. Sign in there with the same account.</P>
      <View>{website.map((item) => <Row key={item.label} item={item} />)}</View>
      <Text style={{ fontFamily: font.mono, fontSize: 11, color: color.muted, textAlign: "center", marginTop: space(4) }}>OSALYTIX</Text>
    </Screen>
  );
}
