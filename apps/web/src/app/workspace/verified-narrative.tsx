/* Render only the server's verified statement segments; exact result controls stay separate. */

export type VerifiedNarrativeValue = {
  version: "verified-narrative-v1" | "verified-narrative-v2";
  mode: "selected" | "fallback";
  segments: {
    statement_id: string;
    text: string;
    evidence_ids: string[];
    kind: string;
  }[];
};

export function VerifiedNarrative({ narrative }: { narrative: VerifiedNarrativeValue }) {
  if (!["verified-narrative-v1", "verified-narrative-v2"].includes(narrative.version) || !narrative.segments.length) return null;
  return (
    <section aria-label="Result explanation" className="dataExplanation">
      {narrative.segments.map(segment => (
        <p key={segment.statement_id} className="explanationPlain" data-kind={segment.kind}>
          {segment.text}
        </p>
      ))}
      <details>
        <summary>Explanation evidence</summary>
        <p>Each statement uses the saved result or quoted source shown with this answer.</p>
        <ul>
          {[...new Set(narrative.segments.flatMap(segment => segment.evidence_ids))].map(id => (
            <li key={id}><code style={{ overflowWrap: "anywhere" }}>{id}</code></li>
          ))}
        </ul>
      </details>
    </section>
  );
}
