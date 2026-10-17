# Language and crop-comparison repair verification

Status: implementation and focused verification complete; broader regression,
final frontend build and private VPS activation are in progress. No live repair
claim is made by this checkpoint.

## Evidence

Private artifacts are retained under
`data/verification/2026-10-17/harvest-followup/`; source-backed tests use fictional
fixtures. The user-supplied farm CSV and its analysis remain ignored/private.

- Count/routing/extra-scope gate: 40 passed, including nine independent scope cases.
- Independent record-selection boundary gate: 18 passed; nulls, tied extrema,
  exact decimals, row/column policies and rejected unsafe SQL expressions.
- Cohort domain: eight passed, covering weighted comparison groups, missing cells,
  constant/sparse measures, exact labels, unit review and population limits.
- Cohort integration: six passed, covering private replay, tampered evidence,
  structured follow-up context and exact PDF/Excel/CSV values.
- Full mypy: 320 source files pass after a checksum-input typing repair.
- Frontend: 63 tests and TypeScript passed; final browser/build evidence pending.
- Focused browser: seven prior passes, then three recheck passes covering two new
  cohort journeys and the existing pooled group comparison. Final mobile recapture
  and source freeze pending. Overlapping checks are not added as distinct cases.

Retained initial failures include SQLGlot FROM-key compatibility, a test response
field assertion, the new comparison button's missing offline record route, five
independently found extra-scope guard failures, a test database-name mistake and
two mypy checksum argument types. Repairs and final evidence stay separate from
those first runs. None is silently removed from the ledger.

## Scope

The current private release is still `4fff22633f0c5f44` on unchanged schema `0029`
until a later entry records activation and live checks. No model configuration,
external connector, dependency or feature-audit status change is part of this
repair. Local fixtures cannot establish general language accuracy or agronomic
causality. See [contract](harvest-language-repair.md).
