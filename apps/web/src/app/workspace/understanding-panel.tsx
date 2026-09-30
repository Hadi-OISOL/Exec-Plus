/* Use case: Lets people review what their data means before relying on an analysis.
What it does: Edits versioned shared definitions and keeps personal goals private. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";

export const domains = [
  "auto",
  "sales",
  "finance",
  "inventory",
  "hr",
  "marketing",
  "operations",
  "research",
  "other",
];
type Column = {
  name: string;
  role: string;
  meaning: string;
  unit: string;
  currency: string;
  unit_column: string;
  date_meaning: string;
  timezone: string;
  missing_policy: string;
  tags: string[];
};
type Filter = {
  column: string;
  operator: string;
  value: string | number | boolean;
};
type Metric = {
  name: string;
  column: string;
  aggregation: string;
  filters: Filter[];
};
type Relationship = {
  join_path_id: string;
  state: string;
  cardinality: string;
};
type Definition = {
  domain: string;
  description: string;
  grain: string;
  sensitivity: string;
  update_mode: string;
  columns: Column[];
  metrics: Metric[];
  relationships: Relationship[];
};
type Understanding = {
  revision_id: string;
  version: number;
  state: string;
  definition: Definition;
  proposal: Definition;
  questions: string[];
  can_edit: boolean;
  column_types: Record<string, string>;
  relationship_options: {
    id: string;
    left_name: string;
    left_column: string;
    right_name: string;
    right_column: string;
  }[];
  preference: { domain_hint: string; goal: string };
  history: { id: string; version: number; state: string; created_at: string }[];
};

function post(body: object): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function UnderstandingPanel({
  root,
  request,
  onChange,
}: {
  root: string;
  request: ApiRequest;
  onChange: () => void;
}) {
  const [context, setContext] = useState<Understanding | null>(null);
  const [definition, setDefinition] = useState<Definition | null>(null);
  const [selected, setSelected] = useState("");
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [historical, setHistorical] = useState<{
    version: number;
    definition: Definition;
  } | null>(null);
  useEffect(() => {
    let active = true;
    request<Understanding>(`${root}/understanding`)
      .then((value) => {
        if (!active) return;
        setContext(value);
        setDefinition(value.definition);
        setGoal(value.preference.goal);
        setSelected(value.definition.columns[0]?.name ?? "");
      })
      .catch((cause) => {
        if (active) setError(cause.message);
      });
    return () => {
      active = false;
    };
  }, [root, request]);

  async function save(state: string) {
    if (!context || !definition) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await request(
        `${root}/understanding`,
        post({
          revision_id: context.revision_id,
          expected_version: context.version,
          state,
          definition,
        }),
      );
      const value = await request<Understanding>(`${root}/understanding`);
      setContext(value);
      setDefinition(value.definition);
      setMessage(
        state === "confirmed"
          ? "Business definitions confirmed. New analyses will use this version."
          : "Definition status updated. Confirm a reviewed version to resume calculations.",
      );
      onChange();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not save definitions.",
      );
    } finally {
      setBusy(false);
    }
  }

  const column = definition?.columns.find((item) => item.name === selected);
  function changeColumn(changes: Partial<Column>) {
    if (definition)
      setDefinition({
        ...definition,
        columns: definition.columns.map((item) =>
          item.name === selected ? { ...item, ...changes } : item,
        ),
      });
  }
  function changeMetric(index: number, changes: Partial<Metric>) {
    if (definition)
      setDefinition({
        ...definition,
        metrics: definition.metrics.map((item, i) =>
          i === index ? { ...item, ...changes } : item,
        ),
      });
  }

  function changeFilter(
    index: number,
    position: number,
    value: string | boolean,
  ) {
    if (!definition) return;
    changeMetric(index, {
      filters: definition.metrics[index].filters.map((filter, i) =>
        i === position ? { ...filter, value } : filter,
      ),
    });
  }

  function changeRelationship(id: string, changes: Partial<Relationship>) {
    if (!definition) return;
    const current = definition.relationships.find(
      (item) => item.join_path_id === id,
    );
    const revised = {
      join_path_id: id,
      state: "inferred",
      cardinality: "many_to_one",
      ...current,
      ...changes,
    };
    setDefinition({
      ...definition,
      relationships: [
        ...definition.relationships.filter((item) => item.join_path_id !== id),
        revised,
      ],
    });
  }

  return (
    <section
      className="panel understandingPanel"
      aria-label="Data understanding"
    >
      <h2>Data understanding</h2>
      <p>
        Review what a row and each field mean. Confirmed definitions are shared
        with your workspace; your personal goal stays private.
      </p>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {!context || !definition ? (
        <p>Loading data meaning…</p>
      ) : (
        <>
          <p>
            <strong>{context.state.replaceAll("_", " ")}</strong> ·{" "}
            {context.version
              ? `Version ${context.version}`
              : "Suggestions from the data profile"}
          </p>
          {context.state === "needs_review" && (
            <p>
              The source revision changed. Your previous definitions are
              retained; review them against this upload.
            </p>
          )}
          {!!context.questions.length && (
            <details>
              <summary>
                Questions worth reviewing ({context.questions.length})
              </summary>
              <ul>
                {context.questions.map((question) => (
                  <li key={question}>{question}</li>
                ))}
              </ul>
            </details>
          )}
          <details open={context.state !== "confirmed"}>
            <summary>Review business definitions</summary>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void save("confirmed");
              }}
            >
              <fieldset disabled={busy || !context.can_edit}>
                <legend>Shared dataset meaning</legend>
                <div className="understandingFields">
                  <label>
                    Business domain
                    <select
                      value={definition.domain}
                      onChange={(event) =>
                        setDefinition({
                          ...definition,
                          domain: event.target.value,
                        })
                      }
                    >
                      {domains.map((item) => (
                        <option key={item} value={item}>
                          {item === "auto" ? "Detect automatically" : item}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    One row represents
                    <select
                      value={definition.grain}
                      onChange={(event) =>
                        setDefinition({
                          ...definition,
                          grain: event.target.value,
                        })
                      }
                    >
                      {[
                        "unknown",
                        "record",
                        "order",
                        "order_item",
                        "customer",
                        "inventory_snapshot",
                        "survey_response",
                        "other",
                      ].map((item) => (
                        <option key={item} value={item}>
                          {item.replaceAll("_", " ")}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Data sensitivity
                    <select
                      value={definition.sensitivity}
                      onChange={(event) =>
                        setDefinition({
                          ...definition,
                          sensitivity: event.target.value,
                        })
                      }
                    >
                      {["internal", "confidential", "restricted"].map(
                        (item) => (
                          <option key={item}>{item}</option>
                        ),
                      )}
                    </select>
                  </label>
                  <label>
                    Expected update behavior
                    <select
                      value={definition.update_mode}
                      onChange={(event) =>
                        setDefinition({
                          ...definition,
                          update_mode: event.target.value,
                        })
                      }
                    >
                      {["snapshot", "append", "replace"].map((item) => (
                        <option key={item}>{item}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <label>
                  Dataset description
                  <textarea
                    maxLength={500}
                    value={definition.description}
                    onChange={(event) =>
                      setDefinition({
                        ...definition,
                        description: event.target.value,
                      })
                    }
                  />
                </label>
                <p>
                  Sensitivity and update behavior describe the data. They do not
                  change sharing permissions or import new rows.
                </p>
                <label>
                  Column to review
                  <select
                    value={selected}
                    onChange={(event) => setSelected(event.target.value)}
                  >
                    {definition.columns.map((item) => (
                      <option key={item.name}>{item.name}</option>
                    ))}
                  </select>
                </label>
                {column && (
                  <div className="understandingFields">
                    <label>
                      Column role
                      <select
                        value={column.role}
                        onChange={(event) =>
                          changeColumn({ role: event.target.value })
                        }
                      >
                        {[
                          "metric",
                          "dimension",
                          "identifier",
                          "ordinal",
                          "ignored",
                        ].map((item) => (
                          <option key={item}>{item}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Column meaning
                      <input
                        maxLength={200}
                        value={column.meaning}
                        onChange={(event) =>
                          changeColumn({ meaning: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      Meaning category
                      <select
                        value={column.tags[0] ?? ""}
                        onChange={(event) =>
                          changeColumn({
                            tags: event.target.value
                              ? [event.target.value]
                              : [],
                          })
                        }
                      >
                        <option value="">No business category</option>
                        {[
                          "revenue",
                          "sales",
                          "cost",
                          "amount",
                          "quantity",
                          "stock",
                          "price",
                          "headcount",
                          "salary",
                          "tenure",
                          "turnover",
                          "hires",
                        ].map((tag) => (
                          <option key={tag}>{tag}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Unit of measurement
                      <input
                        maxLength={40}
                        placeholder="e.g. kilograms"
                        value={column.unit}
                        onChange={(event) =>
                          changeColumn({ unit: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      Currency code
                      <input
                        maxLength={3}
                        placeholder="e.g. PKR"
                        value={column.currency}
                        onChange={(event) =>
                          changeColumn({ currency: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      Per-row currency or unit column
                      <select
                        value={column.unit_column}
                        onChange={(event) =>
                          changeColumn({ unit_column: event.target.value })
                        }
                      >
                        <option value="">None</option>
                        {definition.columns.map((item) => (
                          <option key={item.name}>{item.name}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Missing-value handling
                      <select
                        value={column.missing_policy}
                        onChange={(event) =>
                          changeColumn({ missing_policy: event.target.value })
                        }
                      >
                        <option value="exclude">
                          Exclude missing values from this measure
                        </option>
                        <option value="needs_review">
                          Require review before calculation
                        </option>
                      </select>
                    </label>
                    <label>
                      Date meaning
                      <input
                        maxLength={100}
                        placeholder="e.g. invoice date"
                        value={column.date_meaning}
                        onChange={(event) =>
                          changeColumn({ date_meaning: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      Time zone
                      <input
                        maxLength={80}
                        placeholder="e.g. Asia/Karachi"
                        value={column.timezone}
                        onChange={(event) =>
                          changeColumn({ timezone: event.target.value })
                        }
                      />
                    </label>
                  </div>
                )}
                <details>
                  <summary>Metric definitions and required filters</summary>
                  <p>
                    Define a default calculation for a numeric column. Required
                    filters apply to every new calculation of that column. Dates
                    and time zones are descriptive; no implicit conversion
                    occurs.
                  </p>
                  {definition.metrics.map((metric, index) => (
                    <fieldset key={index}>
                      <legend>Metric {index + 1}</legend>
                      <div className="understandingFields">
                        <label>
                          Metric name
                          <input
                            value={metric.name}
                            maxLength={80}
                            onChange={(event) =>
                              changeMetric(index, { name: event.target.value })
                            }
                            required
                          />
                        </label>
                        <label>
                          Metric column
                          <select
                            value={metric.column}
                            onChange={(event) =>
                              changeMetric(index, {
                                column: event.target.value,
                              })
                            }
                          >
                            {definition.columns
                              .filter((item) => item.role === "metric")
                              .map((item) => (
                                <option key={item.name}>{item.name}</option>
                              ))}
                          </select>
                        </label>
                        <label>
                          Calculation
                          <select
                            value={metric.aggregation}
                            onChange={(event) =>
                              changeMetric(index, {
                                aggregation: event.target.value,
                              })
                            }
                          >
                            {["sum", "avg", "count", "min", "max"].map(
                              (item) => (
                                <option key={item}>{item}</option>
                              ),
                            )}
                          </select>
                        </label>
                      </div>
                      {metric.filters.map((filter, position) => (
                        <div className="understandingFields" key={position}>
                          <label>
                            Filter column
                            <select
                              value={filter.column}
                              onChange={(event) =>
                                changeMetric(index, {
                                  filters: metric.filters.map((item, j) =>
                                    j === position
                                      ? {
                                          ...item,
                                          column: event.target.value,
                                          value:
                                            context.column_types[
                                              event.target.value
                                            ] === "boolean"
                                              ? false
                                              : "",
                                        }
                                      : item,
                                  ),
                                })
                              }
                            >
                              {definition.columns.map((item) => (
                                <option key={item.name}>{item.name}</option>
                              ))}
                            </select>
                          </label>
                          <label>
                            Condition
                            <select
                              value={filter.operator}
                              onChange={(event) =>
                                changeMetric(index, {
                                  filters: metric.filters.map((item, j) =>
                                    j === position
                                      ? {
                                          ...item,
                                          operator: event.target.value,
                                        }
                                      : item,
                                  ),
                                })
                              }
                            >
                              {[
                                "eq",
                                "ieq",
                                "ne",
                                "lt",
                                "lte",
                                "gt",
                                "gte",
                              ].map((item) => (
                                <option key={item} value={item}>
                                  {
                                    {
                                      eq: "equals",
                                      ieq: "equals ignoring case",
                                      ne: "does not equal",
                                      lt: "less than",
                                      lte: "at most",
                                      gt: "greater than",
                                      gte: "at least",
                                    }[item]
                                  }
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            Filter value
                            {context.column_types[filter.column] ===
                            "boolean" ? (
                              <select
                                value={String(filter.value)}
                                onChange={(event) =>
                                  changeFilter(
                                    index,
                                    position,
                                    event.target.value === "true",
                                  )
                                }
                              >
                                <option value="true">true</option>
                                <option value="false">false</option>
                              </select>
                            ) : (
                              <input
                                value={String(filter.value)}
                                maxLength={200}
                                onChange={(event) =>
                                  changeFilter(
                                    index,
                                    position,
                                    event.target.value,
                                  )
                                }
                              />
                            )}
                          </label>
                          <button
                            type="button"
                            onClick={() =>
                              changeMetric(index, {
                                filters: metric.filters.filter(
                                  (_, j) => j !== position,
                                ),
                              })
                            }
                          >
                            Remove filter
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        disabled={metric.filters.length >= 20}
                        onClick={() =>
                          changeMetric(index, {
                            filters: [
                              ...metric.filters,
                              {
                                column: definition.columns[0].name,
                                operator: "eq",
                                value:
                                  context.column_types[
                                    definition.columns[0].name
                                  ] === "boolean"
                                    ? false
                                    : "",
                              },
                            ],
                          })
                        }
                      >
                        Add required filter
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setDefinition({
                            ...definition,
                            metrics: definition.metrics.filter(
                              (_, i) => i !== index,
                            ),
                          })
                        }
                      >
                        Remove metric
                      </button>
                    </fieldset>
                  ))}
                  <button
                    type="button"
                    disabled={
                      definition.metrics.length >= 24 ||
                      !definition.columns.some((item) => item.role === "metric")
                    }
                    onClick={() =>
                      setDefinition({
                        ...definition,
                        metrics: [
                          ...definition.metrics,
                          {
                            name: "",
                            column: definition.columns.find(
                              (item) => item.role === "metric",
                            )!.name,
                            aggregation: "sum",
                            filters: [],
                          },
                        ],
                      })
                    }
                  >
                    Add metric definition
                  </button>
                </details>
                <details>
                  <summary>Dataset relationships</summary>
                  <p>
                    Review declared relationships before using a join. The
                    right-hand key must identify one row. Repeated keys cannot
                    multiply a measure from the other dataset.
                  </p>
                  {!context.relationship_options.length && (
                    <p>No relationships have been declared for this dataset.</p>
                  )}
                  {context.relationship_options.map((path) => {
                    const value = definition.relationships.find(
                      (item) => item.join_path_id === path.id,
                    );
                    return (
                      <fieldset key={path.id}>
                        <legend>
                          {path.left_name} ({path.left_column}) →{" "}
                          {path.right_name} ({path.right_column})
                        </legend>
                        <label>
                          Relationship review
                          <select
                            value={value?.state ?? "inferred"}
                            onChange={(event) =>
                              changeRelationship(path.id, {
                                state: event.target.value,
                              })
                            }
                          >
                            <option value="inferred">
                              Proposed — not approved for analysis
                            </option>
                            <option value="confirmed">Confirmed</option>
                            <option value="rejected">Rejected</option>
                            <option value="needs_review">Needs review</option>
                          </select>
                        </label>
                        <label>
                          Rows matched from left to right
                          <select
                            value={value?.cardinality ?? "many_to_one"}
                            onChange={(event) =>
                              changeRelationship(path.id, {
                                cardinality: event.target.value,
                              })
                            }
                          >
                            <option value="many_to_one">
                              Many rows may match one row
                            </option>
                            <option value="one_to_one">
                              One row matches one row
                            </option>
                          </select>
                        </label>
                      </fieldset>
                    );
                  })}
                </details>
                <div className="understandingActions">
                  <button disabled={busy}>Confirm business definitions</button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void save("needs_review")}
                  >
                    Save for review
                  </button>
                  {context.version > 0 && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void save("rejected")}
                    >
                      Revoke definition
                    </button>
                  )}
                </div>
              </fieldset>
              {!context.can_edit && (
                <p>
                  The dataset creator or a workspace administrator can change
                  shared definitions.
                </p>
              )}
            </form>
          </details>
          <details>
            <summary>Your private analysis goal</summary>
            <form
              onSubmit={async (event) => {
                event.preventDefault();
                setBusy(true);
                setError("");
                try {
                  await request(
                    `${root.split("/uploads/")[0]}/preferences`,
                    post({ domain_hint: context.preference.domain_hint, goal }),
                  );
                  setMessage("Your private goal was saved.");
                } catch (cause) {
                  setError(
                    cause instanceof Error
                      ? cause.message
                      : "Could not save your goal.",
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              <label>
                My analysis goal
                <textarea
                  value={goal}
                  maxLength={500}
                  onChange={(event) => setGoal(event.target.value)}
                />
              </label>
              <button disabled={busy}>Save my goal</button>
            </form>
          </details>
          {!!context.history.length && (
            <details>
              <summary>Definition history</summary>
              <ul>
                {context.history.map((item) => (
                  <li key={item.id}>
                    Version {item.version} · {item.state} ·{" "}
                    {new Date(item.created_at).toLocaleString()}
                    <button
                      type="button"
                      onClick={async () => {
                        setError("");
                        try {
                          setHistorical(
                            await request(
                              `${root.split("/uploads/")[0]}/understandings/${item.id}`,
                            ),
                          );
                        } catch (cause) {
                          setError(
                            cause instanceof Error
                              ? cause.message
                              : "Could not load this version.",
                          );
                        }
                      }}
                    >
                      Inspect version {item.version}
                    </button>
                  </li>
                ))}
              </ul>
              {historical && (
                <article
                  aria-label={`Definition version ${historical.version}`}
                >
                  <h3>Version {historical.version}</h3>
                  <p>{historical.definition.description}</p>
                  <p>
                    {historical.definition.domain} · one row represents{" "}
                    {historical.definition.grain.replaceAll("_", " ")}
                  </p>
                  <ul>
                    {historical.definition.columns.map((column) => (
                      <li key={column.name}>
                        {column.name}: {column.role} {column.meaning}{" "}
                        {column.currency || column.unit}
                      </li>
                    ))}
                  </ul>
                  <ul>
                    {historical.definition.metrics.map((metric) => (
                      <li key={metric.column}>
                        {metric.name}: {metric.aggregation} of {metric.column}
                        {metric.filters
                          .map(
                            (filter) =>
                              `; ${filter.column} ${filter.operator} ${String(filter.value)}`,
                          )
                          .join("")}
                      </li>
                    ))}
                  </ul>
                </article>
              )}
              <p>
                Earlier calculations retain the definition version used when
                they ran.
              </p>
            </details>
          )}
        </>
      )}
    </section>
  );
}
