> **File use case:** Records observed checks for exact private company worksheets.
> **What it does:** Separates passing domain/service evidence, retained failures and remaining browser/release verification.

# Company worksheet verification

Status: working-tree implementation, not deployed. Parent-owned exact arithmetic
passes **39** cases, including fifty independent Fraction-oracle populations under
low Decimal precision, maximum-scale amounts, explicit mapping/rate/period/sign
rejection, cumulative over-elimination and reciprocal company-pair balance checks.

The final combined run passes **64 cases** in 41.917 seconds: 39 arithmetic,
18 real service/export integration, two 0024 migration and five architecture
checks. Three historical 0017/0018/0014 migration-preservation checks also pass
against the new 0024 head. Source and export behavior tested includes:

- Complete two-company files with exact currency translation and balanced internal
  elimination; every result layer and immutable reopening match.
- Owner-private receipts and saved worksheets; another member of both companies
  cannot open or export the run in any of the four formats.
- Missing/unknown accounts or amounts, required measure filters, currency mismatch,
  partial row access and undeclared counterparties are refused without a saved run.
- Real PDF extraction, Excel cell inspection, CSV bundle extraction and PNG metadata
  decoding retain exact tables, raw counterparties and declared rate references.
- Policy changes during filename listing, query execution and PDF rendering discard
  the result. Listing rechecks exact company links, memberships and policy epochs
  under ordered final locks after reading metadata.
  Real PostgreSQL NOWAIT checks prove no company workspace lock spans that work.
- A meaning change inside an actual object read blocks new publication. Historical
  reopening retains the original result and reports its newer meaning honestly.
- Large decimals remain exact; UUID-looking raw counterparties stay external until
  explicitly mapped. Invalid calendar dates produce a 422 input error.
- Tampered saved results are refused. Migration 0023↔0024 preserves every prior
  table, and a nonempty worksheet blocks downgrade without deleting evidence.

The first fixture used PUT for the existing POST department-attachment endpoint;
that 405 was corrected in the test. Two assertions assumed CSV trailing-zero format
rather than the actual typed query scale; they now check the exact query value and
unchanged source bytes. One combined invocation referenced a nonexistent architecture directory; the corrected
invocation used the actual tests/test_architecture.py file. An export header assertion assumed `private,no-store`,
while existing global middleware deliberately returns `no-store`; the check now
asserts that actual policy. Initial logs remain under ignored
`data/verification/2026-10-16/remaining-work/consolidation-*`.

Scoped backend Ruff and mypy (eight source files) pass. All 59 frontend unit tests
pass, including exact allowed export routes/denied arbitrary hosts and paths, and
negative chart-label spacing. Final frontend typecheck and lint also pass after browser cleanup.

The guided browser journey passed in 13.0 seconds (19.9 seconds including runner
startup), with six 1440/390/320 mapping/result layouts, exact saved reopening,
source-byte preservation, draft/failed-write retry, successful-write/failed-list
recovery and a real Excel download. No page errors or duplicate React keys were
recorded. The final three-journey run passes in 46.3 seconds: company consolidation
(14.4 seconds) with actual PDF/Excel/CSV/PNG downloads, existing exact
chart/table/filter/keyboard behavior (12.8 seconds), and full returned-row engine
navigation (10.9 seconds). The offline fixtures explicitly log qualitative
provider-unavailable fallbacks; no hosted model quality claim is made.

The first browser attempt used an implicit-label exact selector that included
select-option text; the actual Account field combobox existed and was enabled.
The semantic combobox locator corrected that harness error. The next run found a
real missing UI route allowance: organization-scoped worksheet exports were
blocked by the workspace-only download guard. The guard now permits only the
explicit UUID worksheet export path, and the corrected real download passed.
Screenshot review also found negative outside bar labels overlapping category
names; an original responsive gutter separates those labels without changing any
value or encoding. These initial failures and captures remain in the ledger.

Combined compatibility, image/build gates, private-demo verification and
source-preserving migration activation remain the parent release process. No
private-demo delivery or representative accounting acceptance is claimed here.


## Atomic worksheet limit repair

Independent review found that disjoint company sets did not share a final quota
lock. A real two-thread, four-company regression began with 49 retained runs; both
creations succeeded before the fix instead of accepting only one. The initial
failure is retained as `consolidation-quota-before.{log,xml}`.

Final insertion now acquires a transaction-scoped advisory lock for the exact
organization/person after all ordered source checks. It spans only the quota
check, insertion and audit writes; source/object reads and computation remain
outside locks. The concurrency regression and affected service/migration/architecture suite
pass all **26 cases** in 54.319 seconds. Exactly one request is saved,
the other receives the worksheet-limit error, all fifty retained records remain,
and the earlier saved output is unchanged. Ruff and mypy (three affected source
files) pass. This adds one new case to the prior 64, giving **65 distinct passing
cases** across those runs; the three historical migration checks remain separate.
The frozen browser flow is unchanged by this server-only quota guard.
