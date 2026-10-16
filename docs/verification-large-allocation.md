> **File use case:** Keeps observed verification for the optional larger allocation method.
> **What it does:** Separates numerical/process evidence, service/browser checks and release status.

# Larger allocation verification

Status: complete for the bounded local/test slice. No deployed acceptance or
broad feature-59 closure is claimed. Original production gates and representative
customer acceptance remain separate.

## Isolated dependency and solver trials

Forty checks passed before application integration: 30 small independent exhaustive
oracles; one 50-action/four-resource case; wall-time kill/reap, cancellation and
memory-cap probes; two hand-computed exact Decimal resource examples; 38-decimal
scaling; unsafe-integer refusal; and actual `UNKNOWN`/`FEASIBLE` outcomes.
The 50-action case found a solver-proven optimum in approximately 0.36 seconds
including process startup, using about 105 MiB maximum RSS and one thread. This
single fictional fixture is not a representative latency or sustained-load claim.

The actual packaged worker also ran successfully as UID 10001 in Python 3.12-slim
with network disabled, a read-only filesystem, one CPU, 900 MiB container memory,
32 process limit, dropped capabilities and no new privileges. It retained exact
`[2,1]` quantities/objective 25 for the integer form of the decimal fixture. This
was a dependency/worker packaging check, not the full application image or VPS.

Independent decimal fixture:

| Action | Unit cost | Unit benefit | Unit hours | Quantity bounds |
| --- | --- | --- | --- | --- |
| A | 0.03 | 0.07 | 0.2 | 0–2 |
| B | 0.05 | 0.11 | 0.1 | 0–2 |

At budget 0.11 and hours 0.5, the unique optimum is A=2/B=1, cost 0.11,
benefit 0.25 and hours 0.5. At hours 0.4, it is A=0/B=2, cost 0.10,
benefit 0.22 and hours 0.2. Tests compare these independently stated values and
retain original decimal strings rather than rounding the source representation.

## Current local checks

The affected backend/domain/architecture regression passes **281 tests** in
151.51 seconds, including 82 new allocation/process/service cases. A subsequent
chart-label/note refinement and one additional independent report test pass 42
export checks; 14 process/numerical rechecks pass after adding the exact runtime
version guard. This gives **282 distinct passing cases** across these runs,
including **83 new cases**, not 337 distinct tests.

All **59 frontend tests**, TypeScript, ESLint, Ruff and mypy (11 source files) pass.
The new real-service browser journey passes in 43.9 seconds (55.5 total); the
existing decision-analysis journey passes separately in 18.3 seconds (28.8 total).
No single combined browser run is claimed. The first command accidentally named a
nonexistent legacy spec and selected only the new test; the actual `decisions.spec.ts`
was then run explicitly.

The new journey covers four exact resources plus a prerequisite, explicit
confirmation reset, failed-save retry, successful-save/failed-history recovery,
immutable replay without searching again, recorded approval, actual XLSX and PNG
downloads, complete source/meaning preservation, no page/duplicate-key errors,
and **1440/390/320** layouts without page overflow. Screenshots and chart images
were inspected: resource tables retain a local horizontal scroll area on narrow
screens, values remain exact, and the optional result chart fits.

Initial PNG inspection found a missing visible unit and unnecessarily dense
process-limit notes. The final builder uses the saved unit and three concise
status/assumption notes; complete limits remain in image metadata and the reports.
The protected four-format export recheck passes after that change. A separately
labelled fictional renderer fixture was visually inspected; the original browser
download is retained as pre-refinement evidence. No post-refinement browser
redownload is claimed.

Coverage includes independent exhaustive small optima; exact scaling and overflow
refusal; zero benefits; 50 actions/four limits; missing/duplicate/invalid inputs;
prerequisites/exclusions; honest feasible/unknown outcomes; resource arithmetic;
hard timeout and repeated cancellation with reaping; concurrency admission;
oversized/malformed/error output; stripped environment; private receipts and
workspace-admin denials; restricted positive calculations and all four exports;
policy changes during solve; stale definitions; and review constraints.

Initial failures retained in ignored verification evidence:

- The isolated downloader twice stalled fetching wheels. Explicit IPv4 retrieval
  succeeded, and both downloaded wheels matched official PyPI sizes/SHA-256 values.
- A trial expected stopping at the first solution to yield `FEASIBLE`; the easy
  fixture was already proved `OPTIMAL`. A no-presolve, zero-hint probe produced an
  actual `FEASIBLE` outcome. The application does not expose these probe settings.
- Initial static checks found a reused local variable type and long strings;
  these were corrected without changing the numerical contract.
- Three first integration assertions were incorrect: governed SQL preserves
  trailing decimal zeros, existing source-change guards may return 422 rather than
  404, and errors are nested under `error.code`. Corrected assertions retain exact
  returned strings and require no saved run after revocation.

Private evidence is under
`data/verification/2026-10-16/remaining-work/large-allocation-*` and the
`ortools-*` trial logs. Downloaded fixtures, local environments and generated
artifacts remain ignored. No user dataset was changed by these fictional tests.
