# Local private dashboard host

This example uses an existing shared Syntelio dashboard and its shared studies.
It adds no account, provider or external service. The host receives only a one-use
`epb_` bootstrap secret; the frame keeps its separate short-lived session in memory.

1. Run Syntelio with synthetic/local data. For this local HTTP exercise only, set
   `EXECPLUS_INTEGRATION_ALLOW_LOOPBACK=true` in that isolated process. Keep the
   default false in other environments. No production configuration change is needed.
2. From the repository root, serve just this example:
   `python3 -m http.server 3100 --bind 127.0.0.1 --directory examples/local-embed-host`
3. Open `http://127.0.0.1:3100`. In Syntelio Team & settings → Embed a dashboard,
   choose a shared dashboard and enter that exact host origin. The owner must still
   have access to every source used by every shared study.
4. Copy the local frame address (`http://127.0.0.1:3000/embed/GRANT_ID`, with your
   actual web port) and only the `epb_…` secret from the one-use code into this form.
   Do not paste account sessions or API keys. Open it within five minutes.
5. The dashboard checks the host and current permissions, and works for at most
   fifteen minutes. Revoke the view in Syntelio and use **Refresh access & results**
   inside the frame to confirm access is withdrawn. **Clear view** removes it here.

The sample permits only loopback Syntelio addresses with no query, fragment or
embedded credentials. It validates the message source, exact origin and grant ID,
then transfers the bootstrap once. It writes no browser storage, makes no fetch
calls, and clears the password input immediately. Reloading needs a new bootstrap.
The iframe cannot download exports or inherit broad account/API authority.

This proves a local host workflow only. Real HTTPS hosting, production domain
allowlisting and independent deployment/security review remain separate gates.
