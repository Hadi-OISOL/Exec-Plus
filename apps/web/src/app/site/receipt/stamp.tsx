/* Use case: The "VERIFIED · READ-ONLY" stamp pressed onto receipts and evidence cards.
What it does: Renders an ink-outlined, slightly rotated stamp whose text is the caller's exact label; the landing spring lives in CSS and only runs when motion is allowed. */

import styles from "./receipt.module.css";

export type StampProps = Readonly<{ label?: string; tone?: "ink" | "saffron"; className?: string }>;

export function Stamp({ label = "Verified · read-only", tone = "ink", className }: StampProps) {
  const classes = [styles.stampBase, tone === "saffron" ? styles.stampSaffron : "", className ?? ""].join(" ").trim();
  return <span className={classes}>{label}</span>;
}
