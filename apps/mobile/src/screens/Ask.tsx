/* Use case: The phone app's Ask tab: chat with Osalytix straight away.
What it does: Opens a chat on the newest file and lets the user switch to another file from the workspace. */

import { useEffect, useState } from "react";
import { Pressable, Text } from "react-native";
import { listFiles, Source } from "../api";
import { useNav } from "../nav";
import { color, font } from "../theme";
import { Button, Card, Loading, P, Screen, s } from "../ui";
import { ChatScreen } from "./Chat";

export function AskScreen() {
  const nav = useNav();
  const [files, setFiles] = useState<Source[] | null>(null);
  const [chosen, setChosen] = useState<Source | null>(null);
  const [picking, setPicking] = useState(false);

  useEffect(() => {
    listFiles(nav.workspaceId)
      .then((list) => {
        setFiles(list);
        setChosen((current) => current ?? list[0] ?? null);
      })
      .catch(() => setFiles([]));
  }, [nav.workspaceId]);

  if (files === null)
    return (
      <Screen kicker="Ask Osalytix" title="Ask">
        <Loading label="Loading your files" />
      </Screen>
    );

  if (!files.length)
    return (
      <Screen kicker="Ask Osalytix" title="Ask anything about your data.">
        <P>First add a file. Then ask in your own words, in any language.</P>
        <Button label="Add a file" onPress={() => nav.tab({ name: "files" })} />
      </Screen>
    );

  if (picking || !chosen)
    return (
      <Screen kicker="Ask Osalytix" title="Which file?" onBack={chosen ? () => setPicking(false) : undefined}>
        {files.map((f) => (
          <Pressable key={f.upload.id} accessibilityRole="button" onPress={() => { setChosen(f); setPicking(false); }}>
            <Card style={f.upload.id === chosen?.upload.id ? { borderColor: color.field, borderWidth: 2 } : undefined}>
              <Text style={{ fontFamily: font.serif, fontSize: 17, color: color.ink }} numberOfLines={1}>
                {f.datasetName}
              </Text>
              <Text style={s.muted} numberOfLines={1}>
                {f.upload.filename}
              </Text>
            </Card>
          </Pressable>
        ))}
      </Screen>
    );

  return <ChatScreen key={chosen.upload.id} workspaceId={nav.workspaceId} source={chosen} asTab onSwitch={() => setPicking(true)} />;
}
