/* Use case: Presents source quotations separately from computed conversation results.
What it does: Reopens permission-checked citations and labels incomplete or conflicting evidence. */

import { useState } from "react";
import type { ApiRequest } from "./profile-panel";

export type Citation = {
  document_id: string;
  chunk_id: string;
  name: string;
  text: string;
  checksum: string;
  citation_url: string;
  source_created_at: string;
};

export function ConversationEvidence({
  citations,
  limitations,
  coverage,
  request,
}: {
  citations: Citation[];
  limitations: string[];
  coverage: string;
  request: ApiRequest;
}) {
  const [opened, setOpened] = useState<Citation | null>(null);
  const [error, setError] = useState("");
  return (
    <section className="conversationEvidence" aria-label="Document evidence">
      <h4>Supporting documents</h4>
      <p>
        These are quoted source statements. Numbers in a document are claims by
        that source, not calculations from your data.
      </p>
      {limitations.map((item) => (
        <p className="errorNotice" role="status" key={item}>
          {item}
        </p>
      ))}
      {coverage === "conflicting" && (
        <strong>Conflicting sources — review required</strong>
      )}
      {citations.map((citation) => (
        <article key={citation.chunk_id}>
          <strong>{citation.name}</strong>
          <p>
            Source uploaded{" "}
            {new Date(citation.source_created_at).toLocaleString()}
          </p>
          <blockquote>{citation.text}</blockquote>
          <button
            type="button"
            onClick={async () => {
              setOpened(null);
              setError("");
              try {
                setOpened(await request<Citation>(citation.citation_url));
              } catch (cause) {
                setError(
                  cause instanceof Error
                    ? cause.message
                    : "This source is unavailable.",
                );
              }
            }}
          >
            Open conversation citation
          </button>
        </article>
      ))}
      {error && <p role="alert">{error}</p>}
      {opened && (
        <details open>
          <summary>Verified conversation source passage</summary>
          <blockquote>{opened.text}</blockquote>
        </details>
      )}
    </section>
  );
}
