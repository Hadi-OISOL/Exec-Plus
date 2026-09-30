/* Use case: Uploads reference documents and explores authorized source passages.
What it does: Keeps document sharing explicit and opens citations through authenticated requests. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";

type Document = { id: string; name: string; shared: boolean };
type Passage = {
  chunk_id: string;
  name: string;
  text: string;
  citation_url: string;
};
export function KnowledgePanel({
  root,
  request,
}: {
  root: string;
  request: ApiRequest;
}) {
  const dataset = root.split("/uploads/")[0];
  const [documents, setDocuments] = useState<Document[]>([]);
  const [passages, setPassages] = useState<Passage[]>([]);
  const [citation, setCitation] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    request<Document[]>(`${dataset}/documents`)
      .then((value) => {
        if (active) setDocuments(value);
      })
      .catch((error) => {
        if (active) setMessage(error.message);
      });
    return () => {
      active = false;
    };
  }, [dataset, request]);
  return (
    <section className="panel" aria-label="Reference documents">
      <h2>Reference documents</h2>
      <p>
        Upload TXT or Markdown documents up to 1 MiB. Search returns source
        passages with citations.
      </p>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const file = form.get("file") as File;
          setBusy(true);
          try {
            await request(
              `${dataset}/documents?name=${encodeURIComponent(file.name)}&shared=${form.has("shared")}`,
              {
                method: "POST",
                headers: { "Content-Type": "text/plain" },
                body: file,
              },
            );
            setDocuments(await request<Document[]>(`${dataset}/documents`));
            setMessage("Document stored.");
          } catch (cause) {
            setMessage(
              cause instanceof Error
                ? cause.message
                : "Could not store document.",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Reference document
          <input type="file" name="file" accept=".txt,.md" required />
        </label>
        <label>
          <input type="checkbox" name="shared" />
          Share document with workspace members
        </label>
        <button disabled={busy}>Upload document</button>
      </form>
      <ul>
        {documents.map((document) => (
          <li key={document.id}>
            {document.name} · {document.shared ? "Workspace" : "Private"}
          </li>
        ))}
      </ul>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          setBusy(true);
          setPassages([]);
          setCitation("");
          try {
            const result = await request<{ passages: Passage[] }>(
              `${dataset}/knowledge/search`,
              {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: form.get("query") }),
              },
            );
            setPassages(result.passages);
            setMessage(
              result.passages.length
                ? "Matching passages"
                : "No matching authorized passages.",
            );
          } catch (cause) {
            setMessage(
              cause instanceof Error ? cause.message : "Search failed.",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Search documents
          <input name="query" required maxLength={500} />
        </label>
        <button disabled={busy}>Search knowledge</button>
      </form>
      {message && <p>{message}</p>}
      {passages.map((passage) => (
        <article key={passage.chunk_id}>
          <h3>{passage.name}</h3>
          <blockquote
            style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
          >
            {passage.text}
          </blockquote>
          <button
            onClick={async () => {
              try {
                const result = await request<{ text: string }>(
                  passage.citation_url,
                );
                setCitation(result.text);
              } catch (cause) {
                setCitation("");
                setMessage(
                  cause instanceof Error
                    ? cause.message
                    : "Citation unavailable.",
                );
              }
            }}
          >
            Open citation
          </button>
        </article>
      ))}
      {citation && (
        <details open>
          <summary>Verified source passage</summary>
          <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
            {citation}
          </p>
        </details>
      )}
    </section>
  );
}
