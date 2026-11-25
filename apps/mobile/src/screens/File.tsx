/* Use case: The analytics side of one data file on the phone, plus the "answer the file questions first" gate.
What it does: Checks the live data-brief so open file questions come first, then renders insights, the automatic dashboard and every per-file analysis tab with exact figures. */

import * as SecureStore from "expo-secure-store";
import { useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { api, rootOf, Source } from "../api";
import { color, font, space } from "../theme";
import { Bars, Card, Chip, ErrorText, Loading, P, Receipt, exact, s } from "../ui";
import type { Brief } from "./FileQuestions";
import { About, Checks, Findings, Forecast, Quality, Unusual } from "./FileTabs";

export type FileTab = "insights" | "dashboard" | "findings" | "checks" | "unusual" | "forecast" | "quality" | "about";
export const FILE_TABS: [FileTab, string][] = [
  ["insights", "Insights"],
  ["dashboard", "Dashboard"],
  ["findings", "Findings"],
  ["checks", "Checks"],
  ["unusual", "Unusual values"],
  ["forecast", "Forecast"],
  ["quality", "Data quality"],
  ["about", "About this data"],
];

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

export function useFileGate(source: Source | undefined, fresh?: boolean) {
  const [phase, setPhase] = useState<"checking" | "questions" | "ready">("checking");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [round, setRound] = useState(0);
  const id = source?.upload.id;

  useEffect(() => {
    if (!source || !id) return;
    let live = true;
    setPhase("checking");
    (async () => {
      if (skipped.has(id) || (await SecureStore.getItemAsync(doneKey(id)))) return live && setPhase("ready");
      for (let attempt = 0; attempt < (fresh ? 6 : 2); attempt += 1) {
        try {
          const value = await api<Brief>(`${rootOf(source)}/data-brief`, { method: "POST" });
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
  }, [id, fresh, round]);

  return {
    phase,
    brief,
    finish: async (saved: boolean) => {
      if (!id) return;
      if (saved) await SecureStore.setItemAsync(doneKey(id), "1");
      else skipped.add(id);
      setPhase("ready");
    },
    reviewAgain: async () => {
      if (!id) return;
      await SecureStore.deleteItemAsync(doneKey(id));
      skipped.delete(id);
      setRound((n) => n + 1);
    },
  };
}

export function FileAnalytics({
  source,
  tab,
  onTab,
  ask,
  onReview,
}: {
  source: Source;
  tab: FileTab;
  onTab: (tab: FileTab) => void;
  ask: (question: string) => void;
  onReview: () => void;
}) {
  const root = rootOf(source);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tiles, setTiles] = useState<Tile[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setOverview(null);
    setTiles(null);
    setError("");
    api<Overview>(`${root}/analyst-overview`).then(setOverview).catch((e) => setError(e.message));
    api<{ dashboard: { tiles: Tile[] } }>(`${root}/auto-dashboard`)
      .then((d) => setTiles(d.dashboard.tiles))
      .catch(() => setTiles([]));
  }, [root]);

  return (
    <View style={{ gap: space(4) }}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space(2) }}>
        {FILE_TABS.map(([key, label]) => (
          <Chip key={key} label={label} active={tab === key} onPress={() => onTab(key)} />
        ))}
        <Chip label="File questions" onPress={onReview} />
      </ScrollView>
      <ErrorText text={error} />
      {tab === "findings" ? (
        <Findings source={source} ask={ask} />
      ) : tab === "checks" ? (
        <Checks source={source} />
      ) : tab === "unusual" ? (
        <Unusual source={source} />
      ) : tab === "forecast" ? (
        <Forecast source={source} onReview={onReview} />
      ) : tab === "quality" ? (
        <Quality source={source} />
      ) : tab === "about" ? (
        <About source={source} ask={ask} />
      ) : tab === "insights" ? (
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
    </View>
  );
}
