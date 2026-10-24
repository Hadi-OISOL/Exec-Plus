/* Use case: Lets a person manage the private preferences used in new agent answers.
What it does: Loads, saves and forgets server-owned workspace memory with explicit conflict recovery. */

import { useCallback, useEffect, useState } from "react";
import { Icon } from "./explore-components";
import type { ApiRequest } from "./profile-panel";

type AgentMemory = {
  workspace_id: string;
  user_id: string;
  version: number;
  role: string;
  focus: string;
  explanation_style: "concise" | "step_by_step";
  updated_at: string | null;
};

export function AgentMemoryPanel({ workspaceId, request }: { workspaceId: string; request: ApiRequest }) {
  const [memory, setMemory] = useState<AgentMemory | null>(null);
  const [role, setRole] = useState("");
  const [focus, setFocus] = useState("");
  const [style, setStyle] = useState<AgentMemory["explanation_style"]>("concise");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [conflict, setConflict] = useState(false);
  const [forgetOpen, setForgetOpen] = useState(false);
  const path = `/workspaces/${workspaceId}/agent-memory`;
  const accept = useCallback((value: AgentMemory) => {
    setMemory(value); setRole(value.role); setFocus(value.focus); setStyle(value.explanation_style);
    setConflict(false); setError("");
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    request<AgentMemory>(path, { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) accept(value);
    }).catch(cause => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load your memory.");
    });
    return () => controller.abort();
  }, [path, request, accept]);

  async function change(forget = false) {
    if (!memory || busy || conflict) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const value = await request<AgentMemory>(forget ? `${path}?expected_version=${memory.version}` : path, forget
        ? { method: "DELETE" }
        : { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_version: memory.version, role, focus, explanation_style: style }) });
      accept(value); setForgetOpen(false);
      setMessage(forget ? "Memory cleared. Future answers will stop using these preferences. Existing replies remain." : "Memory saved. New explanations and suggestions can use these preferences across files in this workspace.");
    } catch (cause) {
      const isConflict = (cause as { status?: number }).status === 409;
      setConflict(isConflict);
      setError(isConflict ? "Your memory changed in another tab. Reload the saved version before editing again. Your current draft is still shown." : cause instanceof Error ? cause.message : "Could not save your memory. Your draft is still here.");
    } finally { setBusy(false); }
  }
  async function reload() {
    setBusy(true); setMessage("");
    try { accept(await request<AgentMemory>(path)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not reload your memory."); }
    finally { setBusy(false); }
  }
  const changed = memory && (role !== memory.role || focus !== memory.focus || style !== memory.explanation_style);
  return <section className="studioMemoryLayout" aria-label="My private agent memory">
    <div className="panel studioMemoryEditor">
      <div className="studioMemoryHeading"><span className="studioToolIcon"><Icon name="memory" size={25} /></span><span className="homeContextStatus">Only you · This workspace</span></div>
      <h2>A data partner that knows your priorities.</h2>
      <p>Tell Syntelio what matters to you. You choose what to save, change or forget.</p>
      {error && <div className="errorNotice" role="alert"><p>{error}</p>{(conflict || !memory) && <button type="button" disabled={busy} onClick={() => void reload()}>Reload saved memory</button>}</div>}
      {message && <p className="studioMemorySuccess" role="status"><Icon name="check" size={18} />{message}</p>}
      {!memory && !error ? <p role="status">Loading your private memory…</p> : memory && <form onSubmit={event => { event.preventDefault(); void change(); }}>
        <label>Your role or perspective <span>For example: I manage retail operations.</span><input value={role} onChange={event => setRole(event.target.value)} maxLength={300} disabled={busy} placeholder="What is your role?" /></label>
        <label>What you usually want to understand <span>A preference for all your files in this workspace.</span><textarea value={focus} onChange={event => setFocus(event.target.value)} maxLength={500} rows={3} disabled={busy} placeholder="I focus on sales changes, unusual costs and practical next steps." /></label>
        <fieldset><legend>How should Syntelio explain things?</legend><div className="studioStyleChoices">
          <label data-selected={style === "concise"}><input type="radio" name="memory-style" value="concise" checked={style === "concise"} onChange={() => setStyle("concise")} disabled={busy} /><span><strong>Short & clear</strong><small>Start with the main point.</small></span></label>
          <label data-selected={style === "step_by_step"}><input type="radio" name="memory-style" value="step_by_step" checked={style === "step_by_step"} onChange={() => setStyle("step_by_step")} disabled={busy} /><span><strong>Step by step</strong><small>Walk through the explanation.</small></span></label>
        </div></fieldset>
        <div className="studioMemorySave"><button type="submit" disabled={busy || conflict || !changed}>{busy ? "Saving…" : "Save my memory"}</button><span>{changed ? "Unsaved changes" : memory.version > 0 ? "Saved preferences" : "Nothing saved yet"}</span></div>
      </form>}
      {memory && memory.version > 0 && <div className="studioForgetMemory">
        {!forgetOpen ? <button type="button" disabled={busy} onClick={() => setForgetOpen(true)}>Forget my memory</button> : <div><p>Clear your saved role, focus and explanation preference? Existing conversations keep their original replies.</p><div><button type="button" disabled={busy || conflict} onClick={() => void change(true)}>Clear saved memory</button><button type="button" disabled={busy} onClick={() => setForgetOpen(false)}>Keep memory</button></div></div>}
      </div>}
    </div>
    <aside className="studioMemoryNotes"><span className="studioEyebrow">HOW IT HELPS</span><h3>Your preferences travel with you.</h3><p>New readings, explanations and starter suggestions can use this memory across your files in this workspace.</p><ul><li><Icon name="check" size={17} /><span><strong>Private to you</strong>Other workspace members do not share your memory.</span></li><li><Icon name="data" size={17} /><span><strong>Data keeps its own meaning</strong>Saved business definitions and file-specific goals stay separate.</span></li><li><Icon name="prepare" size={17} /><span><strong>You stay in control</strong>Edit or forget your preferences here. Existing replies stay unchanged.</span></li></ul><p className="studioMemoryFootnote">This is saved context, not automatic learning from every conversation. It guides explanations; it does not change calculated results or grant access to data.</p></aside>
  </section>;
}
