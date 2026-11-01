/* Use case: Single import point for the public-site visual kit.
What it does: Re-exports the receipt, stamp, print/reveal trigger, paper-field helper classes and the pure layout helpers used by the landing, auth and onboarding pages. */

import "./site-tokens.css";

export { Receipt, tearPoints, barWidth } from "./receipt/receipt";
export type { ReceiptProps, ReceiptRow, ReceiptBar } from "./receipt/receipt";
export { Stamp } from "./receipt/stamp";
export type { StampProps } from "./receipt/stamp";
export { PrintReveal } from "./receipt/print-reveal";
export { default as paper } from "./paper-field.module.css";
