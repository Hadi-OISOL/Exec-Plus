/* Use case: Greets a new person with a short, skippable questionnaire before the workspace opens.
What it does: Asks one question per screen on a paper card over the green field, slides each screen in, keeps drafts across Back/Skip, saves answers once on
finish or "Skip for now", and hands the saved profile back to the workspace. */

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "../profile-panel";
import { hasAnswer, profilePayload, progressLabel, toggleChoice } from "./onboarding-values";
import type { Answer, ProfileView, Question } from "./onboarding-values";
import "../../site/site-tokens.css";
import styles from "./onboarding-flow.module.css";

const check = <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5l3 3 7-7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>;

export function OnboardingFlow({ request, initial, onDone }: { request: ApiRequest; initial: ProfileView; onDone: (profile: ProfileView) => void }) {
  const questions = initial.questionnaire;
  const [version, setVersion] = useState(initial.version);
  const [step, setStep] = useState(-1);
  const [name, setName] = useState(initial.preferred_name);
  const [answers, setAnswers] = useState<Record<string, Answer>>(initial.answers);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<ProfileView | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const question: Question | undefined = questions[step];
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, [step]);

  async function save(status: "completed" | "skipped") {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const profile = await request<ProfileView>("/me/profile", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(profilePayload(version, name, answers, status)) });
      if (status === "skipped") onDone(profile);
      else { setSaved(profile); setStep(questions.length); }
    } catch (cause) {
      if ((cause as { status?: number }).status === 409) {
        try { setVersion((await request<ProfileView>("/me/profile")).version); } catch { setVersion(version); }
        setError("Your profile changed in another tab. Your answers here are kept; press the button again to save them.");
      } else setError("Could not save right now. Your answers are still here; try again or skip for now.");
    } finally { setBusy(false); }
  }
  function next() {
    if (step + 1 < questions.length) setStep(step + 1);
    else void save("completed");
  }
  function submit(event: FormEvent) { event.preventDefault(); if (!busy) next(); }
  const setAnswer = (id: string, value: Answer) => setAnswers(current => ({ ...current, [id]: value }));

  return <main className={styles.screen} aria-label="Getting to know you">
    <form className={styles.card} onSubmit={submit}>
      <div className={styles.brand}><span aria-hidden="true">O</span><span>Osalytix</span></div>
      <div key={step} className={styles.slide}>
      {step === -1 && <>
        <h1 ref={heading} tabIndex={-1}>Hi! To give you better answers, let&apos;s get to know you.</h1>
        <p>Takes about 2 minutes. Mostly taps, very little typing. You can skip any question, and change your answers later under My memory.</p>
        <p className={styles.hint}>Your answers only shape how Osalytix explains things. They never change calculations, filters or who can see data.</p>
        <div className={styles.actions}>
          <button type="button" className={styles.quiet} disabled={busy} onClick={() => void save("skipped")}>Skip for now</button>
          <button type="submit" className={styles.primary}>Let&apos;s start</button>
        </div>
      </>}
      {question && <>
        <div className={styles.progress}><span>Question {progressLabel(step, questions.length)}</span><div className={styles.bar} aria-hidden="true"><span style={{ width: `${((step + 1) / questions.length) * 100}%` }} /></div></div>
        <h1 ref={heading} tabIndex={-1} id="onboarding-question">{question.prompt}</h1>
        {question.hint && <p className={styles.hint}>{question.hint}</p>}
        {question.kind === "text" && (
          <input className={styles.text} aria-labelledby="onboarding-question" autoFocus maxLength={120} value={question.id === "preferred_name" ? name : (answers[question.id] as string | undefined) ?? ""}
            onChange={event => question.id === "preferred_name" ? setName(event.target.value) : setAnswer(question.id, event.target.value)} disabled={busy} />
        )}
        {question.kind !== "text" && (
          <div className={styles.choices} role={question.kind === "single" ? "radiogroup" : "group"} aria-labelledby="onboarding-question">
            {question.options.map(option => {
              const current = answers[question.id];
              const selected = question.kind === "single" ? current === option : Array.isArray(current) && current.includes(option);
              return <button key={option} type="button" className={styles.choice} role={question.kind === "single" ? "radio" : "checkbox"} aria-checked={selected} disabled={busy}
                onClick={() => setAnswer(question.id, question.kind === "single" ? (selected ? "" : option) : toggleChoice(current, option))}>{selected && check}{option}</button>;
            })}
          </div>
        )}
        {error && <p role="alert" className={styles.error}>{error}</p>}
        <div className={styles.actions}>
          <button type="button" disabled={busy} onClick={() => setStep(step - 1)}>Back</button>
          <button type="button" className={styles.quiet} disabled={busy} onClick={() => void save("skipped")}>Skip for now</button>
          {!(question.id === "preferred_name" ? name.trim() : hasAnswer(answers[question.id])) && step + 1 < questions.length && <button type="button" className={styles.quiet} disabled={busy} onClick={next}>Skip this question</button>}
          <button type="submit" className={styles.primary} disabled={busy}>{busy ? "Saving…" : step + 1 < questions.length ? "Continue" : "Finish"}</button>
        </div>
      </>}
      {step === questions.length && saved && <>
        <h1 ref={heading} tabIndex={-1}>Thanks{saved.preferred_name ? `, ${saved.preferred_name}` : ""}! I&apos;ll keep this in mind.</h1>
        <p>New explanations and suggestions can use these preferences. Numbers always come from your data, never from this profile.</p>
        <div className={styles.actions}><button type="button" className={styles.primary} onClick={() => onDone(saved)}>Continue to workspace</button></div>
      </>}
      </div>
    </form>
  </main>;
}
