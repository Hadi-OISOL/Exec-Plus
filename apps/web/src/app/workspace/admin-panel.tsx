/* Use case: Gives explicitly granted platform staff an account-safe operations console.
What it does: Lists bounded workspace metadata and job health, and opens the private support workflow without granting dataset access. */

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import { ProductUsagePanel } from "./product-usage";
import { SupportPanel } from "./support-panel";
import type { StaffRole } from "./support-panel";

type WorkspaceSummary = {
  id: string;
  name: string;
  created_at: string;
  seat_limit: number;
  active_seats: number;
  uploads: number;
  storage_bytes: number;
  plan: { id: string; billing: string };
};
type WorkspaceDetail = WorkspaceSummary & {
  owners: { id: string; email: string }[];
  datasets: number;
  documents: number;
  forecasts: number;
  jobs: Record<string, number>;
  support: Record<string, number>;
};
type WorkspacePage = {
  workspaces: WorkspaceSummary[];
  next_cursor: string | null;
  limit: number;
};

export function AdminPanel({
  role,
  request,
}: {
  role: Exclude<StaffRole, null>;
  request: ApiRequest;
}) {
  const [tab, setTab] = useState(role === "admin" ? "workspaces" : "support");
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState({
    params: "limit=25",
    append: false,
    generation: 0,
  });
  const [selected, setSelected] = useState<WorkspaceDetail | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const operation = useRef<AbortController | null>(null);
  useEffect(() => {
    if (role !== "admin" || tab !== "workspaces") return;
    const controller = new AbortController();
    request<WorkspacePage>(`/admin/workspaces?${query.params}`, {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) {
          setWorkspaces((previous) =>
            query.append
              ? [...previous, ...value.workspaces]
              : value.workspaces,
          );
          setNext(value.next_cursor);
          setLoading(false);
        }
      })
      .catch((cause) => {
        if (!controller.signal.aborted) {
          setWorkspaces([]);
          setSelected(null);
          setReportOpen(false);
          setError(
            cause instanceof Error
              ? cause.message
              : "Admin workspace metadata is unavailable.",
          );
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [role, tab, query, request]);
  useEffect(() => () => operation.current?.abort(), []);
  function find(event?: FormEvent) {
    event?.preventDefault();
    setLoading(true);
    setError("");
    setWorkspaces([]);
    setSelected(null);
    setReportOpen(false);
    setNext(null);
    const params = new URLSearchParams({ limit: "25" });
    if (search.trim()) params.set("q", search.trim());
    setQuery((previous) => ({
      params: params.toString(),
      append: false,
      generation: previous.generation + 1,
    }));
  }
  async function open(id: string) {
    operation.current?.abort();
    const controller = new AbortController();
    operation.current = controller;
    setBusy(true);
    setSelected(null);
    setReportOpen(false);
    setError("");
    try {
      const value = await request<WorkspaceDetail>(`/admin/workspaces/${id}`, {
        signal: controller.signal,
      });
      if (!controller.signal.aborted) setSelected(value);
    } catch (cause) {
      if (!controller.signal.aborted) {
        if (
          [401, 403, 404].includes((cause as { status?: number }).status ?? 0)
        ) {
          setWorkspaces([]);
          setNext(null);
        }
        setError(
          cause instanceof Error
            ? cause.message
            : "Workspace details are unavailable.",
        );
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  return (
    <div className="adminConsole" aria-label="Internal administration">
      <section className="panel">
        <p className="eyebrow">INTERNAL OPERATIONS</p>
        <h2>Admin console</h2>
        <p>
          Your explicit platform role is <strong>{role}</strong>. Privileged
          access is recorded. This console provides operational metadata and
          intentionally shared support requests; it does not open customer data
          or private analyses.
        </p>
        <div className="operationsTabs" aria-label="Console views">
          {role === "admin" && (
            <button
              type="button"
              aria-pressed={tab === "workspaces"}
              onClick={() => setTab("workspaces")}
            >
              Workspaces & health
            </button>
          )}
          <button
            type="button"
            aria-pressed={tab === "support"}
            onClick={() => setTab("support")}
          >
            Support queue
          </button>
        </div>
      </section>
      {tab === "support" ? (
        <SupportPanel staff request={request} />
      ) : (
        role === "admin" && (
          <>
            <section className="panel" aria-label="Admin workspace directory">
              <div className="sectionHeading">
                <h2>Workspace directory</h2>
                <button
                  type="button"
                  onClick={() => find()}
                  disabled={loading || busy}
                >
                  Refresh directory
                </button>
              </div>
              <form onSubmit={find} className="operationsSearch">
                <label>
                  Find a workspace
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    maxLength={80}
                    placeholder="Workspace name or ID"
                  />
                </label>
                <button disabled={loading || busy}>Search workspaces</button>
              </form>
              {loading && (
                <p role="status">Loading authorized operations metadata…</p>
              )}
              {error && (
                <p role="alert" className="errorNotice">
                  {error}
                </p>
              )}
              {!loading && !error && !workspaces.length && (
                <p>No workspaces match this search.</p>
              )}
              {workspaces.length > 0 && (
                <div
                  className="tableScroll"
                  tabIndex={0}
                  role="region"
                  aria-label="Admin workspace metadata"
                >
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Workspace</th>
                        <th scope="col">Seats</th>
                        <th scope="col">Uploads</th>
                        <th scope="col">Retained upload bytes</th>
                        <th scope="col">Plan</th>
                      </tr>
                    </thead>
                    <tbody>
                      {workspaces.map((item) => (
                        <tr key={item.id}>
                          <th scope="row">
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => void open(item.id)}
                            >
                              {item.name}
                            </button>
                            <small>{item.id}</small>
                          </th>
                          <td>
                            {item.active_seats} / {item.seat_limit}
                          </td>
                          <td>{item.uploads}</td>
                          <td>{item.storage_bytes.toLocaleString()}</td>
                          <td>
                            {item.plan.id.replaceAll("_", " ")}
                            <small>Billing: {item.plan.billing}</small>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {next && (
                <button
                  type="button"
                  disabled={loading || busy}
                  onClick={() => {
                    const params = new URLSearchParams(query.params);
                    params.set("cursor", next);
                    setLoading(true);
                    setQuery((previous) => ({
                      params: params.toString(),
                      append: true,
                      generation: previous.generation + 1,
                    }));
                  }}
                >
                  Load more workspaces
                </button>
              )}
              {busy && <p role="status">Loading workspace health…</p>}
            </section>
            {selected && (
              <section
                className="panel adminWorkspaceDetail"
                aria-label="Admin workspace details"
              >
                <div className="sectionHeading">
                  <div>
                    <h2>{selected.name}</h2>
                    <p className="operationsScope">Workspace {selected.id}</p>
                  </div>
                  <span className="operationsBadge">
                    Billing {selected.plan.billing}
                  </span>
                </div>
                <p>
                  Created {new Date(selected.created_at).toLocaleString()}.
                  Owners:{" "}
                  {selected.owners.map((owner) => owner.email).join(", ") ||
                    "No active owner reported"}
                  .
                </p>
                <div className="operationsMetrics">
                  {[
                    [
                      "Active seats",
                      `${selected.active_seats} / ${selected.seat_limit}`,
                    ],
                    ["Datasets", selected.datasets],
                    ["Uploads", selected.uploads],
                    ["Documents", selected.documents],
                    ["Saved forecasts", selected.forecasts],
                    ["Retained upload bytes", selected.storage_bytes],
                  ].map(([name, count]) => (
                    <div key={name}>
                      <span>{name}</span>
                      <strong>{count.toLocaleString()}</strong>
                    </div>
                  ))}
                </div>
                <div className="operationsColumns">
                  <section>
                    <h3>Conversation job health</h3>
                    <p>
                      Aggregate job states only. Questions, answers and private
                      job contents are excluded.
                    </p>
                    <dl className="operationsDefinitions">
                      {Object.entries(selected.jobs).map(([status, count]) => (
                        <div key={status}>
                          <dt>{status.replaceAll("_", " ")}</dt>
                          <dd>{count}</dd>
                        </div>
                      ))}
                    </dl>
                    {!Object.keys(selected.jobs).length && (
                      <p>No conversation jobs recorded.</p>
                    )}
                  </section>
                  <section>
                    <h3>Support request health</h3>
                    <dl className="operationsDefinitions">
                      {Object.entries(selected.support).map(
                        ([status, count]) => (
                          <div key={status}>
                            <dt>{status.replaceAll("_", " ")}</dt>
                            <dd>{count}</dd>
                          </div>
                        ),
                      )}
                    </dl>
                    {!Object.keys(selected.support).length && (
                      <p>No support requests recorded.</p>
                    )}
                  </section>
                </div>
                <button
                  type="button"
                  onClick={() => setReportOpen((value) => !value)}
                  aria-expanded={reportOpen}
                >
                  {reportOpen ? "Hide product usage" : "View product usage"}
                </button>
                {reportOpen && (
                  <ProductUsagePanel
                    key={selected.id}
                    path={`/admin/workspaces/${selected.id}/product-usage`}
                    request={request}
                  />
                )}
              </section>
            )}
          </>
        )
      )}
    </div>
  );
}
