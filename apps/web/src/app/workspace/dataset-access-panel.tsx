/* Use case: Lets workspace owners choose who may use each dataset.
What it does: Edits explicit row and field grants with versioned saves and clear draft recovery. */

import { useCallback, useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import styles from "./dataset-access-panel.module.css";

type Condition = { column: string; operator: string; value: string };
type Grant = { user_id: string; columns: string[] | null; conditions: Condition[] };
type Policy = {
  version: number;
  enabled: boolean;
  grants: Grant[];
  columns: { name: string; type: string }[];
  members: { user_id: string; role: string; display_name: string }[];
};
type Dataset = { id: string; name: string };
const operators = [
  ["eq", "equals"], ["ne", "does not equal"], ["lt", "is less than"],
  ["lte", "is at most"], ["gt", "is greater than"], ["gte", "is at least"],
];

export function DatasetAccessPanel({ workspaceId, request }: { workspaceId: string; request: ApiRequest }) {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [catalogError, setCatalogError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    request<{ datasets: Dataset[] }>(`/workspaces/${workspaceId}/dataset-access`, { signal: controller.signal })
      .then(({ datasets: values }) => {
        if (controller.signal.aborted) return;
        setDatasets(values);
        setDatasetId(current => values.some(value => value.id === current) ? current : "");
      }).catch(cause => {
        if (!controller.signal.aborted) setCatalogError(cause instanceof Error ? cause.message : "Could not load your datasets.");
      }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [workspaceId, request, reload]);
  return <section className={`panel ${styles.panel}`} aria-label="Dataset access settings">
    <div className={styles.heading}><span className="studioEyebrow">WORKSPACE OWNER</span><h2>Who can use this data?</h2></div>
    <p>Choose a dataset, then give each person the rows and fields they need. Changes take effect only when you save.</p>
    {catalogError && <div role="alert"><p>{catalogError}</p><button type="button" onClick={() => { setLoading(true); setCatalogError(""); setReload(value => value + 1); }}>Reload datasets</button></div>}
    {loading ? <p role="status">Loading datasets…</p> : datasets.length ? <label>Dataset to manage
      <select value={datasetId} onChange={event => setDatasetId(event.target.value)}>
        <option value="">Choose a dataset</option>
        {datasets.map(dataset => <option key={dataset.id} value={dataset.id}>{dataset.name}</option>)}
      </select>
    </label> : !catalogError && <p>Upload a file before setting dataset access.</p>}
    {datasetId && <PolicyEditor key={`${workspaceId}:${datasetId}`} root={`/workspaces/${workspaceId}/datasets/${datasetId}/access-policy`} request={request} />}
  </section>;
}

function PolicyEditor({ root, request }: { root: string; request: ApiRequest }) {
  const [saved, setSaved] = useState<Policy | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [newMember, setNewMember] = useState("");
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const accept = useCallback((value: Policy) => {
    setSaved(value); setEnabled(value.enabled); setGrants(value.grants);
    setNewMember(""); setError(""); setConflict(false);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    request<Policy>(root, { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) accept(value);
    }).catch(cause => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load access settings.");
    });
    return () => controller.abort();
  }, [root, request, accept]);
  async function loadSaved() {
    setBusy(true); setMessage("");
    try { accept(await request<Policy>(root)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not reload access settings."); }
    finally { setBusy(false); }
  }
  async function save() {
    if (!saved || busy || conflict) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const value = await request<Policy>(root, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_version: saved.version, enabled, grants }) });
      accept(value); setMessage("Access saved. These rules now apply to this dataset.");
    } catch (cause) {
      setConflict((cause as { status?: number }).status === 409);
      setError((cause as { status?: number }).status === 409
        ? "Someone changed access while you were editing. Your draft is still shown. Reload the saved rules before editing again."
        : cause instanceof Error ? cause.message : "Could not save access. Your draft is still here.");
    } finally { setBusy(false); }
  }
  const changed = saved && (enabled !== saved.enabled || JSON.stringify(grants) !== JSON.stringify(saved.grants));
  function changeGrant(index: number, value: Grant) {
    setGrants(current => current.map((grant, position) => position === index ? value : grant)); setMessage("");
  }
  return <div className={styles.editor}>
    {error && <div role="alert"><p>{error}</p>{(conflict || !saved) && <button type="button" disabled={busy} onClick={() => void loadSaved()}>Reload saved rules</button>}</div>}
    {message && <p className={styles.success} role="status">{message}</p>}
    {!saved && !error && <p role="status">Loading access rules…</p>}
    {saved && <form onSubmit={event => { event.preventDefault(); void save(); }}>
      <fieldset disabled={busy || conflict} className={styles.mode}>
        <legend>Access mode</legend>
        <label><input type="radio" name="access-mode" checked={!enabled} onChange={() => { setEnabled(false); setMessage(""); }} /><span><strong>Workspace access</strong><small>Existing workspace permissions apply.</small></span></label>
        <label><input type="radio" name="access-mode" checked={enabled} onChange={() => { setEnabled(true); setMessage(""); }} /><span><strong>Choose each person’s access</strong><small>Only people with a rule below can use this dataset.</small></span></label>
      </fieldset>
      {enabled && <>
        <p className={styles.notice}>Anyone without a rule, including you, will lose access to this dataset. As the owner, you can still manage these rules here. All row conditions in a rule must match.</p>
        {grants.map((grant, index) => {
          const member = saved.members.find(value => value.user_id === grant.user_id);
          const name = member ? member.display_name || "Workspace member" : "Former member";
          return <details className={styles.grant} key={grant.user_id} open={grants.length === 1}>
            <summary>{name} <span>{grant.columns === null ? "All fields" : `${grant.columns.length} fields`} · {grant.conditions.length ? `${grant.conditions.length} row condition${grant.conditions.length === 1 ? "" : "s"}` : "All rows"}</span></summary>
            <fieldset disabled={busy || conflict}>
              <legend className={styles.legend}>Fields to share</legend>
              <label className={styles.check}><input type="checkbox" checked={grant.columns === null} onChange={event => changeGrant(index, { ...grant, columns: event.target.checked ? null : saved.columns.map(column => column.name) })} />All fields, including future fields</label>
              {grant.columns !== null && <div className={styles.columns}>{saved.columns.map(column => <label className={styles.check} key={column.name}><input type="checkbox" checked={grant.columns!.includes(column.name)} onChange={event => changeGrant(index, { ...grant, columns: event.target.checked ? [...grant.columns!, column.name] : grant.columns!.filter(name => name !== column.name) })} />{column.name}</label>)}</div>}
              {grant.columns?.length === 0 && <p role="alert">Choose at least one field, or remove this person’s rule.</p>}
              <h3>Rows to share</h3>
              {grant.conditions.length === 0 && <p>All rows are shared. Add a condition to limit them.</p>}
              {grant.conditions.map((condition, position) => {
                const update = (value: Condition) => changeGrant(index, { ...grant, conditions: grant.conditions.map((old, row) => row === position ? value : old) });
                const type = saved.columns.find(column => column.name === condition.column)?.type;
                return <div className={styles.condition} key={position} role="group" aria-label={`Row condition ${position + 1} for ${name}`}>
                  <label>Field<select value={condition.column} onChange={event => update({ ...condition, column: event.target.value, value: "" })}>{saved.columns.map(column => <option key={column.name} value={column.name}>{column.name}</option>)}</select></label>
                  <label>Condition<select value={condition.operator} onChange={event => update({ ...condition, operator: event.target.value })}>{operators.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
                  <label>Value{type === "boolean" ? <select required value={condition.value} onChange={event => update({ ...condition, value: event.target.value })}><option value="">Choose a value</option><option value="true">True</option><option value="false">False</option></select> : <input required maxLength={200} type={type === "date" ? "date" : "text"} inputMode={type === "integer" || type === "decimal" ? "decimal" : undefined} value={condition.value} onChange={event => update({ ...condition, value: event.target.value })} />}</label>
                  <button type="button" aria-label={`Remove row condition ${position + 1} for ${name}`} onClick={() => changeGrant(index, { ...grant, conditions: grant.conditions.filter((_, row) => row !== position) })}>Remove condition</button>
                </div>;
              })}
              <div className={styles.actions}>
                <button type="button" disabled={grant.conditions.length >= 12 || !saved.columns.length} onClick={() => changeGrant(index, { ...grant, conditions: [...grant.conditions, { column: saved.columns[0].name, operator: "eq", value: "" }] })}>Add row condition</button>
                <button type="button" aria-label={`Remove access for ${name}`} onClick={() => setGrants(current => current.filter((_, position) => position !== index))}>Remove this person</button>
              </div>
            </fieldset>
          </details>;
        })}
        <div className={styles.add}>
          <label>Person to add<select disabled={busy || conflict} value={newMember} onChange={event => setNewMember(event.target.value)}><option value="">Choose a workspace member</option>{saved.members.filter(member => !grants.some(grant => grant.user_id === member.user_id)).map(member => <option key={member.user_id} value={member.user_id}>{member.display_name} · {member.role}</option>)}</select></label>
          <button type="button" disabled={busy || conflict || !newMember || grants.length >= 50} onClick={() => { setGrants(current => [...current, { user_id: newMember, columns: null, conditions: [] }]); setNewMember(""); setMessage(""); }}>Add person</button>
        </div>
      </>}
      <div className={styles.actions}><button type="submit" disabled={busy || conflict || !changed || (enabled && grants.some(grant => grant.columns?.length === 0))}>{busy ? "Saving…" : "Save access rules"}</button><span>{changed ? "Unsaved changes" : `Saved · Version ${saved.version}`}</span>{changed && <button type="button" disabled={busy} onClick={() => { accept(saved); setMessage(""); }}>Discard draft</button>}</div>
    </form>}
  </div>;
}
