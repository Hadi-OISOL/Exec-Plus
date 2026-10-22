/* Use case: Provides optional local password sign-in and workspace registration.
What it does: Signs new accounts straight in, keeps credentials in memory; operator token access exists only in development builds. */

"use client";

import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";
import { signInAccount } from "./account-session";
import styles from "./local-accounts.module.css";

export function AccountAccess({ api, onSession }: { api: string; onSession: (created: boolean, token: string) => Promise<void> }) {
  const id = useId();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [registration, setRegistration] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [reveal, setReveal] = useState(false);
  const creating = mode === "register";

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${api}/auth/options`, { signal: controller.signal, cache: "no-store" })
      .then(response => (response.ok ? response.json() : null))
      .then(value => { if (value && value.local_registration_enabled === false) { setRegistration(false); setMode("login"); } })
      .catch(() => undefined);
    return () => controller.abort();
  }, [api]);

  function choose(next: "login" | "register") {
    setMode(next); setError(""); setReveal(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const password = String(fields.get("password") ?? "");
    if (creating && password !== fields.get("password_confirmation")) {
      setError("The two passwords do not match. Please enter them again.");
      return;
    }
    setBusy(true); setError("");
    try {
      const result = await signInAccount(fetch, api, { email, password }, creating ? { display_name: String(fields.get("display_name") ?? ""), workspace_name: String(fields.get("workspace_name") ?? "") } : undefined);
      if ("error" in result) {
        if (result.registered) choose("login");
        setError(result.error);
        return;
      }
      form.reset();
      await onSession(creating, result.token);
    } catch {
      setError("Account access is unavailable. Check your connection and try again.");
    } finally { setBusy(false); }
  }

  return <section className={styles.access} aria-label="Local account access">
    <h2>{creating ? "Create your workspace" : "Welcome back"}</h2>
    <p className={styles.lead}>{creating ? "Set up a private workspace, then add your first file. It takes about a minute." : "Sign in to return to your data and saved work."}</p>
    {registration && <div className={styles.choices} role="group" aria-label="Account action">
      <button type="button" aria-pressed={!creating} disabled={busy} onClick={() => choose("login")}>Use existing account</button>
      <button type="button" aria-pressed={creating} disabled={busy} onClick={() => choose("register")}>New account</button>
    </div>}
    {error && <p role="alert" id={`${id}-error`} className={styles.error}>{error}</p>}
    <form onSubmit={submit} className={styles.form} aria-busy={busy} aria-describedby={error ? `${id}-error` : undefined} key={mode}>
      <label htmlFor={`${id}-email`}>Account email</label>
      <input id={`${id}-email`} name="email" type="email" autoComplete="username" inputMode="email" maxLength={254} value={email} onChange={event => setEmail(event.target.value)} aria-invalid={Boolean(error) || undefined} required disabled={busy} />
      {creating && <>
        <label htmlFor={`${id}-name`}>Your name</label>
        <input id={`${id}-name`} name="display_name" autoComplete="name" maxLength={100} required disabled={busy} />
        <label htmlFor={`${id}-workspace`}>Workspace name</label>
        <input id={`${id}-workspace`} name="workspace_name" autoComplete="organization" maxLength={100} placeholder="For example, Finance team" required disabled={busy} />
      </>}
      <label htmlFor={`${id}-password`}>Account password</label>
      <div className={styles.passwordField}>
        <input id={`${id}-password`} name="password" type={reveal ? "text" : "password"} autoComplete={creating ? "new-password" : "current-password"} minLength={creating ? 15 : 1} maxLength={128} aria-describedby={`${id}-password-help`} aria-invalid={Boolean(error) || undefined} required disabled={busy} />
        <button type="button" className={styles.reveal} aria-pressed={reveal} aria-controls={`${id}-password`} disabled={busy} onClick={() => setReveal(value => !value)}>{reveal ? "Hide" : "Show"}<span className={styles.visuallyHidden}> password</span></button>
      </div>
      <small id={`${id}-password-help`}>{creating ? "Use 15–128 characters. A long phrase is easier to remember. Paste and password managers are welcome." : "Sessions last up to eight hours. If you lose your password, ask your workspace administrator about recovery."}</small>
      {creating && <><label htmlFor={`${id}-confirmation`}>Confirm account password</label><input id={`${id}-confirmation`} name="password_confirmation" type={reveal ? "text" : "password"} autoComplete="new-password" minLength={15} maxLength={128} required disabled={busy} /></>}
      <button className={styles.submit} disabled={busy}>{busy ? (creating ? "Creating your workspace…" : "Signing in…") : creating ? "Create local account" : "Sign in with password"}</button>
      <small>Your email is an account name; mailbox ownership is not verified and no email is sent.</small>
    </form>
  </section>;
}
