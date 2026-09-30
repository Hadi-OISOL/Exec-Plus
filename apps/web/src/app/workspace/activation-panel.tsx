/* Use case: Guides users through evidence-based insights and safe product feedback.
What it does: Shows ranked observations, server-managed next steps and fixed feedback categories. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";

type Insight = {
  rank: number;
  text: string;
  next_step: string;
  evidence: { revision_id: string };
};
export function ActivationPanel({
  root,
  request,
}: {
  root: string;
  request: ApiRequest;
}) {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [steps, setSteps] = useState<{ id: string; complete: boolean }[]>([]);
  const [message, setMessage] = useState("");
  const workspace = root.split("/datasets/")[0];
  useEffect(() => {
    let active = true;
    Promise.all([
      request<Insight[]>(`${root}/insights`),
      request<{ checklist: { id: string; complete: boolean }[] }>(
        `${workspace}/onboarding`,
      ),
    ])
      .then(([facts, overview]) => {
        if (active) {
          setInsights(facts);
          setSteps(overview.checklist);
        }
      })
      .catch((error) => {
        if (active) setMessage(error.message);
      });
    return () => {
      active = false;
    };
  }, [root, workspace, request]);
  return (
    <section
      className="panel insightsPanel"
      aria-label="Insights and next steps"
    >
      <div className="sectionHeading">
        <h2>Worth a closer look</h2>
        <span>From your data profile</span>
      </div>
      <ol className="insightList">
        {insights.map((fact) => (
          <li key={fact.rank}>
            <strong>{fact.text}</strong>
            <p>{fact.next_step}</p>
            <details>
              <summary>Source revision</summary>
              <small>{fact.evidence.revision_id}</small>
            </details>
          </li>
        ))}
      </ol>
      <details className="feedbackDetails">
        <summary>Next steps & product feedback</summary>
        <ul>
          {steps.map((step) => (
            <li key={step.id}>
              {step.complete ? "Done" : "Next"}: {step.id.replaceAll("_", " ")}
            </li>
          ))}
        </ul>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            try {
              await request(`${workspace}/feedback`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  feature: form.get("feature"),
                  category: form.get("category"),
                  rating: Number(form.get("rating")),
                }),
              });
              setMessage("Feedback recorded without dataset values.");
            } catch (cause) {
              setMessage(
                cause instanceof Error
                  ? cause.message
                  : "Could not record feedback.",
              );
            }
          }}
        >
          <label>
            Feedback feature
            <select name="feature">
              {[
                "profile",
                "dashboard",
                "question",
                "knowledge",
                "report",
                "onboarding",
              ].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Feedback rating
            <select name="rating">
              {[5, 4, 3, 2, 1].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Feedback category
            <select name="category">
              {[
                "helpful",
                "confusing",
                "incorrect",
                "slow",
                "missing_feature",
              ].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <button>Send product feedback</button>
        </form>
        {message && <p>{message}</p>}
      </details>
    </section>
  );
}
