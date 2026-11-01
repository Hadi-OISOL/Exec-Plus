/* Use case: The pricing section of the public website.
What it does: Prints the Free, Pro and Team plans from the shared plan catalog as three receipts torn from one roll, each with its price, headline, allowance rows and a sign-up action, followed by the Enterprise line and the placeholder-price note. */

import Link from "next/link";
import styles from "../page.module.css";
import { Receipt } from "./kit";
import { PLANS } from "./plans";

const printed = PLANS.filter(plan => plan.priceUsdMonth !== null);
const enterprise = PLANS.find(plan => plan.priceUsdMonth === null);

export function Pricing() {
  return <>
    <div className={styles.roll} aria-hidden="true" />
    <ul className={styles.plans}>
      {printed.map((plan, index) => (
        <li key={plan.key} className={styles.plan} style={{ "--i": index } as React.CSSProperties}>
          <Receipt
            question={plan.name}
            figure={plan.priceUsdMonth === 0 ? "$0" : `$${plan.priceUsdMonth}`}
            unit={plan.priceUsdMonth === 0 ? "forever" : "a month"}
            figureLabel={plan.headline}
            rows={Object.values(plan.limits).map(limit => ({ label: limit.replace(/^[\d,]+\s*(MiB|GiB)?\s*/, "").replace(/^./, first => first.toUpperCase()), value: limit.match(/^[\d,]+(\s*(MiB|GiB))?/)?.[0] ?? limit }))}
            stamp={plan.priceUsdMonth === 0 ? "No card needed" : "Placeholder price"}
            ariaLabel={`${plan.name} plan`}
          >
            <Link href="/signup" className={`${styles.button} ${styles.planButton}`}>Create account</Link>
          </Receipt>
        </li>
      ))}
    </ul>
    {enterprise ? <p className={styles.enterprise}><b>{enterprise.name}.</b> {enterprise.headline} Create an account and write to us from your workspace. <Link href="/signup">Create account</Link></p> : null}
  </>;
}
