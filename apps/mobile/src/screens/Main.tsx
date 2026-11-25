/* Use case: The phone app's single main screen, laid out like a chat app.
What it does: Shows a top bar (menu, current file, new chat), the chat or the file's analytics, a Chat/Analytics switch at the bottom and a side drawer with every chat, analysis and workspace option. */

import { ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { Animated, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, Text, View, useWindowDimensions } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { api, listFiles, rootOf, Source } from "../api";
import { Focus, useNav } from "../nav";
import { color, font, space } from "../theme";
import { Button, Loading, P, s } from "../ui";
import { ChatView } from "./Chat";
import { FILE_TABS, FileAnalytics, useFileGate } from "./File";
import { FileQuestions } from "./FileQuestions";

type Thread = { id: string; title: string; dataset_name: string; upload_id: string; last_activity: string };

export function MainScreen({ focus, setFocus }: { focus: Focus; setFocus: (next: Focus) => void }) {
  const nav = useNav();
  const insets = useSafeAreaInsets();
  const [files, setFiles] = useState<Source[] | null>(null);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [me, setMe] = useState<{ display_name: string; email: string } | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [picker, setPicker] = useState(false);
  const source = focus.source;
  const gate = useFileGate(source, focus.fresh);

  const loadThreads = useCallback(() => {
    api<Thread[]>(`/workspaces/${nav.workspaceId}/threads`).then(setThreads).catch(() => undefined);
  }, [nav.workspaceId]);

  useEffect(() => {
    listFiles(nav.workspaceId)
      .then((list) => {
        setFiles(list);
        if (!focus.source && list[0]) setFocus({ ...focus, source: list[0] });
      })
      .catch(() => setFiles([]));
    api<{ display_name: string; email: string }>("/auth/me").then(setMe).catch(() => undefined);
    loadThreads();
  }, [nav.workspaceId]);

  const open = (next: Partial<Focus>) => {
    setDrawer(false);
    setPicker(false);
    setFocus({ ...focus, threadId: undefined, question: undefined, fresh: false, ...next, chatKey: focus.chatKey + 1 });
  };
  const go = (route: Parameters<typeof nav.push>[0]) => {
    setDrawer(false);
    setPicker(false);
    nav.push(route);
  };
  const ask = (question: string) => open({ mode: "chat", question });

  if (gate.phase === "questions" && gate.brief && source)
    return <FileQuestions brief={gate.brief} root={rootOf(source)} title={source.datasetName} onDone={gate.finish} />;

  let content;
  if (files === null || (files.length && !source)) content = <Loading label="Opening your workspace…" />;
  else if (!files.length || !source)
    content = (
      <View style={{ padding: space(5), gap: space(4), marginTop: space(10) }}>
        <Text style={{ fontFamily: font.serif, fontSize: 28, color: color.ink }}>Start with one file.</Text>
        <P muted>Upload a spreadsheet or try a sample. Osalytix reads it, asks a few questions and then answers in plain words.</P>
        <Button label="Add a file" onPress={() => go({ name: "files" })} />
      </View>
    );
  else if (gate.phase === "checking") content = <Loading label="Reading your file…" />;
  else if (focus.mode === "chat")
    content = (
      <ChatView
        key={focus.chatKey}
        workspaceId={nav.workspaceId}
        source={source}
        threadId={focus.threadId}
        question={focus.question}
        onThread={(id) => {
          setFocus({ ...focus, threadId: id, question: undefined });
          loadThreads();
        }}
      />
    );
  else
    content = (
      <ScrollView contentContainerStyle={{ padding: space(4), paddingBottom: space(10) }}>
        <FileAnalytics source={source} tab={focus.tab} onTab={(tab) => setFocus({ ...focus, tab })} ask={ask} onReview={gate.reviewAgain} />
      </ScrollView>
    );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: color.field }} edges={["top"]}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space(3), paddingVertical: space(2.5), gap: space(2) }}>
        <IconButton label="Open menu" glyph="☰" onPress={() => { loadThreads(); setDrawer(true); }} />
        <Pressable
          onPress={() => setPicker(true)}
          accessibilityRole="button"
          accessibilityLabel="Choose a file"
          style={{ flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: space(1.5) }}
        >
          <Text style={{ color: color.paper, fontFamily: font.serif, fontSize: 18, maxWidth: "85%" }} numberOfLines={1}>
            {source?.datasetName ?? "Osalytix"}
          </Text>
          <Text style={{ color: color.saffron, fontSize: 14 }}>▾</Text>
        </Pressable>
        <IconButton label="New chat" glyph="✎" onPress={() => open({ mode: "chat" })} />
      </View>

      <KeyboardAvoidingView
        style={{ flex: 1, backgroundColor: color.paper, borderTopLeftRadius: 20, borderTopRightRadius: 20, overflow: "hidden" }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        {content}
      </KeyboardAvoidingView>

      <View style={{ flexDirection: "row", backgroundColor: color.card, borderTopWidth: 1, borderTopColor: color.line, paddingBottom: insets.bottom }}>
        {(
          [
            ["chat", "Chat", "❝"],
            ["analytics", "Analytics", "▥"],
          ] as const
        ).map(([mode, label, glyph]) => {
          const active = focus.mode === mode;
          return (
            <Pressable
              key={mode}
              onPress={() => setFocus({ ...focus, mode })}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              style={{ flex: 1, alignItems: "center", paddingVertical: space(2.5) }}
            >
              <Text style={{ fontSize: 20, color: active ? color.saffronInk : color.muted }}>{glyph}</Text>
              <Text style={{ fontSize: 13, fontWeight: active ? "800" : "600", color: active ? color.field : color.muted }}>{label}</Text>
              {active && <View style={{ height: 3, width: 28, backgroundColor: color.saffron, borderRadius: 2, marginTop: 3 }} />}
            </Pressable>
          );
        })}
      </View>

      <Drawer open={drawer} onClose={() => setDrawer(false)}>
        <View style={{ paddingHorizontal: space(5), paddingTop: insets.top + space(4), paddingBottom: space(3) }}>
          <Text style={{ color: color.paper, fontSize: 20, fontWeight: "700" }}>
            <Text style={{ color: color.saffron, fontFamily: font.serif, fontSize: 24 }}>O</Text> Osalytix
          </Text>
          {me ? (
            <Text style={{ color: color.mint, marginTop: space(1) }} numberOfLines={1}>
              {me.display_name} · {me.email}
            </Text>
          ) : null}
          <Button label="+  New chat" onPress={() => open({ mode: "chat" })} style={{ marginTop: space(4) }} />
        </View>
        <ScrollView contentContainerStyle={{ paddingHorizontal: space(3), paddingBottom: insets.bottom + space(8) }}>
          <Section title="Chats" />
          {threads.length === 0 ? <DrawerText>No chats yet.</DrawerText> : null}
          {threads.slice(0, 30).map((t) => (
            <DrawerItem
              key={t.id}
              label={t.title || "Untitled chat"}
              hint={t.dataset_name}
              active={focus.mode === "chat" && focus.threadId === t.id}
              onPress={() => open({ mode: "chat", threadId: t.id, source: files?.find((f) => f.upload.id === t.upload_id) ?? source })}
            />
          ))}
          <Section title="Analytics" />
          {FILE_TABS.map(([tab, label]) => (
            <DrawerItem key={tab} label={label} active={focus.mode === "analytics" && focus.tab === tab} onPress={() => open({ mode: "analytics", tab })} />
          ))}
          {source ? (
            <>
              <DrawerItem label="What-if scenarios" onPress={() => go({ name: "scenarios", source })} />
              <DrawerItem label="Recommendations" onPress={() => go({ name: "recommendations", source })} />
            </>
          ) : null}
          <Section title="Data" />
          <DrawerItem label="Switch file" onPress={() => { setDrawer(false); setPicker(true); }} />
          <DrawerItem label="Upload or manage files" onPress={() => go({ name: "files" })} />
          <Section title="Workspace" />
          <DrawerItem label="My memory" onPress={() => go({ name: "memory" })} />
          <DrawerItem label="Team" onPress={() => go({ name: "team" })} />
          <DrawerItem label="Activity history" onPress={() => go({ name: "audit" })} />
          <DrawerItem label="Help and support" onPress={() => go({ name: "support" })} />
          <DrawerItem label="Plan, usage and account" onPress={() => go({ name: "account" })} />
          <DrawerItem label="Sign out" onPress={nav.signOut} />
        </ScrollView>
      </Drawer>

      <Modal visible={picker} transparent animationType="slide" onRequestClose={() => setPicker(false)}>
        <Pressable style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.35)" }} onPress={() => setPicker(false)} accessibilityLabel="Close" />
        <View style={{ backgroundColor: color.paper, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: space(5), paddingBottom: insets.bottom + space(5), maxHeight: "70%" }}>
          <Text style={{ fontFamily: font.serif, fontSize: 22, color: color.ink, marginBottom: space(3) }}>Choose a file</Text>
          <ScrollView>
            {(files ?? []).map((f) => (
              <Pressable key={f.upload.id} onPress={() => open({ source: f })} accessibilityRole="button" style={{ paddingVertical: space(3), borderBottomWidth: 1, borderBottomColor: color.line }}>
                <Text style={{ fontSize: 16, fontWeight: f.upload.id === source?.upload.id ? "800" : "600", color: color.ink }} numberOfLines={1}>
                  {f.upload.id === source?.upload.id ? "✓ " : ""}
                  {f.datasetName}
                </Text>
                <Text style={s.muted} numberOfLines={1}>
                  {f.upload.filename} · {f.upload.row_count ?? "?"} rows
                </Text>
              </Pressable>
            ))}
          </ScrollView>
          <Button kind="secondary" label="Upload a new file" onPress={() => go({ name: "files" })} style={{ marginTop: space(4) }} />
        </View>
      </Modal>
    </SafeAreaView>
  );
}

