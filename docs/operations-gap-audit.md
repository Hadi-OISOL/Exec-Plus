> **File use case:** Audits the October 6 admin, support, performance and reporting priorities.
> **What it does:** Records the authorized private-demo slice, existing gaps and acceptance boundaries before implementation.

# Operations and product reporting priorities

The user requested an internal admin console, customer-support workflow, measured
performance improvements and product usage/retention reporting, with the existing
VC DOCX kept current after delivery. This pulls a bounded operations slice forward
from Phase 5; it does not complete Phase 5 or waive its eight production gates.
Baseline is `phase2` at `9c2445d` plus the verified, uncommitted Phase 4C delivery.
All forecasting changes and historical receipts must remain intact.

## Verified gaps

| Area | Existing implementation | Missing work |
| --- | --- | --- |
| Administration | Workspace roles, invitations, seats, organizations and Team settings | Explicit staff authorization and a cross-workspace operational metadata console |
| Support | Fixed feature/rating/category feedback records | Private requests, conversation, assignment, triage, escalation, resolution and reopening |
| Product reporting | Manager totals and all-time weekly activity from every audit action | Bounded periods, deliberate activity definitions, mature cohort denominators and visible reports |
| Performance | Bounded compute, durable jobs, debounced discovery and prior query fixes | Usage aggregates currently materialize whole event histories; optional views load eagerly |
| VC report | Desktop DOCX and ignored audit/generator from October 5 | Include verified forecasting, then this slice; maintain reproducible status totals |

The audited usage paths are `ActivationService.overview` and
`WorkspaceService.usage`. The first loads all audit/usage/feedback rows; the second
loads uploads once per dataset. Existing retention counts any actor seen in two
weeks, including automated events, and is not a cohort definition. Browser build
baseline references nine scripts: 734,931 raw bytes / 216,432 gzip bytes. These
measurements identify targets; they are not claims of an improvement yet.

## Authorized delivery contract

- Internal staff grants are separate from workspace roles and managed only through
  the operator CLI. An ordinary owner/admin is never implicitly platform staff.
  Grants can be revoked; every privileged request rechecks the grant. Staff roles
  `admin` and `support` control their respective console capabilities. Staff access
  never grants source, conversation, forecast or receipt access through normal APIs.
- The admin console lists bounded workspace/customer metadata, demo plan status,
  seats, resource/usage totals and job health. It exposes no uploaded rows, SQL,
  prompts, answers, object paths, tokens or credentials. Billing remains unconfigured.
  Privileged reads and writes are audited separately with identifiers/outcomes.
- Support requests are workspace-bound and private to the requester and explicitly
  authorized support staff. Team ownership alone does not reveal another user's
  request. Users intentionally share bounded text with support; the interface explains
  that audience and does not auto-attach source data or logs. Optional diagnostics
  contain only validated own-job identifiers and fixed operational fields.
- Support provides an immutable public reply/status timeline, assignment, priority,
  escalation, resolution and explicit reopening, with optimistic versions, bounded
  lists/messages and transactional audit. No external email or messaging is sent.
- Product reporting is available to workspace managers for their workspace, and
  platform admins through audited metadata projections. UTC periods, a versioned
  allowlist of deliberate human actions, distinct people, activation, feature adoption,
  mature weekly cohorts and rule-based inactivity signals are explicit. Automated
  background work does not establish retention. Incomplete cohorts stay unavailable,
  and inactivity is not a churn prediction. No private text or individual activity
  history is returned to workspace managers.
- Performance work replaces unbounded materialization on the new reporting and
  onboarding paths with database aggregates and defers optional browser code/data.
  Preserve existing public contracts and numerical replay. Measure before/after on
  identical fictional workloads; retain failures and avoid generalized speed claims.

## Acceptance

Real PostgreSQL/MinIO tests must cover grants/revocation, cross-workspace and
requester privacy, staff without data access, stale/concurrent support transitions,
feedback/diagnostic ownership, fixed metadata projection, audit recording, cohort
boundary/zero/maturity cases and migration preservation through 0015. Browser tests
must complete requester/staff support workflows, admin/report views and mobile
layouts. Full regressions, static checks, production builds and a private deployed
rehearsal are required. Preserve a source/image/database checkpoint before migration.
Update the DOCX only from final evidence, distinguishing private-demo features from
production/commercial readiness and broader performance acceptance.

Exports and live connectors remain Phase 4D/4E work. Billing, production identity,
representative load/security/recovery reviews and all existing production gates remain
open. Advanced methods remain Frozen in Phase 6.
