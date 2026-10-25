/* Use case: Lets a person build a simple, honest prediction model from a confirmed file.
What it does: Picks a target and inputs, shows server progress and a private result card
with the plain verdict, holdout scores against the simple guess and associated inputs. */
"use client";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import type { AnalysisBody, AnalysisOptions, AnalysisSummary } from "./decision-types";
import { WorkspaceSelect } from "./workspace-select";
import { inputChoices, isPredictionMethod, metricRows, weightLabel } from "./prediction-model-values";
import type { PredictionOptions, PredictionResult } from "./prediction-model-values";
import styles from "./calendar-anomaly-panel.module.css";

type Options = AnalysisOptions & { prediction_models?: PredictionOptions };
type Body = Omit<AnalysisBody, "run"> & { run: AnalysisSummary & { result: PredictionResult; evidence: AnalysisBody["run"]["evidence"] } };
const post = (body: object): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export function PredictionModelPanel({ root, request, onReview }: { root: string; request: ApiRequest; onReview: () => void }) {
  const datasetRoot = root.split("/uploads/")[0], runsRoot = `${datasetRoot}/decision-analysis`;
  const [options, setOptions] = useState<Options | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [selected, setSelected] = useState<Body | null>(null);
  const [target, setTarget] = useState("");
  const [inputs, setInputs] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [pending, setPending] = useState(""); const [error, setError] = useState(""); const [message, setMessage] = useState("");
  const operation = useRef<AbortController | null>(null);
  const source = options?.prediction_models;
  const targetName = target || source?.targets[0]?.name || "";
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([request<Options>(`${root}/decision-analysis/options`, { signal: controller.signal }), request<AnalysisSummary[]>(runsRoot, { signal: controller.signal })])
      .then(([value, saved]) => { if (!controller.signal.aborted) { setOptions(value); setHistory(saved); } })
      .catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load prediction options."); });
    return () => { controller.abort(); operation.current?.abort(); };
  }, [root, runsRoot, request]);
  async function work(label: string, action: (signal: AbortSignal) => Promise<void>) {
    if (operation.current) return;
    const controller = new AbortController(); operation.current = controller; setPending(label); setError(""); setMessage("");
    try { await action(controller.signal); }
    catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "The model could not be built."); }
    finally { if (!controller.signal.aborted) setPending(""); if (operation.current === controller) operation.current = null; }
  }
  async function create(event: FormEvent) {
    event.preventDefault(); if (!options || !targetName) return;
    await work("Training on 80% of rows and testing on the 20% held back…", async signal => {
      const value = await request<Body>(`${root}/decision-analysis/prediction-models`, { ...post({ name: name.trim() || `Predict ${targetName}`, revision_id: options.revision_id, understanding_id: options.understanding_id, target_column: targetName, input_columns: inputs }), signal });
      if (signal.aborted) return;
      setSelected(value); setHistory(previous => [value.run, ...previous.filter(item => item.id !== value.run.id)]);
      setMessage("Saved privately. Only you can see this model.");
    });
  }
  async function open(id: string) {
    await work("Rebuilding the saved model from its original rows…", async signal => {
      const value = await request<Body>(`${runsRoot}/${id}`, { signal });
      if (!signal.aborted) { setSelected(value); setMessage("The saved model was rebuilt and matches exactly."); }
    });
  }
  const saved = history.filter(item => isPredictionMethod(item.method_version));
  const choices = source ? inputChoices(source, targetName) : [];
  return <section className={`panel ${styles.panel}`} aria-label="Build a prediction model"><header><p className="eyebrow">PREDICTION · PRIVATE · NO AI GUESSWORK</p><h2>Build a prediction model</h2><p>Pick what you want to predict. We train a simple model on most rows, then test it on {source?.holdout_percent ?? 20}% of rows it never saw, and tell you plainly whether it beats a simple guess.</p></header>
    {pending && <p role="status">{pending}</p>}{error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {!options ? <p>{error ? "Options are unavailable. Reload to try again." : "Loading your fields…"}</p> : !source || source.state !== "ready" || !source.targets.length ? <div className={styles.notice}><p>Confirm what your fields mean first. You need a yes/no (two-value) field or a numerical measure to predict.</p><button onClick={onReview}>Review data meanings</button></div> : !source.available ? <p>Prediction models are not available on this server.</p> : <form className={styles.form} onSubmit={create}>
      <fieldset disabled={Boolean(pending)}><legend>1. What do you want to predict?</legend><div className={styles.grid}>
        <WorkspaceSelect label="Field to predict" value={targetName} onValueChange={value => { setTarget(value); setInputs(previous => previous.filter(item => item !== value)); }} options={source.targets.map(item => ({ value: item.name, label: item.name, description: item.task === "classification" ? "Yes/no or two values" : "A number" }))} />
        <label>Model name<input maxLength={100} value={name} placeholder={`Predict ${targetName}`} onChange={event => setName(event.target.value)} /></label>
      </div></fieldset>
      <fieldset disabled={Boolean(pending)}><legend>2. Which fields may it use? (optional)</legend><p>Leave all unticked to use every suitable field. Fields that would give away the answer or act like IDs are switched off and explained.</p>
        <ul className={styles.history}>{choices.map(item => <li key={item.name}><label className="checkLabel"><input type="checkbox" disabled={item.disabled || (!inputs.includes(item.name) && inputs.length >= source.maximum_inputs)} checked={inputs.includes(item.name)} onChange={event => setInputs(previous => event.target.checked ? [...previous, item.name] : previous.filter(value => value !== item.name))} />{item.name}{item.disabled && <small> · not used: {item.excluded_reason}</small>}</label></li>)}</ul>
      </fieldset>
      <button disabled={Boolean(pending) || !targetName}>Build and test the model</button>
      <p>Uses up to {source.maximum_rows.toLocaleString()} rows (a fixed random sample of bigger files) and at most {source.maximum_inputs} fields.</p>
    </form>}
    <section className={styles.history}><h3>Your saved prediction models</h3>{saved.length ? <ul>{saved.map(item => <li key={item.id}><button disabled={Boolean(pending)} onClick={() => open(item.id)}>{item.name}</button></li>)}</ul> : <p>No saved models yet.</p>}</section>
    {selected && <PredictionResultCard key={selected.run.id} body={selected} />}
  </section>;
}

