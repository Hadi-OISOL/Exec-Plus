/* Use case: Helps users understand and safely clean an authorized upload.
What it does: Displays profiles, quality explanations, previews, mapping, and reversible history. */

import { useEffect, useState } from "react";
import { Icon } from "./explore-components";
import styles from "./prepare-profile.module.css";

export type ApiRequest = <T>(path: string, options?: RequestInit) => Promise<T>;
type Column = {
  name: string;
  type: string;
  role: string;
  semantic_tags: string[];
  missing: number;
  type_conflicts: number;
  invalid_dates: number;
  distinct_count: number;
  date_min: string | null;
  date_max: string | null;
};
type Profile = {
  row_count: number;
  column_count: number;
  quality_score: string;
  columns: Column[];
  quality_checks: { code: string; count: number; explanation: string }[];
};
type Revision = {
  id: string;
  parent_id: string | null;
  profile: Profile;
  created_at: string;
  source_checksum: string;
  output_checksum: string;
  recipe: object[];
  algorithm: string;
};
type Step = {
  trim: boolean;
  drop_duplicates: boolean;
  drop_missing: boolean;
  mapping: Record<string, string>;
};
type Preview = {
  revision: Revision;
  headers: string[];
  rows: string[][];
  removed_rows: number;
};
const emptyStep: Step = {
  trim: false,
  drop_duplicates: false,
  drop_missing: false,
  mapping: {},
};
const post = (body: object): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export function ProfilePanel({
  root,
  request,
  onRevisionChange,
  onUnderstand,
}: {
  root: string;
  request: ApiRequest;
  onRevisionChange?: () => void;
  onUnderstand?: () => void;
}) {
  const [active, setActive] = useState<Revision | null>(null);
  const [history, setHistory] = useState<Revision[]>([]);
  const [step, setStep] = useState<Step>(emptyStep);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refreshNeeded, setRefreshNeeded] = useState(false);
  useEffect(() => {
    let cancelled = false;
    request<Revision>(`${root}/profile`)
      .then(
        async (revision) =>
          [revision, await request<Revision[]>(`${root}/revisions`)] as const,
      )
      .then(([revision, revisions]) => {
        if (!cancelled) {
          setActive(revision);
          setHistory(revisions);
        }
      })
      .catch((cause: Error) => {
        if (!cancelled) setError(cause.message);
      });
    return () => {
      cancelled = true;
    };
  }, [root, request]);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Request failed. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  function update(value: Step) {
    setStep(value);
    setPreview(null);
  }
  async function refresh(notifyChange = true) {
    const [revision, revisions] = await Promise.all([
      request<Revision>(`${root}/profile`),
      request<Revision[]>(`${root}/revisions`),
    ]);
    setActive(revision);
    setHistory(revisions);
    setPreview(null);
    setStep(emptyStep);
    setRefreshNeeded(false);
    if (notifyChange) onRevisionChange?.();
  }
  async function afterMutation(message: string) {
    setPreview(null);
    setStep(emptyStep);
    setRefreshNeeded(true);
    setNotice(message);
    onRevisionChange?.();
    try {
      await refresh(false);
    } catch {
      throw new Error("Your change was saved, but the latest profile could not be loaded. Reload the profile before making another change.");
    }
  }
  const flagged = active?.profile.quality_checks.filter(check => check.count > 0) ?? [];
  const checkLabels: Record<string, string> = {
    missing_values: "Missing values",
    duplicate_rows: "Repeated rows",
    type_conflicts: "Mixed data types",
    invalid_dates: "Invalid dates",
    unsupported_structures: "Unsupported structure",
  };
  return (
    <section className={`panel profilePanel ${styles.profile}`} aria-label="Dataset profile">
      <header className={styles.heading}>
        <span className={styles.headingIcon}><Icon name="prepare" size={24} /></span>
        <div><p className={styles.eyebrow}>A GOOD FOUNDATION</p><h2>Know your file. Find your next step.</h2></div>
      </header>
      {error && (
        <p role="alert" aria-label="Profile error" className="errorNotice">
          {error}{" "}
          <button onClick={() => void run(() => refresh())} disabled={busy}>
            Reload profile
          </button>
        </p>
      )}
      <p className={styles.notice} aria-live="polite">{busy ? "Checking your data…" : notice}</p>
      {!active ? (
        <p>Loading profile…</p>
      ) : (
        <>
          <div className={styles.overview}>
            <div className={styles.snapshot}>
              <p className={styles.eyebrow}>{refreshNeeded ? "LAST LOADED VERSION" : "YOUR ACTIVE DATA"}</p>
              <p className={styles.dimensions}>{active.profile.row_count} rows · {active.profile.column_count} columns</p>
              <p>{refreshNeeded ? "Reload to see your saved changes. Your original upload is retained." : "You’re viewing the active version. Your original upload is retained."}</p>
              <div className={styles.score}>
                <span>File consistency <strong>{active.profile.quality_score}<small>/100</small></strong></span>
                <p>Checks file structure, not business accuracy or readiness for every analysis.</p>
              </div>
            </div>
            {onUnderstand && <aside className={styles.nextStep} aria-label="Understand this file">
              <span className={styles.eyebrow}>THE NEXT STEP</span>
              <h3>Review what we know.</h3>
              <p>See what Syntelio understands about this file and review anything missing.</p>
              <button type="button" onClick={onUnderstand} disabled={busy || refreshNeeded}>
                Review data meaning <Icon name="arrow" size={18} />
              </button>
              <span className={styles.nextStepNote}>Your saved answers stay in place.</span>
            </aside>}
          </div>
          <section className={styles.checks} aria-label="File checks">
            <div className={styles.sectionHeading}>
              <div><h3>File checks</h3><p>A quick look at what may need attention.</p></div>
              <span className={`${styles.status} ${flagged.length ? styles.attention : ""}`}>
                {flagged.length ? `${flagged.length} ${flagged.length === 1 ? "check needs" : "checks need"} review` : active.profile.quality_checks.length ? "No issues found in these checks" : "No checks available"}
              </span>
            </div>
            <ul className={styles.checkGrid}>
              {active.profile.quality_checks.map(check => <li key={check.code} className={check.count ? styles.flaggedCheck : ""}>
                <span>{checkLabels[check.code] ?? check.code.replaceAll("_", " ")}</span>
                <strong>{check.count}</strong>
                <small>{check.count ? "Review the details below" : "None found"}</small>
              </li>)}
            </ul>
            {flagged.length > 0 && <ul className={styles.actionableChecks} aria-label="Checks to review">
              {flagged.map(check => <li key={check.code}><strong>{checkLabels[check.code] ?? check.code.replaceAll("_", " ")}</strong><span>{check.explanation}</span></li>)}
            </ul>}
            <details className={styles.checkDetails}>
              <summary>What these checks mean</summary>
              <p>The score checks completeness, exact duplicate rows, numeric or boolean type conflicts, dates and supported structure with equal weight. Counts refer to each check; they are not a total of affected rows.</p>
              <ul>
            {active.profile.quality_checks.map((check) => (
              <li key={check.code}>
                <strong>
                  {check.code.replaceAll("_", " ")}: {check.count}
                </strong>{" "}
                — {check.explanation}
              </li>
            ))}
              </ul>
            </details>
          </section>
          <div className={styles.tools}>
          <details className={styles.disclosure}>
            <summary><span><strong>Explore columns</strong><small>Names, suggested types, missing values and date ranges</small></span><span className={styles.detailCount}>{active.profile.column_count} fields</span></summary>
            <div className={styles.disclosureBody}>
          <p>
            Types and tags are suggestions from column names and values. Metrics
            are numeric fields; dimensions group records. Review identifier
            columns before analysis.
          </p>
          <div className="tableScroll" tabIndex={0} role="region" aria-label="Column profile table">
            <table>
              <thead>
                <tr>
                  <th scope="col">Column</th>
                  <th scope="col">Type / role</th>
                  <th scope="col">Tags</th>
                  <th scope="col">Missing / conflicts / invalid dates</th>
                  <th scope="col">Date range</th>
                </tr>
              </thead>
              <tbody>
                {active.profile.columns.map((column) => (
                  <tr key={column.name}>
                    <td>{column.name}</td>
                    <td>
                      {column.type} / {column.role}
                    </td>
                    <td>{column.semantic_tags.join(", ") || "—"}</td>
                    <td>
                      {column.missing} / {column.type_conflicts} /{" "}
                      {column.invalid_dates}
                    </td>
                    <td>
                      {column.date_min
                        ? `${column.date_min} to ${column.date_max}`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
            </div>
          </details>
          <details className={styles.disclosure}>
            <summary><span><strong>Clean or rename fields</strong><small>Choose changes, inspect the preview, then decide</small></span><Icon name="prepare" size={20} /></summary>
            <div className={styles.disclosureBody}>
          <p>
            Your original stays unchanged. Removing repeated or incomplete rows
            can remove valid records; review the preview before applying.
          </p>
          <fieldset disabled={busy || refreshNeeded}>
            <legend>Cleaning options</legend>
            <label className="checkOption">
              <input
                type="checkbox"
                checked={step.trim}
                onChange={(event) =>
                  update({ ...step, trim: event.target.checked })
                }
              />
              Trim surrounding whitespace
            </label>
            <label className="checkOption">
              <input
                type="checkbox"
                checked={step.drop_duplicates}
                onChange={(event) =>
                  update({ ...step, drop_duplicates: event.target.checked })
                }
              />
              Remove exact duplicate rows
            </label>
            <label className="checkOption">
              <input
                type="checkbox"
                checked={step.drop_missing}
                onChange={(event) =>
                  update({ ...step, drop_missing: event.target.checked })
                }
              />
              Remove rows with missing values
            </label>
            <details>
              <summary>Map column names</summary>
              <p>
                Use clear, unique names. Mapping changes the output column name
                and updates its inferred tags.
              </p>
              {active.profile.columns.map((column) => (
                <label key={column.name}>
                  Rename {column.name}
                  <input
                    maxLength={100}
                    value={step.mapping[column.name] ?? column.name}
                    onChange={(event) =>
                      update({
                        ...step,
                        mapping: {
                          ...step.mapping,
                          [column.name]: event.target.value,
                        },
                      })
                    }
                  />
                </label>
              ))}
            </details>
          </fieldset>
          <button
            disabled={busy || refreshNeeded}
            onClick={() =>
              void run(async () => {
                setPreview(
                  await request<Preview>(
                    `${root}/cleaning/preview`,
                    post({ ...step, expected_revision_id: active.id }),
                  ),
                );
              })
            }
          >
            Preview changes
          </button>
          {preview && (
            <div className="previewBlock" aria-label="Cleaning preview">
              <h3>Changes to review</h3>
              <p>
                {preview.removed_rows} rows removed ·{" "}
                {preview.revision.profile.row_count} rows remaining · Quality
                score: {preview.revision.profile.quality_score}/100
              </p>
              <p>
                First 10 output rows at most. The counts and score cover the
                full file.
              </p>
              <div className="tableScroll" tabIndex={0} role="region" aria-label="Cleaning preview rows">
                <table>
                  <thead>
                    <tr>
                      {preview.headers.map((header) => (
                        <th scope="col" key={header}>
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row, index) => (
                      <tr key={index}>
                        {row.map((cell, column) => (
                          <td key={column}>{cell || "(missing)"}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button
                disabled={busy || refreshNeeded}
                onClick={() =>
                  void run(async () => {
                    await request(
                      `${root}/cleaning/apply`,
                      post({ ...step, expected_revision_id: active.id }),
                    );
                    await afterMutation(
                      "Changes applied. The original file is retained; you can restore any revision below.",
                    );
                  })
                }
              >
                Apply reviewed changes
              </button>
            </div>
          )}
            </div>
          </details>
          <details className={styles.disclosure}>
            <summary><span><strong>Revision history and lineage</strong><small>Revisit a previous version or inspect its source</small></span><Icon name="audit" size={20} /></summary>
            <div className={styles.disclosureBody}>
            <p>
              Restoring changes the active version. It keeps all history and the
              original file.
            </p>
            <ul>
              {history.map((revision, index) => (
                <li key={revision.id}>
                  {revision.parent_id ? `Revision ${index + 1}` : "Original"} ·{" "}
                  {revision.profile.row_count} rows ·{" "}
                  {new Date(revision.created_at).toLocaleString()} ·{" "}
                  {revision.id === active.id ? (
                    "Active"
                  ) : (
                    <button
                      disabled={busy || refreshNeeded}
                      onClick={() =>
                        void run(async () => {
                          await request(
                            `${root}/restore`,
                            post({
                              expected_revision_id: active.id,
                              revision_id: revision.id,
                            }),
                          );
                          await afterMutation("Revision restored.");
                        })
                      }
                    >
                      Restore{" "}
                      {revision.parent_id
                        ? `revision ${index + 1}`
                        : "original"}
                    </button>
                  )}
                </li>
              ))}
            </ul>
            <p>Algorithm: {active.algorithm}</p>
            <p className="checksum">
              Source SHA-256: {active.source_checksum}
              <br />
              Output SHA-256: {active.output_checksum}
            </p>
            <pre className="recipe">
              {JSON.stringify(active.recipe, null, 2)}
            </pre>
            </div>
          </details>
          </div>
        </>
      )}
    </section>
  );
}
