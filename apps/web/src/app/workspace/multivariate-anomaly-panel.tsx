/* Use case: Reviews unusual combinations against a user-selected reference group.
What it does: Keeps exact private records, fitted references, downloads and human feedback together. */
"use client";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import type { AnalysisBody, AnalysisOptions, AnalysisSummary } from "./decision-types";
import type { ExactFraction } from "./calendar-anomaly-types";
import { fractionText } from "./calendar-anomaly-types";
import { AnswerVisualization } from "./answer-visualization";
import { ResultExportActions } from "./result-export-actions";
import { WorkspaceSelect } from "./workspace-select";
import { CalibrationNote, FalseAlarmTargetSelect } from "./false-alarm-target";
import type { DetectorCalibration, FalseAlarmTarget } from "./false-alarm-target";
import styles from "./calendar-anomaly-panel.module.css";

export const MULTIVARIATE_METHOD = "reference-mahalanobis-squared-v1";
export const MULTIVARIATE_CALIBRATED_METHOD = "reference-mahalanobis-calibrated-v1";
type RecordValue = { record_id: string; cohort: string; phase: string; values: Record<string,string>; squared_distance: ExactFraction | null; flagged: boolean | null };
type Result = { metrics: string[]; reference_count: number; evaluated_records: number; flagged_records: number; reference_label: string; comparison_label: string; threshold: ExactFraction; calibration?: DetectorCalibration; records: RecordValue[]; findings: (RecordValue & {id:string})[]; limitations: string[]; reference: { means: ExactFraction[]; scales: ExactFraction[]; normalized_sample_covariance: ExactFraction[][]; normalized_inverse: ExactFraction[][]; infinity_condition: ExactFraction; covariance_denominator: number } };
type Body = Omit<AnalysisBody,"run"> & {run: AnalysisSummary & {result:Result; evidence:AnalysisBody["run"]["evidence"]}};
const post = (body:object):RequestInit => ({method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});

