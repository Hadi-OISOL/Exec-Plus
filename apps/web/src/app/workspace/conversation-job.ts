/* Use case: Defines the browser contract for durable conversation work.
What it does: Interprets server-owned states and ordered activity without inventing progress. */

export type ConversationJob = {
  id: string;
  workspace_id: string;
  thread_id: string;
  turn_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  attempts: number;
  current_stage: string | null;
  cancel_requested: boolean;
  failure_code?: string | null;
};

export type JobEvent = {
  sequence: number;
  stage: string;
  status: "started" | "completed" | "failed" | "cancelled";
  created_at: string;
};

export type JobEvents = { events: JobEvent[]; next_sequence: number };

const stages: Record<string, string> = {
  queued: "Waiting for a worker",
  authorizing: "Checking access",
  checking_source: "Checking the selected source",
  planning: "Interpreting your question",
  validating_plan: "Validating the analysis plan",
  executing_query: "Running a read-only calculation",
  retrieving_documents: "Finding supporting document passages",
  verifying_evidence: "Verifying the answer and its sources",
  finished: "Finishing the request",
};

export function stageLabel(stage: string | null): string {
  return (stage && stages[stage]) || "Waiting for a recorded activity update";
}

export function isTerminalJob(job: ConversationJob): boolean {
  return ["succeeded", "failed", "cancelled", "expired"].includes(job.status);
}

export function jobHeadline(job: ConversationJob): string {
  if (job.status === "succeeded") return "Request completed";
  if (job.status === "failed") return "Request failed";
  if (job.status === "cancelled") return "Request cancelled";
  if (job.status === "expired") return "Request expired";
  if (job.cancel_requested || job.status === "cancelling")
    return "Cancellation requested — waiting for the worker";
  if (job.status === "queued") return stages.queued;
  return stageLabel(job.current_stage);
}

export function mergeJobEvents(
  previous: JobEvent[],
  incoming: JobEvent[],
): JobEvent[] {
  const bySequence = new Map(previous.map((event) => [event.sequence, event]));
  for (const event of incoming)
    if (!bySequence.has(event.sequence)) bySequence.set(event.sequence, event);
  return [...bySequence.values()].sort(
    (left, right) => left.sequence - right.sequence,
  );
}

export function reconcileJob(
  previous: ConversationJob | undefined,
  incoming: ConversationJob,
): ConversationJob {
  if (!previous || previous.id !== incoming.id) return incoming;
  if (
    isTerminalJob(previous) ||
    Date.parse(previous.updated_at) > Date.parse(incoming.updated_at)
  )
    return previous;
  return previous.cancel_requested
    ? { ...incoming, cancel_requested: true }
    : incoming;
}

export function pollPause(
  signal: AbortSignal,
  milliseconds = 1000,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      signal.removeEventListener("abort", abort);
      reject(new DOMException("Activity polling detached", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, milliseconds);
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) abort();
  });
}
