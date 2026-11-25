/* Use case: Website-only Osalytix features brought to the phone app: what-if scenarios, budget recommendations, team, support and PDF export.
What it does: Calls the live decision-analysis, members/invitations, support-ticket and answer PDF routes and shows the server's exact results. */

import { File, Paths } from "expo-file-system";
import * as Sharing from "expo-sharing";
import { useEffect, useState } from "react";
import { Share, Text, View } from "react-native";
import { SITE, api, loadToken, rootOf, Source } from "../api";
import { useNav } from "../nav";
import { color, font, space } from "../theme";
import { Bars, Button, Card, Chip, ErrorText, Field, H, Loading, P, Receipt, Screen, Table, exact, s } from "../ui";

const why = (cause: unknown, fallback: string) => (cause instanceof Error ? cause.message : fallback);

type Options = {
  state: string;
  revision_id: string;
  understanding_id: string | null;
  metrics: { name: string; unit: string }[];
  entities: string[];
};
type RunSummary = { id: string; name: string; kind: string; method_version?: string; created_at: string };
type Run<R> = { current: boolean; run: RunSummary & { result: R; evidence: { units: Record<string, string> } } };

function useAnalysis(source: Source, keep: (run: RunSummary) => boolean) {
  const runsPath = `/workspaces/${source.workspaceId}/datasets/${source.datasetId}/decision-analysis`;
  const [options, setOptions] = useState<Options | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState("");
  const loadRuns = () =>
    api<RunSummary[]>(runsPath)
      .then((all) => setRuns(all.filter(keep)))
      .catch(() => undefined);
  useEffect(() => {
    api<Options>(`${rootOf(source)}/decision-analysis/options`).then(setOptions).catch((e) => setError(why(e, "Could not load this file.")));
    loadRuns();
  }, [source.upload.id]);
  return { options, runs, error, setError, loadRuns, runsPath };
}

function NotReady() {
  return (
    <Card>
      <P>Confirm what each column means and give every measure a fixed unit before using this.</P>
      <P muted>Open the file and answer its questions first.</P>
    </Card>
  );
}

function Lines({ items }: { items?: string[] }) {
  return <>{(items ?? []).map((line) => <P key={line} muted>{line}</P>)}</>;
}

function Saved({ runs, onOpen, busy }: { runs: RunSummary[]; onOpen: (id: string) => void; busy: boolean }) {
  if (!runs.length) return null;
  return (
    <>
      <H>Saved ({runs.length})</H>
      {runs.map((r) => (
        <Button key={r.id} kind="secondary" label={`${r.name} · ${new Date(r.created_at).toLocaleDateString()}`} onPress={() => onOpen(r.id)} disabled={busy} />
      ))}
    </>
  );
}

type ScenarioResult = {
  baseline: string;
  sample_count: number;
  metric: string;
  aggregation: string;
  limitations: string[];
  alternatives: { name: string; result: string; difference: string; percentage_difference: string | null }[];
};

const isAggregateScenario = (r: RunSummary) =>
  r.kind === "scenario_comparison" && !(r.method_version ?? "").startsWith("source-unit-economics");

