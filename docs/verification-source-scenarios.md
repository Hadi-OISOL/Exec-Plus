> **File use case:** Records the source-derived scenario implementation evidence.
> **What it does:** Separates checked local behavior, initial failures and pending release acceptance.

# Source-derived scenario verification

Status: **In progress; not deployed.** This is a separate slice after the frozen
exports/access/forecast release candidate. It adds `source-unit-economics-v1`
without schema, provider, arbitrary-code or external-account changes.

## Current local evidence

- 39 domain/planning checks pass, including a hand-calculated two-product example,
  25 independent Fraction-oracle fixtures, per-unit/row-total equivalence, the
  10,000-row and 21-point bounds, zero/negative/high-precision inputs, exact signed
  outcomes, incomplete populations and incompatible units/grain/governed filters.
- 25 new integration checks pass: typed private receipts and exact saved replay;
  request/result/method/evidence tampering; compatible successors and mixed-method
  refusal; source/meaning history; restricted positive access; hidden-column and
  original-fingerprint exclusion; policy-change publication/replay denial; and
  real PDF, Excel, CSV bundle and both PNG chart extraction.
- 17 existing scenario integration checks and 37 export-builder checks pass.
  The combined run passed 117 cases in 58.27 seconds; a subsequently added
  cross-method successor case passed in 2.33 seconds. Total: **118 distinct**.
- Backend Ruff and mypy, frontend type checking/lint and 55 frontend unit checks pass.
- The new source-scenario journey and existing scenario journey both pass in
  35.1 seconds. They cover retained drafts, explicit confirmations, failed-save and
  failed-history recovery, exact result/sensitivity display, Excel download,
  immutable succession, multi-filter preservation and old/new history separation.
  The new journey checks widths 1440/390/320, reduced motion and zero page errors.
  The charts, exact inspectors and local table scrolling were visually reviewed.
  No full-suite, deployed or representative customer acceptance is claimed here.
- Independent read-only review found no blocking arithmetic or access issue in
  the bounded contract; row meaning, non-overlap and price/unit interpretation
  still depend on the user's explicit declaration.

## Initial failures retained

1. Initial integration run: two test failures and 35 passes. Both tests incorrectly
   expected replay rows under a `result` wrapper; this API returns `rows` at the
   top level. Corrected the assertions without changing the endpoint.
2. First combined run: one failure and 116 passes. The Excel test exposed that the
   model's assumptions/limits appeared only in the evidence section rather than a
   readable result sheet. Added an exact **Model assumptions and limits** table to
   the source-scenario report. Final extraction checks pass in all four formats.
3. Initial static checks caught import ordering, long lines and one necessary type
   narrowing. Corrected before final checks. No failure is counted as a pass.
4. First browser execution reached saved results/download but failed at 390px
   horizontal overflow. A retained second run with a bounded layout-settle check
   proved this was persistent, not chart resize timing. The new source panel was
   outside the old `.decisionPanel` ancestor, so its tables lacked scroll rules.
   Scoped scroll containers and readable cell widths repair the page without
   hiding values; tables also have named keyboard-focusable regions. The earlier
   nine-column sensitivity table's excessive decimal wrapping is corrected.
5. Those browser logs also exposed duplicate React keys from the new sibling
   access/integration panels in the shared Team container. The integration owner
   namespaced its key and restricted mounting to Team. The final scenario run has
   no duplicate-key warning. Disabled-provider qualitative fallback messages in
   this offline run are not counted as hosted-model acceptance.

Private logs remain under the ignored
`data/verification/2026-10-16/remaining-work/` directory. No test data, credentials,
reports or browser captures are committed.

## Remaining gates for this slice

A later separate release needs the combined regression gates, its own protected
live acceptance and source-preservation checks. Broader causal, learned-demand,
nonlinear and representative business acceptance remain distinct.
