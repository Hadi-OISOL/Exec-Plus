/* Use case: The one live thing on the public website: a question box over the real 100-row farm sample.
What it does: Matches what the reader types or taps against four prepared questions, prints the exact precomputed answer on the shared paper receipt with its bars and footer rows, and renders the first answer on the server so the section reads without scripts. */

"use client";

import { useId, useState } from "react";
import styles from "../page.module.css";
import { Receipt } from "./kit";

type Answer = {
  id: string;
  question: string;
  keywords: string[];
  sentence: [string, string, string];
  unit: string;
  lead: string;
  rows: [string, string, number][];
  operation: string;
  grouping: string;
};

export const sampleAnswers: Answer[] = [
  {
    id: "rain", question: "Which region had the most rain?", keywords: ["rain", "rainfall", "barish", "baarish", "region", "wettest", "most"],
    sentence: ["West had the highest average rainfall: ", "1,744.51 mm", " across its 18 fields. East had the least at 1,310.04 mm."],
    unit: "mm", lead: "West",
    rows: [["West", "1,744.51", 1744.51], ["North", "1,599.96", 1599.96], ["South", "1,567.74", 1567.74], ["Central", "1,562.96", 1562.96], ["East", "1,310.04", 1310.04]],
    operation: "AVG(Rainfall_mm)", grouping: "by Region",
  },
  {
    id: "ph", question: "Average soil pH by crop", keywords: ["ph", "soil", "acid", "mitti", "crop", "fasal"],
    sentence: ["Rice fields have the highest average soil pH, ", "6.69", " over 15 fields; Maize the lowest at 5.95 over 17."],
    unit: "", lead: "Rice",
    rows: [["Rice", "6.69", 6.69], ["Cotton", "6.53", 6.53], ["Wheat", "6.52", 6.52], ["Potato", "6.49", 6.49], ["Sugarcane", "6.25", 6.25], ["Maize", "5.95", 5.95]],
    operation: "AVG(Soil_pH)", grouping: "by Crop_Type",
  },
  {
    id: "area", question: "Which crop has the largest fields?", keywords: ["largest", "large", "big", "biggest", "baray", "bade", "area", "hectare", "size", "khet", "crop", "fasal"],
    sentence: ["Wheat has the largest fields on average, ", "9.29 ha", " over 13 fields; Sugarcane the smallest at 4.85 ha over 18."],
    unit: "ha", lead: "Wheat",
    rows: [["Wheat", "9.29", 9.29], ["Potato", "8.86", 8.86], ["Cotton", "8.52", 8.52], ["Rice", "7.68", 7.68], ["Maize", "7.35", 7.35], ["Sugarcane", "4.85", 4.85]],
    operation: "AVG(Field_Area_hectare)", grouping: "by Crop_Type",
  },
  {
    id: "drip", question: "Drip irrigation kitne kheton mein hai?", keywords: ["drip", "irrigation", "kitne", "kitni", "how many", "count", "canal", "sprinkler", "rainfed", "watered"],
    sentence: ["", "19 of 100", " fields use drip irrigation. Canal is the most common method, on 31 fields."],
    unit: "fields", lead: "Drip",
    rows: [["Canal", "31", 31], ["Sprinkler", "26", 26], ["Rainfed", "24", 24], ["Drip", "19", 19]],
    operation: "COUNT(rows)", grouping: "by Irrigation_Type",
  },
];

export function matchSampleAnswer(text: string): Answer | null {
  const words = text.toLowerCase();
  if (!words.trim()) return null;
  let best: Answer | null = null;
  let bestScore = 0;
  for (const answer of sampleAnswers) {
    const score = answer.keywords.filter(keyword => words.includes(keyword)).length;
    if (score > bestScore) { best = answer; bestScore = score; }
  }
  return best;
}

export function AskSample() {
  const id = useId();
  const [text, setText] = useState(sampleAnswers[0].question);
  const answer = matchSampleAnswer(text);
  const max = answer ? Math.max(...answer.rows.map(row => row[2])) : 1;
  return <div className={styles.try}>
    <div>
      <label htmlFor={`${id}-ask`} className={styles.srOnly}>Ask the sample file a question</label>
      <textarea id={`${id}-ask`} className={styles.askLine} data-ui="" rows={1} value={text} onChange={event => setText(event.target.value.replace(/\n/g, " "))} onKeyDown={event => { if (event.key === "Enter") event.preventDefault(); }} placeholder="Ask the sample file…" autoComplete="off" spellCheck={false} />
      <ul className={styles.examples} aria-label="Prepared questions">
        {sampleAnswers.filter(candidate => candidate !== answer).slice(0, 3).map(candidate => <li key={candidate.id}><button type="button" className={styles.example} lang={candidate.id === "drip" ? "ur-Latn" : undefined} onClick={() => setText(candidate.question)}>{candidate.question}</button></li>)}
      </ul>
      <p className={`${styles.muted} ${styles.tryNote}`}>farm_field_survey.csv: 100 fields, 20 columns, Soil, Crop, Rainfall and Region among them. Every answer here is precomputed from the file.</p>
    </div>
    <p className={styles.srOnly} aria-live="polite">{answer ? `${answer.sentence[0]}${answer.sentence[1]}${answer.sentence[2]}` : "No prepared answer matches this question."}</p>
    <div className={`${styles.answer} ${styles.tryAnswer}`}>
      {answer ? <Receipt
        key={answer.id}
        tilt
        question={answer.question}
        figure={answer.sentence[1]}
        figureLabel={`${answer.sentence[0]}${answer.sentence[1]}${answer.sentence[2]}`}
        bars={answer.rows.map(([label, shown, value]) => ({ label, value: shown, share: value / max, emphasis: label === answer.lead }))}
        barsLabel={`${answer.operation} ${answer.grouping}${answer.unit ? `, in ${answer.unit}` : ""}`}
        footer={[{ label: "Dataset", value: "farm_field_survey.csv · version 1" }, { label: "Operation", value: `${answer.operation} ${answer.grouping}` }, { label: "Filters", value: "none" }, { label: "Rows read", value: "100 of 100" }]}
        ariaLabel={`Receipt: ${answer.question}`}
      /> : <p className={styles.muted}>{text.trim() ? "This sample knows four questions. In the product any question goes to the query engine, and an unclear one gets a clarifying question back." : "Type a question, or tap one below."}</p>}
    </div>
  </div>;
}
