/* Use case: Lets expert users inspect source capabilities and recorded quality checks.
What it does: Loads permission-checked metadata on demand and distinguishes observations from heuristics. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";

type Artifact = {
  reference: { kind: string; id: string };
  name: string;
  method_version: string;
  checksum: string | null;
  checksum_scope: string;
  capabilities: string[];
  availability: string;
  limitations: string[];
};
type Quality = {
  profile_version: string;
  findings: {
    code: string;
    category: "observed" | "heuristic";
    count: number;
    denominator: number;
    column: string | null;
    message: string;
  }[];
  limitations: string[];
};

export function SourceDetails({
  root,
  request,
}: {
  root: string;
  request: ApiRequest;
}) {
  const [open, setOpen] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [details, setDetails] = useState<{
    artifacts: Artifact[];
    quality: Quality;
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    Promise.all([
      request<{ artifacts: Artifact[] }>(`${root}/artifacts`, {
        signal: controller.signal,
      }),
      request<Quality>(`${root}/quality`, { signal: controller.signal }),
    ])
      .then(([artifacts, quality]) => {
        if (!controller.signal.aborted)
          setDetails({ artifacts: artifacts.artifacts, quality });
      })
      .catch((cause) => {
        if (!controller.signal.aborted)
          setError(
            cause instanceof Error
              ? cause.message
              : "Source details are unavailable.",
          );
      });
    return () => controller.abort();
  }, [root, request, open, attempt]);
  return (
    <details
      className="workspaceDisclosure sourceDetails"
      open={open}
      onToggle={(event) => {
        if (event.target !== event.currentTarget) return;
        setOpen(event.currentTarget.open);
        setError("");
        setDetails(null);
      }}
    >
      <summary>
        Source capabilities & recorded quality
        <span>
          Supported operations, artifact versions and inspectable data checks
        </span>
      </summary>
      {open && (
        <div className="expandedWorkspaceTools">
          {error ? (
            <>
              <p role="alert">{error}</p>
              <button
                type="button"
                onClick={() => {
                  setError("");
                  setAttempt((value) => value + 1);
                }}
              >
                Retry source details
              </button>
            </>
          ) : !details ? (
            <p role="status">Loading recorded source details…</p>
          ) : (
            <>
              <p>
                These are saved descriptions and checks. Calculations and replay
                verify the source before returning an answer.
              </p>
              <div className="sourceArtifactList">
                {details.artifacts.map((artifact) => (
                  <article
                    key={`${artifact.reference.kind}:${artifact.reference.id}`}
                  >
                    <h3>{artifact.reference.kind.replaceAll("_", " ")}</h3>
                    <p>{artifact.name}</p>
                    <p>
                      Supported operations:{" "}
                      {artifact.capabilities.join(", ") || "None"}.
                    </p>
                    <details>
                      <summary>Version & provenance</summary>
                      <p>Method: {artifact.method_version}</p>
                      <p>Artifact: {artifact.reference.id}</p>
                      {artifact.checksum && (
                        <p>
                          Checksum ({artifact.checksum_scope}):{" "}
                          {artifact.checksum}
                        </p>
                      )}
                      {artifact.limitations.map((limitation) => (
                        <p key={limitation}>{limitation}</p>
                      ))}
                    </details>
                  </article>
                ))}
              </div>
              <h3>Recorded quality checks</h3>
              <p>
                Profile version: {details.quality.profile_version}. Suggested
                patterns are not confirmed business rules.
              </p>
              {details.quality.findings.length ? (
                <details>
                  <summary>
                    Inspect {details.quality.findings.length} recorded findings
                  </summary>
                  <ul className="sourceQualityList">
                    {details.quality.findings.map((finding, index) => (
                      <li key={`${finding.code}:${finding.column}:${index}`}>
                        <strong>
                          {finding.category === "observed"
                            ? "Observed"
                            : "Suggested pattern"}
                          {finding.column ? ` · ${finding.column}` : ""}
                        </strong>
                        <p>{finding.message}</p>
                        <span>
                          {finding.count.toLocaleString()} of{" "}
                          {finding.denominator.toLocaleString()}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : (
                <p>No findings were recorded by these checks.</p>
              )}
              {details.quality.limitations.map((limitation) => (
                <p key={limitation}>{limitation}</p>
              ))}
            </>
          )}
        </div>
      )}
    </details>
  );
}
