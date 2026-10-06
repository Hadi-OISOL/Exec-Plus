/* Use case: Explains workspace adoption and retention from authorized aggregate evidence.
What it does: Displays server-defined UTC periods, mature cohorts and inactivity signals without exposing individual histories. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";

type Count = number | string;
export type ProductUsage = {
  version: string;
  workspace_id: string;
  as_of: string;
  period: { start: string; end: string; weeks: number; timezone: string };
  summary: {
    active_users: Count;
    active_members: Count;
    current_members: Count;
    activated_members: Count;
    never_active_members: Count;
    inactive_14d_members: Count;
  };
  weekly: {
    week_start: string;
    active_users: Count;
    actions: Count;
    complete: boolean;
  }[];
  features: { feature: string; actions: Count; users: Count }[];
  cohorts: {
    cohort_week: string;
    users: Count;
    cells: {
      week_offset: number;
      eligible: boolean;
      retained: Count | null;
      rate_percent: string | null;
    }[];
  }[];
  usage: {
    uploads: Count;
    storage_bytes: Count;
    queries_completed: Count;
    queries_failed: Count;
    forecasts_created: Count;
  };
  definitions: {
    activity: string;
    cohort: string;
    retention: string;
    activation: string;
    inactivity: string;
  };
  limitations: string[];
};

export function ProductUsagePanel({
  path,
  request,
}: {
  path: string;
  request: ApiRequest;
}) {
  const [weeks, setWeeks] = useState(8);
  const [generation, setGeneration] = useState(0);
  const [report, setReport] = useState<ProductUsage | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    request<ProductUsage>(`${path}?weeks=${weeks}`, {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) {
          setReport(value);
          setPending(false);
        }
      })
      .catch((cause) => {
        if (!controller.signal.aborted) {
          setError(
            cause instanceof Error
              ? cause.message
              : "Usage reporting is unavailable.",
          );
          setPending(false);
        }
      });
    return () => controller.abort();
  }, [path, request, weeks, generation]);
  function refresh() {
    setReport(null);
    setError("");
    setPending(true);
    setGeneration((value) => value + 1);
  }
  return (
    <section
      className="panel productUsage"
      aria-label="Product usage and retention"
    >
      <div className="sectionHeading">
        <div>
          <p className="eyebrow">PRODUCT ADOPTION</p>
          <h2>Usage & retention</h2>
        </div>
        <button type="button" onClick={refresh} disabled={pending}>
          Refresh report
        </button>
      </div>
      <p>
        Understand whether people return to useful work. These aggregate signals
        describe recorded activity; inactivity is not a prediction of customer
        churn.
      </p>
      <label className="operationsPeriod">
        Reporting window
        <select
          value={weeks}
          disabled={pending}
          onChange={(event) => {
            setWeeks(Number(event.target.value));
            setReport(null);
            setError("");
            setPending(true);
          }}
        >
          {[4, 8, 12].map((value) => (
            <option key={value} value={value}>
              {value} weeks
            </option>
          ))}
        </select>
      </label>
      {pending && <p role="status">Loading aggregate product activity…</p>}
      {error && (
        <p role="alert" className="errorNotice">
          {error}
        </p>
      )}
      {report && (
        <>
          <p className="operationsScope">
            {report.period.start.slice(0, 10)} to{" "}
            {report.period.end.slice(0, 10)} · {report.period.timezone}.
            Measured through{" "}
            {new Date(report.as_of)
              .toISOString()
              .replace("T", " ")
              .slice(0, 19)}{" "}
            UTC.
          </p>
          <div className="operationsMetrics">
            {[
              ["People active in this window", report.summary.active_users],
              ["Current members", report.summary.current_members],
              ["Active current members", report.summary.active_members],
              ["Activated current members", report.summary.activated_members],
              [
                "Never active current members",
                report.summary.never_active_members,
              ],
              ["Inactive for 14 days", report.summary.inactive_14d_members],
            ].map(([label, value]) => (
              <div key={label}>
                <span>{label}</span>
                <strong>{value.toLocaleString()}</strong>
              </div>
            ))}
          </div>
          <div className="operationsColumns">
            <section>
              <h3>Weekly activity</h3>
              <div
                className="tableScroll"
                tabIndex={0}
                role="region"
                aria-label="Weekly product activity"
              >
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Week beginning (UTC)</th>
                      <th scope="col">People</th>
                      <th scope="col">Actions</th>
                      <th scope="col">Window</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.weekly.map((week) => (
                      <tr key={week.week_start}>
                        <th scope="row">{week.week_start}</th>
                        <td>{week.active_users}</td>
                        <td>{week.actions}</td>
                        <td>{week.complete ? "Complete" : "In progress"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <section>
              <h3>Feature adoption</h3>
              {report.features.length ? (
                <div
                  className="tableScroll"
                  tabIndex={0}
                  role="region"
                  aria-label="Feature adoption"
                >
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Feature</th>
                        <th scope="col">People</th>
                        <th scope="col">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.features.map((item) => (
                        <tr key={item.feature}>
                          <th scope="row">
                            {item.feature.replaceAll("_", " ")}
                          </th>
                          <td>{item.users}</td>
                          <td>{item.actions}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p>No qualifying feature activity in this window.</p>
              )}
            </section>
          </div>
          <section>
            <h3>Weekly return cohorts</h3>
            <p>
              {report.definitions.cohort} {report.definitions.retention}
            </p>
            {report.cohorts.length ? (
              <div
                className="tableScroll"
                tabIndex={0}
                role="region"
                aria-label="Weekly retention cohorts"
              >
                <table className="cohortTable">
                  <thead>
                    <tr>
                      <th scope="col">First active week</th>
                      <th scope="col">People</th>
                      {Array.from(
                        { length: report.period.weeks },
                        (_, index) => (
                          <th key={index} scope="col">
                            Week {index}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {report.cohorts.map((cohort) => (
                      <tr key={cohort.cohort_week}>
                        <th scope="row">{cohort.cohort_week}</th>
                        <td>{cohort.users}</td>
                        {cohort.cells.map((cell) => (
                          <td
                            key={cell.week_offset}
                            className={
                              cell.eligible ? "cohortMature" : "cohortPending"
                            }
                          >
                            {cell.eligible && cell.rate_percent !== null ? (
                              <>
                                <strong>{cell.rate_percent}%</strong>
                                <small>
                                  {cell.retained} / {cohort.users} people
                                </small>
                              </>
                            ) : (
                              "Not mature"
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p>No qualifying first-use cohorts in this window.</p>
            )}
            <p>
              “Not mature” means the full return week has not finished. It is
              not a zero retention result.
            </p>
          </section>
          <details>
            <summary>Resource counts & reporting definitions</summary>
            <dl className="operationsDefinitions">
              {Object.entries(report.usage).map(([key, value]) => (
                <div key={key}>
                  <dt>{key.replaceAll("_", " ")}</dt>
                  <dd>{value.toLocaleString()}</dd>
                </div>
              ))}
              {Object.entries(report.definitions).map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </details>
          <ul className="studyLimitations">
            {report.limitations.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