export function MultivariateAnomalyPanel({root,request,onReview}:{root:string;request:ApiRequest;onReview:()=>void}) {
  const datasetRoot=root.split("/uploads/")[0], runsRoot=`${datasetRoot}/decision-analysis`;
  const [options,setOptions]=useState<AnalysisOptions|null>(null);
  const [history,setHistory]=useState<AnalysisSummary[]>([]);
  const [selected,setSelected]=useState<Body|null>(null);
  const [metrics,setMetrics]=useState<string[]>([]);
  const [identifier,setIdentifier]=useState(""); const [group,setGroup]=useState("");
  const [reference,setReference]=useState(""); const [comparison,setComparison]=useState("");
  const [threshold,setThreshold]=useState("9"); const [target,setTarget]=useState<FalseAlarmTarget>(""); const [name,setName]=useState("");
  const [confirmed,setConfirmed]=useState(false);
  const [pending,setPending]=useState(""); const [error,setError]=useState(""); const [message,setMessage]=useState("");
  const operation=useRef<AbortController|null>(null);
  const source=options?.multivariate_anomalies;
  const idColumn=identifier||source?.identifiers[0]||"", groupColumn=group||source?.groups[0]||"";
  function clearProtected() {setOptions(null);setHistory([]);setSelected(null);setConfirmed(false);}
  useEffect(()=>{
    const controller=new AbortController();
    Promise.all([request<AnalysisOptions>(`${root}/decision-analysis/options`,{signal:controller.signal}),request<AnalysisSummary[]>(runsRoot,{signal:controller.signal})])
      .then(([value,saved])=>{if(!controller.signal.aborted){setOptions(value);setHistory(saved);}})
      .catch(cause=>{if(!controller.signal.aborted){setOptions(null);setHistory([]);setSelected(null);setConfirmed(false);setError(cause instanceof Error?cause.message:"Could not load analysis options.");}});
    return()=>{controller.abort();operation.current?.abort();};
  },[root,runsRoot,request]);
  async function work(label:string,action:(signal:AbortSignal)=>Promise<void>) {
    if(operation.current)return;
    const controller=new AbortController();operation.current=controller;setPending(label);setError("");setMessage("");
    try {await action(controller.signal);}
    catch(cause){if(!controller.signal.aborted){clearProtected();setError(cause instanceof Error?cause.message:"The analysis could not complete.");}}
    finally{if(!controller.signal.aborted)setPending("");if(operation.current===controller)operation.current=null;}
  }
  async function reload(){await work("Checking access and saved results…",async signal=>{
    const [value,saved]=await Promise.all([request<AnalysisOptions>(`${root}/decision-analysis/options`,{signal}),request<AnalysisSummary[]>(runsRoot,{signal})]);
    if(!signal.aborted){setOptions(value);setHistory(saved);setSelected(null);setConfirmed(false);}
  });}
  async function create(event:FormEvent){event.preventDefault();if(!options||!confirmed)return;
    await work("Checking complete records and the earlier reference…",async signal=>{
      const value=await request<Body>(`${root}/decision-analysis/multivariate-anomalies`,{...post({name:name.trim()||"Unusual combinations",model:target?MULTIVARIATE_CALIBRATED_METHOD:MULTIVARIATE_METHOD,...(target?{target_false_alarm_rate:target}:{}),revision_id:options.revision_id,understanding_id:options.understanding_id,metrics,identifier_column:idColumn,cohort_column:groupColumn,reference_label:reference,comparison_label:comparison,threshold:target?"9":threshold,filters:[]}),signal});
      if(signal.aborted)return;
      setSelected(value);setConfirmed(false);setMessage("Saved privately. Source records are unchanged.");
      try {const saved=await request<AnalysisSummary[]>(runsRoot,{signal});if(!signal.aborted)setHistory(saved);}
      catch {if(!signal.aborted)throw new Error("Your result was saved, but history could not reload. Use Reload saved results; do not repeat the calculation.");}
    });
  }
  async function open(id:string){await work("Replaying the original evidence…",async signal=>{
    const value=await request<Body>(`${runsRoot}/${id}`,{signal});if(!signal.aborted){setSelected(value);setMessage("The original result and source evidence were verified.");}
  });}
  async function review(target:string,status:string,note:string){if(!selected)return;await work("Saving your private review…",async signal=>{
    const value=await request<Body>(`${runsRoot}/${selected.run.id}/reviews`,{...post({target,status,note,expected_version:selected.review_version}),signal});if(!signal.aborted){setSelected(value);setMessage("Review saved. The original model and records are unchanged.");}
  });}
  const saved=history.filter(item=>item.method_version===MULTIVARIATE_METHOD||item.method_version===MULTIVARIATE_CALIBRATED_METHOD);
  return <section className={`panel ${styles.panel}`} aria-label="Unusual combinations"><header><p className="eyebrow">OBSERVED COMBINATIONS · PRIVATE REVIEW</p><h2>Which records look different together?</h2><p>Choose a reference group you trust, then compare another group using two to four measures. A high distance asks for review; it does not prove an error or a cause.</p></header>
    {pending&&<p role="status">{pending}</p>}{error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    {!options?<p>{error?"Options are unavailable. Reload to check access again.":"Loading available fields…"}</p>:options.state!=="ready"||!source?.identifiers.length||!source.groups.length?<div className={styles.notice}><p>Confirm a unique record identifier, a group field and fixed units for at least two measures first.</p><button onClick={onReview}>Review data meanings</button></div>:<form className={styles.form} onSubmit={create} onChange={event=>{if(!(event.target instanceof HTMLInputElement)||event.target.name!=="comparison-confirmation")setConfirmed(false);}}>
      <fieldset disabled={Boolean(pending)}><legend>1. Choose the records and measures</legend><div className={styles.grid}>
        <label>Analysis name<input maxLength={100} value={name} onChange={event=>setName(event.target.value)} /></label>
        <WorkspaceSelect label="Unique record identifier" value={idColumn} onValueChange={value=>{setIdentifier(value);setConfirmed(false);}} options={source.identifiers.map(value=>({value,label:value}))} />
        <WorkspaceSelect label="Group field" value={groupColumn} onValueChange={value=>{setGroup(value);setConfirmed(false);}} options={source.groups.map(value=>({value,label:value}))} />
      </div><p>Pick two to four measures. Each must use the same required population filters; missing values and repeated identifiers are refused.</p><div className={styles.grid}>{options.metrics.map(item=><label className="checkLabel" key={item.name}><input type="checkbox" checked={metrics.includes(item.name)} disabled={!metrics.includes(item.name)&&metrics.length>=4} onChange={event=>setMetrics(previous=>event.target.checked?[...previous,item.name]:previous.filter(value=>value!==item.name))} />{item.name} · {item.unit}</label>)}</div></fieldset>
      <fieldset disabled={Boolean(pending)}><legend>2. Name the two groups</legend><div className={styles.grid}><label>Reference group equals<input required maxLength={200} value={reference} onChange={event=>setReference(event.target.value)} /></label><label>Comparison group equals<input required maxLength={200} value={comparison} onChange={event=>setComparison(event.target.value)} /></label><FalseAlarmTargetSelect value={target} onChange={setTarget} /><label>Squared-distance review threshold<input required inputMode="decimal" value={target?"":threshold} disabled={Boolean(target)} placeholder={target?"Set by the target":undefined} onChange={event=>setThreshold(event.target.value)} /></label></div><p>Use exact group names. The reference needs 30–500 complete records; both groups together may contain at most 1,000. Other groups are excluded. A threshold of 9 is a review choice, not a probability.</p><label className="checkLabel"><input name="comparison-confirmation" type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)} required />I chose this reference for these measures. Flags are comparisons, not confirmed errors.</label></fieldset>
      <button disabled={Boolean(pending)||!confirmed||metrics.length<2||reference===comparison}>Calculate and save privately</button>
    </form>}
    <section className={styles.history}><h3>Your saved combination checks</h3><button disabled={Boolean(pending)} onClick={reload}>Reload saved results</button>{saved.length?<ul>{saved.map(item=><li key={item.id}><button disabled={Boolean(pending)} onClick={()=>open(item.id)}>{item.name}</button></li>)}</ul>:<p>No saved combination checks yet.</p>}</section>
    {selected&&<MultivariateResult key={selected.run.id} body={selected} datasetRoot={datasetRoot} pending={Boolean(pending)} onReplay={()=>open(selected.run.id)} onReview={review} />}
  </section>;
}

