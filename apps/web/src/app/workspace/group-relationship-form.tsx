/* Use case: Lets a person choose an explicit, governed group comparison.
What it does: Sends selected field names through the existing private conversation flow. */

import { useId, useState } from "react";

type Meaning = {
  state: string;
  definition: { columns: { name: string; role: string; unit: string; currency: string; unit_column: string }[] };
  column_types: Record<string, string>;
};

export function GroupRelationshipForm({ understanding, onAsk, onReview }: {
  understanding: Meaning;
  onAsk: (question: string) => void;
  onReview: () => void;
}) {
  const id = useId();
  const [first, setFirst] = useState("");
  const [second, setSecond] = useState("");
  const [group, setGroup] = useState("");
  const columns = understanding.definition.columns;
  const metrics = columns.filter(column => column.role === "metric" && ["integer", "decimal"].includes(understanding.column_types[column.name]) && Boolean(column.unit || column.currency) && !column.unit_column);
  const categories = columns.filter(column => ["dimension", "ordinal"].includes(column.role) && understanding.column_types[column.name] !== "date");
  const ready = understanding.state === "confirmed" && metrics.length >= 2 && categories.length > 0;
  const chosen = ready && first !== second && metrics.some(column => column.name === first) && metrics.some(column => column.name === second) && categories.some(column => column.name === group);
  const question = `Compare the relationship between ${JSON.stringify(first)} and ${JSON.stringify(second)} within groups of ${JSON.stringify(group)}.`;
  const tooLong = chosen && question.length > 500;
  const valid = chosen && !tooLong;
  return <details className="groupComparisonSetup">
    <summary>Compare groups <span>Does the overall pattern hold within each group?</span></summary>
    {ready ? <form aria-label="Compare relationships within groups" onSubmit={event => {
      event.preventDefault();
      if (valid) onAsk(question);
    }}>
      <p>Choose two measures and a category. We will check them together, then separately within each group.</p>
      <div className="groupComparisonFields">
        <label htmlFor={`${id}-first`}>First measure<select id={`${id}-first`} required value={first} onChange={event => setFirst(event.target.value)}><option value="">Choose a measure</option>{metrics.map(column => <option key={column.name} value={column.name} disabled={column.name === second}>{column.name} · {column.currency || column.unit}</option>)}</select></label>
        <label htmlFor={`${id}-second`}>Second measure<select id={`${id}-second`} required value={second} onChange={event => setSecond(event.target.value)}><option value="">Choose a measure</option>{metrics.map(column => <option key={column.name} value={column.name} disabled={column.name === first}>{column.name} · {column.currency || column.unit}</option>)}</select></label>
        <label htmlFor={`${id}-group`}>Group by<select id={`${id}-group`} required value={group} onChange={event => setGroup(event.target.value)}><option value="">Choose a category</option>{categories.map(column => <option key={column.name} value={column.name}>{column.name}</option>)}</select></label>
      </div>
      <p className="groupComparisonHint">Needs at least two groups with 20 complete, varying pairs each. Up to 12 groups and 10,000 rows; saved required filters must match. This describes relationships, not causes.</p>
      {tooLong && <p role="alert">These names make the question too long. Shorten the column names in Prepare data, then try again.</p>}
      <button type="submit" disabled={!valid}>Compare these groups</button>
    </form> : <div className="groupComparisonUnavailable"><p>Confirm two numerical measures with fixed units and one grouping field before comparing.</p><button type="button" onClick={onReview}>Review data meanings</button></div>}
  </details>;
}