export function ScenariosScreen({ source }: { source: Source }) {
  const nav = useNav();
  const { options, runs, error, setError, loadRuns, runsPath } = useAnalysis(source, isAggregateScenario);
  const [metric, setMetric] = useState("");
  const [aggregation, setAggregation] = useState<"sum" | "avg">("sum");
  const [changes, setChanges] = useState("10, -5");
  const [confirmed, setConfirmed] = useState(false);
  const [shown, setShown] = useState<Run<ScenarioResult> | null>(null);
  const [busy, setBusy] = useState(false);

  const chosen = metric || options?.metrics[0]?.name || "";

  async function work(action: () => Promise<Run<ScenarioResult>>) {
    setBusy(true);
    setError("");
    try {
      setShown(await action());
    } catch (cause) {
      setError(why(cause, "The comparison could not run."));
    } finally {
      setBusy(false);
    }
  }

  function run() {
    if (!options) return;
    const values = changes.split(/[,\s]+/).map((v) => v.replace(/%$/, "").replace(/^\+/, "")).filter(Boolean);
    if (!values.length || values.length > 5 || values.some((v) => !/^-?\d+(\.\d+)?$/.test(v)))
      return setError("Enter one to five percentage changes, for example 10, -5.");
    work(async () => {
      const result = await api<Run<ScenarioResult>>(`${rootOf(source)}/decision-analysis/scenarios`, {
        body: {
          name: `What-if: ${chosen}`.slice(0, 100),
          metric: chosen,
          aggregation,
          revision_id: options.revision_id,
          understanding_id: options.understanding_id,
          filters: [],
          alternatives: values.map((v) => ({ name: `${v.startsWith("-") ? "" : "+"}${v}%`, operation: "percent_change", value: v })),
          assumptions_confirmed: true,
          parent_run_id: null,
        },
      });
      setConfirmed(false);
      loadRuns();
      return result;
    });
  }

  const result = shown?.run.result;
  const unit = result ? shown?.run.evidence.units[result.metric] ?? "" : "";
  return (
    <Screen kicker="What if" title="Try a change" onBack={nav.back}>
      <ErrorText text={error} />
      {!options ? (
        error ? null : <Loading label="Checking your measures…" />
      ) : options.state !== "ready" ? (
        <NotReady />
      ) : (
        <>
          <P muted>Change one measure by a percentage and compare it with your data. Your file stays untouched.</P>
          <Text style={s.label}>Measure</Text>
          <View style={s.row}>
            {options.metrics.map((m) => (
              <Chip key={m.name} label={`${m.name} · ${m.unit}`} active={m.name === chosen} onPress={() => { setMetric(m.name); setConfirmed(false); }} />
            ))}
          </View>
          <Text style={s.label}>Start from the</Text>
          <View style={s.row}>
            <Chip label="Total" active={aggregation === "sum"} onPress={() => { setAggregation("sum"); setConfirmed(false); }} />
            <Chip label="Average" active={aggregation === "avg"} onPress={() => { setAggregation("avg"); setConfirmed(false); }} />
          </View>
          <Field label="Changes in % (up to 5)" value={changes} onChangeText={(v) => { setChanges(v); setConfirmed(false); }} placeholder="e.g. 10, -5" maxLength={60} />
          <Chip label="I understand these are my assumptions, not forecasts" active={confirmed} onPress={() => setConfirmed(!confirmed)} />
          <Button label="Compare" onPress={run} busy={busy} disabled={!confirmed} />
        </>
      )}
      {result && shown && (
        <Receipt title={shown.run.name} stamp="EXACT">
          <P muted>
            {shown.current ? "Current data." : "Older data or meanings — run again for current data."} {exact(result.sample_count)} records.
          </P>
          <Table
            columns={["Option", `Value (${unit})`, "Change", "Change %"]}
            rows={[
              [`Starting ${result.aggregation === "avg" ? "average" : "total"}`, result.baseline, "0", "0"],
              ...result.alternatives.map((a) => [a.name, a.result, a.difference, a.percentage_difference ?? "—"]),
            ]}
          />
          <Bars rows={[{ label: "Starting value", value: result.baseline }, ...result.alternatives.map((a) => ({ label: a.name, value: a.result }))]} unit={unit} />
          <Lines items={result.limitations} />
        </Receipt>
      )}
      <Saved runs={runs} busy={busy} onOpen={(id) => work(() => api<Run<ScenarioResult>>(`${runsPath}/${id}`))} />
    </Screen>
  );
}

type AllocationResult = {
  status: string;
  budget: string;
  quantum: string;
  cost: string | null;
  benefit: string | null;
  unused_budget?: string;
  reason?: string;
  baseline: { cost: string; benefit: string; feasible: boolean };
  allocations: { candidate: string; quantity: number; cost: string; benefit: string }[];
  assumptions: string[];
  limitations: string[];
};

const ALLOCATION_METHODS = ["integer-budget-v1", "two-resource-enumeration-v1", "selection-rules-enumeration-v1"];

