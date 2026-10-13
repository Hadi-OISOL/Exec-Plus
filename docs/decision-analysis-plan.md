> **File use case:** Audits and sequences the October 10 anomaly and recommendation request.
> **What it does:** Defines the approved private-demo extension, reusable contracts and acceptance requirements before implementation.

# Anomaly and decision analysis

Status: Complete for the bounded local/test and private-demo extension. The user explicitly authorized implementation of VC items
58–59 and the accompanying human-review dependency (60), after starting the demo.
This authorization opens the bounded private-demo work below; it does not clear
Phase 5 acceptance or activate the rest of Phase 6.

The implementation, limitations and API are described in
[the user/maintainer guide](decision-analysis.md). The
[verification ledger](verification-decision-analysis.md) records local checks,
retained failed attempts, migration preservation and the eight-user rehearsal.
Broad VC 58/59 remain Partial; basic private recommendation review (60) is Done.

## Gap audit

| Component | Existing evidence | Missing extension |
| --- | --- | --- |
| Source contracts | Retained uploads/revisions, confirmed meanings/units, governed queries | Method-specific eligibility, baseline and decision assumptions |
| Detection | Quality heuristics, threshold alerts, exact monitoring drivers | Statistical anomaly methods, immutable findings and labelled feedback |
| Prediction | Private daily/monthly forecasts with held-out error evidence | Anomaly calibration; current heuristic forecast ranges cannot be sold as calibrated anomaly bounds |
| Decisions | Descriptive suggestions and grounded commentary | Objective, allowed actions, declared constraints, calculated alternatives and infeasibility |
| Approval | Meaning confirmation and refresh review | Source-bound recommendation approval/rejection states and optimistic review history |
| Operations | Bounded query execution, durable conversation jobs, private audit | Bounded analysis work and tenant-private result persistence/replay |

The new code must reuse existing source access, exact query receipts and historical
reconstruction. Domain computation stays standard-library-only. Method registration
is server-owned; neither models nor browsers may execute arbitrary code.

## Delivery sequence

1. Versioned analysis/result contracts and deterministic method registry. Introduce
   weighted MAD/IQR candidate detection with explicit small-sample/constant-baseline
   handling; observed unusualness is not error, fraud or a causal claim.
2. Authorized source queries, immutable private runs, evidence verification and
   bounded feedback. Baselines/thresholds/configuration are retained with every run.
3. A generic bounded allocation decision module using source-derived candidate
   costs/benefits and explicitly acknowledged linear-effect assumptions. Retain
   a do-nothing baseline, declared budget/quantity constraints, exact calculated
   alternatives, optimality within the supported bounds and infeasibility states.
4. Private human review: approve/reject/reopen, optimistic sequence and source
   freshness checks. Approval never executes an external action.
5. Browser findings/recommendation views, real-service tests and private VPS release
   with source/image/database checkpoints. Update the 64-item audit and DOCX only
   after verification.

## Common record contract

Every run binds workspace, dataset, owner, upload, revision, understanding, method
version, parameters, source query IDs, source checksum and result checksum. Opening
replays original evidence under current permissions. Changed current sources are
disclosed; original evidence remains inspectable but cannot be newly approved as
current. Numerical source values and calculated outputs retain exact decimal strings.

Feedback and review history are append-only, actor-owned and bounded. They do not
silently retrain a detector or rewrite an earlier result. Membership is checked at
start, execution, publication, reopening and review. Workspace administration does
not grant access to another user's private runs.

## Scope and future expansion

The framework can add seasonal/time-series, multivariate and drift detectors after
method-specific evaluation. The initial methods do not claim universal detection
or calibrated fraud probabilities. A statistical score is not a business priority.
User-defined materiality and review context must remain explicit.

Decision modules are reusable contracts, not a claim that observational records
prove intervention effects. Allocation outcomes are conditional on user-acknowledged
cost/benefit semantics and linear assumptions. Inventory, pricing, workforce,
causal effects, nonlinear optimization and external execution each need separately
validated modules. Inadequate inputs must return clarification/unsupported scope.

## Acceptance

- Independently calculated fixtures, weighted/duplicate cases, exact decimals,
  zero/constant/missing/small samples, bounded work and deterministic replay.
- Allocation constraints, exhaustive small-case comparison, tie rules, infeasible
  mandatory quantities and unsupported nonlinear/unknown-effect inputs.
- Cross-workspace/private-owner denials, revocation, tampered receipts/results,
  stale definitions, source bytes, concurrent review edits and immutable histories.
- Backend/architecture/static checks, frontend types/lint/build and real-service
  desktop/mobile browser journeys. Preserve prior receipts/forecast/study flows.
- Preserve a checked backup and source/images before any VPS migration. Demo
  acceptance does not satisfy the eight production gates.
