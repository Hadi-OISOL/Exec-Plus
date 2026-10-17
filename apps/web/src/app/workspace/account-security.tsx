/* Use case: Gives the current person control of local account credentials.
What it does: Displays a shareable account ID and requires password proof for security changes. */

"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import styles from "./local-accounts.module.css";

type Account = { user_id: string; kind: "local_password" | "operator"; email_verified: boolean; password_changed_at: string | null };
type AccountEvent = { id: string; action: string; created_at: string };

export function AccountSecurity({ request, onSession, onDisabled }: { request: ApiRequest; onSession: (token: string) => void; onDisabled: () => void }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [events, setEvents] = useState<AccountEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([request<Account>("/auth/account", { signal: controller.signal }), request<{ events: AccountEvent[] }>("/auth/account/events", { signal: controller.signal })]).then(([value, history]) => {
      if (!controller.signal.aborted) { setAccount(value); setEvents(history.events); setError(""); }
    }).catch(cause => { if (!controller.signal.aborted) { setAccount(null); setEvents([]); setError(cause instanceof Error ? cause.message : "Could not load account settings."); } });
    return () => controller.abort();
  }, [request]);

  async function change(event: FormEvent<HTMLFormElement>, disable: boolean) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    if (!disable && fields.get("new_password") !== fields.get("new_password_confirmation")) {
      setError("The two new passwords do not match. Please enter them again.");
      return;
    }
    setBusy(true); setError(""); setMessage("");
    try {
      const body = disable
        ? { password: fields.get("password"), confirmed: fields.get("confirmed") === "on" }
        : { current_password: fields.get("current_password"), new_password: fields.get("new_password") };
      const value = await request<{ token: string } | undefined>(disable ? "/auth/disable" : "/auth/password", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      form.reset();
      if (disable) onDisabled();
      else if (value) { onSession(value.token); setMessage("Password changed. Your other sessions and issued access keys were revoked. This session is ready."); }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update the account."); }
    finally { setBusy(false); }
  }

  return <section className={`panel ${styles.security}`} aria-label="Your account settings">
    <h2>Your account</h2>
    {error && <p role="alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    {!account && !error && <p role="status">Loading your account…</p>}
    {account && <>
      <p>Your account ID: <code className={styles.identifier}>{account.user_id}</code></p>
      <p>Share this ID with your workspace manager when they check an invitation. An email address alone does not prove account ownership.</p>
      {account.kind === "operator" ? <p>Your access is managed by the local operator. Password controls apply to local password accounts.</p> : <>
        <details><summary>Change your password</summary>
          <form className={styles.form} onSubmit={event => void change(event, false)}>
            <label>Current password<input type="password" name="current_password" autoComplete="current-password" maxLength={128} required disabled={busy} /></label>
            <label>New password<input type="password" name="new_password" autoComplete="new-password" minLength={15} maxLength={128} required disabled={busy} /></label>
            <label>Confirm new password<input type="password" name="new_password_confirmation" autoComplete="new-password" minLength={15} maxLength={128} required disabled={busy} /></label>
            <small>Use 15–128 characters. This also revokes your other sessions, customer API keys and embedded access.</small>
            <button disabled={busy}>Change password</button>
          </form>
        </details>
        <details><summary>Disable your account</summary>
          <p>This stops your access and revokes your sessions and issued keys. Your workspace data and history stay saved. A local operator must check account control before recovery.</p>
          <form className={styles.form} onSubmit={event => void change(event, true)}>
            <label>Password to disable account<input type="password" name="password" autoComplete="current-password" maxLength={128} required disabled={busy} /></label>
            <label className={styles.checkbox}><input type="checkbox" name="confirmed" required disabled={busy} /> I understand that I will be signed out and will need operator help to restore access.</label>
            <button disabled={busy}>Disable my account</button>
          </form>
        </details>
        <details><summary>Recent account activity</summary><ul>{events.map(event => <li key={event.id}>{event.action.replaceAll(".", " ")} · {new Date(event.created_at).toLocaleString()}</li>)}</ul></details>
      </>}
    </>}
  </section>;
}

export function InvitationIdentityApproval({ request, workspaceId, invitationId, email }: { request: ApiRequest; workspaceId: string; invitationId: string; email: string }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    setBusy(true); setMessage(""); setError("");
    try {
      await request(`/workspaces/${workspaceId}/invitations/${invitationId}/identity-approval`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ account_id: fields.get("account_id"), identity_checked: fields.get("checked") === "on" }) });
      setMessage("Account approved for this invitation. Your teammate can now accept the invitation link.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not approve this account."); }
    finally { setBusy(false); }
  }
  return <details><summary>Check the local account for {email}</summary>
    <p>Ask your teammate for their account ID from Team &amp; settings. Check it with the intended person before approving. This does not verify their mailbox.</p>
    <form onSubmit={submit} className={styles.form}>
      <label>Invited account ID<input name="account_id" required maxLength={36} disabled={busy} /></label>
      <label className={styles.checkbox}><input type="checkbox" name="checked" required disabled={busy} /> I checked this exact account ID with the intended teammate.</label>
      <button disabled={busy}>Approve account for {email}</button>
      {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
    </form>
  </details>;
}
