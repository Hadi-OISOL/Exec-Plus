/* Use case: Saves and opens authorized questions, configurations, and executed analyses.
What it does: Creates private or workspace-shared items and exposes authenticated replay links. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";

type Item = { id: string; name: string; kind: string; shared: boolean };
const post = (body: object): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export function SaveControl({
  root,
  request,
  kind,
  payload,
  name,
}: {
  root: string;
  request: ApiRequest;
  kind: string;
  payload: object;
  name: string;
}) {
  const [shared, setShared] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    setMessage("");
    try {
      await request(
        `${root}/saved-items`,
        post({ kind, name: name.slice(0, 100), payload, shared }),
      );
      setMessage(shared ? "Saved for workspace members." : "Saved privately.");
      window.dispatchEvent(new Event("execplus-saved"));
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <label>
        <input
          type="checkbox"
          checked={shared}
          onChange={(event) => setShared(event.target.checked)}
        />
        Share {name} with workspace members
      </label>
      <button type="button" disabled={busy} onClick={() => void save()}>
        Save {name}
      </button>
      {message && <p role="status">{message}</p>}
    </div>
  );
}

export function SavedPanel({
  root,
  request,
}: {
  root: string;
  request: ApiRequest;
}) {
  const [schedules, setSchedules] = useState<
    { id: string; item_id: string; enabled: boolean }[]
  >([]);
  const [items, setItems] = useState<Item[]>([]);
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState("");
  const workspacePath = root.split("/datasets/")[0];
  useEffect(() => {
    let active = true;
    function refresh() {
      request<Item[]>(`${root}/saved-items`)
        .then((value) => {
          if (active) setItems(value);
        })
        .catch((cause) => {
          if (active) setError(cause.message);
        });
    }
    request<{ id: string; item_id: string; enabled: boolean }[]>(
      `${workspacePath}/report-schedules`,
    )
      .then((value) => {
        if (active) setSchedules(value);
      })
      .catch((cause) => {
        if (active) setError(cause.message);
      });
    refresh();
    window.addEventListener("execplus-saved", refresh);
    return () => {
      active = false;
      window.removeEventListener("execplus-saved", refresh);
    };
  }, [root, workspacePath, request]);
  async function open(id: string) {
    setError("");
    setResult(null);
    try {
      setResult(
        await request(`${workspacePath}/saved-items/${id}/run`, post({})),
      );
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not open saved item.",
      );
    }
  }
  return (
    <section className="panel" aria-label="Saved work">
      <h2>Saved work</h2>
      <p>
        Analysis replay uses its original revision. Questions and dashboards use
        the current revision.
      </p>
      {items.map((item) => (
        <article key={item.id}>
          <strong>{item.name}</strong> · {item.shared ? "Workspace" : "Private"}{" "}
          <button onClick={() => void open(item.id)}>Open {item.name}</button>
          {item.kind === "analysis" && (
            <button
              onClick={async () => {
                try {
                  await request(
                    `${workspacePath}/report-schedules`,
                    post({ item_id: item.id, interval_hours: 24 }),
                  );
                  setSchedules(
                    await request(`${workspacePath}/report-schedules`),
                  );
                } catch (cause) {
                  setError(
                    cause instanceof Error
                      ? cause.message
                      : "Could not schedule.",
                  );
                }
              }}
            >
              Email {item.name} daily to me
            </button>
          )}
          {item.shared && (
            <a
              href={`/workspace?workspace=${workspacePath.split("/").pop()}&saved=${item.id}`}
            >
              Link to {item.name}
            </a>
          )}
        </article>
      ))}
      {schedules
        .filter((schedule) => schedule.enabled)
        .map((schedule) => (
          <p key={schedule.id}>
            Daily report subscribed{" "}
            <button
              onClick={async () => {
                try {
                  await request(
                    `${workspacePath}/report-schedules/${schedule.id}`,
                    { method: "DELETE" },
                  );
                  setSchedules(
                    await request(`${workspacePath}/report-schedules`),
                  );
                } catch (cause) {
                  setError(
                    cause instanceof Error
                      ? cause.message
                      : "Could not unsubscribe.",
                  );
                }
              }}
            >
              Unsubscribe report
            </button>
          </p>
        ))}
      {!items.length && <p>No saved items yet.</p>}
      {error && <p role="alert">{error}</p>}
      {result !== null && (
        <details open>
          <summary>Verified saved result and lineage</summary>
          <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </details>
      )}
    </section>
  );
}
