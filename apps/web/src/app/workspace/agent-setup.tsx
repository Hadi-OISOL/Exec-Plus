/* Use case: Offers a short, optional first setup for private agent preferences.
What it does: Preserves Back/Skip drafts and writes role, focus and explanation style only after an explicit save. */

import { useEffect, useRef, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import styles from "./agent-setup.module.css";

type Memory = { user_id: string; version: number; role: string; focus: string; explanation_style: "concise" | "step_by_step" };
const roles = ["I run or manage a team", "I analyse data", "I am learning about this data"];
const aims = ["Understand what this data means", "Find patterns and unusual values", "Compare results and choose next steps"];

export function AgentSetup({ workspaceId, request, onEdit }: { workspaceId: string; request: ApiRequest; onEdit: () => void }) {
  const [memory, setMemory] = useState<Memory | null>(null);
  const [step, setStep] = useState(0);
  const [role, setRole] = useState("");
  const [focus, setFocus] = useState("");
  const [customRole, setCustomRole] = useState(false);
  const [customFocus, setCustomFocus] = useState(false);
  const [style, setStyle] = useState<Memory["explanation_style"]>("concise");
  const [skipped, setSkipped] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [saved, setSaved] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const path = `/workspaces/${workspaceId}/agent-memory`;
  useEffect(() => {
    const controller = new AbortController();
    request<Memory>(path, { signal: controller.signal }).then(value => {
      if (controller.signal.aborted) return;
      setMemory(value); setRole(value.role); setFocus(value.focus); setStyle(value.explanation_style);
      setCustomRole(Boolean(value.role && !roles.includes(value.role))); setCustomFocus(Boolean(value.focus && !aims.includes(value.focus)));
      try { setSkipped(localStorage.getItem(`execplus.agent-setup.${workspaceId}.${value.user_id}`) === "skip"); } catch { setSkipped(false); }
    }).catch(() => { if (!controller.signal.aborted) setError("Private preferences could not be loaded. You can still explore your file."); });
    return () => controller.abort();
  }, [path, request, workspaceId]);

  function go(next: number) { setStep(next); requestAnimationFrame(() => heading.current?.focus({ preventScroll: true })); }
  function skip() {
    setSkipped(true); setStep(0);
    if (memory) try { localStorage.setItem(`execplus.agent-setup.${workspaceId}.${memory.user_id}`, "skip"); } catch { setSkipped(true); }
  }
  async function save() {
    if (!memory || busy || conflict) return;
    setBusy(true); setError("");
    try {
      const value = await request<Memory>(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_version: memory.version, role: role.trim(), focus: focus.trim(), explanation_style: style }) });
      setMemory(value); setSaved(true); setStep(0);
    } catch (cause) {
      const changed = (cause as { status?: number }).status === 409;
      setConflict(changed);
      setError(changed ? "Your preferences changed in another tab. Your draft is still here; open My memory to review the saved version." : "Your preferences were not saved. Your choices are still here; try again.");
    } finally { setBusy(false); }
  }

  if (!memory) return error ? <aside className={styles.compact}><p>{error}</p><button type="button" onClick={onEdit}>Open My memory</button></aside> : null;
  if (memory.version > 0 || skipped) return <aside className={styles.compact} aria-label="Private answer preferences"><p role={saved ? "status" : undefined}>{saved ? "Preferences saved. New explanations and suggestions can use them." : memory.role || memory.focus ? "Your saved preferences help shape new explanations." : "You can personalize explanations whenever you like."}</p><button type="button" onClick={onEdit}>Edit my preferences</button>{skipped && memory.version === 0 && <button type="button" onClick={() => { setSkipped(false); go(1); }}>Quick setup</button>}</aside>;
  return <section className={styles.setup} aria-label="Quick private agent setup">
    {step === 0 ? <><div><span className={styles.eyebrow}>MAKE IT YOURS · OPTIONAL</span><h3>How should I help you?</h3><p>Three quick choices make explanations easier to follow. Only you can see them.</p></div><div className={styles.actions}><button type="button" onClick={() => go(1)}>Personalize my answers</button><button type="button" onClick={skip}>Maybe later</button></div></> : <>
      <p className={styles.progress}>Step {Math.min(step, 3)} of 3 · Private to you in this workspace</p>
      <h3 ref={heading} tabIndex={-1}>{step === 1 ? "Which sounds most like you?" : step === 2 ? "What do you usually want help with?" : step === 3 ? "How should I explain things?" : "Ready to remember these choices?"}</h3>
      {step === 1 && <label>Your perspective<select value={customRole ? "custom" : role} onChange={event => { setCustomRole(event.target.value === "custom"); setRole(event.target.value === "custom" ? "" : event.target.value); }} disabled={busy}><option value="">Choose one, or skip this step</option>{roles.map(value => <option key={value}>{value}</option>)}<option value="custom">Write my own</option></select>{customRole && <input aria-label="Your own perspective" value={role} onChange={event => setRole(event.target.value)} maxLength={300} />}</label>}
      {step === 2 && <label>Your usual aim<select value={customFocus ? "custom" : focus} onChange={event => { setCustomFocus(event.target.value === "custom"); setFocus(event.target.value === "custom" ? "" : event.target.value); }} disabled={busy}><option value="">Choose one, or skip this step</option>{aims.map(value => <option key={value}>{value}</option>)}<option value="custom">Write my own</option></select>{customFocus && <input aria-label="Your own aim" value={focus} onChange={event => setFocus(event.target.value)} maxLength={500} />}</label>}
      {step === 3 && <fieldset><legend>Explanation style</legend><label><input type="radio" name="setup-style" checked={style === "concise"} onChange={() => setStyle("concise")} />Short and simple</label><label><input type="radio" name="setup-style" checked={style === "step_by_step"} onChange={() => setStyle("step_by_step")} />Explain step by step</label></fieldset>}
      {step === 4 && <><dl><div><dt>Your perspective</dt><dd>{role.trim() || "Not set"}</dd></div><div><dt>Your usual aim</dt><dd>{focus.trim() || "Not set"}</dd></div><div><dt>Explanation style</dt><dd>{style === "concise" ? "Short and simple" : "Step by step"}</dd></div></dl><p>Save these for new explanations and suggestions across your files. This does not change calculations, shared definitions or old replies. Edit or forget them in My memory.</p></>}
      {error && <p role="alert">{error}{conflict && <button type="button" onClick={onEdit}>Open My memory</button>}</p>}
      <div className={styles.actions}><button type="button" disabled={busy} onClick={() => go(step - 1)}>Back</button><button type="button" disabled={busy} onClick={skip}>Skip without saving</button>{step < 4 ? <button type="button" onClick={() => go(step + 1)}>Continue</button> : <button type="button" disabled={busy || conflict} onClick={() => void save()}>{busy ? "Saving preferences…" : "Save my preferences"}</button>}</div>
    </>}
  </section>;
}
