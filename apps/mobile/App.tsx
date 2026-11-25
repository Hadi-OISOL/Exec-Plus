/* Use case: Entry point of the Osalytix phone app.
What it does: Restores the secure session, asks new users the profile questions once, shows the single chat-style main screen and the pages opened from its menu, with Android back support. */

import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useState } from "react";
import { BackHandler, Text, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { api, ApiError, loadToken, saveToken } from "./src/api";
import { Focus, NavContext, Route } from "./src/nav";
import { AccountScreen } from "./src/screens/Account";
import { AuthScreen } from "./src/screens/Auth";
import { RecommendationsScreen, ScenariosScreen, SupportScreen, TeamScreen } from "./src/screens/Features";
import { FilesScreen } from "./src/screens/Files";
import { MainScreen } from "./src/screens/Main";
import { ProfileScreen } from "./src/screens/Profile";
import { AuditScreen, MemoryScreen } from "./src/screens/Workspace";
import { color } from "./src/theme";
import { Loading } from "./src/ui";

type Session = { workspaceId: string; profilePending: boolean };
const START: Focus = { mode: "chat", tab: "insights", chatKey: 0 };

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
  const [stack, setStack] = useState<Route[]>([{ name: "main" }]);
  const [focus, setFocus] = useState<Focus>(START);
  const [bootError, setBootError] = useState("");

  const start = useCallback(async () => {
    setBootError("");
    try {
      if (!(await loadToken())) return setSession(null);
      const workspaces = await api<{ id: string }[]>("/workspaces");
      const profile = await api<{ status: string }>("/me/profile").catch(() => ({ status: "completed" }));
      if (!workspaces.length) throw new Error("This account has no workspace yet. Create one on the website.");
      setSession({ workspaceId: workspaces[0].id, profilePending: profile.status === "pending" });
      setStack([{ name: "main" }]);
      setFocus(START);
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

  const nav = {
    push: (next: Route) => setStack((s) => [...s, next]),
    back,
    open: (next: Partial<Focus>) => {
      setFocus((current) => ({ ...current, threadId: undefined, question: undefined, ...next, chatKey: current.chatKey + 1 }));
      setStack([{ name: "main" }]);
    },
    workspaceId: session.workspaceId,
    signOut: async () => {
      await api("/auth/logout", { method: "POST" }).catch(() => undefined);
      await saveToken(null);
      setSession(null);
    },
  };
  const route = stack[stack.length - 1];

  return (
    <NavContext.Provider value={nav}>
      <View style={{ flex: 1, backgroundColor: color.field }}>
        {route.name === "main" ? (
          <MainScreen focus={focus} setFocus={setFocus} />
        ) : route.name === "files" ? (
          <FilesScreen />
        ) : route.name === "memory" ? (
          <MemoryScreen />
        ) : route.name === "audit" ? (
          <AuditScreen />
        ) : route.name === "account" ? (
          <AccountScreen />
        ) : route.name === "profile" ? (
          <ProfileScreen onDone={back} />
        ) : route.name === "team" ? (
          <TeamScreen workspaceId={session.workspaceId} />
        ) : route.name === "support" ? (
          <SupportScreen workspaceId={session.workspaceId} />
        ) : route.name === "scenarios" ? (
          <ScenariosScreen source={route.source} />
        ) : (
          <RecommendationsScreen source={route.source} />
        )}
      </View>
    </NavContext.Provider>
  );
}
