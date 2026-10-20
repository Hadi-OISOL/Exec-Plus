> **File use case:** Contract for requirement 33's governed contribution studies.
> **What it does:** Defines implemented exact comparisons, saved-study permissions and their local acceptance checks.

# Contribution studies

Status: implemented in the Phase 2 working tree, not deployed. Local numerical,
API, access and export verification is recorded in
[the contribution verification ledger](verification-contribution-studies.md).
The full Phase 2 acceptance gate remains separate.

The study answers “Which recorded groups account for this difference?” It does
not identify business causes. It compares two explicitly selected authorized
snapshots or two declared nonoverlapping date windows. Both datasets must belong
to the current workspace; cross-company reporting remains the consolidation
workflow.

## Existing architecture

Use a new, versioned `contribution` method in the existing `Study` and
`StudyVersion` records. Creation is private. Owner-only explicit sharing,
immutable versions, six-pin dashboards and protected downloads remain the
existing mechanisms. Other descriptive studies and owner-private `AnalysisRun`
records keep their present behavior. No new schema or parallel sharing system is
needed.

Each side retains dataset/upload/revision/confirmed-meaning IDs, selected measure,
segment, filters, optional date window and query receipts. The existing study's
dataset/upload identify its baseline source. Evidence contains **both** source
references and confirmed definitions. Creation checks current versions before
and after calculation. Reopening replays both saved receipts, recomputes the
versioned formulas and checks agreement with the saved result.

Every receiving actor needs current access to both sources and their recorded
row/column policy scope. Sharing a study or dashboard grants neither source
access nor private data access. Listing versions, opening a pin, exporting and
rendering an embedded shared board must recheck every source. Revocation makes
the affected saved view unavailable. Original private analyses are unaffected.

## Exact differences

- Choose a confirmed additive measure with one fixed declared unit and a
  confirmed category. Map fields explicitly when the two datasets use different
  names. Unit conversion is not inferred.
- Apply required metric filters and the current actor's row/column policy before
  producing receipts. Reject conflicting populations, unsupported nonadditive
  grains, missing units and over-limit result populations.
- Retain each group's presence, row count, present-value count and missing-value
  count on both sides. A group absent from one snapshot is distinct from a
  present group whose recorded value is zero or missing.
- Compute exact signed changes, rank by absolute contribution with a stable tie
  order and expose the complete supporting receipt rows. Chart rounding never
  replaces the exact tables.
- Missing values follow the confirmed missing-value policy. They are not
  imputed. Undefined changes and unavailable reconciliation must be explicit;
  missing-only groups must not silently become observed zero values.
- Percent contributions have an explicit denominator. A zero net change has no
  percentage contribution; opposing effects can exceed 100% of a nonzero net
  change. Such percentages are accounting ratios, not probabilities.

## Eligible price, volume and mix

This optional decomposition uses confirmed currency revenue and compatible
quantity units. Observed unit revenue is `revenue / quantity`, not an inferred
catalog price or a claim about why prices changed. Missing required values,
nonpositive quantities or incompatible units prevent this decomposition; they
do not trigger guessed prices or missing-value replacement.

For the matched product cohort, let `Q_t` be total quantity, `w_ti` product `i`'s
quantity share, and `p_ti` its observed unit revenue. Use the declared formula
order **volume → mix → price**:

- Volume: `(Q_1 - Q_0) × sum(w_0i × p_0i)`.
- Mix: `Q_1 × sum((w_1i - w_0i) × p_0i)`.
- Price: `Q_1 × sum(w_1i × (p_1i - p_0i))`.

These three components reconcile exactly to the matched cohort's revenue
change. Newly observed products contribute their recorded comparison revenue;
exited products contribute minus their recorded baseline revenue. They are
reported separately, without counterfactual prices. If no eligible matched
cohort exists, that fact is stated rather than inventing a decomposition.

Use exact rational numerators/denominators for intermediate ratios and
nonterminating results. Provide clearly marked decimal display values alongside
them. Reconciliation compares exact fractions, never rounded displays. This
order is an accounting convention; another valid order can distribute interaction
effects differently.

## User experience

Place an explicit “Explain a change” action in the existing study library. Offer
period and dataset comparisons with selected fields and dates; show the precise
comparison scope before saving. Keep the resulting totals and contribution chart
visible. Put complete records, formulas and detailed source evidence in clearly
named secondary views. Reuse the app's chart, select, export and sharing controls.

The normal saved-study list, board pins and protected PDF/Excel/CSV downloads
must include contribution results, their exact components, coverage, method and
both-source provenance. Numerical exports are generated server-side from replayed
evidence, never from browser-provided result values.

