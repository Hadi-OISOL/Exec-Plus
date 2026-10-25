> **File use case:** Contract for the fixed, no-AI "Build a prediction model" recipe.
> **What it does:** States inputs, limits, method, verdict rules, storage, reopening and evidence.

# Build a prediction model (`prediction-model-v1`)

Opt-in analysis in **Anomalies & decisions → Analysis method → Prediction · build a
prediction model**. It ships the plain recipe the RD-Agent pilot showed works
(`docs/reports/rd-agent-pilot.md`); RD-Agent itself is not used and no language model
chooses the method, computes a number or writes the verdict.

## API

- `GET …/uploads/{upload_id}/decision-analysis/options` adds `prediction_models`:
  `targets` (`name`, `task`), `inputs` (`name`, `kind`, `excluded_reason`), `state`,
  `available`, `maximum_inputs` (30), `maximum_rows` (10,000), `holdout_percent` (20).
- `POST …/uploads/{upload_id}/decision-analysis/prediction-models` with `name`,
  `revision_id`, `understanding_id`, `target_column`, optional `input_columns` (≤30,
  empty = every suitable field) and optional `positive_label`. Returns the saved run (201).
- List/open use the existing owner-only `…/datasets/{dataset_id}/decision-analysis` and
  `…/decision-analysis/{run_id}`. Reviews are refused (422): a model has no findings.

## Rules

- **Confirmed meaning required**; stale `revision_id`/`understanding_id` or a newer
  accepted refresh source is refused (422). Filters are not supported in v1.
- **Target:** any non-identifier field with exactly two recorded values → classification;
  a numerical measure → regression (its required metric filters apply). Positive class:
  `positive_label`, else the single yes-like value (yes/y/true/t/1), else the rarer value.
- **Leakage guard:** identifiers/ignored fields, ID-like fields (≥95% distinct, text or
  non-metric integers), and fields whose name suggests a post-outcome value (duration,
  outcome, result, converted, won, lost, closed, final, …) or contains the target's name
  are excluded with a reason; choosing one explicitly is refused. Dates and categories
  with more than 50 values are excluded. A warning is added when a single input alone
  reaches holdout AUC ≥ 0.97 (R² ≥ 0.95 for regression).
- **Rows:** one governed projection query (receipt stored, owner-private `analysis`
  aggregation) ordered by every field. Profile-v5 columnar files over 10,000 rows use the
  disclosed `domain/sampling.py` fixed-seed sample; older non-columnar files over 10,000
  rows are refused. At least 50 rows with a target and 10 per class.
- **Split:** 20% holdout drawn with `sample_positions` (seed 20261027), separately within
  each class for classification. The model never trains on these rows.
- **Encoding (training rows only):** numbers standardised, missing filled with the
  training mean; categories one-hot for values with ≥5 training rows (top 20), the rest
  share one "(other values)" column, missing is its own value. Missing counts are reported.
- **Method:** L2 logistic regression (C=1, intercept unpenalised, L-BFGS-B ≤1000
  iterations) or least-squares linear regression, NumPy 2.2.6 / SciPy 1.15.3 (already
  pinned). scikit-learn was **not** added: the recipe is ~150 lines on pinned libraries,
  avoiding a new ~40 MB runtime dependency and new restricted-image checks.
- **Metrics on the holdout:** AUC and accuracy vs majority class (AUC 0.5);
  MAE and R² vs always guessing the training mean.
- **Verdict:** "Beats the simple guess by X" only when AUC ≥ 0.55 *and* the Hanley–McNeil
  95% margin keeps it above 0.5; for regression when MAE improves ≥5%, R² > 0 and the
  paired error improvement has z > 1.96. Otherwise "Not better than guessing — don't use
  it." Top 10 weights are labelled "associated with, not a cause".
- **Bounds:** ≤10,000 rows × ≤30 inputs (≤20 columns per category) keeps training to
  seconds inside the request, so the jobs worker is not used.

## Storage and reopening

No migration. Runs are stored in `analysis_runs` with `kind="robust_distribution"` and
`method_version="prediction-model-v1"` as the discriminator (same pattern as multivariate
and calendar extensions). Reopening re-executes the projection, compares the receipt,
rebuilds the request from the original source/definition, retrains and requires an
identical result and checksum; a changed statistics engine version is refused (409).
Owner-only visibility, the 50-runs limit and audit `analysis.created` are shared.

## Evidence (2026-10-25)

- Pilot split (sklearn 3,616/905 rows, `duration` removed): product trainer AUC **0.7376**,
  identical to the pilot's sklearn logistic regression 0.7376; accuracy 0.8862 vs 0.8851
  majority. Product's own split on bank.csv: AUC 0.7654, accuracy 0.8905 vs 0.8850.
  Reproduce: `python scripts/reproduce_prediction_pilot.py data/research/rd-agent-pilot`.
- Unit tests compare against independent pandas/Newton recomputation, and (when
  scikit-learn is importable, test-only) sklearn 1.6.1 within 1e-4 AUC.

## Not in v1

Scoring new rows / prediction CSV download, filters, dates as inputs, non-linear models,
probability calibration, and multi-class targets.
