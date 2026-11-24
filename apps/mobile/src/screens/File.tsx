/* Use case: Opens one data file on the phone: its questions first, then insights and the automatic dashboard.
What it does: Checks the live data-brief and shows only the file questions while any remain, then loads the analyst overview and auto dashboard with exact figures and an Ask button. */

import * as SecureStore from "expo-secure-store";
import { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { api, rootOf, Source } from "../api";
import { useNav } from "../nav";
import { color, font, space } from "../theme";
import { Bars, Button, Card, Chip, ErrorText, Loading, P, Receipt, Screen, exact, s } from "../ui";
import { Brief, FileQuestions } from "./FileQuestions";

type ChartRow = { label: string; value?: string; count?: string };
type Chart = { type: string; title: string; y?: { label: string; unit: string | null }; rows: ChartRow[] } | null;
type Overview = {
  kpis: { id: string; label: string; value: string; unit: string | null; detail: string }[];
  insights: { id: string; title: string; summary: string; statements: string[]; chart: Chart }[];
  limitations?: string[];
};
type Tile = { id: string; kind: string; title: string; reason: string; kpi: { label: string; value: string; unit: string | null } | null; chart: Chart };

const skipped = new Set<string>();
const doneKey = (id: string) => `brief.${id}`;

function chartRows(chart: Chart) {
  return (chart?.rows ?? []).map((r) => ({ label: r.label, value: r.value ?? r.count }));
}

export function FileScreen({ source, fresh }: { source: Source; fresh?: boolean }) {
  const nav = useNav();
  const root = rootOf(source);
  const [phase, setPhase] = useState<"checking" | "questions" | "ready">("checking");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [tab, setTab] = useState<"insights" | "dashboard">("insights");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tiles, setTiles] = useState<Tile[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    (async () => {
      if (skipped.has(source.upload.id) || (await SecureStore.getItemAsync(doneKey(source.upload.id)))) return live && setPhase("ready");
      for (let attempt = 0; attempt < (fresh ? 6 : 2); attempt += 1) {
        try {
          const value = await api<Brief>(`${root}/data-brief`, { method: "POST" });
          if (!live) return;
          const unavailable = value.source !== "model" && !value.model_enabled && value.review_mode !== "missing";
          if (value.already_confirmed || unavailable) return setPhase("ready");
          setBrief(value);
          return setPhase("questions");
        } catch {
          await new Promise((r) => setTimeout(r, 1200));
        }
      }
      if (live) setPhase("ready");
    })();
    return () => {
      live = false;
    };
  }, [root, source.upload.id, fresh]);

  useEffect(() => {
    if (phase !== "ready") return;
    setError("");
    api<Overview>(`${root}/analyst-overview`).then(setOverview).catch((e) => setError(e.message));
    api<{ dashboard: { tiles: Tile[] } }>(`${root}/auto-dashboard`)
      .then((d) => setTiles(d.dashboard.tiles))
      .catch(() => setTiles([]));
  }, [phase, root]);

  if (phase === "checking")
    return (
      <Screen kicker={source.upload.filename} title={source.datasetName} onBack={nav.back}>
        <Loading label="Reading your file…" />
      </Screen>
    );

  if (phase === "questions" && brief)
    return (
      <FileQuestions
        brief={brief}
        root={root}
        title={source.datasetName}
        onDone={async (saved) => {
          if (saved) await SecureStore.setItemAsync(doneKey(source.upload.id), "1");
          else skipped.add(source.upload.id);
          setPhase("ready");
        }}
      />
    );

  const ask = (question?: string) => nav.push({ name: "chat", workspaceId: source.workspaceId, source, question });

  return (
    <Screen kicker={source.upload.filename} title={source.datasetName} onBack={nav.back}>
      <Button label="Ask about this file" onPress={() => ask()} />
      <View style={s.row}>
        <Chip label="Insights" active={tab === "insights"} onPress={() => setTab("insights")} />
        <Chip label="Dashboard" active={tab === "dashboard"} onPress={() => setTab("dashboard")} />
        <Chip label="File questions" onPress={async () => { await SecureStore.deleteItemAsync(doneKey(source.upload.id)); skipped.delete(source.upload.id); setPhase("checking"); }} />
      </View>
      <ErrorText text={error} />
      {tab === "insights" ? (
        overview === null ? (
          <Loading label="Six analysts are checking your file…" />
        ) : (
          <>
            <View style={[s.row, { gap: space(3) }]}>
              {overview.kpis.map((k) => (
                <Card key={k.id} style={{ width: "47%", padding: space(3) }}>
                  <Text style={s.muted}>{k.label}</Text>
                  <Text style={{ fontFamily: font.serif, fontSize: 26, color: color.ink }}>
                    {exact(k.value)}
                    {k.unit ? <Text style={{ fontSize: 16 }}> {k.unit}</Text> : null}
                  </Text>
                </Card>
              ))}
            </View>
            {overview.insights.map((insight) => (
              <Receipt key={insight.id} title={insight.title} stamp="DOUBLE-CHECKED">
                <P>{insight.summary}</P>
                {insight.chart && insight.chart.rows?.length ? <Bars rows={chartRows(insight.chart)} unit={insight.chart.y?.unit} /> : null}
                {insight.statements.slice(1).map((line) => (
                  <Text key={line} style={[s.muted, { marginTop: space(2) }]}>
                    {line}
                  </Text>
                ))}
                <View style={[s.row, { marginTop: space(3) }]}>
                  <Chip label="Ask about this" onPress={() => ask(`Tell me more about ${insight.title}`)} />
                </View>
              </Receipt>
            ))}
            {(overview.limitations ?? []).map((line) => (
              <P key={line} muted>
                {line}
              </P>
            ))}
          </>
        )
      ) : tiles === null ? (
        <Loading label="Building your dashboard…" />
      ) : tiles.length === 0 ? (
        <P muted>No dashboard yet for this file.</P>
      ) : (
        tiles.map((tile) =>
          tile.kpi ? (
            <Card key={tile.id}>
              <Text style={s.muted}>{tile.kpi.label}</Text>
              <Text style={{ fontFamily: font.serif, fontSize: 34, color: color.field }}>
                {exact(tile.kpi.value)}
                {tile.kpi.unit ? ` ${tile.kpi.unit}` : ""}
              </Text>
              <P muted>{tile.reason}</P>
            </Card>
          ) : (
            <Receipt key={tile.id} title={tile.title}>
              <P muted>{tile.reason}</P>
              {tile.chart ? <Bars rows={chartRows(tile.chart)} unit={tile.chart.y?.unit} /> : null}
            </Receipt>
          ),
        )
      )}
    </Screen>
  );
}
