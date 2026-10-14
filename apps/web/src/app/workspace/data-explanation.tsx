/* Use case: Makes grounded data explanations readable without changing their content.
What it does: Presents recognized sections with semantic headings and preserves plain historical answers as text. */

import { useId } from "react";

const sections = new Map([
  ["What this data is about", "meaning"],
  ["How the fields fit together", "fields"],
  ["Useful things to explore", "explore"],
  ["One thing to clarify", "clarify"],
  ["What I can do now", "next"],
  ["Context used", "context"],
]);

export function DataExplanation({ message }: { message: string }) {
  const id = useId();
  return <div className="dataExplanation">
    {message.split("\n\n").map((paragraph, index) => {
      const separator = paragraph.indexOf("\n");
      const title = separator < 0 ? "" : paragraph.slice(0, separator);
      const kind = sections.get(title);
      if (!kind) return <p className="explanationPlain" key={index}>{paragraph}</p>;
      const content = paragraph.slice(separator + 1);
      if (kind === "context") return <details className="explanationContext" key={index}>
        <summary>{title}</summary><p>{content}</p>
      </details>;
      const heading = `${id}-${index}`;
      return <section className="explanationCard" data-kind={kind} aria-labelledby={heading} key={index}>
        <h3 id={heading}>{title}</h3><p>{content}</p>
      </section>;
    })}
  </div>;
}
