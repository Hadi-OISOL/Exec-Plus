/* Use case: Makes the path from an uploaded file to a verified answer visible.
What it does: Provides accessible navigation icons, a live schema diagram and bounded record tables. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";

export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, string> = {
    overview: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
    data: "M4 4h16v16H4z M4 9h16 M4 14h16 M10 4v16",
    prepare: "M4 7h16 M4 17h16 M8 4v6 M16 14v6",
    documents: "M6 3h9l4 4v14H6z M14 3v5h5 M9 12h7 M9 16h5",
    saved: "M6 3h12v18l-6-4-6 4z",
    forecasts: "M3 20V4 M3 20h18 M5 16l5-6 4 3 7-9 M17 4h4v4",
    audit: "M6 3h12v18H6z M9 7h6 M9 11h6 M9 15h3",
    support:
      "M4 13v-1a8 8 0 0 1 16 0v5h-4v-6h4 M4 11h4v6H4z M20 17a4 4 0 0 1-4 4h-4",
    admin: "M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6z M9 12l2 2 4-4",
    usage: "M3 20h18 M6 17v-5 M12 17V4 M18 17V8",
    team: "M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2 M16 4a4 4 0 0 1 0 8 M21 21v-2a4 4 0 0 0-3-4 M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
    chat: "M21 11a9 9 0 0 1-9 9H4l-2 2V11a9 9 0 0 1 19 0 M7 10h10 M7 14h6",
    upload: "M12 16V3 M7 8l5-5 5 5 M4 15v6h16v-6",
    arrow: "M5 12h14 M13 6l6 6-6 6",
    check: "M4 12l5 5L20 6",
    sparkle: "M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z",
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name] ?? paths.overview} />
    </svg>
  );
}

type Column = { name: string; type: string; role: string };
export type Cell = string | number | boolean | null;
export type Records = {
  columns: string[];
  rows: Cell[][];
  records_analyzed: number;
  matched_records?: number | null;
};

export function RecordTable({
  data,
  countLabel = "source records",
}: {
  data: Records;
  countLabel?: string;
}) {
  const [page, setPage] = useState(0);
  const start = page * 10;
  const visible = data.rows.slice(start, start + 10);
  return (
    <div className="recordResult">
      <div
        className="tableScroll"
        tabIndex={0}
        role="region"
        aria-label="Result records"
      >
        <table>
          <thead>
            <tr>
              {data.columns.map((name) => (
                <th key={name} scope="col">
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, i) => (
              <tr key={start + i}>
                {row.map((value, j) => (
                  <td key={j}>{String(value ?? "—")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!data.rows.length && (
        <p className="emptyResult">
          No matching records. Try a different filter.
        </p>
      )}
      <div className="recordPagination">
        <span>
          {data.rows.length
            ? `${start + 1}–${Math.min(start + 10, data.rows.length)}`
            : "0"}{" "}
          of {data.rows.length.toLocaleString()} returned ·{" "}
          {(data.matched_records ?? data.records_analyzed).toLocaleString()}{" "}
          {data.matched_records === undefined || data.matched_records === null
            ? countLabel
            : "matching"}
        </span>
        {data.rows.length > 10 && (
          <div>
            <button
              type="button"
              aria-label="Previous records"
              disabled={!page}
              onClick={() => setPage(page - 1)}
            >
              ←
            </button>
            <button
              type="button"
              aria-label="Next records"
              disabled={start + 10 >= data.rows.length}
              onClick={() => setPage(page + 1)}
            >
              →
            </button>
          </div>
        )}
      </div>
      {data.matched_records !== undefined &&
        data.matched_records !== null &&
        data.matched_records > data.rows.length && (
          <p className="resultLimit">
            This result is limited to the first{" "}
            {data.rows.length.toLocaleString()} records. Add a narrower filter
            to explore the remaining matches.
          </p>
        )}
    </div>
  );
}

export function DatasetMap({
  root,
  filename,
  request,
  onQuestion,
}: {
  root: string;
  filename: string;
  request: ApiRequest;
  onQuestion: (question: string) => void;
}) {
  const [columns, setColumns] = useState<Column[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    request<{ columns: Column[] }>(`${root}/schema`)
      .then((result) => {
        if (active) setColumns(result.columns);
      })
      .catch(() => {
        if (active)
          setError(
            "The column map could not be loaded. Reopen the dataset to retry.",
          );
      });
    return () => {
      active = false;
    };
  }, [root, request]);
  return (
    <section className="datasetJourney" aria-label="Data journey">
      <div className="journeyTitle">
        <span className="eyebrow">FROM FILE TO ANSWER</span>
        <span className="verifiedBadge">
          <Icon name="check" size={14} />{" "}
          {error
            ? "Needs attention"
            : columns.length
              ? "Structure ready"
              : "Reading structure"}
        </span>
      </div>
      <ol className="journeySteps">
        <li>
          <span className="journeyIcon">
            <Icon name="upload" />
          </span>
          <div>
            <strong>File retained</strong>
            <small>{filename}</small>
          </div>
        </li>
        <li>
          <span className="journeyIcon">
            <Icon name="data" />
          </span>
          <div>
            <strong>Profile & map</strong>
            <small>
              {columns.length
                ? `${columns.length} columns recognized`
                : "Loading columns…"}
            </small>
          </div>
        </li>
        <li>
          <span className="journeyIcon">
            <Icon name="overview" />
          </span>
          <div>
            <strong>Explore insights</strong>
            <small>Calculated from your data</small>
          </div>
        </li>
        <li>
          <span className="journeyIcon">
            <Icon name="chat" />
          </span>
          <div>
            <strong>Ask a question</strong>
            <small>Inspect the answer & source</small>
          </div>
        </li>
      </ol>
      {error && <p role="alert">{error}</p>}
      <details className="columnMap">
        <summary>
          Explore your column map{" "}
          <span>
            {columns.filter((c) => c.role === "metric").length} metrics ·{" "}
            {columns.filter((c) => c.role === "dimension").length} categories
          </span>
        </summary>
        <div className="mapBranches">
          {["metric", "dimension"].map((role) => (
            <div key={role} className="mapBranch">
              <h3>{role === "metric" ? "Measure" : "Explore by"}</h3>
              <div>
                {columns
                  .filter((column) => column.role === role)
                  .map((column) => (
                    <button
                      type="button"
                      key={column.name}
                      onClick={() =>
                        onQuestion(
                          role === "metric"
                            ? `What is the total ${column.name}?`
                            : `Show records with ${column.name}`,
                        )
                      }
                    >
                      <span>{column.name}</span>
                      <small>{column.type}</small>
                      <Icon name="arrow" size={14} />
                    </button>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </details>
    </section>
  );
}
