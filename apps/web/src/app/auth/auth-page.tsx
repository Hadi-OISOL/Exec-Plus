/* Use case: Standalone sign-in, sign-up and reset pages outside the workspace shell.
What it does: Places the shared account form on the left under the brand, a navy panel with a real verified answer on the right, and, once the API has set its session cookie, sends the browser to the workspace. */

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Shot } from "../site/shot";
import { AuthForm } from "./auth-form";
import type { AuthMode } from "./auth-form";
import styles from "./auth.module.css";

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function AuthPage({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  return <main className={styles.page}>
    <div className={styles.side}>
      <Link className={styles.brand} href="/" aria-label="Syntelio home"><span className={styles.mark} aria-hidden="true">S</span>Syntelio</Link>
      <div className={styles.card}>
        <AuthForm mode={mode} api={api} onSession={async () => router.push("/workspace")} />
      </div>
      <p className={styles.foot}><span>© {new Date().getFullYear()} Syntelio</span><Link href="/">Home</Link><Link href="/#defend">Security &amp; privacy</Link></p>
    </div>
    <aside className={styles.panel} aria-label="What Syntelio does">
      <h2>Every answer shows its working.</h2>
      <Shot className={styles.shotFrame} name="stage-ask" alt="A verified Syntelio answer for average rainfall by region, with its chart controls" width={550} height={370} />
      <p>A real answer from the 100-row sample file. The query engine computed it; the model only worded it. Ask in English, Urdu or Roman Urdu.</p>
    </aside>
  </main>;
}
