/* Use case: Downloads an authorized result in a chosen portable format.
What it does: Offers explicit, cancellable exports with clear format and exactness notes, without sending browser result values. */

import { createContext, useContext, useEffect, useRef, useState } from "react";
import styles from "./result-export-actions.module.css";

export type ExportFormat = "pdf" | "xlsx" | "csv" | "png";
export type ExportDownload = (path: string, format: ExportFormat, signal: AbortSignal, body?: object) => Promise<void>;
export const ExportDownloadContext = createContext<ExportDownload | null>(null);

type ExportProps = { path: string; charts?: string[]; body?: object; label?: string };
export function ResultExportActions(props: ExportProps) {
  return <ExportControl key={`${props.path}:${JSON.stringify(props.body ?? {})}`} {...props} />;
}
function ExportControl({ path, charts = [], body, label = "Download result" }: ExportProps) {
  const download = useContext(ExportDownloadContext);
  const [format, setFormat] = useState<ExportFormat>("pdf");
  const [chart, setChart] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const operation = useRef<AbortController | null>(null);
  useEffect(() => () => operation.current?.abort(), []);
  if (!download) return null;
  async function start() {
    if (busy || !download) return;
    const controller = new AbortController();
    operation.current = controller; setBusy(true); setMessage(""); setError("");
    try {
      const [base, parameters] = path.split("?");
      const query = new URLSearchParams(parameters); query.set("chart", String(chart));
      await download(body ? path : `${base}.${format}?${query}`, format, controller.signal, body ? { ...body, format, chart } : undefined);
      if (!controller.signal.aborted) setMessage("Download started. Your saved result stays unchanged.");
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Download failed. Try again.");
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  return <details className={styles.export}>
    <summary>{label}</summary>
    <div className={styles.controls}>
      <label>File type<select value={format} disabled={busy} onChange={event => { setFormat(event.target.value as ExportFormat); setError(""); setMessage(""); }}><option value="pdf">PDF report</option><option value="xlsx">Excel · exact text cells</option><option value="csv">CSV + evidence (.zip)</option>{charts.length > 0 && <option value="png">PNG chart image</option>}</select></label>
      {format === "png" && charts.length > 1 && <label>Chart<select value={chart} disabled={busy} onChange={event => setChart(Number(event.target.value))}>{charts.map((title, index) => <option key={index} value={index}>{title}</option>)}</select></label>}
      <button type="button" disabled={busy} onClick={() => void start()}>{busy ? "Preparing download…" : `Download ${format === "xlsx" ? "Excel" : format === "csv" ? "CSV bundle" : format.toUpperCase()}`}</button>
    </div>
    <p>{format === "xlsx" ? "Every returned value is stored as text to preserve long numbers. The Evidence sheet keeps original types and source details." : format === "csv" ? "Includes every returned row and exact evidence. Formula-like text is escaped in CSV; the evidence file keeps the original text and types." : format === "png" ? "A portable chart of the saved result, with exact values and source evidence inside the image metadata." : "Saved results, figures, exact tables and source evidence. This does not run a new analysis."} A downloaded copy cannot be recalled after sharing.</p>
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
  </details>;
}
