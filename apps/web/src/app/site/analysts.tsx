/* Use case: The analyst-team sentence on the public website.
What it does: Sets the ten real analyst names as one statement and lights one name at a time every two seconds, unless motion is reduced. */

"use client";

import { useEffect, useState } from "react";
import styles from "../page.module.css";

const analysts = ["File reader", "Data quality", "Composition", "Distribution", "Segments", "Relationships", "Unusual values", "Trends", "Dashboard builder", "Purpose guide"];

export function AnalystSentence() {
  const [lit, setLit] = useState(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => { if (!document.hidden) setLit(value => (value + 1) % analysts.length); }, 2000);
    return () => window.clearInterval(timer);
  }, []);
  return <p className={styles.statement}>
    <span className={styles.lit}>Every file is read by </span>
    {analysts.map((name, index) => <span key={name} className={index === lit ? styles.lit : undefined}>{index === analysts.length - 1 ? `and the ${name}.` : index === analysts.length - 2 ? `the ${name}, ` : `${name}, `}</span>)}
  </p>;
}
