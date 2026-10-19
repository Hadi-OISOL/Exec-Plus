/* Use case: Makes real server work inspectable while a question is running.
What it does: Displays recorded actions and confirmed states, with explicit cancellation and accessible updates. */

import { jobHeadline, jobDetail, isTerminalJob, stageLabel, activityStages, eventStatusLabel } from "./conversation-job";
import { RequestProgress } from "./request-progress";
import type { ConversationJob, JobEvent } from "./conversation-job";

export function ConversationActivity({
  job,
  events,
  expert,
  cancelPending = false,
  error = "",
  onCancel,
}: {
  job: ConversationJob;
  events: JobEvent[];
  expert: boolean;
  cancelPending?: boolean;
  error?: string;
  onCancel?: () => void;
}) {
  const terminal = isTerminalJob(job);
  const stages = activityStages(events);
  const cancelling =
    cancelPending || job.cancel_requested || job.status === "cancelling";
  return (
    <section
      className="conversationActivity"
      aria-label="Recorded request activity"
      tabIndex={onCancel ? 0 : undefined}
    >
      <div className="activityHeading">
        {!terminal ? <RequestProgress
          title={cancelPending && !job.cancel_requested ? "Sending cancellation request…" : jobHeadline(job)}
          detail={jobDetail(job)}
          paused={cancelling}
        /> : <div>
          <span className="activityEyebrow">
            {terminal ? "Recorded activity" : "Current activity"}
          </span>
          <p
            role={onCancel ? "status" : undefined}
            aria-atomic={onCancel ? true : undefined}
          >
            {!terminal && (
              <span className="activityIndicator" aria-hidden="true" />
            )}
            {cancelPending && !job.cancel_requested && !terminal
              ? "Sending cancellation request…"
              : jobHeadline(job)}
          </p>
        </div>}
        {!terminal && onCancel && (
          <button
            type="button"
            className="quietButton"
            disabled={cancelling}
            onClick={onCancel}
          >
            {cancelling ? "Cancellation requested" : "Cancel request"}
          </button>
        )}
      </div>
      {error && (
        <p className="errorNotice" role="alert">
          {error}
        </p>
      )}
      {!expert && terminal && stages.length > 0 && (
        <ol className="activityStages" aria-label="Recorded work stages">
          {stages.slice(-4).map(event => (
            <li key={event.stage} data-status={event.status}>
              <span className="activityStageMark" aria-hidden="true">{event.status === "completed" ? "✓" : event.status === "failed" ? "!" : "•"}</span>
              <span>{stageLabel(event.stage)}</span>
              <span className="activityEventStatus">{eventStatusLabel(event.status)}</span>
            </li>
          ))}
        </ol>
      )}
      <details className="recordedActions">
        <summary>
          Recorded actions{events.length ? ` (${events.length})` : ""}
        </summary>
        <p>These recorded steps show what ExecPlus did with your request.</p>
        {events.length ? (
          <ol>
            {events.map((event) => (
              <li key={event.sequence}>
                <span>{stageLabel(event.stage)}</span>
                <span className="activityEventStatus">{eventStatusLabel(event.status)}</span>
                <time dateTime={event.created_at}>
                  {new Date(event.created_at).toLocaleTimeString()}
                </time>
              </li>
            ))}
          </ol>
        ) : (
          <p>
            {terminal
              ? "No recorded actions are available."
              : "Waiting for activity updates."}
          </p>
        )}
        {expert && (
          <p className="activityIdentifiers">
            Request: {job.id} · Attempts: {job.attempts}
          </p>
        )}
      </details>
    </section>
  );
}
