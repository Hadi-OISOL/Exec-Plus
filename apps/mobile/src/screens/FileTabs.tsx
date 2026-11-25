/* Use case: The extra analytics views for one file in the phone app (the same analyses the website shows).
What it does: Loads findings, hypothesis checks, unusual values, data quality, forecasts and the "about this data" follow-up questions from the live API and renders them as receipts. */

import { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { api, rootOf, Source } from "../api";
import { color, font, space } from "../theme";
import { Bars, Button, Card, Chip, ErrorText, Field, H, Loading, P, Receipt, Table, exact, s, short } from "../ui";

type Ask = (question: string) => void;

function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setData(null);
    setError("");
    load()
      .then((value) => live && setData(value))
      .catch((cause) => live && setError(cause instanceof Error ? cause.message : "Could not load this view."));
    return () => {
      live = false;
    };
  }, deps);
  return { data, error };
}

function Limits({ items }: { items?: string[] }) {
  return <>{(items ?? []).map((line) => <P key={line} muted>{line}</P>)}</>;
}

export function Findings({ source, ask }: { source: Source; ask: Ask }) {
  type Discovery = {
    summary: string;
    shape: { rows: string; columns: string; metrics: string; dimensions: string };
    findings: { id: string; title: string; text: string; question: string }[];
    quality: { code: string; text: string; action: string }[];
    suggestions: string[];
    limitations: string[];
  };
  const { data, error } = useLoad(() => api<Discovery>(`${rootOf(source)}/discovery`), [source.upload.id]);
  if (error) return <ErrorText text={error} />;
  if (!data) return <Loading label="Finding the first facts in your file…" />;
  return (
    <>
      <Card>
        <P>{data.summary}</P>
        <Text style={{ fontFamily: font.mono, color: color.saffronInk, fontSize: 12, marginTop: space(2) }}>
          {data.shape.rows} rows · {data.shape.columns} columns · {data.shape.metrics} measures · {data.shape.dimensions} categories
        </Text>
      </Card>
      {data.findings.map((f) => (
        <Receipt key={f.id} title={f.title} stamp="EXACT">
          <P>{f.text}</P>
          <View style={[s.row, { marginTop: space(2) }]}>
            <Chip label="Ask this" onPress={() => ask(f.question)} />
          </View>
        </Receipt>
      ))}
      {data.quality.map((q) => (
        <P key={q.code} muted>
          {q.text} {q.action}
        </P>
      ))}
      <H>Good questions to ask</H>
      <View style={s.row}>
        {data.suggestions.map((q) => <Chip key={q} label={q} onPress={() => ask(q)} />)}
      </View>
      <Limits items={data.limitations} />
    </>
  );
}

export function Checks({ source }: { source: Source }) {
  type Item = { id: string; statement: string; status: string; finding: string; question?: string };
  const { data, error } = useLoad(
    () => api<{ items: Item[]; limitations: string[] }>(`/workspaces/${source.workspaceId}/uploads/${source.upload.id}/hypotheses`),
    [source.upload.id],
  );
  if (error) return <ErrorText text={error} />;
  if (!data) return <Loading label="Testing ideas against your rows…" />;
  const label: Record<string, string> = { supported: "SUPPORTED", not_supported: "NOT SUPPORTED", inconclusive: "UNCLEAR" };
  return (
    <>
      <P muted>Ideas about your data, each checked against the actual rows.</P>
      {data.items.map((item) => (
        <Receipt key={item.id} title={item.statement} stamp={label[item.status] ?? item.status.toUpperCase()}>
          <P>{item.finding}</P>
        </Receipt>
      ))}
      <Limits items={data.limitations} />
    </>
  );
}

