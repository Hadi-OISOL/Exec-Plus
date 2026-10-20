/* Use case: Shows a headline number the way an executive dashboard tile does.
What it does: Counts up to the exact returned string (immediately under reduced motion), keeps that exact text in the DOM for readers and tests, and draws an optional approximate sparkline. */

"use client";

import { useEffect, useState } from "react";
import { plotNumber } from "../visualization-values";
import { countUpFrames } from "./chart-values";
import { useReducedMotion } from "./kit-chart";
import styles from "./chart-kit.module.css";

export function useCountUp(display: string, duration = 700): string | null {
  const reducedMotion = useReducedMotion();
  const [frame, setFrame] = useState<string | null>(null);
  useEffect(() => {
    const frames = countUpFrames(display);
    if (reducedMotion || frames.length < 2) return;
    let handle = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const index = Math.min(frames.length - 1, Math.floor(((now - start) / duration) * frames.length));
      setFrame(index >= frames.length - 1 ? null : frames[index]);
      if (index < frames.length - 1) handle = requestAnimationFrame(tick);
    };
    handle = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(handle); setFrame(null); };
  }, [display, duration, reducedMotion]);
  return frame;
}

export function CountUpValue({ value, exact, className = "" }: { value: string; exact?: string; className?: string }) {
  const frame = useCountUp(value);
  return <strong className={`${styles.countUp} ${className}`} title={exact ?? value} data-frame={frame ?? undefined}>{value}</strong>;
}

export function sparkPath(values: (string | null)[], width = 120, height = 32): { line: string; area: string } {
  const numbers = values.map(value => plotNumber(value));
  const present = numbers.filter((value): value is number => value !== null);
  if (present.length < 2) return { line: "", area: "" };
  const minimum = Math.min(...present);
  const span = Math.max(...present) - minimum || 1;
  const points = numbers.map((value, index) => value === null ? null : [(index / (numbers.length - 1)) * width, height - 2 - ((value - minimum) / span) * (height - 4)] as const);
  const line = points.map((point, index) => point ? `${index && points[index - 1] ? "L" : "M"}${point[0].toFixed(1)} ${point[1].toFixed(1)}` : "").join("");
  const first = points.find(Boolean)!;
  const last = [...points].reverse().find(Boolean)!;
  return { line, area: `${line}L${last[0].toFixed(1)} ${height}L${first[0].toFixed(1)} ${height}Z` };
}

export function StatTile({ label, value, exact, unit, caption, spark, className = "", valueClassName = "" }: { label: string; value: string; exact?: string; unit?: string; caption?: string; spark?: (string | null)[]; className?: string; valueClassName?: string }) {
  const path = spark ? sparkPath(spark) : null;
  return <div className={`${styles.tile} ${className}`}>
    <span className={styles.tileLabel}>{label}</span>
    <span><CountUpValue className={`${styles.tileValue} ${valueClassName}`} value={value} exact={exact} />{unit && <span className={styles.tileUnit}>{unit}</span>}</span>
    {path?.line && <svg className={styles.spark} viewBox="0 0 120 32" preserveAspectRatio="none" aria-hidden="true"><path d={path.area} /><path d={path.line} /></svg>}
    {caption && <span className={styles.tileCaption}>{caption}</span>}
  </div>;
}
