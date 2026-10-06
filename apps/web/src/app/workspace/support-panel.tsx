/* Use case: Connects a requester with explicitly authorized internal support staff.
What it does: Provides private requests, public reply history and version-checked triage without attaching source data. */

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";

export type StaffRole = "admin" | "support" | null;
type Ticket = {
  id: string;
  workspace_id: string;
  requester_id: string;
  subject: string;
  feature: string;
  category: string;
  status: string;
  priority: string;
  assignee_id: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
};
type SupportDetail = {
  ticket: Ticket & {
    description: string;
    feedback_id: string | null;
    job_id: string | null;
  };
  events: {
    id: string;
    sequence: number;
    actor_id: string;
    actor_role: "requester" | "staff";
    kind: string;
    body: string | null;
    status: string;
    priority: string;
    assignee_id: string | null;
    created_at: string;
  }[];
  diagnostics: null | {
    id: string;
    status: string;
    current_stage: string | null;
    failure_code: string | null;
    created_at: string;
    updated_at: string;
  };
};
type TicketPage = {
  tickets: Ticket[];
  next_cursor: string | null;
  limit: number;
};
type Staff = { id: string; email: string; role: string };
const statuses = [
  "open",
  "triaged",
  "in_progress",
  "waiting_on_customer",
  "escalated",
  "resolved",
];
const features = [
  "upload",
  "profile",
  "dashboard",
  "question",
  "knowledge",
  "report",
  "onboarding",
  "forecast",
  "refresh",
  "account",
  "other",
];
const categories = [
  "question",
  "problem",
  "incorrect",
  "slow",
  "missing_feature",
  "other",
];
const json = (method: string, body: object): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
const label = (value: string) => value.replaceAll("_", " ");