function IconButton({ label, glyph, onPress }: { label: string; glyph: string; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={8}
      style={({ pressed }) => ({ width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center", backgroundColor: pressed ? color.fieldSoft : "transparent" })}
    >
      <Text style={{ color: color.paper, fontSize: 22 }}>{glyph}</Text>
    </Pressable>
  );
}

function Drawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  const { width } = useWindowDimensions();
  const size = Math.min(340, width * 0.84);
  const x = useRef(new Animated.Value(-size)).current;
  const [shown, setShown] = useState(open);

  useEffect(() => {
    if (open) setShown(true);
    Animated.timing(x, { toValue: open ? 0 : -size, duration: 220, useNativeDriver: true }).start(() => {
      if (!open) setShown(false);
    });
  }, [open, size]);

  if (!shown) return null;
  return (
    <View style={{ position: "absolute", top: 0, bottom: 0, left: 0, right: 0 }}>
      <Pressable style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.4)" }} onPress={onClose} accessibilityLabel="Close menu" />
      <Animated.View style={{ position: "absolute", top: 0, bottom: 0, left: 0, width: size, backgroundColor: color.field, transform: [{ translateX: x }] }}>
        {children}
      </Animated.View>
    </View>
  );
}

function Section({ title }: { title: string }) {
  return (
    <Text style={{ color: color.mint, fontSize: 11, fontWeight: "800", letterSpacing: 1.5, marginTop: space(5), marginBottom: space(1), marginLeft: space(2) }}>
      {title.toUpperCase()}
    </Text>
  );
}

function DrawerText({ children }: { children: ReactNode }) {
  return <Text style={{ color: color.mint, marginLeft: space(2), opacity: 0.8 }}>{children}</Text>;
}

function DrawerItem({ label, hint, active, onPress }: { label: string; hint?: string; active?: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      style={({ pressed }) => ({
        paddingVertical: space(2.5),
        paddingHorizontal: space(2),
        borderRadius: 10,
        backgroundColor: active ? color.fieldSoft : pressed ? "rgba(255,255,255,0.06)" : "transparent",
      })}
    >
      <Text style={{ color: color.paper, fontSize: 15, fontWeight: active ? "700" : "500" }} numberOfLines={1}>
        {label}
      </Text>
      {hint ? (
        <Text style={{ color: color.mint, fontSize: 12, opacity: 0.85 }} numberOfLines={1}>
          {hint}
        </Text>
      ) : null}
    </Pressable>
  );
}