export function RecommendationsScreen({ source }: { source: Source }) {
  const nav = useNav();
  const { options, runs, error, setError, loadRuns, runsPath } = useAnalysis(source, (r) =>
    ALLOCATION_METHODS.includes(r.method_version ?? ""),
  );
  const [entity, setEntity] = useState("");
  const [cost, setCost] = useState("");
  const [benefit, setBenefit] = useState("");
  const [budget, setBudget] = useState("");
  const [quantum, setQuantum] = useState("1");
  const [most, setMost] = useState("1");
  const [confirmed, setConfirmed] = useState(false);
  const [shown, setShown] = useState<Run<AllocationResult> | null>(null);
  const [busy, setBusy] = useState(false);

  const entityName = entity || options?.entities[0] || "";
  const costName = cost || options?.metrics[0]?.name || "";
  const benefitName = benefit || options?.metrics[1]?.name || "";
  const unitOf = (name: string) => options?.metrics.find((m) => m.name === name)?.unit ?? "";

  async function work(action: () => Promise<Run<AllocationResult>>) {
    setBusy(true);
    setError("");
    try {
      setShown(await action());
    } catch (cause) {
      setError(why(cause, "The recommendation could not run."));
    } finally {
      setBusy(false);
    }
  }

  function run() {
    if (!options) return;
    if (costName === benefitName) return setError("Choose different columns for cost and benefit.");
    if (!/^\d+$/.test(most) || Number(most) > 10) return setError("Most per action must be a whole number from 0 to 10.");
    work(async () => {
      const result = await api<Run<AllocationResult>>(`${rootOf(source)}/decision-analysis/allocations`, {
        body: {
          name: "Budget allocation",
          revision_id: options.revision_id,
          understanding_id: options.understanding_id,
          filters: [],
          entity_column: entityName,
          cost_column: costName,
          benefit_column: benefitName,
          budget: budget.trim(),
          quantum: quantum.trim(),
          maximum_quantity: Number(most),
          bounds: [],
          assumptions_confirmed: true,
        },
      });
      setConfirmed(false);
      loadRuns();
      return result;
    });
  }

  const result = shown?.run.result;
  const ready = options?.state === "ready";
  return (
    <Screen kicker="Recommendation" title="Best actions within a budget" onBack={nav.back}>
      <ErrorText text={error} />
      {!options ? (
        error ? null : <Loading label="Checking your columns…" />
      ) : !ready ? (
        <NotReady />
      ) : !options.entities.length || options.metrics.length < 2 ? (
        <Card>
          <P>This needs a file with one row per action: a name column, a cost column and a benefit column.</P>
        </Card>
      ) : (
        <>
          <P muted>
            Each row of the file is one possible action (at most 20). Osalytix picks the mix with the highest total benefit that fits your budget.
          </P>
          <Text style={s.label}>Action name column</Text>
          <View style={s.row}>
            {options.entities.map((n) => <Chip key={n} label={n} active={n === entityName} onPress={() => { setEntity(n); setConfirmed(false); }} />)}
          </View>
          <Text style={s.label}>Cost of one action</Text>
          <View style={s.row}>
            {options.metrics.map((m) => <Chip key={m.name} label={`${m.name} · ${m.unit}`} active={m.name === costName} onPress={() => { setCost(m.name); setConfirmed(false); }} />)}
          </View>
          <Text style={s.label}>Benefit of one action</Text>
          <View style={s.row}>
            {options.metrics.map((m) => <Chip key={m.name} label={`${m.name} · ${m.unit}`} active={m.name === benefitName} onPress={() => { setBenefit(m.name); setConfirmed(false); }} />)}
          </View>
          <Field label={`Total budget (${unitOf(costName)})`} value={budget} onChangeText={setBudget} keyboardType="decimal-pad" placeholder="e.g. 1000" maxLength={100} />
          <Field label="Budget step (every cost must be a multiple)" value={quantum} onChangeText={setQuantum} keyboardType="decimal-pad" placeholder="e.g. 1 or 0.01" maxLength={100} />
          <Field label="Most of each action (0–10)" value={most} onChangeText={setMost} keyboardType="number-pad" maxLength={2} />
          <Chip label="I confirm fixed costs and benefits that add up" active={confirmed} onPress={() => setConfirmed(!confirmed)} />
          <Button label="Recommend" onPress={run} busy={busy} disabled={!confirmed || !budget.trim() || !quantum.trim()} />
        </>
      )}
      {result && shown && (
        <Receipt title={shown.run.name} stamp={result.status === "feasible" ? "EXACT" : "NO FIT"}>
          <P muted>{shown.current ? "Current data." : "Older data or meanings — run again for current data."}</P>
          {result.reason ? <P>{result.reason}</P> : null}
          <Text style={{ fontFamily: font.mono, color: color.ink, marginTop: space(1) }}>
            Cost {exact(result.cost)} · benefit {exact(result.benefit)}
            {result.unused_budget !== undefined ? ` · unused ${exact(result.unused_budget)}` : ""}
          </Text>
          <P muted>
            Budget {exact(result.budget)}, step {exact(result.quantum)}. Doing nothing: cost {exact(result.baseline.cost)}, benefit {exact(result.baseline.benefit)}.
          </P>
          <Table
            columns={["Action", "How many", "Cost", "Benefit"]}
            rows={result.allocations.map((a) => [a.candidate, a.quantity, a.cost, a.benefit])}
          />
          <Lines items={[...result.assumptions, ...result.limitations]} />
        </Receipt>
      )}
      <Saved runs={runs} busy={busy} onOpen={(id) => work(() => api<Run<AllocationResult>>(`${runsPath}/${id}`))} />
    </Screen>
  );
}

