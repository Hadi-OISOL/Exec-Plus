/* Use case: One password sign-in, sign-up and reset-code form shared by /login, /signup, /reset and the signed-out workspace.
What it does: Shows Google sign-in when the API enables it, signs new accounts straight in, keeps credentials in memory and either switches mode in place or links between the auth pages. */

"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";
import { resetAccountPassword, signInAccount } from "../workspace/account-session";
import styles from "./auth.module.css";

export type AuthMode = "login" | "register" | "reset";
type Props = { mode: AuthMode; api: string; onSession: (created: boolean, token: string) => Promise<void>; switchMode?: (mode: AuthMode) => void };

const titles: Record<AuthMode, [string, string]> = {
  login: ["Welcome back", "Sign in to return to your data and saved work."],
  register: ["Create your Syntelio account", "Set up a private workspace, then add your first file. It takes about a minute."],
  reset: ["Reset your password", "Enter the one-time code your administrator gave you after checking it is really you. Codes expire after 30 minutes."],
};

export function GoogleMark() {
  return <svg aria-hidden="true" width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>;
}

export function AuthForm({ mode, api, onSession, switchMode }: Props) {
  const id = useId();
  const [registration, setRegistration] = useState(true);
  const [google, setGoogle] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [reveal, setReveal] = useState(false);
  const creating = mode === "register";
  const resetting = mode === "reset";
  const choosing = creating || resetting;
  const [title, lead] = titles[mode];

  useEffect(() => {
    const controller = new AbortController();
    const read = (path: string) => fetch(`${api}${path}`, { signal: controller.signal, cache: "no-store" }).then(response => (response.ok ? response.json() : null)).catch(() => null);
    read("/auth/options").then(value => { if (value && value.local_registration_enabled === false) setRegistration(false); });
    read("/auth/google/config").then(value => setGoogle(Boolean(value?.enabled)));
    return () => controller.abort();
  }, [api]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const password = String(fields.get("password") ?? "");
    if (choosing && password !== fields.get("password_confirmation")) {
      setError("The two passwords do not match. Please enter them again.");
      return;
    }
    setBusy(true); setError("");
    try {
      if (resetting) {
        const failure = await resetAccountPassword(fetch, api, { email, code: String(fields.get("code") ?? "").trim(), new_password: password });
        if (failure) { setError(failure); return; }
      }
      const result = await signInAccount(fetch, api, { email, password }, creating ? { display_name: String(fields.get("display_name") ?? ""), workspace_name: String(fields.get("workspace_name") ?? "") } : undefined);
      if ("error" in result) {
        if (result.registered) switchMode?.("login");
        setError(result.error);
        return;
      }
      form.reset();
      await onSession(creating, result.token);
    } catch {
      setError("Account access is unavailable. Check your connection and try again.");
    } finally { setBusy(false); }
  }

  function alt(to: AuthMode, button: string, link: string) {
    if (switchMode) return <button type="button" className={styles.link} disabled={busy} onClick={() => { setError(""); setReveal(false); switchMode(to); }}>{button}</button>;
    return <Link className={styles.link} href={to === "login" ? "/login" : to === "register" ? "/signup" : "/reset"}>{link}</Link>;
  }

  return <section className={styles.access} aria-label="Local account access">
    <h1 className={styles.title}>{title}</h1>
    <p className={styles.lead}>{lead}</p>
    {google && !resetting && <>
      <form method="get" action={`${api}/auth/google/start`}>
        <button type="submit" className={styles.google} disabled={busy}><GoogleMark />Continue with Google</button>
      </form>
      <p className={styles.divider} role="separator" aria-label="or"><span>or</span></p>
    </>}
    {error && <p role="alert" id={`${id}-error`} className={styles.error}>{error}</p>}
    <form onSubmit={submit} className={styles.form} aria-busy={busy} aria-describedby={error ? `${id}-error` : undefined} key={mode}>
      {creating && <>
        <label htmlFor={`${id}-name`}>Your name</label>
        <input id={`${id}-name`} name="display_name" autoComplete="name" maxLength={100} required disabled={busy} />
      </>}
      <label htmlFor={`${id}-email`}>Account email</label>
      <input id={`${id}-email`} name="email" type="email" autoComplete="username" inputMode="email" maxLength={254} value={email} onChange={event => setEmail(event.target.value)} aria-invalid={Boolean(error) || undefined} required disabled={busy} />
      {creating && <>
        <label htmlFor={`${id}-workspace`}>Company or workspace name</label>
        <input id={`${id}-workspace`} name="workspace_name" autoComplete="organization" maxLength={100} placeholder="For example, Finance team" required disabled={busy} />
      </>}
      {resetting && <><label htmlFor={`${id}-code`}>One-time reset code</label><input id={`${id}-code`} name="code" autoComplete="one-time-code" maxLength={64} required disabled={busy} /></>}
      <div className={styles.labelRow}>
        <label htmlFor={`${id}-password`}>{resetting ? "New account password" : "Account password"}</label>
        {mode === "login" && alt("reset", "Have a reset code?", "Forgot password? Use a reset code")}
      </div>
      <div className={styles.passwordField}>
        <input id={`${id}-password`} name="password" type={reveal ? "text" : "password"} autoComplete={choosing ? "new-password" : "current-password"} minLength={choosing ? 15 : 1} maxLength={128} aria-describedby={`${id}-password-help`} aria-invalid={Boolean(error) || undefined} required disabled={busy} />
        <button type="button" className={styles.reveal} aria-pressed={reveal} aria-controls={`${id}-password`} disabled={busy} onClick={() => setReveal(value => !value)}>{reveal ? "Hide" : "Show"}<span className="srOnly"> password</span></button>
      </div>
      <small id={`${id}-password-help`}>{choosing ? "Use 15–128 characters. A long phrase is easier to remember; password managers are welcome." : "Sessions last up to eight hours."}</small>
      {choosing && <><label htmlFor={`${id}-confirmation`}>Confirm account password</label><input id={`${id}-confirmation`} name="password_confirmation" type={reveal ? "text" : "password"} autoComplete="new-password" minLength={15} maxLength={128} required disabled={busy} /></>}
      <button className={styles.submit} disabled={busy}>{busy ? (creating ? "Creating your workspace…" : resetting ? "Resetting…" : "Signing in…") : creating ? "Create account" : resetting ? "Reset password and sign in" : "Sign in with password"}</button>
    </form>
    <p className={styles.alt}>
      {mode === "login" && registration && <>New to Syntelio? {alt("register", "New account", "Create account")}</>}
      {creating && <>Already have an account? {alt("login", "Use existing account", "Log in")}</>}
      {resetting && alt("login", "Back to sign in", "Back to log in")}
    </p>
    <p className={styles.privacy}>Your email is your account name. We do not verify the mailbox or send email.</p>
  </section>;
}