function PredictionResultCard({ body }: { body: Body }) {
  const result = body.run.result;
  const good = result.verdict.status === "beats_guess";
  return <section className={styles.result} aria-label="Prediction model result"><h3>{body.run.name}</h3>
    <p className={styles.notice} role="note"><strong>{good ? "Useful: " : "Don't use it: "}</strong>{result.verdict.text}</p>
    {result.warnings.length > 0 && <ul aria-label="Warnings">{result.warnings.map(item => <li key={item}><strong>Check: </strong>{item}</li>)}</ul>}
    <div className="tableWrap" tabIndex={0} role="region" aria-label="Scores on held-back rows"><table><caption>Scores on {result.coverage.holdout_rows.toLocaleString()} held-back rows</caption><thead><tr><th>Measure</th><th>This model</th><th>Simple guess</th></tr></thead><tbody>{metricRows(result).map(([label, model, guess]) => <tr key={label}><td>{label}</td><td>{model}</td><td>{guess}</td></tr>)}</tbody></table></div>
    {result.details.map(item => <p key={item}>{item}</p>)}
    <h4>Inputs most associated with the outcome</h4><p>These are associations in your data, not causes. Changing an input will not necessarily change the outcome.</p>
    <div className="tableWrap" tabIndex={0} role="region" aria-label="Top input weights"><table><thead><tr><th>Input</th><th>Weight</th><th>Direction</th><th>Meaning</th></tr></thead><tbody>{result.weights.map(item => <tr key={weightLabel(item)}><td>{weightLabel(item)}</td><td>{item.weight}</td><td>{item.direction}</td><td>{item.label}</td></tr>)}</tbody></table></div>
    <details><summary>How this was built</summary><dl className={styles.cards}><div><dt>Rows used</dt><dd>{result.coverage.used_rows.toLocaleString()}</dd></div><div><dt>Training rows</dt><dd>{result.coverage.training_rows.toLocaleString()}</dd></div><div><dt>Held-back rows</dt><dd>{result.coverage.holdout_rows.toLocaleString()}</dd></div></dl>
      <p>Method: {result.method.name}. {result.method.inputs}</p><p>Split: {result.method.split}</p>
      {result.coverage.missing_target_rows > 0 && <p>{result.coverage.missing_target_rows} rows without a recorded target were left out.</p>}
      {Object.keys(result.coverage.missing_inputs).length > 0 && <p>Missing values filled: {Object.entries(result.coverage.missing_inputs).map(([key, count]) => `${key} (${count})`).join(", ")}.</p>}
      <p>Inputs used: {result.inputs.join(", ")}.</p>
      {result.exclusions.length > 0 && <ul>{result.exclusions.map(item => <li key={item.column}>{item.column}: {item.reason}</li>)}</ul>}
    </details>
    <details><summary>Limits</summary><ul>{result.limitations.map(item => <li key={item}>{item}</li>)}</ul><p>Receipt: {body.run.evidence.query_id}. Result checksum: {body.run.evidence.result_checksum}.</p></details>
  </section>;
}