export function SupportPanel({
  workspaceId,
  staff = false,
  request,
}: {
  workspaceId?: string;
  staff?: boolean;
  request: ApiRequest;
}) {
  const collection = staff
    ? "/admin/support-tickets"
    : `/workspaces/${workspaceId}/support-tickets`;
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [query, setQuery] = useState({
    params: "limit=25",
    append: false,
    generation: 0,
  });
  const [filter, setFilter] = useState("");
  const [status, setStatus] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [staffList, setStaffList] = useState<Staff[]>([]);
  const [detail, setDetail] = useState<SupportDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const operation = useRef<AbortController | null>(null);
  useEffect(() => {
    if (!staff && !workspaceId) return;
    const controller = new AbortController();
    request<TicketPage>(`${collection}?${query.params}`, {
      signal: controller.signal,
    })
      .then((result) => {
        if (!controller.signal.aborted) {
          setTickets((previous) =>
            query.append ? [...previous, ...result.tickets] : result.tickets,
          );
          setNext(result.next_cursor);
          setLoading(false);
        }
      })
      .catch((cause) => {
        if (!controller.signal.aborted) {
          setTickets([]);
          setDetail(null);
          setError(
            cause instanceof Error
              ? cause.message
              : "Support requests are unavailable.",
          );
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [collection, query, request, staff, workspaceId]);
  useEffect(() => {
    if (!staff) return;
    const controller = new AbortController();
    request<{ staff: Staff[] }>("/admin/staff", { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setStaffList(value.staff);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [staff, request]);
  useEffect(() => () => operation.current?.abort(), []);
  function path(ticket: Ticket) {
    return `${staff ? "/admin" : ""}/workspaces/${ticket.workspace_id}/support-tickets/${ticket.id}`;
  }
  function refresh(event?: FormEvent) {
    event?.preventDefault();
    const params = new URLSearchParams({ limit: "25" });
    if (filter.trim()) params.set("q", filter.trim());
    if (status) params.set("status", status);
    if (priorityFilter) params.set("priority", priorityFilter);
    setLoading(true);
    setError("");
    setTickets([]);
    setNext(null);
    setQuery((previous) => ({
      params: params.toString(),
      append: false,
      generation: previous.generation + 1,
    }));
  }
  async function perform(
    action: (signal: AbortSignal) => Promise<SupportDetail>,
    success: string,
    reloadList = false,
  ) {
    if (busy) return;
    operation.current?.abort();
    const controller = new AbortController();
    operation.current = controller;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const value = await action(controller.signal);
      if (controller.signal.aborted) return;
      setDetail(value);
      setMessage(success);
      if (reloadList) refresh();
    } catch (cause) {
      if (!controller.signal.aborted) {
        if (
          (cause as { status?: number }).status === 403 ||
          (cause as { status?: number }).status === 401 ||
          (cause as { status?: number }).status === 404
        ) {
          setDetail(null);
          setTickets([]);
          setStaffList([]);
        }
        setError(
          cause instanceof Error
            ? cause.message
            : "Support request could not complete.",
        );
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  if (!staff && !workspaceId)
    return (
      <section className="panel" aria-label="Your support requests">
        <h2>Support</h2>
        <p>
          Select or create a workspace in Team & settings to open a support
          request.
        </p>
      </section>
    );
  return (
    <section
      className="panel supportPanel"
      aria-label={staff ? "Internal support queue" : "Your support requests"}
    >
      <div className="sectionHeading">
        <div>
          <p className="eyebrow">
            {staff ? "INTERNAL SUPPORT" : "WE’RE HERE TO HELP"}
          </p>
          <h2>{staff ? "Support queue" : "Support"}</h2>
        </div>
        <button
          type="button"
          disabled={busy || loading}
          onClick={() => refresh()}
        >
          Refresh requests
        </button>
      </div>
      <p>
        {staff
          ? "Only explicitly authorized support staff and the requester can read these conversations. Workspace membership grants no support access."
          : "Your requests are private to you and authorized internal support staff. Other workspace members, including owners, cannot read them."}
      </p>
      {!staff && (
        <details className="supportCreate">
          <summary>Open a support request</summary>
          <p>
            Share only what support needs. Do not include passwords, tokens or
            confidential rows. Files, prompts, answers and logs are not attached
            automatically.
          </p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const form = event.currentTarget;
              const values = new FormData(form);
              const body: Record<string, string> = {
                subject: String(values.get("subject")),
                description: String(values.get("description")),
                feature: String(values.get("feature")),
                category: String(values.get("category")),
              };
              if (values.get("job_id"))
                body.job_id = String(values.get("job_id"));
              if (values.get("feedback_id"))
                body.feedback_id = String(values.get("feedback_id"));
              void perform(
                (signal) =>
                  request<SupportDetail>(collection, {
                    ...json("POST", body),
                    signal,
                  }),
                "Request opened. Support can now read the details you shared.",
                true,
              );
            }}
          >
            <label>
              Request subject
              <input name="subject" required maxLength={120} disabled={busy} />
            </label>
            <div className="operationsFields">
              <label>
                Support feature
                <select name="feature" disabled={busy}>
                  {features.map((value) => (
                    <option key={value} value={value}>
                      {label(value)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Request category
                <select name="category" disabled={busy}>
                  {categories.map((value) => (
                    <option key={value} value={value}>
                      {label(value)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              What happened?
              <textarea
                name="description"
                required
                maxLength={4000}
                rows={4}
                disabled={busy}
              />
            </label>
            <details>
              <summary>Optional diagnostic references</summary>
              <p>
                These must belong to you in this workspace. A job reference
                shares its status and fixed failure code with support; it does
                not share your question, source or answer.
              </p>
              <label>
                Your job ID (optional)
                <input name="job_id" disabled={busy} />
              </label>
              <label>
                Your feedback ID (optional)
                <input name="feedback_id" disabled={busy} />
              </label>
            </details>
            <button disabled={busy}>Submit support request</button>
          </form>
        </details>
      )}
      <form className="supportFilters operationsFields" onSubmit={refresh}>
        <label>
          Search requests
          <input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            maxLength={80}
            placeholder="Subject or request ID"
          />
        </label>
        <label>
          Request status
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">All statuses</option>
            {statuses.map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Request priority
          <select
            value={priorityFilter}
            onChange={(event) => setPriorityFilter(event.target.value)}
          >
            <option value="">All priorities</option>
            <option value="normal">Normal</option>
            <option value="high">High</option>
          </select>
        </label>
        <button disabled={loading || busy}>Filter requests</button>
      </form>
      {loading && <p role="status">Loading support requests…</p>}
      {error && (
        <p role="alert" className="errorNotice">
          {error}
          {detail && (
            <>
              {" "}
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  void perform(
                    (signal) =>
                      request<SupportDetail>(path(detail.ticket), { signal }),
                    "Latest request loaded.",
                  )
                }
              >
                Reload selected request
              </button>
            </>
          )}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {!loading && !error && !tickets.length && (
        <p>No visible support requests match this view.</p>
      )}
      <div className="supportLayout">
        <div className="supportRequestList" aria-label="Request list">
          {tickets.map((ticket) => (
            <button
              type="button"
              key={ticket.id}
              disabled={busy}
              aria-pressed={detail?.ticket.id === ticket.id}
              onClick={() => {
                setDetail(null);
                void perform(
                  (signal) => request<SupportDetail>(path(ticket), { signal }),
                  "",
                );
              }}
            >
              <strong>{ticket.subject}</strong>
              <span>
                {label(ticket.status)} · {ticket.priority}
              </span>
              <small>{new Date(ticket.updated_at).toLocaleString()}</small>
              <small>Request {ticket.id}</small>
            </button>
          ))}
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
              Load more requests
            </button>
          )}
        </div>
        {detail && (
          <article
            className="supportDetail"
            aria-label="Selected support request"
          >
            <div className="sectionHeading">
              <h3>{detail.ticket.subject}</h3>
              <span className="operationsBadge">
                {label(detail.ticket.status)}
              </span>
            </div>
            <p>
              {label(detail.ticket.feature)} · {label(detail.ticket.category)} ·{" "}
              {detail.ticket.priority} priority
            </p>
            <p className="supportText">{detail.ticket.description}</p>
            <p className="operationsScope">
              Request {detail.ticket.id} · Version {detail.ticket.version}
            </p>
            {staff && (
              <form
                key={`triage-${detail.ticket.id}-${detail.ticket.version}`}
                className="supportTriage"
                onSubmit={(event) => {
                  event.preventDefault();
                  const values = new FormData(event.currentTarget);
                  void perform(
                    (signal) =>
                      request<SupportDetail>(path(detail.ticket), {
                        ...json("PATCH", {
                          expected_version: detail.ticket.version,
                          status: values.get("status"),
                          priority: values.get("priority"),
                          assignee_id: values.get("assignee") || null,
                          body: String(values.get("note") || ""),
                        }),
                        signal,
                      }),
                    "Triage updated and recorded in the shared timeline.",
                    true,
                  );
                }}
              >
                <h4>Triage this request</h4>
                <div className="operationsFields">
                  <label>
                    Update status
                    <select
                      name="status"
                      defaultValue={detail.ticket.status}
                      disabled={busy || detail.ticket.status === "resolved"}
                    >
                      {statuses.map((value) => (
                        <option key={value} value={value}>
                          {label(value)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Update priority
                    <select
                      name="priority"
                      defaultValue={detail.ticket.priority}
                      disabled={busy || detail.ticket.status === "resolved"}
                    >
                      <option value="normal">Normal</option>
                      <option value="high">High</option>
                    </select>
                  </label>
                  <label>
                    Assign support staff
                    <select
                      name="assignee"
                      defaultValue={detail.ticket.assignee_id ?? ""}
                      disabled={busy || detail.ticket.status === "resolved"}
                    >
                      <option value="">Unassigned</option>
                      {staffList.map((person) => (
                        <option key={person.id} value={person.id}>
                          {person.email} · {person.role}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label>
                  Public triage note
                  <textarea
                    name="note"
                    maxLength={4000}
                    rows={2}
                    disabled={busy || detail.ticket.status === "resolved"}
                  />
                </label>
                <p>The requester can read this note and all status updates.</p>
                <button disabled={busy || detail.ticket.status === "resolved"}>
                  Save triage
                </button>
              </form>
            )}
            <h4>Conversation & status history</h4>
            <ol className="supportTimeline">
              {detail.events.map((event) => (
                <li key={event.id}>
                  <div>
                    <strong>
                      {event.actor_role === "staff" ? "Support" : "Requester"} ·{" "}
                      {label(event.kind)}
                    </strong>
                    <time dateTime={event.created_at}>
                      {new Date(event.created_at).toLocaleString()}
                    </time>
                  </div>
                  {event.body && <p className="supportText">{event.body}</p>}
                  <small>
                    {label(event.status)} · {event.priority}
                  </small>
                </li>
              ))}
            </ol>
            {detail.ticket.status === "resolved" ? (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  const body = String(
                    new FormData(event.currentTarget).get("reopen") || "",
                  );
                  void perform(
                    (signal) =>
                      request<SupportDetail>(`${path(detail.ticket)}/reopen`, {
                        ...json("POST", {
                          expected_version: detail.ticket.version,
                          body,
                        }),
                        signal,
                      }),
                    "Request reopened.",
                    true,
                  );
                }}
              >
                <label>
                  Why reopen? (optional)
                  <textarea
                    name="reopen"
                    maxLength={4000}
                    rows={2}
                    disabled={busy}
                  />
                </label>
                <button disabled={busy}>Reopen request</button>
              </form>
            ) : (
              <form
                key={`reply-${detail.ticket.id}-${detail.ticket.version}`}
                onSubmit={(event) => {
                  event.preventDefault();
                  const body = String(
                    new FormData(event.currentTarget).get("reply") || "",
                  );
                  void perform(
                    (signal) =>
                      request<SupportDetail>(
                        `${path(detail.ticket)}/messages`,
                        {
                          ...json("POST", {
                            body,
                            expected_version: detail.ticket.version,
                          }),
                          signal,
                        },
                      ),
                    "Reply added to this request.",
                    true,
                  );
                }}
              >
                <label>
                  Reply to this request
                  <textarea
                    name="reply"
                    required
                    maxLength={4000}
                    rows={3}
                    disabled={busy}
                  />
                </label>
                <button disabled={busy}>Send reply</button>
              </form>
            )}
            {detail.diagnostics && (
              <details>
                <summary>Shared job diagnostics</summary>
                <dl className="operationsDefinitions">
                  {Object.entries(detail.diagnostics).map(([key, value]) => (
                    <div key={key}>
                      <dt>{label(key)}</dt>
                      <dd>{value ?? "Not available"}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            )}
          </article>
        )}
      </div>
      {busy && <p role="status">Saving or loading this support request…</p>}
    </section>
  );
}