export function Unusual({ source }: { source: Source }) {
  type Scan = {
    state: string;
    summary: string;
    findings: { row: string; column: string; value: string; direction: string; explanation: string; score: string }[];
    measures: { column: string; checked: number; usual_low: string; usual_high: string; flagged: number }[];
    limitations: string[];
    message?: string;
  };
  const [scan, setScan] = useState<Scan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = async () => {
    setBusy(true);
    setError("");
    try {
      setScan(await api<Scan>(`${rootOf(source)}/decision-analysis/unusual-values`, { method: "POST" }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The scan could not run.");
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    run();
  }, [source.upload.id]);
  if (!scan) return busy ? <Loading label="Scanning every measure for unusual values…" /> : <ErrorText text={error} />;
  return (
    <>
      <Card>
        <P>{scan.summary || scan.message}</P>
      </Card>
      {(scan.findings ?? []).map((f, i) => (
        <Receipt key={`${f.row}-${f.column}-${i}`} title={`${f.column}: ${exact(f.value)}`} stamp={f.direction === "high" ? "HIGH" : "LOW"}>
          <P>{f.explanation}</P>
        </Receipt>
      ))}
      {scan.measures?.length ? (
        <Table
          columns={["Measure", "Checked", "Usual low", "Usual high", "Flagged"]}
          rows={scan.measures.map((m) => [m.column, m.checked, m.usual_low, m.usual_high, m.flagged])}
        />
      ) : null}
      <Limits items={scan.limitations} />
      <Button kind="secondary" label="Scan again" onPress={run} busy={busy} />
    </>
  );
}

export function Quality({ source }: { source: Source }) {
  type Report = {
    legacy_profile_score: string;
    findings: { code: string; count: number; denominator: number; column: string | null; message: string }[];
    limitations: string[];
  };
  const { data, error } = useLoad(() => api<Report>(`${rootOf(source)}/quality`), [source.upload.id]);
  if (error) return <ErrorText text={error} />;
  if (!data) return <Loading label="Checking data quality…" />;
  const problems = data.findings.filter((f) => f.count > 0);
  return (
    <>
      <Card>
        <Text style={s.muted}>File consistency score</Text>
        <Text style={{ fontFamily: font.serif, fontSize: 40, color: color.field }}>{short(data.legacy_profile_score)}</Text>
        <P muted>{problems.length ? `${problems.length} checks found something to review.` : "Every basic check passed."}</P>
      </Card>
      {data.findings.map((f, i) => (
        <Receipt key={`${f.code}-${f.column}-${i}`} title={`${f.code.replace(/_/g, " ")}${f.column ? ` · ${f.column}` : ""}`} stamp={f.count ? `${f.count} FOUND` : "OK"}>
          <P muted>
            {f.count} of {f.denominator}. {f.message}
          </P>
        </Receipt>
      ))}
      <Limits items={data.limitations} />
    </>
  );
}

type Point = { period: string; estimate: string; lower: string; upper: string };
type Run = {
  id: string;
  name: string;
  created_at: string;
  request: { metric: string; horizon: number; frequency: string };
  result?: { predictions: Point[]; accuracy: { mae: string | null; wape_percent: string | null }; method: { id: string } };
};

export function Forecast({ source, onReview }: { source: Source; onReview: () => void }) {
  type Options = {
    state: string;
    revision_id: string;
    understanding_id: string | null;
    limitations: string[];
    blockers: { code: string; message: string }[];
    quick_start?: { kind: string; message: string; metric?: string; [k: string]: unknown };
  };
  const dataset = `/workspaces/${source.workspaceId}/datasets/${source.datasetId}`;
  const [options, setOptions] = useState<Options | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [shown, setShown] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Options>(`${rootOf(source)}/forecasts/options`).then(setOptions).catch((e) => setError(e.message));
    api<Run[]>(`${dataset}/forecasts`).then(setRuns).catch(() => undefined);
  }, [source.upload.id]);

  async function quick() {
    const q = options?.quick_start;
    if (!options || q?.kind !== "forecast") return;
    setBusy(true);
    setError("");
    try {
      const keys = ["name", "time_column", "metric", "aggregation", "frequency", "horizon", "coverage_start", "coverage_end"];
      const run = await api<Run>(`${rootOf(source)}/forecasts`, {
        body: {
          ...Object.fromEntries(keys.map((k) => [k, q[k]])),
          season_length: null,
          filters: [],
          coverage_confirmed: true,
          revision_id: options.revision_id,
          understanding_id: options.understanding_id,
        },
      });
      setShown(run);
      setRuns((all) => [run, ...all.filter((r) => r.id !== run.id)]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The forecast could not run.");
    } finally {
      setBusy(false);
    }
  }

  async function open(id: string) {
    setBusy(true);
    try {
      setShown(await api<Run>(`${dataset}/forecasts/${id}`));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not open the forecast.");
    } finally {
      setBusy(false);
    }
  }

  if (!options) return error ? <ErrorText text={error} /> : <Loading label="Checking whether this file can be forecast…" />;
  const q = options.quick_start;
  const predictions = shown?.result?.predictions ?? [];
  return (
    <>
      <Card>
        <P>{q?.message ?? "Forecasts need a date column and confirmed measures."}</P>
        {q?.kind === "forecast" ? (
          <Button label={`Forecast ${q.metric}`} onPress={quick} busy={busy} style={{ marginTop: space(3) }} />
        ) : options.state !== "ready" ? (
          <Button kind="secondary" label="Answer the file questions first" onPress={onReview} style={{ marginTop: space(3) }} />
        ) : null}
      </Card>
      {options.blockers.map((b) => <P key={b.code} muted>{b.message}</P>)}
      <ErrorText text={error} />
      {shown && (
        <Receipt title={shown.name} stamp="ESTIMATE">
          <P muted>
            {shown.request.metric} · next {shown.request.horizon} {shown.request.frequency === "monthly" ? "months" : "days"} · method {shown.result?.method.id}
          </P>
          <Bars rows={predictions.slice(0, 12).map((p) => ({ label: p.period, value: p.estimate }))} />
          <Table columns={["Period", "Estimate", "Low", "High"]} rows={predictions.map((p) => [p.period, p.estimate, p.lower, p.upper])} />
          {shown.result?.accuracy.mae ? (
            <P muted>Average error on past data: {short(shown.result.accuracy.mae)}{shown.result.accuracy.wape_percent ? ` (${short(shown.result.accuracy.wape_percent)}%)` : ""}</P>
          ) : null}
          <P muted>Forecasts are estimates, not exact numbers. The range is a heuristic, not a guarantee.</P>
        </Receipt>
      )}
      {runs.length > 0 && <H>Saved forecasts</H>}
      {runs.map((r) => (
        <Card key={r.id}>
          <Text style={{ fontWeight: "700", color: color.ink }}>{r.name}</Text>
          <Text style={s.muted}>{new Date(r.created_at).toLocaleString()}</Text>
          <Button kind="ghost" label="Open ›" onPress={() => open(r.id)} />
        </Card>
      ))}
      <Limits items={options.limitations} />
    </>
  );
}

export function About({ source, ask }: { source: Source; ask: Ask }) {
  type Question = { id: string; prompt: string; kind: string; options: string[]; hint: string };
  type Purpose = {
    summary: string;
    benefits: string[];
    suggested_questions: { title: string; question: string }[];
    follow_up?: { questions: Question[]; answers: Record<string, unknown>; status: string };
  };
  const { data, error } = useLoad(
    () => api<Purpose>(`/workspaces/${source.workspaceId}/uploads/${source.upload.id}/dataset-purpose`),
    [source.upload.id],
  );
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [saved, setSaved] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (data?.follow_up) setAnswers(data.follow_up.answers ?? {});
  }, [data]);
  if (error) return <ErrorText text={error} />;
  if (!data) return <Loading label="Working out what this data is for…" />;

  async function save(status: "completed" | "skipped") {
    setBusy(true);
    setSaved("");
    try {
      const kept = Object.fromEntries(Object.entries(answers).filter(([, v]) => typeof v === "string" && v.trim()));
      await api(`${rootOf(source)}/dataset-focus`, { method: "PUT", body: { answers: status === "completed" ? kept : {}, status } });
      setSaved(status === "completed" ? "Saved. Your dashboard and suggestions now follow these answers." : "Skipped.");
    } catch (cause) {
      setSaved(cause instanceof Error ? cause.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Card>
        <P>{data.summary}</P>
      </Card>
      {data.benefits.map((b) => <P key={b}>• {b}</P>)}
      <View style={s.row}>
        {data.suggested_questions.map((q) => <Chip key={q.question} label={q.title} onPress={() => ask(q.question)} />)}
      </View>
      {data.follow_up && data.follow_up.questions.length > 0 && (
        <Receipt title="A few questions about this data" stamp={data.follow_up.status === "completed" ? "ANSWERED" : undefined}>
          {data.follow_up.questions.map((q) => {
            const value = typeof answers[q.id] === "string" ? (answers[q.id] as string) : "";
            const set = (v: string) => setAnswers({ ...answers, [q.id]: v });
            return (
              <View key={q.id} style={{ marginBottom: space(3), gap: space(2) }}>
                {q.kind === "text" ? (
                  <Field label={q.prompt} value={value} onChangeText={set} maxLength={120} />
                ) : (
                  <>
                    <Text style={s.label}>{q.prompt}</Text>
                    <View style={s.row}>
                      {q.options.map((o) => (
                        <Chip key={o} label={o} active={value === o} onPress={() => set(value === o ? "" : o)} />
                      ))}
                    </View>
                  </>
                )}
              </View>
            );
          })}
          <Button label="Save my answers" onPress={() => save("completed")} busy={busy} />
          <Button kind="ghost" label="Skip" onPress={() => save("skipped")} disabled={busy} />
          {saved ? <P muted>{saved}</P> : null}
        </Receipt>
      )}
    </>
  );
}
