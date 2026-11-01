/* Use case: The paper receipt that accompanies every public-site figure.
What it does: Renders a server-side receipt (header, question, serif figure, mono rows, bar list, footer rows, perforated edge, optional printer slot) from exact caller-supplied strings; motion is opt-in through data-print and happens in CSS. */

import type { ReactNode } from "react";
import styles from "./receipt.module.css";
import { Stamp } from "./stamp";

export type ReceiptRow = Readonly<{ label: string; value: string; emphasis?: boolean }>;
export type ReceiptBar = Readonly<{ label: string; value: string; share: number; emphasis?: boolean }>;

export type ReceiptProps = Readonly<{
  header?: string;
  question: string;
  figure?: string;
  unit?: string;
  figureLabel?: string;
  rows?: readonly ReceiptRow[];
  bars?: readonly ReceiptBar[];
  barsLabel?: string;
  footer?: readonly ReceiptRow[];
  stamp?: string | false;
  frame?: "printer" | "none";
  print?: boolean;
  tilt?: boolean;
  ariaLabel?: string;
  className?: string;
  children?: ReactNode;
}>;

export function tearPoints(teeth: number, depth = 4): string {
  const step = 100 / teeth;
  const points = ["0,0", "100,0"];
  for (let index = teeth; index >= 0; index -= 1) {
    const x = Math.round(index * step * 100) / 100;
    points.push(`${x},${index % 2 === 0 ? depth : 0}`);
  }
  return points.join(" ");
}

export function barWidth(share: number): string {
  const clamped = Math.min(1, Math.max(0, share));
  return `${Math.round(clamped * 1000) / 10}%`;
}

export function Receipt({
  header,
  question,
  figure,
  unit,
  figureLabel,
  rows = [],
  bars = [],
  barsLabel,
  footer = [],
  stamp = "Verified · read-only",
  frame = "none",
  print = true,
  tilt = false,
  ariaLabel = "Answer with its receipt",
  className,
  children,
}: ReceiptProps) {
  let order = 0;
  const next = () => ({ "--i": order++ } as React.CSSProperties);
  const total = rows.length + bars.length + footer.length + (figure ? 1 : 0);
  const classes = [styles.receipt, tilt ? styles.tilt : "", className ?? ""].join(" ").trim();
  return (
    <figure className={classes} aria-label={ariaLabel} data-print={print ? "" : undefined} style={{ "--n": total } as React.CSSProperties}>
      {frame === "printer" ? <div className={styles.slot} aria-hidden="true" /> : null}
      <div className={styles.tape}>
        <div className={styles.paper}>
          {header ? <p className={styles.header}>{header}</p> : null}
          <p className={styles.question}>{question}</p>
          {figure ? (
            <p className={styles.figureLine} style={next()}>
              <span className={styles.figure}>{figure}</span>
              {unit ? <span className={styles.unit}>{unit}</span> : null}
            </p>
          ) : null}
          {figureLabel ? <p className={styles.figureLabel}>{figureLabel}</p> : null}
          {rows.length ? (
            <dl className={styles.rows}>
              {rows.map(row => (
                <div key={row.label} className={row.emphasis ? `${styles.row} ${styles.emphasis}` : styles.row} style={next()}>
                  <dt>{row.label}</dt>
                  <dd>{row.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          {bars.length ? (
            <ul className={styles.bars} aria-label={barsLabel}>
              {bars.map(bar => (
                <li key={bar.label} className={bar.emphasis ? `${styles.bar} ${styles.emphasis}` : styles.bar} style={next()}>
                  <span>{bar.label}</span>
                  <span className={styles.track} aria-hidden="true"><i className={styles.fill} style={{ width: barWidth(bar.share) }} /></span>
                  <span className={styles.barValue}>{bar.value}</span>
                </li>
              ))}
            </ul>
          ) : null}
          {children}
          {footer.length ? (
            <dl className={`${styles.rows} ${styles.footer}`}>
              {footer.map(row => (
                <div key={row.label} className={styles.row} style={next()}>
                  <dt>{row.label}</dt>
                  <dd>{row.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          {stamp ? <Stamp label={stamp} className={styles.stamp} /> : null}
        </div>
        <svg className={styles.tear} viewBox="0 0 100 4" preserveAspectRatio="none" aria-hidden="true" focusable="false">
          <polygon points={tearPoints(24)} />
        </svg>
      </div>
    </figure>
  );
}
