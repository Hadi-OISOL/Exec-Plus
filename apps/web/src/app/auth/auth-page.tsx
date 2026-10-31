/* Use case: Standalone sign-in, sign-up and reset pages outside the workspace shell.
What it does: Centers the shared account form under the brand and, once the API has set its session cookie, sends the browser to the workspace. */

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthForm } from "./auth-form";
import type { AuthMode } from "./auth-form";
import styles from "./auth.module.css";

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function AuthPage({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  return <main className={styles.page}>
    <Link className={styles.brand} href="/" aria-label="Syntelio home"><span className={styles.mark} aria-hidden="true">S</span>Syntelio</Link>
    <div className={styles.card}>
      <AuthForm mode={mode} api={api} onSession={async () => router.push("/workspace")} />
    </div>
    <p className={styles.foot}>© {new Date().getFullYear()} Syntelio <Link href="/">Home</Link><Link href="/#security">Security &amp; privacy</Link></p>
  </main>;
}
