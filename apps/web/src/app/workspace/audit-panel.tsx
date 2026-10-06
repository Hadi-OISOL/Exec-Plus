/* Use case: Lets workspace members inspect activity they are allowed to access.
What it does: Searches permission-filtered audit metadata using server pagination and UTC date filters. */

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";

type AuditEvent = {
  id: string;
  actor_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  created_at: string;
};
type AuditPage = {
  events: AuditEvent[];
  next_cursor: string | null;
  limit: number;
};

export function AuditPanel({
  workspaceId,
  request,
}: {
  workspaceId: string;
  request: ApiRequest;
}) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(true);
  const [next, setNext] = useState<string | null>(null);
  const [query, setQuery] = useState({
    params: "limit=25",
    append: false,
    generation: 0,
  });
  const [search, setSearch] = useState("");
  const [action, setAction] = useState("");
  const [resource, setResource] = useState("");
  const [from, setFrom] = useState("");
  const [through, setThrough] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    request<AuditPage>(
      `/workspaces/${workspaceId}/audit-history?${query.params}`,
      { signal: controller.signal },
    )
      .then((result) => {
        if (controller.signal.aborted) return;
        setEvents((previous) =>
          query.append ? [...previous, ...result.events] : result.events,
        );
        setNext(result.next_cursor);
        setPending(false);
      })
      .catch((cause) => {
        if (controller.signal.aborted) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Audit history could not be loaded.",
        );
        setPending(false);
      });
    return () => controller.abort();
  }, [workspaceId, request, query]);
  function searchHistory(event?: FormEvent) {
    event?.preventDefault();
    const params = new URLSearchParams({ limit: "25" });
    if (search.trim()) params.set("q", search.trim());
    if (action.trim()) params.set("action", action.trim());
    if (resource.trim()) params.set("resource_type", resource.trim());
    if (from) params.set("since", `${from}T00:00:00Z`);
    if (through) params.set("until", `${through}T23:59:59.999999Z`);
    setEvents([]);
    setError("");
    setPending(true);
    setNext(null);
    setQuery((previous) => ({
      params: params.toString(),
      append: false,
      generation: previous.generation + 1,
    }));
  }
  return (
    <section className="panel auditPanel" aria-label="Workspace audit history">
      <div className="sectionHeading">
        <div>
          <p className="eyebrow">ACTIVITY RECORD</p>
          <h2>Workspace audit history</h2>
        </div>
        <button
          type="button"
          disabled={pending}
          onClick={() => searchHistory()}
        >
          Refresh history
        </button>
      </div>
      <p>
        Inspect actions visible under your current workspace access. Private
        activity stays private. Dates below use UTC; open an analysis to inspect
        its numerical evidence.
      </p>
      <form onSubmit={searchHistory} className="auditFilters">
        <label>
          Search audit history
          <input
            type="search"
            value={search}
            maxLength={80}
            placeholder="Action, resource type or ID"
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label>
          Exact audit action
          <input
            value={action}
            maxLength={50}
            placeholder="Optional"
            onChange={(event) => setAction(event.target.value)}
          />
        </label>
        <label>
          Resource type
          <input
            value={resource}
            maxLength={30}
            placeholder="Optional"
            onChange={(event) => setResource(event.target.value)}
          />
        </label>
        <label>
          From date (UTC)
          <input
            type="date"
            value={from}
            max={through || undefined}
            onChange={(event) => setFrom(event.target.value)}
          />
        </label>
        <label>
          Through date (UTC)
          <input
            type="date"
            value={through}
            min={from || undefined}
            onChange={(event) => setThrough(event.target.value)}
          />
        </label>
        <button disabled={pending}>Apply audit filters</button>
      </form>
      {error && (
        <p role="alert" className="errorNotice">
          {error}
        </p>
      )}
      <p role="status">
        {pending
          ? "Loading recorded activity…"
          : `${events.length} events shown${next ? " · More available" : ""}`}
      </p>
      {events.length > 0 ? (
        <div
          className="tableScroll"
          role="region"
          aria-label="Audit events"
          tabIndex={0}
        >
          <table>
            <thead>
              <tr>
                <th scope="col">When (UTC)</th>
                <th scope="col">Action</th>
                <th scope="col">Resource</th>
                <th scope="col">Actor ID</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td>
                    <time dateTime={event.created_at}>
                      {new Date(event.created_at)
                        .toISOString()
                        .replace("T", " ")
                        .slice(0, 19)}
                    </time>
                  </td>
                  <td>{event.action}</td>
                  <td>
                    {event.resource_type}
                    <small>{event.resource_id}</small>
                  </td>
                  <td>{event.actor_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        !pending && !error && <p>No visible events match these filters.</p>
      )}
      {next && (
        <button
          type="button"
          disabled={pending}
          onClick={() => {
            const params = new URLSearchParams(query.params);
            params.set("cursor", next);
            setError("");
            setPending(true);
            setQuery((previous) => ({
              params: params.toString(),
              append: true,
              generation: previous.generation + 1,
            }));
          }}
        >
          Load more events
        </button>
      )}
    </section>
  );
}
