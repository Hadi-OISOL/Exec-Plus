/* Use case: Signs password accounts in, including new accounts straight after registration.
What it does: Runs the register-then-login sequence; the server sets its httpOnly cookie and the token stays in page memory only. */

type Credentials = { email: string; password: string };
export type AccessResult = { signedIn: true; token: string } | { error: string; registered: boolean };

async function post(fetcher: typeof fetch, url: string, body: object): Promise<{ ok: boolean; result: { message?: string; token?: string; error?: { message?: string } } }> {
  const response = await fetcher(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), credentials: "include", cache: "no-store" });
  return { ok: response.ok, result: await response.json().catch(() => ({})) };
}

export async function signInAccount(fetcher: typeof fetch, api: string, credentials: Credentials, registration?: { display_name: string; workspace_name: string }): Promise<AccessResult> {
  const unavailable = "Account access is unavailable. Please try again.";
  if (registration) {
    const created = await post(fetcher, `${api}/auth/register`, { ...credentials, ...registration });
    if (!created.ok) return { error: created.result.error?.message ?? unavailable, registered: false };
  }
  const login = await post(fetcher, `${api}/auth/login`, credentials);
  if (login.ok) return { signedIn: true, token: login.result.token ?? "" };
  const reason = login.result.error?.message ?? unavailable;
  return registration
    ? { error: `We could not sign you in automatically: ${reason} If this email already had an account, sign in with that account's password.`, registered: true }
    : { error: reason, registered: false };
}
