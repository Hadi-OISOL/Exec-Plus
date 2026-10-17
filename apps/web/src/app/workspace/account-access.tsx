/* Use case: Provides optional local password sign-in and workspace registration.
What it does: Keeps credentials in memory and leaves operator token access available. */

"use client";

import { useId, useState } from "react";
import type { FormEvent } from "react";
import styles from "./local-accounts.module.css";

export function AccountAccess({ api, onSession }: { api: string; onSession: (token: string) => Promise<void> }) {
  const id = useId();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    if (mode === "register" && fields.get("password") !== fields.get("password_confirmation")) {
      setError("The two passwords do not match. Please enter them again.");
      return;
    }
    const body = mode === "register"
      ? { email: fields.get("email"), password: fields.get("password"), display_name: fields.get("display_name"), workspace_name: fields.get("workspace_name") }
      : { email: fields.get("email"), password: fields.get("password") };
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}/auth/${mode}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), credentials: "omit", cache: "no-store" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error?.message ?? "Account access is unavailable. Please try again.");
      form.reset();
      if (mode === "register") {
        setMode("login");
        setMessage(result.message);
      } else await onSession(result.token);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Account access is unavailable. Please try again.");
    } finally { setBusy(false); }
  }

  return <section className={styles.access} aria-label="Local account access">
    <h3>Your local account</h3>
    <p>Create a private workspace or return to your work. Your email is an account name; mailbox ownership is not verified.</p>
    <div className={styles.choices} aria-label="Account action">
      <button type="button" aria-pressed={mode === "login"} disabled={busy} onClick={() => { setMode("login"); setError(""); }}>Use existing account</button>
      <button type="button" aria-pressed={mode === "register"} disabled={busy} onClick={() => { setMode("register"); setError(""); }}>New account</button>
    </div>
    {message && <p role="status">{message}</p>}
    {error && <p role="alert">{error}</p>}
    <form onSubmit={submit} className={styles.form} aria-busy={busy} key={mode}>
      <label htmlFor={`${id}-email`}>Account email</label>
      <input id={`${id}-email`} name="email" type="email" autoComplete="username" maxLength={254} value={email} onChange={event => setEmail(event.target.value)} required disabled={busy} />
      {mode === "register" && <>
        <label htmlFor={`${id}-name`}>Your name</label>
        <input id={`${id}-name`} name="display_name" autoComplete="name" maxLength={100} required disabled={busy} />
        <label htmlFor={`${id}-workspace`}>Workspace name</label>
        <input id={`${id}-workspace`} name="workspace_name" autoComplete="organization" maxLength={100} required disabled={busy} />
      </>}
      <label htmlFor={`${id}-password`}>Account password</label>
      <input id={`${id}-password`} name="password" type="password" autoComplete={mode === "register" ? "new-password" : "current-password"} minLength={mode === "register" ? 15 : 1} maxLength={128} aria-describedby={`${id}-password-help`} required disabled={busy} />
      <small id={`${id}-password-help`}>{mode === "register" ? "Use 15–128 characters. A long phrase is easier to remember. Paste and password managers are welcome." : "Sessions last up to eight hours. Ask your local operator about recovery if you lose your password."}</small>
      {mode === "register" && <><label htmlFor={`${id}-confirmation`}>Confirm account password</label><input id={`${id}-confirmation`} name="password_confirmation" type="password" autoComplete="new-password" minLength={15} maxLength={128} required disabled={busy} /></>}
      <button disabled={busy}>{busy ? "Working…" : mode === "register" ? "Create local account" : "Sign in with password"}</button>
    </form>
  </section>;
}
