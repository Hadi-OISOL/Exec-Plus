/* Use case: Gives workspace owners explicit control over private integrations.
What it does: Creates narrowly scoped keys, one-use embedded views and approved webhooks while showing secrets only in the current screen. */

import { useCallback, useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import styles from "./integrations-panel.module.css";

type Key = { id: string; name: string; operations: string[]; expires_at: string; revoked_at: string | null };
type Grant = { id: string; host_origin: string; expires_at: string; session_expires_at: string | null; revoked_at: string | null };
type Subscription = { id: string; destination: string; event_types: string[]; revoked_at: string | null };
type HookState = { subscriptions: Subscription[]; enabled: boolean; allowed_origins: string[]; capacity_limited: boolean; last_failure: string | null };
type Catalog = { datasets: { id: string; name: string }[] };
type Board = { id: string; name: string; shared: boolean; pins: string[] };
const operationLabels = [["profile:read", "Read file structure"], ["rows:read", "Read allowed rows"], ["query:read", "Calculate confirmed measures"], ["boards:read", "Read shared dashboards"], ["studies:read", "Read saved studies"], ["forecasts:read", "Read my saved forecasts"], ["analyses:read", "Read my saved analyses"], ["jobs:read", "Read my request status"]];
const eventLabels = [["job.succeeded", "My completed questions"], ["job.failed", "My failed questions"], ["refresh.accepted", "My accepted refreshes"]];
const timestamp = (value: string) => `${value.slice(0, 19).replace("T", " ")} UTC`;

export function IntegrationsPanel({ workspaceId, request }: { workspaceId: string; request: ApiRequest }) {
  const root = `/workspaces/${workspaceId}`;
  const [keys, setKeys] = useState<Key[]>([]);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [hooks, setHooks] = useState<HookState | null>(null);
  const [datasets, setDatasets] = useState<Catalog["datasets"]>([]);
  const [boards, setBoards] = useState<Board[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [additionalDatasets, setAdditionalDatasets] = useState<string[]>([]);
  const [boardId, setBoardId] = useState("");
  const [tab, setTab] = useState("keys");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [secret, setSecret] = useState<{ label: string; value: string } | null>(null);
  const [deliveries, setDeliveries] = useState<{ event: { id: string; kind: string }; status: string; attempts: number; last_status: number | null }[] | null>(null);
  const read = useCallback((signal?: AbortSignal) => Promise.all([
    request<Key[]>(`${root}/integrations/keys`, { signal }), request<Grant[]>(`${root}/integrations/embeds`, { signal }),
    request<HookState>(`${root}/integrations/webhooks`, { signal }), request<Catalog>(`${root}/dataset-access`, { signal }),
    request<Board[]>(`${root}/study-boards`, { signal }),
  ]), [root, request]);
  const accept = useCallback((values: [Key[], Grant[], HookState, Catalog, Board[]]) => {
    setKeys(values[0]); setGrants(values[1]); setHooks(values[2]); setDatasets(values[3].datasets);
    setBoards(values[4].filter(value => value.shared && value.pins.length));
  }, []);
  const clear = useCallback(() => {
    setKeys([]); setGrants([]); setHooks(null); setDatasets([]); setBoards([]);
    setSecret(null); setDeliveries(null); setDatasetId(""); setBoardId(""); setAdditionalDatasets([]);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    read(controller.signal).then(values => { if (!controller.signal.aborted) accept(values); })
      .catch(cause => { if (!controller.signal.aborted) { clear(); setError(cause instanceof Error ? cause.message : "Integration settings could not load."); } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [read, accept, clear]);
  async function action(work: () => Promise<void>) {
    setBusy(true); setError("");
    let completed = false;
    try { await work(); completed = true; accept(await read()); }
    catch (cause) {
      clear();
      const detail = cause instanceof Error ? cause.message : "Please try again.";
      setError(completed ? `The action completed, but the updated list could not load. ${detail}` : detail);
    }
    finally { setBusy(false); }
  }
  const dataPicker = <label>Integration dataset<select value={datasetId} onChange={event => setDatasetId(event.target.value)} required disabled={busy}><option value="">Choose a dataset</option>{datasets.map(value => <option value={value.id} key={value.id}>{value.name}</option>)}</select></label>;
  return <section className={`panel ${styles.panel}`} aria-label="Private integrations">
    <header><p className="studioEyebrow">WORKSPACE OWNER</p><h2>Connect your own tools</h2><p>Choose exactly what another tool can read. Saved row and field permissions still apply.</p></header>
    <div className={styles.tabs} role="group" aria-label="Integration type">{[["keys", "Read-only API"], ["embeds", "Embed a dashboard"], ["hooks", "Notifications"]].map(([id, label]) => <button key={id} aria-pressed={tab === id} disabled={busy} onClick={() => { setTab(id); setSecret(null); setDeliveries(null); }}>{label}</button>)}</div>
    {loading && <p role="status">Loading private integration settings…</p>}
    {error && <p role="alert" className="errorNotice">{error}</p>}
    {!loading && error && <button disabled={busy} onClick={() => void action(async () => undefined)}>Reload integrations</button>}
    {secret && <aside className={styles.secret} aria-label="New integration secret"><h3>{secret.label}</h3><p>Save this now. It is only shown here, and disappears when you leave or dismiss it. Keep it out of URLs and public source code.</p><textarea aria-label={secret.label} value={secret.value} readOnly rows={secret.value.includes("\n") ? 10 : 3} spellCheck={false} /><button onClick={() => setSecret(null)}>I saved it — hide secret</button></aside>}
    {!loading && tab === "keys" && <><form className={styles.form} onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); void action(async () => { const value = await request<{ secret: string }>(`${root}/integrations/keys`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: data.get("name"), dataset_ids: [...new Set([datasetId, ...additionalDatasets])], operations: data.getAll("operation"), expires_seconds: Number(data.get("expiry")) }) }); setSecret({ label: "New read-only API key", value: value.secret }); }); }}>
      <h3>A key for selected datasets</h3><p>Keys use only your signed-in account and its current access. They cannot act as another member. They expire automatically and can be revoked at any time. Limit: 60 requests per minute.</p>
      <label>Key name<input name="name" required maxLength={100} disabled={busy} placeholder="My reporting tool" /></label>{dataPicker}
      {datasets.length > 1 && <details><summary>Include other datasets used by this result</summary><p>A comparison or dashboard needs permission to every source it uses. Choose up to 20 datasets in total.</p><fieldset disabled={busy}><legend>Additional datasets</legend>{datasets.filter(value => value.id !== datasetId).map(value => <label className={styles.check} key={value.id}><input type="checkbox" checked={additionalDatasets.includes(value.id)} disabled={!additionalDatasets.includes(value.id) && additionalDatasets.length >= 19} onChange={event => setAdditionalDatasets(previous => event.target.checked ? [...previous, value.id] : previous.filter(id => id !== value.id))} />{value.name}</label>)}</fieldset></details>}
      <fieldset disabled={busy}><legend>Allow this tool to</legend>{operationLabels.map(([id, label]) => <label className={styles.check} key={id}><input name="operation" type="checkbox" value={id} defaultChecked={id === "profile:read"} />{label}</label>)}</fieldset>
      <label>Key lifetime<select name="expiry" disabled={busy}><option value="86400">1 day</option><option value="604800">7 days</option><option value="2592000">30 days</option></select></label><button disabled={busy || !datasetId}>Create read-only key</button>
    </form><div className={styles.items}>{keys.map(value => <article key={value.id}><div><h3>{value.name}</h3><p>{value.revoked_at ? "Revoked" : `Expires ${timestamp(value.expires_at)}`}</p><p>{value.operations.map(op => operationLabels.find(item => item[0] === op)?.[1] ?? op).join(" · ")}</p></div>{!value.revoked_at && <button disabled={busy} onClick={() => void action(async () => { await request(`${root}/integrations/keys/${value.id}`, { method: "DELETE" }); })}>Revoke key</button>}</article>)}</div></>}
    {!loading && tab === "embeds" && <><form className={styles.form} onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); void action(async () => {
      const value = await request<{ bootstrap_secret: string; grant: Grant }>(`${root}/integrations/embeds`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ board_id: boardId, host_origin: data.get("origin") }) });
      const frameUrl = `${window.location.origin}/embed/${value.grant.id}`;
      const snippet = `<iframe id="execplus-board" src="${frameUrl}" title="Private Syntelio dashboard" style="width:100%;height:800px;border:0"></iframe>\n<script>\nconst frame = document.getElementById("execplus-board");\nwindow.addEventListener("message", event => {\n  if (event.source !== frame.contentWindow || event.origin !== ${JSON.stringify(window.location.origin)} || event.data?.type !== "execplus:ready" || event.data.grantId !== ${JSON.stringify(value.grant.id)}) return;\n  frame.contentWindow.postMessage({ type: "execplus:open", grantId: ${JSON.stringify(value.grant.id)}, secret: ${JSON.stringify(value.bootstrap_secret)} }, ${JSON.stringify(window.location.origin)});\n});\n</script>`;
      setSecret({ label: "One-use private embed code", value: snippet });
    }); }}><h3>Share a private dashboard view</h3><p>The chosen dashboard and all its studies must be shared in this workspace. The code opens once within 5 minutes, then works for 15 minutes. Changing sharing or permissions can stop access.</p>
      <label>Shared dashboard<select required disabled={busy} value={boardId} onChange={event => setBoardId(event.target.value)}><option value="">Choose a shared dashboard</option>{boards.map(value => <option value={value.id} key={value.id}>{value.name}</option>)}</select></label>
      {!boards.length && <p>Create a shared dashboard with shared studies in Saved work first.</p>}
      <label>Approved host origin<input name="origin" type="url" required placeholder="https://your-site.example" disabled={busy} /><span>The exact site origin, without a page path or wildcard.</span></label><button disabled={busy || !boardId}>Create private embed</button>
    </form><div className={styles.items}>{grants.map(value => <article key={value.id}><div><h3>{value.host_origin}</h3><p>{value.revoked_at ? "Revoked" : `Expires ${timestamp(value.session_expires_at ?? value.expires_at)}`}</p></div>{!value.revoked_at && <button disabled={busy} onClick={() => void action(async () => { await request(`${root}/integrations/embeds/${value.id}`, { method: "DELETE" }); })}>Revoke embedded view</button>}</article>)}</div></>}
    {!loading && tab === "hooks" && <><div className={styles.notice}><h3>Signed notifications</h3><p>Send a small status message when your question finishes or your refresh is accepted. Messages contain IDs and status, never answers or file contents.</p><p>Delivery can retry up to 6 times. Receivers must verify the signature and ignore repeated event IDs.</p>{!hooks?.enabled && <p>An operator must configure an approved receiver and protected signing key before delivery can be enabled.</p>}{hooks?.last_failure && <p role="status">The delivery worker last reported a problem at {timestamp(hooks.last_failure)}. Pending events can retry.</p>}{hooks?.capacity_limited && <p role="status">The notification queue is full. Ask an operator to review delivery.</p>}</div>
      {hooks?.enabled && <form className={styles.form} onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); void action(async () => { const value = await request<{ signing_secret: string }>(`${root}/integrations/webhooks`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dataset_ids: [datasetId], event_types: data.getAll("event"), destination: data.get("destination") }) }); setSecret({ label: "Webhook signing secret (hex)", value: value.signing_secret }); }); }}>{dataPicker}<label>Approved receiver URL<input name="destination" type="url" required disabled={busy} /></label><p>Approved origins: {hooks.allowed_origins.join(", ")}</p><fieldset disabled={busy}><legend>Notify me about</legend>{eventLabels.map(([id, label]) => <label className={styles.check} key={id}><input name="event" type="checkbox" value={id} defaultChecked={id === "job.succeeded"} />{label}</label>)}</fieldset><button disabled={busy || !datasetId}>Create notification</button></form>}
      <div className={styles.items}>{hooks?.subscriptions.map(value => <article key={value.id}><div><h3>{value.destination}</h3><p>{value.revoked_at ? "Revoked" : value.event_types.join(" · ")}</p></div><div className={styles.actions}><button disabled={busy} onClick={() => void action(async () => { setDeliveries(await request(`${root}/integrations/webhooks/${value.id}/deliveries`)); })}>View recent deliveries</button>{!value.revoked_at && <><button disabled={busy || !hooks.enabled} onClick={() => void action(async () => { const result = await request<{ signing_secret: string }>(`${root}/integrations/webhooks/${value.id}/rotate`, { method: "POST" }); setSecret({ label: "Replacement signing secret (hex)", value: result.signing_secret }); })}>Replace signing secret</button><button disabled={busy} onClick={() => void action(async () => { await request(`${root}/integrations/webhooks/${value.id}`, { method: "DELETE" }); })}>Revoke notification</button></>}</div></article>)}</div>
      {deliveries && <div className={styles.deliveries}><h3>Recent delivery attempts</h3>{!deliveries.length && <p>No matching events have been collected yet.</p>}{deliveries.map(value => <p key={value.event.id}>{value.event.kind} · {value.status} · {value.attempts} attempts{value.last_status ? ` · HTTP ${value.last_status}` : ""}</p>)}</div>}
    </>}
  </section>;
}
