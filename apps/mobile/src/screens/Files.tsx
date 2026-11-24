/* Use case: The phone app's home: the user's data files, uploads and sample files.
What it does: Lists every upload in the current workspace, uploads a picked file to the live API, imports fictional samples and shows storage use. */

import * as DocumentPicker from "expo-document-picker";
import { useCallback, useEffect, useState } from "react";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { api, Source, Upload } from "../api";
import { useNav } from "../nav";
import { color, font, space } from "../theme";
import { Button, Card, ErrorText, H, Loading, P, Screen, s } from "../ui";

type Dataset = { id: string; name: string };
type Sample = { id: string; name: string; description: string };

const MIME: Record<string, string> = {
  csv: "text/csv",
  txt: "text/plain",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};

function size(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}

export function FilesScreen() {
  const nav = useNav();
  const wid = nav.workspaceId;
  const [files, setFiles] = useState<Source[] | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [storage, setStorage] = useState<{ used_bytes: number; quota_bytes: number } | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const datasets = await api<Dataset[]>(`/workspaces/${wid}/datasets`);
      const lists = await Promise.all(
        datasets.map(async (d) => {
          const uploads = await api<Upload[]>(`/workspaces/${wid}/datasets/${d.id}/uploads`);
          return uploads.map((upload) => ({ workspaceId: wid, datasetId: d.id, datasetName: d.name, upload }));
        }),
      );
      setFiles(lists.flat().sort((a, b) => b.upload.created_at.localeCompare(a.upload.created_at)));
      api("/me/storage").then(setStorage).catch(() => undefined);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load files.");
      setFiles([]);
    }
  }, [wid]);

  useEffect(() => {
    load();
    api<Sample[]>("/samples").then(setSamples).catch(() => undefined);
  }, [load]);

  async function pick() {
    setError("");
    const picked = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true, multiple: false });
    if (picked.canceled || !picked.assets?.length) return;
    const asset = picked.assets[0];
    const extension = asset.name.split(".").pop()?.toLowerCase() ?? "";
    setBusy("Uploading " + asset.name);
    try {
      const blob = await (await fetch(asset.uri)).blob();
      const name = asset.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim() || "My data";
      const dataset = await api<Dataset>(`/workspaces/${wid}/datasets`, { body: { name: name.slice(0, 100) } });
      const upload = await api<Upload>(
        `/workspaces/${wid}/datasets/${dataset.id}/uploads?filename=${encodeURIComponent(asset.name)}`,
        { method: "POST", raw: blob, contentType: MIME[extension] ?? asset.mimeType ?? "application/octet-stream" },
      );
      await load();
      nav.push({ name: "file", fresh: true, source: { workspaceId: wid, datasetId: dataset.id, datasetName: dataset.name, upload } });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed.");
    } finally {
      setBusy("");
    }
  }

  async function sample(item: Sample) {
    setBusy("Adding " + item.name);
    setError("");
    try {
      const upload = await api<Upload>(`/workspaces/${wid}/samples/${item.id}`, { method: "POST" });
      await load();
      nav.push({ name: "file", fresh: true, source: { workspaceId: wid, datasetId: upload.dataset_id, datasetName: item.name, upload } });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not add the sample.");
    } finally {
      setBusy("");
    }
  }

  return (
    <Screen kicker="Your data" title="Files" scroll={false}>
      <ScrollView
        contentContainerStyle={{ gap: space(4), paddingBottom: space(24) }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
      >
        <Card style={{ backgroundColor: color.field, borderColor: color.field }}>
          <Text style={{ color: color.paper, fontFamily: font.serif, fontSize: 20 }}>Bring a file. Ask anything.</Text>
          <Text style={{ color: color.mint, marginTop: space(1), marginBottom: space(4), lineHeight: 20 }}>
            CSV, Excel, JSON, Parquet and more, up to 500 MB. Every answer is calculated from your file.
          </Text>
          <Button label={busy || "Upload a file"} onPress={pick} busy={!!busy} />
        </Card>
        <ErrorText text={error} />
        {storage && (
          <P muted>
            Storage: {size(storage.used_bytes)} of {size(storage.quota_bytes)} used
          </P>
        )}
        {files === null ? (
          <Loading label="Loading your files" />
        ) : files.length === 0 ? (
          <P muted>No files yet. Upload one or start with a sample below.</P>
        ) : (
          files.map((f) => (
            <Pressable key={f.upload.id} onPress={() => nav.push({ name: "file", source: f })} accessibilityRole="button">
              {({ pressed }) => (
                <Card style={{ opacity: pressed ? 0.85 : 1 }}>
                  <Text style={{ fontFamily: font.serif, fontSize: 18, color: color.ink }} numberOfLines={1}>
                    {f.datasetName}
                  </Text>
                  <Text style={[s.muted, { marginTop: 2 }]} numberOfLines={1}>
                    {f.upload.filename}
                  </Text>
                  <View style={[s.row, { marginTop: space(2) }]}>
                    <Text style={{ fontFamily: font.mono, color: color.saffronInk, fontSize: 12 }}>
                      {f.upload.row_count ?? "?"} rows · {f.upload.column_count ?? "?"} columns · {size(f.upload.size)}
                    </Text>
                  </View>
                </Card>
              )}
            </Pressable>
          ))
        )}
        {samples.length > 0 && (
          <>
            <H>Try a sample</H>
            <P muted>Fictional practice files — nothing real.</P>
            {samples.map((item) => (
              <Card key={item.id}>
                <Text style={{ fontWeight: "700", color: color.ink, fontSize: 15 }}>{item.name}</Text>
                <Text style={[s.muted, { marginVertical: space(2) }]} numberOfLines={3}>
                  {item.description}
                </Text>
                <Button kind="secondary" label="Use this sample" onPress={() => sample(item)} disabled={!!busy} />
              </Card>
            ))}
          </>
        )}
      </ScrollView>
    </Screen>
  );
}
