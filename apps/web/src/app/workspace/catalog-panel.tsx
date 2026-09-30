/* Use case: Discovers authorized data by its saved business meaning.
What it does: Shows current source dates and definition review state before opening a dataset. */

import { useState } from "react";
import type { ApiRequest } from "./profile-panel";

type Entry = {
  dataset_id: string;
  name: string;
  description: string;
  state: string;
  source_uploaded_at: string | null;
  source_revised_at: string | null;
  definition_version: number;
  documents: { id: string; name: string }[];
};

export function CatalogPanel({
  workspaceId,
  request,
  select,
}: {
  workspaceId: string;
  request: ApiRequest;
  select: (id: string) => Promise<void>;
}) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <section className="panel" aria-label="Find data by meaning">
      <h3>Find data by meaning</h3>
      <p>
        Search saved descriptions, column meanings, metric names or document
        titles. Source dates describe retained snapshots.
      </p>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          const q = String(
            new FormData(event.currentTarget).get("query") || "",
          );
          setBusy(true);
          setEntries([]);
          setMessage("");
          try {
            const items = await request<Entry[]>(
              `/workspaces/${workspaceId}/catalog?q=${encodeURIComponent(q)}`,
            );
            setEntries(items);
            if (!items.length) setMessage("No matching data found.");
          } catch (error) {
            setMessage(
              error instanceof Error ? error.message : "Search unavailable.",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Search your catalog
          <input
            name="query"
            maxLength={200}
            placeholder="For example: paid revenue"
          />
        </label>
        <button disabled={busy}>{busy ? "Searching…" : "Find data"}</button>
      </form>
      <p aria-live="polite">{message}</p>
      {entries.map((entry) => (
        <article key={entry.dataset_id} className="answerEvidence">
          <h4>{entry.name}</h4>
          <p>{entry.description || "No saved description yet."}</p>
          <p>
            Meaning: {entry.state.replaceAll("_", " ")} · version{" "}
            {entry.definition_version}
          </p>
          <p>
            Uploaded:{" "}
            {entry.source_uploaded_at
              ? new Date(entry.source_uploaded_at).toLocaleString()
              : "No upload"}
          </p>
          <p>
            Revised:{" "}
            {entry.source_revised_at
              ? new Date(entry.source_revised_at).toLocaleString()
              : "Not profiled"}
          </p>
          {entry.documents.length > 0 && (
            <p>
              Documents: {entry.documents.map((doc) => doc.name).join(", ")}
            </p>
          )}
          <button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await select(entry.dataset_id);
              } catch (error) {
                setEntries([]);
                setMessage(
                  error instanceof Error
                    ? error.message
                    : "Source unavailable.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            Open {entry.name}
          </button>
        </article>
      ))}
    </section>
  );
}
