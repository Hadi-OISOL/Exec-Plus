/* Use case: Gives members a controlled refresh and proactive monitoring workspace.
What it does: Stages files, reviews changed meaning, replays findings and manages private alerts. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import { studyJson } from "./studies-panel";

type Column = {
  name: string;
  role: string;
  unit: string;
  currency: string;
  meaning: string;
};
type Definition = {
  grain: string;
  columns: Column[];
  relationships: object[];
} & Record<string, unknown>;
type Meaning = {
  state: string;
  revision_id: string;
  definition: Definition;
  column_types: Record<string, string>;
  history: { id: string }[];
};
type Feed = {
  id: string;
  version: number;
  source: {
    upload_id: string;
    as_of: string;
    coverage_start: string | null;
    coverage_end: string | null;
  };
  interval_hours: number;
  freshness_hours: number;
  enabled: boolean;
  next_due: string;
  state: string;
};
type Candidate = {
  id: string;
  status: string;
  created_at: string;
  details: {
    mode: string;
    failure_code?: string;
    schema_changed?: boolean;
    relationships_invalidated?: boolean;
    definition?: Definition;
    output_upload_id?: string;
    old_schema?: string[][];
    new_schema?: string[][];
    stats?: Record<string, number>;
  };
};
type Overview = {
  feed: Feed | null;
  candidates: Candidate[];
  can_edit: boolean;
  stale?: boolean;
  definition_state?: string;
};
type Rule = {
  id: string;
  operator: string;
  threshold: string;
  cooldown_minutes: number;
  enabled: boolean;
};
type Delivery = {
  id: string;
  observation_id: string;
  status: string;
  read_at: string | null;
  created_at: string;
};
type MonitorRow = {
  monitor: {
    id: string;
    name: string;
    enabled: boolean;
    relevance: number;
    method: {
      column: string;
      aggregation: string;
      date_column: string | null;
      segment: string | null;
    };
  };
  observations: {
    id: string;
    status: string;
    source_version: number;
    failure_code?: string;
  }[];
  rules: Rule[];
  deliveries: Delivery[];
};
type Finding = {
  value: string | null;
  previous: string | null;
  delta: string | null;
  percent_change: string | null;
  sample_count: number;
  present_count: number;
  missing_count: number;
  limitations: string[];
  drivers: { segment: unknown[]; delta: string }[];
  interpretation: string;
};
type Observation = {
  observation: {
    id: string;
    status: string;
    source_version: number;
    source: { as_of: string };
    evidence: {
      unit?: string;
      quality_score?: string;
      periods?: { start: string; end: string }[];
      queries?: Record<string, string>;
      failure_code?: string;
      coverage?: object;
      method?: object;
    };
  };
  monitor: { name: string; relevance: number };
  finding: Finding | null;
  results?: object;
};
const human = (value: string) => value.replaceAll("_", " ");
const localNow = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};

function requestIdentifier(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20),
  ].join("-");
}

export function RefreshPanel({
  root,
  request,
  onActivated,
  onReview,
}: {
  root: string;
  request: ApiRequest;
  onActivated: (id: string) => Promise<void>;
  onReview: () => void;
}) {
  const dataPath = root.split("/uploads/")[0];
  const workspacePath = root.split("/datasets/")[0];
  const [overview, setOverview] = useState<Overview | null>(null);
  const [meaning, setMeaning] = useState<Meaning | null>(null);
  const [monitors, setMonitors] = useState<MonitorRow[]>([]);
  const [findings, setFindings] = useState<Observation[]>([]);
  const [opened, setOpened] = useState<Observation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [asOf, setAsOf] = useState(localNow);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [hours, setHours] = useState(24);
  const [freshness, setFreshness] = useState(48);
  const [enabled, setEnabled] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState("replace");
  const [keys, setKeys] = useState("");
  const [duplicates, setDuplicates] = useState("keep_all");
  const [review, setReview] = useState<{
    candidate: Candidate;
    definition: Definition;
  } | null>(null);
  const [name, setName] = useState("");
  const [metric, setMetric] = useState("");
  const [aggregation, setAggregation] = useState("sum");
  const [segment, setSegment] = useState("");
  const [dateColumn, setDateColumn] = useState("");
  const [relevance, setRelevance] = useState(3);
  const [filterColumn, setFilterColumn] = useState("");
  const [filterOperator, setFilterOperator] = useState("eq");
  const [filterValue, setFilterValue] = useState("");
  const [alertMonitor, setAlertMonitor] = useState("");
  const [operator, setOperator] = useState("gt");
  const [threshold, setThreshold] = useState("");
  const [cooldown, setCooldown] = useState(60);
  useEffect(() => {
    let active = true;
    Promise.all([
      request<Overview>(`${dataPath}/refresh`),
      request<Meaning>(`${root}/understanding`),
      request<{ monitors: MonitorRow[] }>(`${dataPath}/monitors`),
      request<Observation[]>(`${dataPath}/observations`),
    ])
      .then(([o, m, rows, f]) => {
        if (active) {
          setOverview(o);
          setMeaning(m);
          setMonitors(rows.monitors);
          setFindings(f);
          if (o.feed) {
            setHours(o.feed.interval_hours);
            setFreshness(o.feed.freshness_hours);
            setEnabled(o.feed.enabled);
          }
        }
      })
      .catch((cause: Error) => {
        if (active) setError(cause.message);
      });
    return () => {
      active = false;
    };
  }, [root, dataPath, request]);
  async function reload() {
    const [o, m, f] = await Promise.all([
      request<Overview>(`${dataPath}/refresh`),
      request<{ monitors: MonitorRow[] }>(`${dataPath}/monitors`),
      request<Observation[]>(`${dataPath}/observations`),
    ]);
    setOverview(o);
    setMonitors(m.monitors);
    setFindings(f);
  }
  async function act(task: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await task();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "The action could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }
  function dates() {
    return {
      as_of: new Date(asOf).toISOString(),
      coverage_start: start || null,
      coverage_end: end || null,
    };
  }
  const columns = meaning?.definition.columns || [];
  const feed = overview?.feed;
  const editable = overview?.can_edit;
  async function open(id: string) {
    setOpened(
      await request<Observation>(`${workspacePath}/observations/${id}`),
    );
  }
  return (
    <div className="refreshWorkspace">
      <section className="panel refreshIntro">
        <div>
          <span className="eyebrow">Watch what changes</span>
          <h2>Refresh &amp; alerts</h2>
          <p>
            Keep a checked snapshot, follow your key measures, and see the
            evidence behind each change.
          </p>
        </div>
        <button type="button" disabled={busy} onClick={() => act(reload)}>
          Reload refresh status
        </button>
        <ol className="refreshFlow" aria-label="Refresh workflow">
          <li>1 · Stage a file</li>
          <li>2 · Validate &amp; review</li>
          <li>3 · Activate snapshot</li>
          <li>4 · Observe &amp; notify</li>
        </ol>
        {error && <p role="alert">{error}</p>}
        {message && <p role="status">{message}</p>}
        {feed && (
          <div className="refreshFacts">
            <span>
              Version <strong>{feed.version}</strong>
            </span>
            <span>
              Source as of{" "}
              <strong>{new Date(feed.source.as_of).toLocaleString()}</strong>
            </span>
            <span>
              Freshness{" "}
              <strong>{overview.stale ? "Stale" : "Within limit"}</strong>
            </span>
            <span>
              Meaning <strong>{human(overview.definition_state || "")}</strong>
            </span>
            <span>
              Ingestion <strong>{human(feed.state)}</strong>
            </span>
          </div>
        )}
      </section>
      {meaning?.state !== "confirmed" && (
        <section className="panel">
          <h3>Confirm the data meaning first</h3>
          <p>
            Refresh and monitoring need an agreed row meaning and units.
            Existing observations remain historical evidence.
          </p>
          <button onClick={onReview}>Review data meaning</button>
        </section>
      )}
      {editable && (
        <section className="panel">
          <h3>
            {feed ? "Review refresh settings" : "Set up a refresh source"}
          </h3>
          <p>
            The selected upload becomes the baseline. A schedule processes files
            staged here; it cannot read your computer automatically. Saving
            settings creates a new source version.
          </p>
          <form
            className="refreshForm"
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                if (!meaning) return;
                await request(
                  `${dataPath}/refresh`,
                  studyJson("PUT", {
                    upload_id: root.split("/uploads/")[1],
                    revision_id: meaning.revision_id,
                    understanding_id: meaning.history.at(-1)?.id,
                    expected_version: feed?.version || 0,
                    interval_hours: hours,
                    freshness_hours: freshness,
                    enabled,
                    ...dates(),
                  }),
                );
                await reload();
                setMessage(
                  "Refresh settings saved. The selected source is the baseline.",
                );
              });
            }}
          >
            <label>
              Source data is current as of
              <input
                type="datetime-local"
                required
                value={asOf}
                onChange={(e) => setAsOf(e.target.value)}
              />
            </label>
            <label>
              Complete coverage starts (optional)
              <input
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <label>
              Complete coverage ends (optional)
              <input
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </label>
            <label>
              Check staged files every (hours)
              <input
                type="number"
                min={1}
                max={8760}
                value={hours}
                onChange={(e) => setHours(Number(e.target.value))}
              />
            </label>
            <label>
              Consider stale after (hours)
              <input
                type="number"
                min={1}
                max={8760}
                value={freshness}
                onChange={(e) => setFreshness(Number(e.target.value))}
              />
            </label>
            <label className="refreshCheck">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
              />{" "}
              Enable scheduled activation
            </label>
            <p className="refreshFull">
              Only declare complete date coverage if every intended record for
              those dates is included. Monthly observations compare the last two
              complete calendar months before the source date.
            </p>
            <button disabled={busy || meaning?.state !== "confirmed"}>
              Save refresh settings
            </button>
          </form>
          {feed?.enabled && (
            <p>
              Next staged-file check: {new Date(feed.next_due).toLocaleString()}
              . Files needing review stay queued for your decision.
            </p>
          )}
        </section>
      )}
      {feed && editable && (
        <section className="panel">
          <h3>Stage the next file</h3>
          <p>
            The source time and complete-coverage dates above apply to this
            candidate. Previous snapshots and original files are retained.
          </p>
          <form
            className="refreshForm"
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                if (!file) return;
                const body = new FormData();
                body.set("file", file);
                body.set(
                  "options",
                  JSON.stringify({
                    request_id: requestIdentifier(),
                    expected_version: feed.version,
                    mode,
                    keys:
                      mode === "replace"
                        ? []
                        : keys
                            .split(",")
                            .map((k) => k.trim())
                            .filter(Boolean),
                    duplicates: mode === "replace" ? "keep_all" : duplicates,
                    ...dates(),
                  }),
                );
                const c = await request<Candidate>(
                  `${dataPath}/refresh/candidates`,
                  { method: "POST", body },
                );
                await reload();
                setMessage(
                  `File ${human(c.status)}. ${c.status === "failed" ? "The active data has not changed." : "Activate when ready, or let the schedule process a validated candidate."}`,
                );
              });
            }}
          >
            <label>
              Refresh file
              <input
                type="file"
                accept=".csv,.xlsx"
                required
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>
            <label>
              Update behavior
              <select
                value={mode}
                onChange={(e) => {
                  setMode(e.target.value);
                  if (e.target.value === "merge") setDuplicates("ignore_exact");
                }}
              >
                <option value="replace">Replace full snapshot</option>
                <option value="append">Append records</option>
                <option value="merge">Merge by key (no deletions)</option>
              </select>
            </label>
            {mode !== "replace" && (
              <>
                <label>
                  Key columns, separated by commas
                  <input
                    value={keys}
                    onChange={(e) => setKeys(e.target.value)}
                    placeholder="order_id"
                  />
                </label>
                <label>
                  Duplicate handling
                  <select
                    value={duplicates}
                    onChange={(e) => setDuplicates(e.target.value)}
                  >
                    {mode === "append" && (
                      <option value="keep_all">Keep all rows (no keys)</option>
                    )}
                    <option value="reject">Reject duplicate keys</option>
                    <option value="ignore_exact">
                      Ignore exact duplicate rows by key
                    </option>
                  </select>
                </label>
              </>
            )}
            <button
              disabled={busy || overview.definition_state !== "confirmed"}
            >
              Validate staged file
            </button>
          </form>
        </section>
      )}
      {!!overview?.candidates.length && (
        <section className="panel">
          <h3>Refresh history</h3>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Staged</th>
                  <th>Mode</th>
                  <th>State</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {overview.candidates.map((c) => (
                  <tr key={c.id}>
                    <td>{new Date(c.created_at).toLocaleString()}</td>
                    <td>{c.details.mode}</td>
                    <td>
                      {human(c.status)}
                      {c.details.failure_code && (
                        <small> · {human(c.details.failure_code)}</small>
                      )}
                      {c.details.schema_changed && (
                        <small> · schema changed</small>
                      )}
                    </td>
                    <td>
                      {editable && c.status === "queued" && (
                        <button
                          disabled={busy}
                          onClick={() =>
                            act(async () => {
                              const result = await request<Candidate>(
                                `${workspacePath}/refresh-candidates/${c.id}/activate`,
                                { method: "POST" },
                              );
                              if (
                                result.status === "activated" &&
                                result.details.output_upload_id
                              ) {
                                await request(
                                  `${dataPath}/observations/process`,
                                  { method: "POST" },
                                );
                                await onActivated(
                                  result.details.output_upload_id,
                                );
                              } else {
                                await reload();
                                setMessage(
                                  `Candidate ${human(result.status)}. Stage again against the current source.`,
                                );
                              }
                            })
                          }
                        >
                          Activate snapshot
                        </button>
                      )}
                      {editable && c.status === "needs_review" && (
                        <button
                          disabled={busy}
                          onClick={() =>
                            setReview({
                              candidate: c,
                              definition: structuredClone(
                                c.details.definition!,
                              ),
                            })
                          }
                        >
                          Review changed meaning
                        </button>
                      )}
                      {editable &&
                        ["queued", "needs_review"].includes(c.status) && (
                          <button
                            disabled={busy}
                            onClick={() =>
                              act(async () => {
                                await request(
                                  `${workspacePath}/refresh-candidates/${c.id}/review`,
                                  studyJson("POST", { reject: true }),
                                );
                                await reload();
                              })
                            }
                          >
                            Reject candidate
                          </button>
                        )}
                      <details>
                        <summary>Refresh evidence</summary>
                        <pre>{JSON.stringify(c.details, null, 2)}</pre>
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {review && (
        <section className="panel" aria-label="Review candidate meaning">
          <h3>Review the candidate meaning</h3>
          <p>
            The new snapshot needs your confirmation. Its definitions become
            current only when you activate it.
          </p>
          {review.candidate.details.relationships_invalidated && (
            <p>
              Existing relationships are invalidated. Reconfirm them in Data
              meaning after activation.
            </p>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                await request(
                  `${workspacePath}/refresh-candidates/${review.candidate.id}/review`,
                  studyJson("POST", { definition: review.definition }),
                );
                setReview(null);
                await reload();
                setMessage("Candidate reviewed. It can now be activated.");
              });
            }}
          >
            <label>
              Each row represents
              <select
                value={review.definition.grain}
                onChange={(e) =>
                  setReview({
                    ...review,
                    definition: { ...review.definition, grain: e.target.value },
                  })
                }
              >
                {[
                  "record",
                  "order",
                  "order_item",
                  "customer",
                  "inventory_snapshot",
                  "survey_response",
                  "other",
                ].map((g) => (
                  <option key={g} value={g}>
                    {human(g)}
                  </option>
                ))}
              </select>
            </label>
            {review.definition.columns.map((c, i) => (
              <div className="refreshForm" key={c.name}>
                <strong>{c.name}</strong>
                <label>
                  Role for {c.name}
                  <select
                    value={c.role}
                    onChange={(e) =>
                      setReview({
                        ...review,
                        definition: {
                          ...review.definition,
                          columns: review.definition.columns.map((v, j) =>
                            j === i ? { ...v, role: e.target.value } : v,
                          ),
                        },
                      })
                    }
                  >
                    {[
                      "metric",
                      "dimension",
                      "identifier",
                      "ordinal",
                      "ignored",
                    ].map((r) => (
                      <option key={r}>{r}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Unit for {c.name}
                  <input
                    value={c.unit}
                    onChange={(e) =>
                      setReview({
                        ...review,
                        definition: {
                          ...review.definition,
                          columns: review.definition.columns.map((v, j) =>
                            j === i ? { ...v, unit: e.target.value } : v,
                          ),
                        },
                      })
                    }
                  />
                </label>
                <label>
                  Currency for {c.name}
                  <input
                    value={c.currency}
                    maxLength={3}
                    onChange={(e) =>
                      setReview({
                        ...review,
                        definition: {
                          ...review.definition,
                          columns: review.definition.columns.map((v, j) =>
                            j === i
                              ? { ...v, currency: e.target.value.toUpperCase() }
                              : v,
                          ),
                        },
                      })
                    }
                  />
                </label>
              </div>
            ))}
            <button disabled={busy}>Approve candidate meaning</button>
            <button type="button" onClick={() => setReview(null)}>
              Close review
            </button>
          </form>
        </section>
      )}
      {feed && editable && (
        <section className="panel">
          <h3>Add a measure to watch</h3>
          <p>
            Up to six active monitors, visible to current workspace members.
            Choose relevance explicitly; your private goals are not shared.
          </p>
          <form
            className="refreshForm"
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                await request(
                  `${dataPath}/monitors`,
                  studyJson("POST", {
                    name: name || `${aggregation} ${metric}`,
                    method: {
                      kind: "metric",
                      column: metric,
                      aggregation,
                      filters: filterColumn
                        ? [
                            {
                              column: filterColumn,
                              operator: filterOperator,
                              value: filterValue,
                            },
                          ]
                        : [],
                    },
                    date_column: dateColumn || null,
                    segment: segment || null,
                    relevance,
                  }),
                );
                await request(`${dataPath}/observations/process`, {
                  method: "POST",
                });
                await reload();
                setMessage(
                  "Monitor created with replayable baseline evidence.",
                );
              });
            }}
          >
            <label>
              Monitor name
              <input
                value={name}
                maxLength={100}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label>
              Metric
              <select
                aria-label="Metric"
                required
                value={metric}
                onChange={(e) => setMetric(e.target.value)}
              >
                <option value="">Choose a measure</option>
                {columns
                  .filter((c) => c.role === "metric")
                  .map((c) => (
                    <option key={c.name}>{c.name}</option>
                  ))}
              </select>
            </label>
            <label>
              Calculation
              <select
                value={aggregation}
                onChange={(e) => {
                  setAggregation(e.target.value);
                  if (e.target.value !== "sum") setSegment("");
                }}
              >
                {["sum", "avg", "count", "min", "max"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label>
              Comparison
              <select
                value={dateColumn}
                onChange={(e) => setDateColumn(e.target.value)}
              >
                <option value="">Previous snapshot</option>
                {columns
                  .filter(
                    (c) =>
                      meaning?.column_types[c.name] === "date" &&
                      c.role === "dimension",
                  )
                  .map((c) => (
                    <option key={c.name} value={c.name}>
                      Complete months by {c.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Driver segment (sum only)
              <select
                disabled={aggregation !== "sum"}
                value={segment}
                onChange={(e) => setSegment(e.target.value)}
              >
                <option value="">No segment breakdown</option>
                {columns
                  .filter((c) => ["dimension", "ordinal"].includes(c.role))
                  .map((c) => (
                    <option key={c.name}>{c.name}</option>
                  ))}
              </select>
            </label>
            <label>
              Relevance (1–5)
              <input
                type="number"
                min={1}
                max={5}
                value={relevance}
                onChange={(e) => setRelevance(Number(e.target.value))}
              />
            </label>
            <label>
              Optional filter
              <select
                value={filterColumn}
                onChange={(e) => setFilterColumn(e.target.value)}
              >
                <option value="">All records</option>
                {columns.map((c) => (
                  <option key={c.name}>{c.name}</option>
                ))}
              </select>
            </label>
            {filterColumn && (
              <>
                <label>
                  Filter comparison
                  <select
                    value={filterOperator}
                    onChange={(e) => setFilterOperator(e.target.value)}
                  >
                    {["eq", "ne", "gt", "gte", "lt", "lte"].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Filter value
                  <input
                    required
                    value={filterValue}
                    onChange={(e) => setFilterValue(e.target.value)}
                  />
                </label>
              </>
            )}
            <button disabled={busy || meaning?.state !== "confirmed"}>
              Create monitor
            </button>
          </form>
        </section>
      )}
      {feed && (
        <section className="panel">
          <div className="refreshHeading">
            <h3>Proactive observations</h3>
            {editable && (
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await request(`${dataPath}/observations/process`, {
                      method: "POST",
                    });
                    await reload();
                  })
                }
              >
                Process pending observations
              </button>
            )}
          </div>
          <p>
            Ranked by declared relevance, relative change, then profile quality.
            A zero baseline has no percentage change. These are descriptive
            findings, not anomaly or causal claims.
          </p>
          {!findings.length && (
            <p>Add a monitor to build the first observation.</p>
          )}
          <div className="observationGrid">
            {findings.map((o) => (
              <article className="observationCard" key={o.observation.id}>
                <span className="eyebrow">
                  Relevance {o.monitor.relevance} · Source v
                  {o.observation.source_version}
                </span>
                <h4>{o.monitor.name}</h4>
                {o.finding ? (
                  <>
                    <strong className="observationValue">
                      {o.finding.value ?? "No value"}{" "}
                      <small>{o.observation.evidence.unit}</small>
                    </strong>
                    <p>Change: {o.finding.delta ?? "No comparable baseline"}</p>
                    <p>
                      Sample: {o.finding.sample_count} records ·{" "}
                      {o.finding.present_count} present ·{" "}
                      {o.finding.missing_count} missing
                    </p>
                    {o.observation.evidence.periods?.map((p) => (
                      <p key={p.start}>
                        {p.start} to {p.end} (end excluded)
                      </p>
                    ))}
                    <ul className="refreshLimitations">
                      {o.finding.limitations.map((l) => (
                        <li key={l}>{human(l)}</li>
                      ))}
                    </ul>
                    {!!o.finding.drivers.length && (
                      <table>
                        <caption>Computed contributions to change</caption>
                        <thead>
                          <tr>
                            <th>Segment</th>
                            <th>Contribution</th>
                          </tr>
                        </thead>
                        <tbody>
                          {o.finding.drivers.map((d, i) => (
                            <tr key={i}>
                              <td>
                                {d.segment.map(String).join(" / ") ||
                                  "Missing category"}
                              </td>
                              <td>{d.delta}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                    <button
                      disabled={busy}
                      onClick={() => act(() => open(o.observation.id))}
                    >
                      Open observation evidence
                    </button>
                  </>
                ) : (
                  <p>
                    {human(o.observation.status)}:{" "}
                    {human(
                      o.observation.evidence.failure_code ||
                        "Waiting for the worker",
                    )}
                  </p>
                )}
              </article>
            ))}
          </div>
        </section>
      )}
      {opened && (
        <section className="panel">
          <h3>Observation evidence · {opened.monitor.name}</h3>
          <p>
            Source as of{" "}
            {new Date(opened.observation.source.as_of).toLocaleString()}. Each
            receipt below was replayed against its retained source and original
            meaning.
          </p>
          <details open>
            <summary>Method, coverage and query receipts</summary>
            <pre>{JSON.stringify(opened, null, 2)}</pre>
          </details>
          <button onClick={() => setOpened(null)}>Close evidence</button>
        </section>
      )}
      {!!monitors.length && (
        <section className="panel">
          <h3>My KPI alerts</h3>
          <p>
            Alerts appear only in your in-app inbox. New source versions are
            checked once; a breached threshold can notify again after its
            cooldown. Stale or incomplete evidence blocks delivery.
          </p>
          <form
            className="refreshForm"
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                await request(
                  `${workspacePath}/monitors/${alertMonitor}/alerts`,
                  studyJson("POST", {
                    operator,
                    threshold,
                    cooldown_minutes: cooldown,
                  }),
                );
                await reload();
                setMessage(
                  "Private alert subscribed. It applies to future observations.",
                );
              });
            }}
          >
            <label>
              Alert monitor
              <select
                required
                value={alertMonitor}
                onChange={(e) => setAlertMonitor(e.target.value)}
              >
                <option value="">Choose a monitor</option>
                {monitors
                  .filter((m) => m.monitor.enabled)
                  .map((m) => (
                    <option key={m.monitor.id} value={m.monitor.id}>
                      {m.monitor.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Threshold comparison
              <select
                value={operator}
                onChange={(e) => setOperator(e.target.value)}
              >
                <option value="gt">Above</option>
                <option value="gte">At least</option>
                <option value="lt">Below</option>
                <option value="lte">At most</option>
              </select>
            </label>
            <label>
              Threshold
              <input
                required
                inputMode="decimal"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
              />
            </label>
            <label>
              Cooldown (minutes)
              <input
                type="number"
                min={1}
                max={10080}
                value={cooldown}
                onChange={(e) => setCooldown(Number(e.target.value))}
              />
            </label>
            <button disabled={busy}>Subscribe to alert</button>
          </form>
          {monitors.map((m) => (
            <article className="refreshMonitor" key={m.monitor.id}>
              <h4>
                {m.monitor.name} · {m.monitor.enabled ? "Active" : "Disabled"}
              </h4>
              {editable && m.monitor.enabled && (
                <button
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      await request(
                        `${workspacePath}/monitors/${m.monitor.id}`,
                        { method: "DELETE" },
                      );
                      await reload();
                    })
                  }
                >
                  Disable monitor
                </button>
              )}
              {m.rules
                .filter((r) => r.enabled)
                .map((r) => (
                  <p key={r.id}>
                    {human(r.operator)} {r.threshold} · {r.cooldown_minutes}{" "}
                    minute cooldown{" "}
                    <button
                      disabled={busy}
                      onClick={() =>
                        act(async () => {
                          await request(`${workspacePath}/alerts/${r.id}`, {
                            method: "DELETE",
                          });
                          await reload();
                        })
                      }
                    >
                      Unsubscribe
                    </button>
                  </p>
                ))}
              {m.deliveries.map((d) => (
                <div className="refreshDelivery" key={d.id}>
                  <span>
                    {new Date(d.created_at).toLocaleString()} ·{" "}
                    <strong>{human(d.status)}</strong>
                    {d.read_at ? " · Read" : ""}
                  </span>
                  <button
                    disabled={busy}
                    onClick={() => act(() => open(d.observation_id))}
                  >
                    View alert evidence
                  </button>
                  {d.status === "delivered" && !d.read_at && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        act(async () => {
                          await request(
                            `${workspacePath}/alert-events/${d.id}/read`,
                            { method: "POST" },
                          );
                          await reload();
                        })
                      }
                    >
                      Mark read
                    </button>
                  )}
                </div>
              ))}
              <details>
                <summary>Observation history</summary>
                {m.observations.map((o) => (
                  <p key={o.id}>
                    Version {o.source_version} · {human(o.status)}{" "}
                    <button
                      disabled={busy}
                      onClick={() => act(() => open(o.id))}
                    >
                      Replay observation
                    </button>
                  </p>
                ))}
              </details>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
