/* Use case: Helps one person resume the existing data advancement journey.
What it does: Saves private guide position and explicit skips without fabricating completed work. */

"use client";

import { useCallback, useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import { WorkspaceSelect } from "./workspace-select";
import styles from "./local-accounts.module.css";

type Step = { id: string; label: string; observed: boolean; skipped: boolean };
type Progress = { version: number; active_step: string; skipped_steps: string[]; paused: boolean; finished: boolean; notice: string; steps: Step[] };
const destinations: Record<string, string> = { setup: "team", data: "data", quality: "prepare", meaning: "prepare", analysis: "ask", dashboard: "studies", recommendations: "decisions", team: "team" };
const help: Record<string, string> = {
  setup: "Your account and workspace are ready. You can change workspace settings or create an organization from Team & settings.",
  data: "Upload a CSV or Excel file, or try a clearly labelled fictional sample.",
  quality: "Open Prepare data to inspect actual missing values, types and duplicates. Preview any cleaning before applying it.",
  meaning: "Review what a row and each field mean. Confirm shared meanings only when they are right; personal notes stay private.",
  analysis: "Ask about a measure or explore a verified comparison. Open the evidence to check its inputs and exact answer.",
  dashboard: "Save an analysis or create a dashboard from verified results so you can return to it.",
  recommendations: "Explore a scenario or bounded recommendation when you have the required units and assumptions. Review it before making a decision.",
  team: "Create an invitation when you are ready. Local password accounts need their exact account ID checked by the workspace manager.",
};

export function OnboardingGuide({ workspaceId, request, defaultOpen, onNavigate }: { workspaceId: string; request: ApiRequest; defaultOpen: boolean; onNavigate: (section: string) => void }) {
  const path = `/workspaces/${workspaceId}/onboarding-progress`;
  const [progress, setProgress] = useState<Progress | null>(null);
  const [open, setOpen] = useState(defaultOpen);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const reload = useCallback(async (signal?: AbortSignal) => {
    try {
      const value = await request<Progress>(path, { signal });
      if (!signal?.aborted) { setProgress(value); setConflict(false); setError(""); }
      return value;
    } catch (cause) {
      if (!signal?.aborted) { setProgress(null); setConflict(true); }
      throw cause;
    }
  }, [request, path]);
  useEffect(() => {
    const controller = new AbortController();
    Promise.resolve().then(() => reload(controller.signal)).then(value => { if (!controller.signal.aborted) setOpen(defaultOpen && !value.paused && !value.finished); }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load your setup guide."); });
    return () => controller.abort();
  }, [reload, defaultOpen]);

  async function save(changes: Partial<Progress>) {
    if (!progress || busy || conflict) return;
    setBusy(true); setError("");
    try {
      const next = { ...progress, ...changes };
      const value = await request<Progress>(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_version: progress.version, active_step: next.active_step, skipped_steps: next.skipped_steps, paused: next.paused, finished: next.finished }) });
      setProgress(value);
      if (value.paused || value.finished) setOpen(false);
    } catch (cause) {
      const stale = (cause as { status?: number }).status === 409;
      setConflict(true);
      if (!stale) setProgress(null);
      setError(stale ? "Your guide changed in another tab. Reload its saved position before continuing." : `${cause instanceof Error ? cause.message : "Could not save your guide."} Reload the guide before continuing.`);
    } finally { setBusy(false); }
  }
  const current = progress?.steps.find(step => step.id === progress.active_step);
  const pending = progress?.steps.filter(step => !step.observed && !step.skipped) ?? [];
  const index = progress?.steps.findIndex(step => step.id === progress.active_step) ?? 0;

  return <details className={styles.guide} open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Your setup guide <span className={styles.stepState}>Private to you{progress?.finished ? " · finished" : progress?.paused ? " · paused" : ""}</span></summary>
    {error && <p role="alert">{error}</p>}
    {(!progress || conflict) && <button type="button" disabled={busy} onClick={() => void reload().catch(cause => setError(cause instanceof Error ? cause.message : "Could not reload your guide."))}>Reload setup guide</button>}
    {progress && <>
      <p>{progress.notice}</p>
      {(progress.paused || progress.finished) && <button type="button" disabled={busy || conflict} onClick={() => void save({ paused: false, finished: false })}>Resume guide</button>}
      <WorkspaceSelect id={`setup-step-${workspaceId}`} label="Setup step" value={progress.active_step} disabled={busy || conflict} onValueChange={value => void save({ active_step: value })} options={progress.steps.map(step => ({ value: step.id, label: step.label, description: step.skipped ? "Explicitly skipped" : step.observed ? "Related activity recorded" : "No related activity recorded yet" }))} />
      {current && <div className={styles.current}>
        <h3>{current.label}</h3><p>{help[current.id]}</p>
        <p className={styles.stepState}>{current.skipped ? "You skipped this step. You can return whenever you want." : current.observed ? "Related activity is recorded for your account. You can review it again." : "This step has no related activity recorded yet."}</p>
        <div className={styles.actions}>
          <button type="button" disabled={busy || conflict} onClick={() => onNavigate(destinations[current.id])}>Open this step</button>
          {current.skipped ? <button type="button" disabled={busy || conflict} onClick={() => void save({ skipped_steps: progress.skipped_steps.filter(step => step !== current.id) })}>Return to this step</button> : !current.observed && <button type="button" disabled={busy || conflict} onClick={() => void save({ skipped_steps: [...progress.skipped_steps, current.id], active_step: progress.steps[Math.min(index + 1, progress.steps.length - 1)].id })}>Skip this step</button>}
          {index < progress.steps.length - 1 && <button type="button" disabled={busy || conflict} onClick={() => void save({ active_step: progress.steps[index + 1].id })}>Next setup step</button>}
        </div>
      </div>}
      <div className={styles.actions}>
        <button type="button" disabled={busy || conflict} onClick={() => void reload().catch(cause => setError(cause instanceof Error ? cause.message : "Could not refresh your guide."))}>Refresh recorded progress</button>
        <button type="button" disabled={busy || conflict} onClick={() => void save({ paused: true })}>Pause guide</button>
        <button type="button" disabled={busy || conflict || pending.length > 0} onClick={() => void save({ finished: true, paused: false })}>Finish guide</button>
      </div>
      {pending.length > 0 && <small>Complete or explicitly skip {pending.length} remaining {pending.length === 1 ? "step" : "steps"} before finishing.</small>}
    </>}
  </details>;
}
