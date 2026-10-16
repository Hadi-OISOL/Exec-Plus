/* Use case: Downloads a permitted saved answer only when its owner asks.
What it does: Shows progress and errors, cancels abandoned requests and delegates authenticated binary access to the workspace. */

import { useEffect, useRef, useState } from "react";

export type PdfDownload = (path: string, signal: AbortSignal) => Promise<void>;

export function AnswerPdfDownload({ path, download }: { path: string; download: PdfDownload }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const operation = useRef<AbortController | null>(null);
  useEffect(() => () => operation.current?.abort(), [path]);
  async function start() {
    if (busy) return;
    const controller = new AbortController();
    operation.current = controller; setBusy(true); setError(""); setDone(false);
    try { await download(path, controller.signal); if (!controller.signal.aborted) setDone(true); }
    catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "This answer could not be downloaded. Please try again."); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <div className="answerSaveActions"><button type="button" disabled={busy} onClick={() => void start()}>{busy ? "Preparing PDF…" : "Download PDF"}</button>{done && <span role="status">PDF download started.</span>}{error && <p role="alert">{error}</p>}</div>;
}
