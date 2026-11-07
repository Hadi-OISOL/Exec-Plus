/* Use case: Standalone sign-in, sign-up and reset pages outside the workspace shell.
What it does: Splits the screen into a paper form column under the wordmark and a green field that prints the shared kit receipt for one real answer from the sample file; once the API has set its session cookie, it sends the browser to the workspace. */

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthForm } from "./auth-form";
import type { AuthMode } from "./auth-form";
import { PrintReveal, Receipt } from "@/app/site/kit";
import styles from "./auth.module.css";

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const rainfall = [{ label: "West", value: "1744.51", share: 1, emphasis: true }, { label: "North", value: "1599.96", share: 1599.96 / 1744.51 }, { label: "South", value: "1567.74", share: 1567.74 / 1744.51 }, { label: "Central", value: "1562.96", share: 1562.96 / 1744.51 }, { label: "East", value: "1310.04", share: 1310.04 / 1744.51 }];

export function AuthPage({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  return <main className={styles.page}>
    <div className={styles.side}>
      <Link className={styles.brand} href="/" aria-label="Osalytix home"><span className={styles.mark} aria-hidden="true">O</span>Osalytix</Link>
      <div className={styles.card}>
        <AuthForm mode={mode} api={api} onSession={async () => router.push("/workspace")} />
      </div>
      <p className={styles.foot}><span>© {new Date().getFullYear()} Osalytix</span><Link href="/">Home</Link><Link href="/#defend">Security &amp; privacy</Link></p>
    </div>
    <aside className={styles.panel} aria-label="What Osalytix does">
      <p className={styles.claim}>Every number comes with a <em>receipt.</em></p>
      <div className={styles.printer}>
        <Receipt header="test_100rows.csv · 100 rows · 20 columns" question="Which region had the most rainfall on average?" figure="1,744.5" unit="mm" figureLabel="West, average Rainfall_mm" bars={rainfall} barsLabel="Average rainfall by region, millimetres" footer={[{ label: "Query", value: "AVG(Rainfall_mm) GROUP BY Region" }, { label: "Access", value: "read-only · replayable" }]} stamp="Verified · replayable" frame="printer" print />
      </div>
      <PrintReveal />
    </aside>
  </main>;
}