function MultivariateResult({body,datasetRoot,pending,onReplay,onReview}:{body:Body;datasetRoot:string;pending:boolean;onReplay:()=>void;onReview:(target:string,status:string,note:string)=>Promise<void>}) {
  const result=body.run.result;
  const [target,setTarget]=useState("");const [status,setStatus]=useState("investigate");const [note,setNote]=useState("");
  const compared=result.records.filter(row=>row.phase==="comparison");const finding=target||result.findings[0]?.id||"";
  return <section className={styles.result} aria-label="Saved combination result"><h3>{body.run.name}</h3><p>{body.current?"Current source and meanings.":"Historical source or meanings; review current data before acting."}</p>
    <ResultExportActions path={`${datasetRoot}/analyses/${body.run.id}/export?kind=anomaly`} charts={["Observed combination distances"]} /><button disabled={pending} onClick={onReplay}>Replay original combination evidence</button>
    <dl className={styles.cards}><div><dt>Reference records</dt><dd>{result.reference_count}</dd></div><div><dt>Comparison records</dt><dd>{result.evaluated_records}</dd></div><div><dt>Records to review</dt><dd>{result.flagged_records}</dd></div></dl>
    <p className={styles.notice}>Only “{result.reference_label}” fitted the reference. “{result.comparison_label}” records are scored against it. Larger squared distances are more unusual under this model; they are not probabilities.</p>
    <AnswerVisualization title="Observed combination distances" columns={["Record","Squared distance (display)","Flagged"]} rows={compared.map(row=>[row.record_id,row.squared_distance?.display??null,row.flagged])} />
    <p>Declared threshold: {fractionText(result.threshold)}. Charts use decimal displays; exact fractions determine flags.</p><CalibrationNote value={result.calibration} />
    <details><summary>Every selected record and exact distance</summary><AnswerVisualization title="Complete combination evidence" chartAllowed={false} initialMode="table" columns={["Record","Group",...result.metrics.map(name=>`${name} (${body.run.evidence.units[name]})`),"Squared distance (exact)","Flagged"]} rows={result.records.map(row=>[row.record_id,row.cohort,...result.metrics.map(name=>row.values[name]),row.squared_distance?fractionText(row.squared_distance):null,row.flagged])} /></details>
    <details><summary>How the reference was calculated</summary><p>Sample covariance uses {result.reference.covariance_denominator} as its denominator. Scaling preserves each measure’s unit separately.</p><AnswerVisualization title="Reference means and scales" chartAllowed={false} initialMode="table" columns={["Measure","Mean","Normalization scale"]} rows={result.metrics.map((name,index)=>[name,fractionText(result.reference.means[index]),fractionText(result.reference.scales[index])])} /><p>Normalized covariance condition: {fractionText(result.reference.infinity_condition)}. Values over 100,000,000 are refused.</p><div className="tableWrap" tabIndex={0} role="region" aria-label="Exact covariance matrices"><pre>{JSON.stringify({covariance:result.reference.normalized_sample_covariance,inverse:result.reference.normalized_inverse},null,2)}</pre></div></details>
    <h4>Review the findings</h4>{result.findings.length?<form className={styles.form} onSubmit={async event=>{event.preventDefault();await onReview(finding,status,note);}}><div className={styles.grid}><WorkspaceSelect label="Record to review" value={finding} onValueChange={setTarget} options={result.findings.map(row=>({value:row.id,label:row.record_id}))} /><WorkspaceSelect label="Review decision" value={status} onValueChange={setStatus} options={[{value:"investigate",label:"Investigate"},{value:"expected",label:"Expected"},{value:"data_issue",label:"Data issue"},{value:"dismissed",label:"Dismiss"}]} /></div><label>Reason<textarea required maxLength={1000} value={note} onChange={event=>setNote(event.target.value)} /></label><button disabled={pending}>Save private review</button></form>:<p>No records met this rule. Other unusual patterns may still exist.</p>}
    <details><summary>Review history ({body.reviews.length})</summary>{body.reviews.map(item=><p key={item.id}>{item.sequence}. {item.status} · {item.note}</p>)}</details><details><summary>Assumptions, limits and source evidence</summary><ul>{result.limitations.map(item=><li key={item}>{item}</li>)}</ul><p>Receipt: {body.run.evidence.query_id}. Result checksum: {body.run.evidence.result_checksum}.</p></details>
  </section>;
}
