/* Use case: The phone app's account page.
What it does: Shows who is signed in, the workspace plan and usage from the live API, lets the user redo the profile questions, open the website and sign out. */

import { useEffect, useState } from "react";
import { Linking, Text, View } from "react-native";
import { api, SITE } from "../api";
import { useNav } from "../nav";
import { color, font, space } from "../theme";
import { Button, Card, ErrorText, H, Loading, P, Receipt, Screen } from "../ui";

type Me = { email: string; display_name: string };
type Usage = { assignment: { plan_key: string; ends_at: string }; allowances: Record<string, { limit: number | null; used: number; state: string }> };

const PLAN: Record<string, string> = { demo: "Free", starter: "Pro", growth: "Team", enterprise: "Enterprise" };
const LABEL: Record<string, string> = {
  datasets: "Files",
  processing: "Calculations",
  model_attempts: "AI requests",
  exports: "Exports",
  forecasts: "Forecasts",
  saved_studies: "Saved studies",
  seats: "Team seats",
};

export function AccountScreen() {
  const nav = useNav();
  const [me, setMe] = useState<Me | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Me>("/auth/me").then(setMe).catch((e) => setError(e.message));
    api<Usage>(`/workspaces/${nav.workspaceId}/plan-usage`).then(setUsage).catch(() => undefined);
  }, [nav.workspaceId]);

  return (
    <Screen kicker="Account" title={me ? `Hello, ${me.display_name.split(" ")[0]}.` : "Account"}>
      <ErrorText text={error} />
      {!me ? (
        <Loading label="Loading account" />
      ) : (
        <Card>
          <Text style={{ fontFamily: font.serif, fontSize: 19, color: color.ink }}>{me.display_name}</Text>
          <Text style={{ color: color.muted, marginTop: 2 }}>{me.email}</Text>
        </Card>
      )}
      {usage && (
        <Receipt title={`${PLAN[usage.assignment.plan_key] ?? usage.assignment.plan_key} plan`} stamp="THIS MONTH">
          {Object.entries(usage.allowances)
            .filter(([key]) => LABEL[key])
            .map(([key, a]) => (
              <View key={key} style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: space(1) }}>
                <Text style={{ color: color.ink }}>{LABEL[key]}</Text>
                <Text style={{ fontFamily: font.mono, color: a.state === "ok" ? color.ink : color.danger }}>
                  {a.used} / {a.limit ?? "∞"}
                </Text>
              </View>
            ))}
        </Receipt>
      )}
      <H>Settings</H>
      <Button kind="secondary" label="Redo the get-to-know-you questions" onPress={() => nav.push({ name: "profile" })} />
      <Button kind="secondary" label="Open Osalytix on the web" onPress={() => Linking.openURL(SITE)} />
      <P muted>Forecasts, what-if scenarios, exports, connectors and team settings are on the website for now.</P>
      <Button label="Sign out" onPress={nav.signOut} />
    </Screen>
  );
}
