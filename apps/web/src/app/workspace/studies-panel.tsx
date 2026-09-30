/* Use case: Turns confirmed meanings into interactive, reproducible investigations.
What it does: Runs supported studies, reopens versions and manages permission-aware six-pin dashboards. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import { RecordTable, type Cell } from "./explore-components";

type Method = {
  kind: string;
  column: string;
  aggregation?: string;
  group_by?: string[];
  filters?: object[];
  order?: string[];
};
type Suggestion = {
  id: string;
  component: string;
  method: Method;
  question: string;
  reason: string;
};
type Views = {
  state: string;
  domain?: string;
  revision_id: string;
  understanding_id: string;
  dismissed?: string[];
  recommendations: Suggestion[];
  columns?: { name: string; role: string }[];
  limitations: string[];
};
type Version = {
  id: string;
  number: number;
  upload_id: string;
  question: string;
  created_at: string;
  method: Method;
  evidence: {
    component: string;
    source_uploaded_at: string;
    sources: { revision_id: string; understanding_id: string }[];
    method_version: string;
  };
};
type Study = {
  id: string;
  name: string;
  owner_id: string;
  shared: boolean;
  versions: Version[];
};
type Table = { columns: string[]; rows: Cell[][]; coverage?: Table };
type Result = {
  study: Study;
  version: Version;
  display: Table;
  sample_count: number;
  unit: string;
  limitations: string[];
  results: object[];
};
type Board = {
  id: string;
  name: string;
  owner_id: string;
  shared: boolean;
  version: number;
  pins: string[];
};
type Comparison = {
  comparable: boolean;
  before: Result;
  after: Result;
  differences: {
    group: Cell[];
    before: string | null;
    after: string | null;
    delta: string | null;
  }[];
  limitation: string;
};
export const studyJson = (method: string, value: object): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(value),
});

function StudyChart({ data, component }: { data: Table; component: string }) {
  const [selected, setSelected] = useState<number | null>(null);
  const rows = data.rows.slice(0, 30);
  const values = rows.map((row) =>
    row.at(-1) === null ? NaN : Number(row.at(-1)),
  );
  const magnitude = Math.max(
    1,
    ...values.filter(Number.isFinite).map(Math.abs),
  );
  if (component === "card")
    return (
      <p className="kpiValue studyValue">
        {String(data.rows[0]?.at(-1) ?? "No matching values")}
      </p>
    );
  if (!["bar", "line", "distribution"].includes(component) || !rows.length)
    return null;
  const points = values.map(
    (value, index) =>
      `${20 + (index * 560) / Math.max(1, values.length - 1)},${100 - (value / magnitude) * 75}`,
  );
  return (
    <div className="studyChart">
      {component === "line" && (
        <svg
          viewBox="0 0 600 200"
          role="img"
          aria-label="Observed values by date; gaps are not interpolated"
        >
          <path d="M20 100H580" stroke="currentColor" opacity="0.2" />
          {points.map(
            (point, index) =>
              Number.isFinite(values[index]) && (
                <circle
                  key={index}
                  cx={point.split(",")[0]}
                  cy={point.split(",")[1]}
                  r="4"
                  fill="currentColor"
                />
              ),
          )}
        </svg>
      )}
      <p className="chartCaption">
        {component === "line"
          ? "Observed date points; no inferred values between dates."
          : "Bar size is approximate; labels and the table retain exact values."}{" "}
        Select a value to inspect it.
      </p>
      <ul className="barList">
        {rows.map((row, index) => (
          <li key={index}>
            <button
              className="barButton"
              type="button"
              aria-pressed={selected === index}
              onClick={() => setSelected(selected === index ? null : index)}
            >
              <span className="barLabel">
                {row
                  .slice(0, -1)
                  .map((value) => String(value ?? "Missing response"))
                  .join(" / ")}
              </span>
              <span className="barTrack">
                <span
                  className="barFill"
                  style={{
                    width: `${Number.isFinite(values[index]) ? (Math.abs(values[index]) / magnitude) * 100 : 0}%`,
                  }}
                />
              </span>
              <span className="barValue">
                {String(row.at(-1) ?? "No value")}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {data.rows.length > 30 && (
        <p>
          Chart shows the first 30 groups. The table includes every returned
          group.
        </p>
      )}
      {selected !== null && (
        <p role="status">
          Selected:{" "}
          {rows[selected]
            .map((value) => String(value ?? "Missing response"))
            .join(" · ")}
        </p>
      )}
    </div>
  );
}

export function StudyResult({ value }: { value: Result }) {
  return (
    <article
      className="studyResult"
      aria-label={`Study result: ${value.study.name}`}
    >
      <div className="sectionHeading">
        <h3>{value.study.name}</h3>
        <span>
          Version {value.version.number} ·{" "}
          {value.study.shared ? "Workspace" : "Private"}
        </span>
      </div>
      <p>{value.version.question}</p>
      <p className="chartCaption">
        {value.sample_count} matching records · Unit: {value.unit} · Source
        uploaded{" "}
        {new Date(value.version.evidence.source_uploaded_at).toLocaleString()}
      </p>
      <StudyChart
        key={value.version.id}
        data={value.display}
        component={value.version.evidence.component}
      />
      <RecordTable
        key={`records-${value.version.id}`}
        data={{ ...value.display, records_analyzed: value.sample_count }}
      />
      {value.display.coverage && value.version.method.kind === "metric" && (
        <details>
          <summary>Sample coverage and missing values</summary>
          <RecordTable
            data={{
              ...value.display.coverage,
              records_analyzed: value.sample_count,
            }}
          />
        </details>
      )}
      <ul className="studyLimitations">
        {value.limitations.map((text) => (
          <li key={text}>{text}</li>
        ))}
      </ul>
      <details>
        <summary>Study method, source versions and evidence</summary>
        <p>{value.version.evidence.method_version}</p>
        <pre>
          {JSON.stringify(
            { version: value.version, results: value.results },
            null,
            2,
          )}
        </pre>
      </details>
    </article>
  );
}

export function StudiesPanel({
  root,
  request,
  actorId,
  onReview,
}: {
  root: string;
  request: ApiRequest;
  actorId: string;
  onReview: () => void;
}) {
  const datasetPath = root.split("/uploads/")[0];
  const workspacePath = root.split("/datasets/")[0];
  const [views, setViews] = useState<Views | null>(null);
  const [studies, setStudies] = useState<Study[]>([]);
  const [boards, setBoards] = useState<Board[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [board, setBoard] = useState<{
    board: Board;
    studies: Result[];
  } | null>(null);
  const [boardId, setBoardId] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState("distribution");
  const [column, setColumn] = useState("");
  const [group, setGroup] = useState("");
  const [aggregation, setAggregation] = useState("sum");
  const [order, setOrder] = useState("");
  const [before, setBefore] = useState("");
  const [after, setAfter] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([
      request<Views>(`${root}/adaptive-views`),
      request<Study[]>(`${datasetPath}/studies`),
      request<Board[]>(`${workspacePath}/study-boards`),
    ])
      .then(([nextViews, nextStudies, nextBoards]) => {
        if (active) {
          setViews(nextViews);
          setStudies(nextStudies);
          setBoards(nextBoards);
        }
      })
      .catch((cause: Error) => {
        if (active) setError(cause.message);
      });
    return () => {
      active = false;
    };
  }, [root, datasetPath, workspacePath, request]);
  async function action(task: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await task();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not complete the study action.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    setStudies(await request(`${datasetPath}/studies`));
    setBoards(await request(`${workspacePath}/study-boards`));
  }
  async function create(method: Method, question: string) {
    if (!views) return;
    const next = await request<Result>(
      `${root}/studies`,
      studyJson("POST", {
        name: (name || question).slice(0, 100),
        question,
        method,
        revision_id: views.revision_id,
        understanding_id: views.understanding_id,
      }),
    );
    setResult(next);
    setComparison(null);
    setMessage("Study saved privately with its original evidence.");
    await refresh();
  }
  async function updateBoard(
    next: Board,
    pins: string[],
    shared = next.shared,
  ) {
    await request(
      `${workspacePath}/study-boards/${next.id}`,
      studyJson("PATCH", {
        name: next.name,
        shared,
        pins,
        expected_version: next.version,
      }),
    );
    setBoard(null);
    await refresh();
  }
  const selectedBoard = boards.find((item) => item.id === boardId);
  const usableColumns =
    views?.columns?.filter(
      (item) => !["identifier", "ignored"].includes(item.role),
    ) ?? [];
  return (
    <section className="panel studiesPanel" aria-label="Studies and dashboards">
      <div className="sectionHeading">
        <h2>Studies & dashboards</h2>
        <span>Evidence you can return to</span>
      </div>
      <p>
        Start with a suggested view or a descriptive survey. Every run saves a
        version; rerunning preserves the original.
      </p>
      {error && (
        <p role="alert" className="errorNotice">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {!views && !error && <p>Reading confirmed data meaning…</p>}
      <button type="button" onClick={onReview}>
        Review meaning or change my goal
      </button>
      {views?.state === "needs_review" && (
        <p>
          Confirm Data understanding for this snapshot to unlock recommendations
          and studies.
        </p>
      )}
      {views?.state === "ready" && (
        <>
          <p>
            Recommended for {views.domain}. Your goal affects suggestions
            privately.
          </p>
          <label>
            Study name (optional)
            <input
              maxLength={100}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Give this investigation a name"
            />
          </label>
          <div className="studyRecommendations">
            {views.recommendations.map((item) => (
              <article key={item.id} className="studySuggestion">
                <span className="studyComponent">{item.component}</span>
                <h3>{item.question}</h3>
                <p>{item.reason}</p>
                <div className="studyActions">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      void action(() => create(item.method, item.question))
                    }
                  >
                    Run & save study
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    aria-label={`Dismiss ${item.question}`}
                    onClick={() =>
                      void action(async () => {
                        await request(
                          `${root}/adaptive-views/dismissals`,
                          studyJson("POST", {
                            understanding_id: views.understanding_id,
                            dismissed: [...(views.dismissed ?? []), item.id],
                          }),
                        );
                        setViews(await request(`${root}/adaptive-views`));
                      })
                    }
                  >
                    Dismiss
                  </button>
                </div>
              </article>
            ))}
          </div>
          {!views.recommendations.length && (
            <p>
              No supported suggestions remain. Review units and roles, or
              restore dismissed suggestions.
            </p>
          )}
          {!!views.dismissed?.length && (
            <button
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  await request(
                    `${root}/adaptive-views/dismissals`,
                    studyJson("POST", {
                      understanding_id: views.understanding_id,
                      dismissed: [],
                    }),
                  );
                  setViews(await request(`${root}/adaptive-views`));
                })
              }
            >
              Restore dismissed suggestions
            </button>
          )}
          <details className="studyBuilder">
            <summary>Build a descriptive study or ordered survey view</summary>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void action(() =>
                  create(
                    {
                      kind,
                      column,
                      aggregation: kind === "metric" ? aggregation : "count",
                      group_by: group ? [group] : [],
                      order:
                        kind === "distribution"
                          ? order
                              .split(",")
                              .map((value) => value.trim())
                              .filter(Boolean)
                          : [],
                    },
                    `${kind === "metric" ? aggregation : kind} of ${column}${group ? ` by ${group}` : ""}`,
                  ),
                );
              }}
            >
              <label>
                Study method
                <select
                  value={kind}
                  onChange={(event) => setKind(event.target.value)}
                >
                  <option value="distribution">Response distribution</option>
                  <option value="missingness">Missing values</option>
                  <option value="metric">Numeric measure</option>
                </select>
              </label>
              <label>
                Study column
                <select
                  required
                  value={column}
                  onChange={(event) => setColumn(event.target.value)}
                >
                  <option value="">Choose a column</option>
                  {usableColumns.map((item) => (
                    <option key={item.name}>{item.name}</option>
                  ))}
                </select>
              </label>
              <label>
                Compare groups
                <select
                  value={group}
                  onChange={(event) => setGroup(event.target.value)}
                >
                  <option value="">All records</option>
                  {usableColumns
                    .filter(
                      (item) =>
                        ["dimension", "ordinal"].includes(item.role) &&
                        item.name !== column,
                    )
                    .map((item) => (
                      <option key={item.name}>{item.name}</option>
                    ))}
                </select>
              </label>
              {kind === "metric" && (
                <label>
                  Aggregation
                  <select
                    value={aggregation}
                    onChange={(event) => setAggregation(event.target.value)}
                  >
                    {["sum", "avg", "count", "min", "max"].map((value) => (
                      <option key={value}>{value}</option>
                    ))}
                  </select>
                </label>
              )}
              {kind === "distribution" && (
                <label>
                  Category order (comma separated; required for ordinal
                  responses)
                  <input
                    value={order}
                    maxLength={2000}
                    onChange={(event) => setOrder(event.target.value)}
                    placeholder="Disagree, Neutral, Agree"
                  />
                </label>
              )}
              <button disabled={busy || !column}>Run descriptive study</button>
            </form>
          </details>
        </>
      )}
      {result && (
        <>
          <StudyResult value={result} />
          <div className="studyActions">
            <label>
              Pin to dashboard
              <select
                value={boardId}
                onChange={(event) => setBoardId(event.target.value)}
              >
                <option value="">Choose a dashboard</option>
                {boards
                  .filter((item) => item.owner_id === actorId)
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} ({item.pins.length}/6)
                    </option>
                  ))}
              </select>
            </label>
            <button
              disabled={
                busy ||
                !selectedBoard ||
                selectedBoard.pins.length >= 6 ||
                selectedBoard.pins.includes(result.version.id)
              }
              onClick={() =>
                void action(async () => {
                  if (selectedBoard)
                    await updateBoard(selectedBoard, [
                      ...selectedBoard.pins,
                      result.version.id,
                    ]);
                  setMessage("Result pinned to the dashboard.");
                })
              }
            >
              Pin this result
            </button>
          </div>
        </>
      )}
      <div className="studyLibrary">
        <h3>Saved studies</h3>
        <p>
          Sharing makes the chosen question, method and all versions visible to
          workspace members.
        </p>
        {!studies.length && <p>No studies yet.</p>}
        {studies.map((item) => (
          <article key={item.id}>
            <h4>
              {item.name} · {item.shared ? "Workspace" : "Private"}
            </h4>
            <div className="studyActions">
              {item.versions.map((version) => (
                <button
                  disabled={busy}
                  key={version.id}
                  onClick={() =>
                    void action(async () => {
                      setResult(
                        await request(
                          `${workspacePath}/study-versions/${version.id}`,
                        ),
                      );
                      setComparison(null);
                    })
                  }
                >
                  Open version {version.number}
                </button>
              ))}
              {item.owner_id === actorId && (
                <>
                  <button
                    disabled={busy}
                    onClick={() =>
                      void action(async () => {
                        await request(
                          `${workspacePath}/studies/${item.id}`,
                          studyJson("PATCH", { shared: !item.shared }),
                        );
                        setResult(null);
                        setBoard(null);
                        await refresh();
                      })
                    }
                  >
                    {item.shared
                      ? "Make study private"
                      : "Share study with workspace"}
                  </button>
                  <button
                    disabled={busy || views?.state !== "ready"}
                    onClick={() =>
                      void action(async () => {
                        if (!views) return;
                        setResult(
                          await request(
                            `${workspacePath}/studies/${item.id}/rerun`,
                            studyJson("POST", {
                              upload_id: root.split("/").pop(),
                              parent_id: item.versions.at(-1)?.id,
                              revision_id: views.revision_id,
                              understanding_id: views.understanding_id,
                            }),
                          ),
                        );
                        await refresh();
                        setMessage(
                          "New study version saved. The original is unchanged.",
                        );
                      })
                    }
                  >
                    Rerun on selected snapshot
                  </button>
                </>
              )}
            </div>
          </article>
        ))}
      </div>
      <details>
        <summary>Compare study versions</summary>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void action(async () => {
              setComparison(
                await request(
                  `${workspacePath}/study-comparison?before=${encodeURIComponent(before)}&after=${encodeURIComponent(after)}`,
                ),
              );
            });
          }}
        >
          <label>
            Earlier version
            <select
              required
              value={before}
              onChange={(event) => setBefore(event.target.value)}
            >
              <option value="">Choose a saved version</option>
              {studies.flatMap((item) =>
                item.versions.map((version) => (
                  <option key={version.id} value={version.id}>
                    {item.name} · v{version.number}
                  </option>
                )),
              )}
            </select>
          </label>
          <label>
            Later version
            <select
              required
              value={after}
              onChange={(event) => setAfter(event.target.value)}
            >
              <option value="">Choose another version</option>
              {studies
                .filter((item) =>
                  item.versions.some((version) => version.id === before),
                )
                .flatMap((item) =>
                  item.versions
                    .filter((version) => version.id !== before)
                    .map((version) => (
                      <option key={version.id} value={version.id}>
                        {item.name} · v{version.number}
                      </option>
                    )),
                )}
            </select>
          </label>
          <button disabled={busy || !before || !after}>Compare evidence</button>
        </form>
      </details>
      {comparison && (
        <div aria-label="Study comparison">
          <p>{comparison.limitation}</p>
          {comparison.differences.length > 0 && (
            <RecordTable
              data={{
                columns: ["Group", "Earlier", "Later", "Change"],
                rows: comparison.differences.map((item) => [
                  item.group.map(String).join(" / ") || "All",
                  item.before,
                  item.after,
                  item.delta,
                ]),
                records_analyzed: comparison.differences.length,
              }}
            />
          )}
          <div className="studyComparison">
            <StudyResult value={comparison.before} />
            <StudyResult value={comparison.after} />
          </div>
        </div>
      )}
      <div className="studyLibrary">
        <h3>Workspace dashboards</h3>
        <p>
          Pin up to six saved results. Shared dashboards require explicitly
          shared studies.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const boardName = String(new FormData(form).get("name") ?? "");
            void action(async () => {
              const created = await request<Board>(
                `${workspacePath}/study-boards`,
                studyJson("POST", { name: boardName }),
              );
              setBoardId(created.id);
              form.reset();
              await refresh();
            });
          }}
        >
          <label>
            Dashboard name
            <input name="name" required maxLength={100} />
          </label>
          <button disabled={busy}>Create study dashboard</button>
        </form>
        {boards.map((item) => (
          <article key={item.id}>
            <strong>{item.name}</strong> · {item.pins.length}/6 pins ·{" "}
            {item.shared ? "Workspace" : "Private"}
            <div className="studyActions">
              <button
                disabled={busy}
                onClick={() =>
                  void action(async () => {
                    setBoard(null);
                    setBoard(
                      await request(`${workspacePath}/study-boards/${item.id}`),
                    );
                  })
                }
              >
                Open dashboard {item.name}
              </button>
              {item.owner_id === actorId && (
                <>
                  <button
                    disabled={busy}
                    onClick={() =>
                      void action(() =>
                        updateBoard(item, item.pins, !item.shared),
                      )
                    }
                  >
                    {item.shared ? "Make dashboard private" : "Share dashboard"}
                  </button>
                  {!!item.pins.length && (
                    <button
                      disabled={busy}
                      onClick={() => void action(() => updateBoard(item, []))}
                    >
                      Clear all pins
                    </button>
                  )}
                  {item.pins.map((pin, index) => (
                    <button
                      key={pin}
                      disabled={busy}
                      onClick={() =>
                        void action(() =>
                          updateBoard(
                            item,
                            item.pins.filter((value) => value !== pin),
                          ),
                        )
                      }
                    >
                      Remove pin {index + 1}
                    </button>
                  ))}
                </>
              )}
            </div>
          </article>
        ))}
      </div>
      {board && (
        <section aria-label={`Pinned dashboard: ${board.board.name}`}>
          <h3>{board.board.name}</h3>
          {!board.studies.length && <p>Run a study and pin a result here.</p>}
          <div className="studyPinnedGrid">
            {board.studies.map((item) => (
              <StudyResult key={item.version.id} value={item} />
            ))}
          </div>
        </section>
      )}
    </section>
  );
}
