/* Use case: Entry point of the Osalytix phone app.
What it does: Restores the secure session, asks new users the profile questions once, and switches between the Files, Chats and Account tabs and their pushed screens with Android back support. */

import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useState } from "react";
import { BackHandler, Pressable, Text, View } from "react-native";
import { SafeAreaProvider, useSafeAreaInsets } from "react-native-safe-area-context";
import { api, ApiError, loadToken, saveToken } from "./src/api";
import { NavContext, Route } from "./src/nav";
import { AccountScreen } from "./src/screens/Account";
import { AuthScreen } from "./src/screens/Auth";
import { ChatScreen } from "./src/screens/Chat";
import { ChatsScreen } from "./src/screens/Chats";
import { FileScreen } from "./src/screens/File";
import { FilesScreen } from "./src/screens/Files";
import { HomeScreen } from "./src/screens/Home";
import { ProfileScreen } from "./src/screens/Profile";
import { color } from "./src/theme";
import { Loading } from "./src/ui";

type Session = { workspaceId: string; profilePending: boolean };
const TABS: { route: Route; label: string; glyph: string }[] = [
  { route: { name: "home" }, label: "Home", glyph: "⌂" },
  { route: { name: "files" }, label: "Files", glyph: "▤" },
  { route: { name: "chats" }, label: "Chats", glyph: "❝" },
  { route: { name: "account" }, label: "Account", glyph: "◉" },
];

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <Root />
    </SafeAreaProvider>
  );
}

function Root() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [stack, setStack] = useState<Route[]>([{ name: "home" }]);
  const [bootError, setBootError] = useState("");

  const start = useCallback(async () => {
    setBootError("");
    try {
      if (!(await loadToken())) return setSession(null);
      const workspaces = await api<{ id: string }[]>("/workspaces");
      const profile = await api<{ status: string }>("/me/profile").catch(() => ({ status: "completed" }));
      if (!workspaces.length) throw new Error("This account has no workspace yet. Create one on the website.");
      setSession({ workspaceId: workspaces[0].id, profilePending: profile.status === "pending" });
      setStack([{ name: "home" }]);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        await saveToken(null);
        return setSession(null);
      }
      setBootError(cause instanceof Error ? cause.message : "Could not reach Osalytix.");
      setSession(null);
    }
  }, []);

  useEffect(() => {
    start();
  }, [start]);

  const back = useCallback(() => setStack((s) => (s.length > 1 ? s.slice(0, -1) : s)), []);

  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (stack.length > 1) {
        back();
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [stack.length, back]);

  if (session === undefined)
    return (
      <View style={{ flex: 1, backgroundColor: color.paper, justifyContent: "center" }}>
        <Loading label="Opening Osalytix…" />
      </View>
    );

  if (session === null)
    return (
      <View style={{ flex: 1 }}>
        {bootError ? (
          <Text style={{ backgroundColor: color.danger, color: color.white, padding: 12, paddingTop: 48 }}>{bootError}</Text>
        ) : null}
        <AuthScreen onSignedIn={start} />
      </View>
    );

  if (session.profilePending)
    return <ProfileScreen onDone={() => setSession({ ...session, profilePending: false })} />;

  const route = stack[stack.length - 1];
  const nav = {
    push: (next: Route) => setStack((s) => [...s, next]),
    back,
    tab: (next: Route) => setStack([next]),
    workspaceId: session.workspaceId,
    signOut: async () => {
      await api("/auth/logout", { method: "POST" }).catch(() => undefined);
      await saveToken(null);
      setSession(null);
    },
  };

  return (
    <NavContext.Provider value={nav}>
      <View style={{ flex: 1, backgroundColor: color.paper }}>
        <View style={{ flex: 1 }}>{renderRoute(route, back)}</View>
        {stack.length === 1 && <TabBar current={route.name} onSelect={nav.tab} />}
      </View>
    </NavContext.Provider>
  );
}

function renderRoute(route: Route, back: () => void) {
  switch (route.name) {
    case "home":
      return <HomeScreen />;
    case "files":
      return <FilesScreen />;
    case "chats":
      return <ChatsScreen />;
    case "account":
      return <AccountScreen />;
    case "profile":
      return <ProfileScreen onDone={back} />;
    case "file":
      return <FileScreen key={route.source.upload.id} source={route.source} fresh={route.fresh} />;
    case "chat":
      return <ChatScreen key={route.threadId ?? route.source?.upload.id} {...route} />;
  }
}

function TabBar({ current, onSelect }: { current: string; onSelect: (r: Route) => void }) {
  const insets = useSafeAreaInsets();
  return (
    <View style={{ flexDirection: "row", backgroundColor: color.card, borderTopWidth: 1, borderTopColor: color.line, paddingBottom: insets.bottom }}>
      {TABS.map((tab) => {
        const active = tab.route.name === current;
        return (
          <Pressable
            key={tab.label}
            onPress={() => onSelect(tab.route)}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            style={{ flex: 1, alignItems: "center", paddingVertical: 10 }}
          >
            <Text style={{ fontSize: 18, color: active ? color.saffronInk : color.muted }}>{tab.glyph}</Text>
            <Text style={{ fontSize: 12, fontWeight: active ? "800" : "600", color: active ? color.field : color.muted }}>{tab.label}</Text>
            {active && <View style={{ height: 3, width: 24, backgroundColor: color.saffron, borderRadius: 2, marginTop: 3 }} />}
          </Pressable>
        );
      })}
    </View>
  );
}