## Acceptance evidence required

Independent arithmetic fixtures cover exact differences, ties, cancellation,
absent/new/exited groups, missing-only groups, zero totals, high precision,
nonterminating ratios and the declared price/volume/mix order. Source tests cover
date windows, explicit mappings, incompatible units, required filters, truncation
and source changes during computation.

Integration tests cover private creation, teammate denial, explicit sharing,
owner-only updates, multi-source grant/revocation, restricted rows/columns,
historical pinned versions, replay agreement, exports and board rendering. A
browser journey must actually create, inspect, save, share, reopen and download
the contribution study. Existing descriptive-study and private-analysis tests
remain required regressions. Final commands/results belong in the Phase 2
verification ledger after execution.

## Permission binding

The existing study records already retain `evidence.sources`; both source
references must continue using that contract so exports, API keys and embedding
can inspect them. A new study still uses its baseline dataset as `dataset_id`.
The receiving actor must not learn the study title or version metadata when no
saved version is accessible. In particular, an unrestricted baseline must not
override a revoked comparison-source grant.

Contribution projections also need a saved-version permission binding. Knowing
a projection query UUID must not expose private study records through general
query replay, artifact inspection, saved-item creation or dashboard-query export.
The existing private analysis receipt boundary can carry that binding without
weakening ordinary analysis ownership. Shared study access must resolve the
exact saved version, confirm that it owns the query UUID and recheck both source
references. A failed or unpublished study must not become a public receipt.

The bounded method reads at most 10,000 matching rows per side and at
most 128 distinct groups, with no truncation represented as a full population.
Each selected measure uses its existing confirmed aggregation and required
filters. Price/volume/mix measures must use the same filtered population on a
side, and the two sides must have identical declared currency and quantity
units. Period comparisons use explicit nonoverlapping ISO date ranges, never
row order. Unsupported stock-snapshot totals and unknown row meanings require
review instead of an implicit additive assumption.

Missing-only groups remain undefined. An absent group can have a recorded entry
or exit contribution, but a present group with no measured values cannot be
turned into zero. Opposing contributions may cancel to a zero net change, in
which case percentage contribution is unavailable. The complete exact component
sum and its reconciliation status remain visible alongside rounded charts.


## Implementation and local demonstration

The engine is `apps/api/src/execplus/domain/contributions.py`; the bounded study
workflow is `application/services/contribution_studies.py`. The existing study
route returns a `contribution` result beside two replayed record tables. No
migration, provider call, solver, runtime dependency or new sharing subsystem is
required. The method identifier is `segment-contribution-v1`.

In **Studies & dashboards**, open **Explain a change**. Choose **Two date ranges**
or **Two file snapshots**, select the amount/category on each side, and confirm
that rows contain additive amounts without duplicate totals. Period comparisons
use the same fields and filters on both sides, with inclusive ISO dates and the
comparison starting after the baseline ends. This does not certify complete
calendar coverage. Snapshot comparisons permit explicit field mappings, require
current confirmed meanings and remain within one workspace.

Enable the optional volume/mix/unit-revenue calculation only when the file has
complete positive quantities and currency revenue. The server validates required
metric filters, units and supported additive row meanings. Total/category cards
and signed charts remain visible; supporting records, exact fractions, coverage
and formulas have named secondary views. These views reuse Radix Select and the
existing ECharts/table components. Nothing infers a catalog price or cause.

A rerun preserves original versions. For a period study it applies the two saved
windows to the newly selected baseline snapshot. For a two-file study it changes
only the selected baseline snapshot; the comparison snapshot stays fixed. If
that comparison's confirmed meaning has changed, create an explicit new
comparison after reviewing both files. The saved method and both sets of source
IDs remain inspectable. Sharing/pinning follows the ordinary study controls.

PDF, Excel, CSV-evidence bundles and PNG use server-replayed rows. Reports include
exact changes, coverage, optional decomposition, formulas and both source
references. Existing portable-export bounds and Excel's exact-text-cell contract
remain unchanged; the evidence retains original types. Each projection uses the
existing processing allowance. A refused or failed publication does not create
a saved study or make its provisional receipts readable.

Limits: 10,000 matching rows per side, 128 distinct categories across both sides,
20 effective filters per side and the existing export file/cell limits. Unsupported
stock snapshots, conflicting metric populations, mixed/per-row units, missing-only
groups, excessive populations and stale permissions are never silently repaired.
Missing-only groups make the net result unavailable; absent groups are explicitly
labelled entries/exits. Empty selected populations have empty sums, not an observed
performance finding. Wider causal or predictive conclusions are outside this method.
