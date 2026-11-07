/* Use case: The "how it works" split on the public website.
What it does: A range slider with four stops swaps a stage clause and the real product screen that matches it; the stage names are buttons too, and the first stage renders without scripts. */

"use client";

import { useState } from "react";
import { Shot } from "./shot";
import styles from "../page.module.css";

const stages = [
  { name: "Add", clause: "First, add your file", note: "CSV, Excel, JSON, Parquet, SQLite, SPSS, Stata, SAS or XML up to 500 MB, or a read-only connection to PostgreSQL, MySQL, SQL Server or Google Sheets.", shot: "stage-add", alt: "The upload step: a drop zone that takes a CSV, Excel, JSON, Parquet or other data file up to 500 MB", width: 630, height: 310 },
  { name: "Confirm", clause: "Then confirm what it means", note: "Osalytix profiles every column, suggests roles and units, and asks only about what it could not infer.", shot: "stage-confirm", alt: "The prepare step: the active file, 100 rows and 20 columns, with its file-consistency score", width: 557, height: 280 },
  { name: "Read", clause: "Then read what the analysts found", note: "Findings, charts and suggested questions arrive without prompting, each recalculated by an independent check.", shot: "stage-read", alt: "The analyst team list: ten checks, each marked done with what it found", width: 322, height: 625 },
  { name: "Ask", clause: "Then ask, forecast and export", note: "Keep asking in your own words, run forecasts and what-ifs, and export answers to PDF or Excel with their evidence.", shot: "stage-ask", alt: "A verified chat answer for average rainfall by region with its chart controls", width: 550, height: 370 },
];

export function Stages() {
  const [index, setIndex] = useState(0);
  const stage = stages[index];
  return <div className={styles.stages}>
    <div className={styles.stageText} aria-live="polite">
      <h3 key={`h-${index}`} className={styles.stageFade}>{stage.clause}</h3>
      <p key={`p-${index}`} className={styles.stageFade}>{stage.note}</p>
    </div>
    <div className={styles.stageShot}>
      <Shot key={stage.shot} className={styles.stageFade} name={stage.shot} alt={stage.alt} width={stage.width} height={stage.height} />
    </div>
    <div className={styles.trackWrap}>
      <div className={styles.track}>
        <div className={styles.trackBar}>
          <span className={styles.trackRail} aria-hidden="true" /><span className={styles.trackDone} aria-hidden="true" style={{ width: `${(index / (stages.length - 1)) * 100}%` }} />
          <input className={styles.range} type="range" min={0} max={stages.length - 1} step={1} value={index} aria-label="Stage" aria-valuetext={stage.clause} onChange={event => setIndex(Number(event.target.value))} />
        </div>
        <ul className={styles.stageNames}>
          {stages.map((candidate, candidateIndex) => <li key={candidate.name}><button type="button" className={styles.stageName} aria-current={candidateIndex === index ? "step" : undefined} onClick={() => setIndex(candidateIndex)}>{candidate.name}</button></li>)}
        </ul>
      </div>
    </div>
  </div>;
}
