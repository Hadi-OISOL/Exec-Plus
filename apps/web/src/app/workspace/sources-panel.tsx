/* Use case: Lets workspace owners import approved PostgreSQL snapshots.
What it does: Keeps credentials outside the browser, retains retry identity and separates import from refresh activation. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import styles from "./sources-panel.module.css";

type Source = {
  id: string; version: number; label: string; enabled: boolean; max_rows: number; max_bytes: number;
  tables: { schema: string; table: string; columns: string[] }[];
};
type ImportRecord = {
  id: string; status: "extracting" | "imported" | "staged" | "failed";
  created_at: string; upload_id: string | null; candidate_id: string | null; failure_code: string | null;
  selection: { source_id: string; source_version: number; table: { schema: string; table: string; columns: string[] }; mode: string };
  snapshot: { row_count: number; extracted_at: string } | null;
};
type ImportRequest = {
  request_id: string; source_id: string; source_version: number; schema_name: string; table: string;
  columns: string[]; mode: "upload" | "refresh"; expected_feed_version: number | null;
};
type Props = {
  workspaceId: string; datasetId: string; request: ApiRequest;
  onImported: (uploadId: string) => Promise<void>; onReview: (uploadId: string) => void; onRefresh: () => void;
};
const failureMessages: Record<string, string> = {
  source_unavailable: "The approved source could not be reached. An operator can check the connection.",
  source_credentials: "The connection needs an operator to check its credentials.",
  source_secret: "The connection needs an operator to check its protected credentials.",
  source_role: "The source account needs an operator to check its read-only permissions.",
  source_table: "An operator must review the approved source table before it can be imported.",
  source_version: "The approved source changed. Refresh sources, then choose a new attempt.",
  source_timeout: "The source took too long to respond. Try a new attempt when it is available.",
  source_rows: "The source is empty or exceeds the approved row limit. No data was imported.",
  source_size: "The complete table exceeds the approved size limit. No partial data was imported.",
  source_schema: "The table's fields or types changed. An operator must review the approved source.",
  source_value: "A source value needs preparation before it can be imported.",
  source_interrupted: "This attempt was closed after an interruption. A new attempt reads the source again.",
};
const when = (value: string) => `${value.slice(0, 19).replace("T", " ")} UTC`;

export function SourcesPanel({ workspaceId, datasetId, request, onImported, onReview, onRefresh }: Props) {
  const [sources, setSources] = useState<Source[]>([]);
  const [history, setHistory] = useState<ImportRecord[]>([]);
  const [feedVersion, setFeedVersion] = useState<number | null>(null);
  const [sourceId, setSourceId] = useState("");
  const [tableIndex, setTableIndex] = useState(0);
  const [columns, setColumns] = useState<string[] | null>(null);
  const [mode, setMode] = useState<"upload" | "refresh">("upload");
  const [attempt, setAttempt] = useState<ImportRequest | null>(null);
  const [result, setResult] = useState<ImportRecord | null>(null);
  const [loadKey, setLoadKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    const options = { signal: controller.signal };
    Promise.all([
      request<{ sources: Source[] }>(`/workspaces/${workspaceId}/sources`, options),
      datasetId ? request<{ imports: ImportRecord[] }>(`/workspaces/${workspaceId}/datasets/${datasetId}/source-imports`, options) : Promise.resolve({ imports: [] }),
      datasetId ? request<{ feed: { version: number } | null }>(`/workspaces/${workspaceId}/datasets/${datasetId}/refresh`, options) : Promise.resolve({ feed: null }),
    ]).then(([catalog, imports, overview]) => {
      if (controller.signal.aborted) return;
      setSources(catalog.sources); setHistory(imports.imports); setFeedVersion(overview.feed?.version ?? null);
      setLoadError("");
      setSourceId(current => catalog.sources.some(value => value.enabled && value.id === current)
        ? current : catalog.sources.find(value => value.enabled)?.id || "");
      setColumns(current => current ?? catalog.sources.find(value => value.enabled)?.tables[0]?.columns ?? []);
    }).catch(cause => {
      if (!controller.signal.aborted) {
        setSources([]); setHistory([]); setFeedVersion(null);
        setLoadError(cause instanceof Error ? cause.message : "Sources could not be loaded. Please try again.");
      }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [workspaceId, datasetId, request, loadKey]);
  const source = sources.find(value => value.id === sourceId && value.enabled);
  const effectiveTableIndex = source?.tables[tableIndex] ? tableIndex : 0;
  const table = source?.tables[effectiveTableIndex];
  const selectedColumns = table?.columns.filter(value => columns?.includes(value)) ?? [];
  const locked = pending || attempt !== null;
  const reload = () => { setLoading(true); setLoadKey(value => value + 1); };
  const clearAttempt = () => { setAttempt(null); setResult(null); setError(""); setNotice(""); };
  const importSource = async () => {
    let body = attempt;
    if (!body) {
      if (!source || !table || !datasetId || !selectedColumns.length) return;
      body = {
        request_id: crypto.randomUUID(), source_id: source.id, source_version: source.version,
        schema_name: table.schema, table: table.table, columns: selectedColumns,
        mode, expected_feed_version: mode === "refresh" ? feedVersion : null,
      };
    }
    setAttempt(body); setPending(true); setError(""); setNotice("");
    let saved: ImportRecord;
    try {
      saved = await request<ImportRecord>(`/workspaces/${workspaceId}/datasets/${datasetId}/source-imports`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      setResult(saved); setHistory(current => [saved, ...current.filter(value => value.id !== saved.id)]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The result could not be checked. Retry the same attempt.");
      setPending(false); return;
    }
    if (saved.status === "imported" && saved.upload_id) {
      try { await onImported(saved.upload_id); }
      catch { setNotice("Your import is saved. Reload the data library if it does not appear yet."); }
    }
    setPending(false);
  };
  const disconnect = async () => {
    if (!source) return;
    setPending(true); setError("");
    try {
      await request(`/workspaces/${workspaceId}/sources/${source.id}/disconnect`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_version: source.version }),
      });
      clearAttempt(); setSourceId(""); setColumns(null); setTableIndex(0);
      setNotice("Source disconnected. Your saved imports are still available."); reload();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The source could not be disconnected. Please retry."); }
    finally { setPending(false); }
  };
  const renderRecord = (record: ImportRecord) => <article className={styles.record} key={record.id}>
    <div><strong>{record.status === "imported" ? "Import saved" : record.status === "staged" ? "Refresh ready for review" : record.status === "failed" ? "Import did not finish" : "Import still running"}</strong>
      <p>{record.selection.table.schema}.{record.selection.table.table} · {record.selection.table.columns.length} fields</p>
      <p className={styles.caption}>{record.snapshot ? `${record.snapshot.row_count} rows · Read ${when(record.snapshot.extracted_at)}` : when(record.created_at)}</p></div>
    {record.status === "failed" && <p>{failureMessages[record.failure_code ?? ""] ?? "Nothing new was published by this attempt. Check the source settings, then start a new attempt."}</p>}
    {record.status === "extracting" && <p>Refresh this list to check again. An operator can close an interrupted attempt.</p>}
    {record.status === "imported" && record.upload_id && <button type="button" onClick={() => onReview(record.upload_id!)}>Review imported data</button>}
    {record.status === "staged" && <button type="button" onClick={onRefresh}>Review staged refresh</button>}
  </article>;
  return <section className={`panel ${styles.panel}`} aria-label="Database sources">
    <div className={styles.header}><div><p className="studioEyebrow">APPROVED CONNECTIONS</p><h2>Bring in database data</h2>
      <p>Choose an approved table. Syntelio saves a read-only copy for you to review.</p></div>
      <button type="button" onClick={reload} disabled={pending || loading}>Refresh sources</button></div>
    {loading ? <p role="status">Loading approved sources…</p> : loadError ? <p role="alert" className="errorNotice">{loadError}</p> : <>
      {!sources.some(value => value.enabled) ? <p className={styles.notice}>No database source is connected yet. An operator can register a read-only PostgreSQL connection and approve the tables and fields you can import.</p> : <>
        {!datasetId && <p className={styles.notice}>Choose a dataset above, or create a named dataset, to receive the import.</p>}
        <fieldset disabled={locked || !datasetId} className={styles.form}><legend>Choose what to import</legend>
          <div className={styles.choices}>
            <label>Approved source<select value={sourceId} onChange={event => {
              setSourceId(event.target.value); setTableIndex(0); setColumns(sources.find(value => value.id === event.target.value)?.tables[0]?.columns ?? []);
            }}>{sources.filter(value => value.enabled).map(value => <option key={value.id} value={value.id}>{value.label}</option>)}</select></label>
            <label>Source table<select value={effectiveTableIndex} onChange={event => {
              const index = Number(event.target.value); setTableIndex(index); setColumns(source?.tables[index]?.columns ?? []);
            }}>{source?.tables.map((value, index) => <option key={`${value.schema}.${value.table}`} value={index}>{value.schema}.{value.table}</option>)}</select></label>
          </div>
          <details className={styles.fields}><summary>Fields to import ({selectedColumns.length})</summary>
            <div>{table?.columns.map(column => <label key={column}><input type="checkbox" checked={columns?.includes(column) ?? false} onChange={event => setColumns(current => event.target.checked ? [...current ?? [], column] : (current ?? []).filter(value => value !== column))} />{column}</label>)}</div>
          </details>
          <label>Import action<select value={mode} onChange={event => setMode(event.target.value as "upload" | "refresh")}>
            <option value="upload">Save a new snapshot</option><option value="refresh" disabled={feedVersion === null}>Stage a replacement refresh</option>
          </select></label>
          <p className={styles.caption}>{mode === "upload" ? "This saves a new file. Review its meaning before calculating from it." : "This stages a full replacement. Your active refresh source changes only after review and activation."}</p>
        </fieldset>
        {source && <p className={styles.caption}>Complete snapshots only · Up to {source.max_rows.toLocaleString("en-US")} rows · Approved fields only</p>}
        {feedVersion === null && datasetId && <p className={styles.caption}>To update an existing source, <button type="button" className={styles.textButton} onClick={onRefresh}>set up a refresh feed</button> first.</p>}
        <div className={styles.actions}>
          {!result && <button type="button" disabled={pending || (!attempt && (!source || !table || !datasetId || !selectedColumns.length || (mode === "refresh" && feedVersion === null)))} onClick={() => void importSource()}>
            {pending ? "Reading approved source…" : attempt ? "Retry same attempt" : mode === "refresh" ? "Stage source refresh" : "Import snapshot"}</button>}
          {attempt && !pending && <button type="button" onClick={clearAttempt}>{result?.status === "failed" ? "Start a new attempt" : result ? "Choose another import" : "Change selection for a new attempt"}</button>}
        </div>
        {attempt && !result && !pending && <p className={styles.caption}>Retry checks the same attempt, so a lost connection does not create a duplicate. A new attempt reads the source again.</p>}
        <details className={styles.disconnect}><summary>Connection settings</summary><p>Disconnecting prevents future imports. Saved files and results stay in your workspace.</p>
          <button type="button" disabled={pending || !!attempt || !source} onClick={() => void disconnect()}>Disconnect selected source</button></details>
      </>}
      {error && <p role="alert" className="errorNotice">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {result && <div role="status" className={styles.latest}>{renderRecord(result)}</div>}
      {history.filter(value => value.id !== result?.id).length > 0 && <details className={styles.history}><summary>Your saved import attempts ({history.filter(value => value.id !== result?.id).length})</summary>
        {history.filter(value => value.id !== result?.id).map(renderRecord)}</details>}
    </>}
  </section>;
}
