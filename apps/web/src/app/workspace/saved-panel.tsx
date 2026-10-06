/* Use case: Saves and opens authorized questions, configurations, and executed analyses.
What it does: Creates private or workspace-shared items and exposes authenticated replay links. */

import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import { Icon } from "./explore-components";
import { LibraryControls, visibleLibraryItem } from "./library-controls";
import type { LibraryLayout, LibraryVisibility } from "./library-controls";
import { SavedResult } from "./saved-result";
import type { SavedAnswer } from "./saved-result";
import styles from "./library.module.css";

type Item = { id: string; name: string; kind: string; shared: boolean; description?: string; created_at?: string };
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
  initialItemId,
}: {
  root: string;
  request: ApiRequest;
  initialItemId?: string;
}) {
  return <SavedLibrary key={root} root={root} request={request} initialItemId={initialItemId} />;
}

function SavedLibrary({ root, request, initialItemId }: {
  root: string;
  request: ApiRequest;
  initialItemId?: string;
}) {
  const [schedules, setSchedules] = useState<
    { id: string; item_id: string; enabled: boolean }[]
  >([]);
  const [items, setItems] = useState<Item[]>([]);
  const [result, setResult] = useState<{ id: string; answer: SavedAnswer } | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [visibility, setVisibility] = useState<LibraryVisibility>("all");
  const [layout, setLayout] = useState<LibraryLayout>("grid");
  const [kind, setKind] = useState("all");
  const [loading, setLoading] = useState(true);
  const [opening, setOpening] = useState("");
  const openingController = useRef<AbortController | null>(null);
  const workspacePath = root.split("/datasets/")[0];
  useEffect(() => {
    let active = true;
    function refresh() {
      request<Item[]>(`${root}/saved-items`)
        .then((value) => {
          if (active) {
            setItems(value);
            setLoading(false);
            setResult((previous) => previous && value.some((item) => item.id === previous.id) ? previous : null);
          }
        })
        .catch((cause) => {
          if (active) {
            setError(cause.message);
            setResult(null);
            setItems([]);
            setLoading(false);
          }
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
      openingController.current?.abort();
      window.removeEventListener("execplus-saved", refresh);
    };
  }, [root, workspacePath, request]);
  const open = useCallback(async (id: string) => {
    openingController.current?.abort();
    const controller = new AbortController();
    openingController.current = controller;
    setError("");
    setResult(null);
    setOpening(id);
    try {
      const answer = await request<SavedAnswer>(`${workspacePath}/saved-items/${id}/run`, { ...post({}), signal: controller.signal });
      if (!controller.signal.aborted) setResult({ id, answer });
    } catch (cause) {
      if (!controller.signal.aborted) setError(
        cause instanceof Error ? cause.message : "Could not open saved item.",
      );
    } finally {
      if (!controller.signal.aborted) setOpening("");
    }
  }, [workspacePath, request]);
  useEffect(() => {
    let active = true;
    if (initialItemId) void Promise.resolve().then(() => {
      if (active) void open(initialItemId);
    });
    return () => {
      active = false;
      openingController.current?.abort();
    };
  }, [initialItemId, open]);
  const visible = items.filter((item) => visibleLibraryItem(item, search, visibility) && (kind === "all" || item.kind === kind));
  const selected = items.find((item) => item.id === result?.id);
  return (
    <section className={`panel ${styles.library}`} aria-label="Saved work">
      <div className={styles.libraryHeader}>
        <div>
          <span className={styles.eyebrow}>Your answer library</span>
          <h2>Saved work</h2>
          <p>Return to useful answers, questions and dashboard configurations for the selected data. Analysis replay uses its original revision. Questions and dashboards use the current revision.</p>
        </div>
        <span className={styles.badge}>{items.length} saved</span>
      </div>
      <LibraryControls name="saved work" search={search} onSearch={setSearch} visibility={visibility} onVisibility={setVisibility} layout={layout} onLayout={setLayout} count={visible.length} />
      <div className={styles.actions} role="group" aria-label="Saved item types">
        {[["all", "All"], ["analysis", "Answers"], ["question", "Questions"], ["prompt", "Prompts"], ["dashboard", "Dashboards"]].map(([value, label]) => (
          <button key={value} type="button" aria-pressed={kind === value} onClick={() => setKind(value)}>{label}</button>
        ))}
      </div>
      {error && <p role="alert" className="errorNotice">{error}</p>}
      {opening && <p role="status">Opening saved work and verifying access…</p>}
      {result && selected && <SavedResult value={result.answer} name={selected.name} kind={selected.kind} request={request} />}
      {loading && <p role="status">Loading your saved work…</p>}
      <div className={layout === "grid" ? styles.grid : styles.list} data-library-layout={layout} aria-label="Saved items" style={{ marginTop: 20 }}>
      {visible.map((item) => (
        <article key={item.id} className={styles.card}>
          <div className={styles.cardTop}>
            <span className={styles.cardIcon}><Icon name={item.kind === "dashboard" ? "overview" : item.kind === "analysis" ? "usage" : "chat"} /></span>
            <span className={styles.cardType}>{item.kind === "analysis" ? "Answer" : item.kind}</span>
            <span className={styles.badge}>{item.shared ? "Workspace" : "Private"}</span>
          </div>
          <h3>{item.name}</h3>
          <p className={styles.description}>{item.description || (item.kind === "analysis" ? "A saved execution with its original source evidence." : "A saved configuration to run on the current revision.")}</p>
          {item.created_at && <p className={styles.metadata}>Saved {new Date(item.created_at).toLocaleDateString()}</p>}
          <div className={styles.actions}>
          <button disabled={opening === item.id} onClick={() => void open(item.id)}>Open {item.name}</button>
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
          </div>
        </article>
      ))}
      </div>
      {!loading && !items.length && <div className={styles.empty}><h3>No saved items yet.</h3><p>Save an answer or question while exploring your data. It will appear here with its sharing status.</p></div>}
      {!loading && items.length > 0 && !visible.length && <p className={styles.empty}>No saved work matches these filters. Try another name or visibility.</p>}
      <div className={styles.savedSchedules}>
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
      </div>
    </section>
  );
}