type Member = { user_id: string; email: string; role: string };
type Invitation = { id: string; email: string; role: string; status: string; expires_at: string };

export function TeamScreen({ workspaceId }: { workspaceId: string }) {
  const nav = useNav();
  const base = `/workspaces/${workspaceId}`;
  const [members, setMembers] = useState<Member[] | null>(null);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"member" | "admin">("member");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const load = () => {
    api<Member[]>(`${base}/members`).then(setMembers).catch((e) => setError(why(e, "Could not load members.")));
    api<Invitation[]>(`${base}/invitations`).then(setInvitations).catch((e) => setNote(why(e, "")));
  };
  useEffect(load, [workspaceId]);

  const linkOf = (id: string) => `${SITE}/workspace?workspace=${workspaceId}&invitation=${id}`;
  const active = (i: Invitation) => i.status === "pending" && Date.parse(i.expires_at) > Date.now();

  async function act(action: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError("");
    setNote("");
    try {
      await action();
      setNote(done);
      load();
    } catch (cause) {
      setError(why(cause, "That did not work."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen kicker="Workspace" title="Team" onBack={nav.back}>
      <ErrorText text={error} />
      {note ? <P muted>{note}</P> : null}
      {!members && !error ? <Loading label="Loading your team…" /> : null}
      {members && <H>Members ({members.length})</H>}
      {members?.map((m) => (
        <View key={m.user_id} style={{ paddingVertical: space(2.5), borderBottomWidth: 1, borderBottomColor: color.line }}>
          <Text style={{ color: color.ink, fontWeight: "600" }}>{m.email}</Text>
          <Text style={{ fontFamily: font.mono, fontSize: 11, color: color.muted }}>{m.role}</Text>
        </View>
      ))}
      <H>Invite someone</H>
      <P muted>Only owners and admins can invite. Only the owner can invite an admin. No email is sent — share the link yourself.</P>
      <Field label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" maxLength={254} />
      <View style={s.row}>
        <Chip label="Member" active={role === "member"} onPress={() => setRole("member")} />
        <Chip label="Admin" active={role === "admin"} onPress={() => setRole("admin")} />
      </View>
      <Button
        label="Create invitation"
        busy={busy}
        disabled={!email.trim()}
        onPress={() =>
          act(async () => {
            const made = await api<Invitation>(`${base}/invitations`, { body: { email: email.trim(), role } });
            setEmail("");
            await Share.share({ message: `Join my Osalytix workspace: ${linkOf(made.id)}` }).catch(() => undefined);
          }, "Invitation created. It reserves a seat for seven days.")
        }
      />
      {invitations.length ? <H>Invitations</H> : null}
      {invitations.map((i) => (
        <Card key={i.id}>
          <Text style={{ color: color.ink, fontWeight: "600" }}>{i.email}</Text>
          <Text style={{ fontFamily: font.mono, fontSize: 11, color: color.muted }}>
            {i.role} · {i.status === "pending" && !active(i) ? "expired" : i.status} · until {new Date(i.expires_at).toLocaleDateString()}
          </Text>
          {active(i) ? (
            <View style={[s.row, { marginTop: space(2) }]}>
              <Chip label="Share link" onPress={() => Share.share({ message: `Join my Osalytix workspace: ${linkOf(i.id)}` }).catch(() => undefined)} />
              <Chip label="Revoke" onPress={() => act(() => api(`${base}/invitations/${i.id}`, { method: "DELETE" }), "Invitation revoked.")} />
            </View>
          ) : null}
        </Card>
      ))}
    </Screen>
  );
}

type Ticket = { id: string; subject: string; category: string; status: string; version: number; updated_at: string };
type Detail = {
  ticket: Ticket & { description: string };
  events: { id: string; actor_role: "requester" | "staff"; kind: string; body: string | null; status: string; created_at: string }[];
};
const CATEGORIES = ["question", "problem", "incorrect", "slow", "missing_feature", "other"];
const words = (v: string) => v.replace(/_/g, " ");

export function SupportScreen({ workspaceId }: { workspaceId: string }) {
  const nav = useNav();
  const base = `/workspaces/${workspaceId}/support-tickets`;
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [category, setCategory] = useState("question");
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = () =>
    api<{ tickets: Ticket[] }>(`${base}?limit=50`)
      .then((r) => setTickets(r.tickets))
      .catch((e) => setError(why(e, "Could not load your requests.")));
  useEffect(() => {
    load();
  }, [workspaceId]);

  async function act(action: () => Promise<Detail>) {
    setBusy(true);
    setError("");
    try {
      setDetail(await action());
      load();
    } catch (cause) {
      setError(why(cause, "That did not work."));
    } finally {
      setBusy(false);
    }
  }

  if (detail) {
    const t = detail.ticket;
    return (
      <Screen kicker={`Support · ${words(t.status)}`} title={t.subject} onBack={() => { setDetail(null); setError(""); }}>
        <Card>
          <P>{t.description}</P>
        </Card>
        {detail.events.filter((e) => e.body).map((e) => (
          <Receipt key={e.id} title={e.actor_role === "staff" ? "Support" : "You"} stamp={words(e.status).toUpperCase()}>
            <P>{e.body}</P>
            <P muted>{new Date(e.created_at).toLocaleString()}</P>
          </Receipt>
        ))}
        <ErrorText text={error} />
        {t.status === "resolved" ? (
          <Button
            kind="secondary"
            label="Reopen request"
            busy={busy}
            onPress={() => act(() => api<Detail>(`${base}/${t.id}/reopen`, { body: { expected_version: t.version, body: "" } }))}
          />
        ) : (
          <>
            <Field label="Reply" value={reply} onChangeText={setReply} multiline maxLength={4000} />
            <Button
              label="Send reply"
              busy={busy}
              disabled={!reply.trim()}
              onPress={() =>
                act(async () => {
                  const next = await api<Detail>(`${base}/${t.id}/messages`, { body: { body: reply.trim(), expected_version: t.version } });
                  setReply("");
                  return next;
                })
              }
            />
          </>
        )}
      </Screen>
    );
  }

  return (
    <Screen kicker="Help" title="Support" onBack={nav.back}>
      <H>New request</H>
      <Field label="Subject" value={subject} onChangeText={setSubject} maxLength={120} />
      <Field label="What happened?" value={message} onChangeText={setMessage} multiline maxLength={4000} />
      <View style={s.row}>
        {CATEGORIES.map((c) => <Chip key={c} label={words(c)} active={c === category} onPress={() => setCategory(c)} />)}
      </View>
      <ErrorText text={error} />
      <Button
        label="Send request"
        busy={busy}
        disabled={!subject.trim() || !message.trim()}
        onPress={() =>
          act(async () => {
            const made = await api<Detail>(base, { body: { subject: subject.trim(), description: message.trim(), feature: "other", category } });
            setSubject("");
            setMessage("");
            return made;
          })
        }
      />
      <H>My requests</H>
      {!tickets && !error ? <Loading label="Loading your requests…" /> : null}
      {tickets?.length === 0 ? <P muted>No requests yet.</P> : null}
      {tickets?.map((t) => (
        <Button
          key={t.id}
          kind="secondary"
          label={`${t.subject} · ${words(t.status)}`}
          disabled={busy}
          onPress={() => act(() => api<Detail>(`${base}/${t.id}`))}
        />
      ))}
    </Screen>
  );
}

export function ExportButton({ workspaceId, threadId, turnId }: { workspaceId: string; threadId: string; turnId: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function download() {
    setBusy(true);
    setError("");
    try {
      const token = await loadToken();
      if (!token) throw new Error("Please sign in again.");
      const file = await File.downloadFileAsync(
        `${SITE}/api/workspaces/${workspaceId}/threads/${threadId}/turns/${turnId}/export.pdf`,
        new File(Paths.cache, `osalytix-answer-${turnId}.pdf`),
        { headers: { Authorization: `Bearer ${token}`, Origin: SITE, Accept: "application/pdf" }, idempotent: true },
      );
      if (!(await Sharing.isAvailableAsync())) throw new Error("Sharing is not available on this device.");
      await Sharing.shareAsync(file.uri, { mimeType: "application/pdf", UTI: "com.adobe.pdf", dialogTitle: "Osalytix answer" });
    } catch (cause) {
      setError(why(cause, "This answer could not be downloaded. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ gap: space(1) }}>
      <Button kind="ghost" label="Save as PDF" onPress={download} busy={busy} />
      <ErrorText text={error} />
    </View>
  );
}
