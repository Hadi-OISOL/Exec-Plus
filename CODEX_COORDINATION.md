> **File use case:** Shared ownership and integration handoff for the three ExecPlus sessions.
> **What it does:** Separates observed work, proposed UI ownership and acknowledged integration windows.

# ExecPlus coordination — October 17, 2026

## Read before editing

Read `AGENTS.md`, `ROADMAP.md`, `docs/decisions/architecture.md`, then the local
`data/agent-memory/context.json` and `data/agent-memory/connector-merge-coordination.json`.
Run `python3 data/agent-tools/project.py status` and inspect the current worktrees.
This document does not supersede an existing reservation or open an integration window.

## Work division

| Session | Observed work and responsibility | Boundary |
| --- | --- | --- |
| EXECT_PLUS_WHOLE | Native accounts/onboarding, entitlements, operational metrics, Phase 1 validation; subsequent analytical methods, permissions, combined integration and separately authorized releases | Owns root `phase2` work in progress, core API wiring, migrations 0025–0027, workspace page, account/plan/incident panels and functional workflow changes |
| EXECT_PLUS2 | Connector adapters and connector UI, isolated merge against the Phase 1 source snapshot | Owns `data/agent-tools/worktrees/connector-merge`; reserves migrations 0028–0029 after 0027; root integration still closed |
| Executive Plus 3 — this UI session | UI audit, library evaluation, typography/tokens, presentation, responsive behavior, accessibility and UI evidence | Prepare changes in `data/agent-tools/worktrees/premium-ui`, branch `ui/premium-20261017`; do not edit the other sessions' active application files |

Identity mapping is supported by the local session index and the connector coordination
record. Existing sessions are not addressable by this chat's agent messaging tool.
Shared files are the communication channel. **EXECT_PLUS2 acknowledged** isolated UI
audit/styling ownership in its own memory section and confirmed no overlap with the
studio CSS-only proposal. Connector/Google panels and workspace OAuth/import workflows
remain reserved. **EXECT_PLUS_WHOLE also acknowledged** isolated studio styling,
typography, tokens and layout work. Component/props/API/package changes remain
reserved until a narrow handoff; no root integration window is open.

## Current state and completed work

- Base: `d4db038` on `phase2`. Root has extensive uncommitted Phase 1 work. Preserve it.
- Historical deployed state: web `5c48d3c`, API/jobs `867c5a0`, schema 0020.
  This UI session has not inspected or changed the deployed service.
- WHOLE's memory records implemented accounts/plans/metrics on local schema 0027;
  full gate and compatibility work remain underway. Prior baseline: 2,380 backend
  passes, 59 frontend passes; browser baseline retained four failures and three skips.
- PLUS2 reports connector checks and combined-overlay checks in its own memory.
  These are reported results, not fresh UI-session or combined-root acceptance.
- Preserve the migration chain 0024 → 0025 → 0026 → 0027 → 0028 → 0029.
- All eight production gates remain blocked. Do not change feature counts from UI polish.

## File ownership and conflict handling

- WHOLE: `apps/api/**`, migrations 0025–0027, `apps/web/src/app/workspace/page.tsx`,
  account/onboarding/plan/incident/usage/admin functionality, shared regression
  fixtures/configuration, main roadmap and release handoff.
- PLUS2: connector adapters/migrations and connector/Google frontend panels in its
  isolated worktree. Shared API/client/root-page wiring needs WHOLE's handoff.
- UI: the seven requested `UI_*.md` deliverables, this coordination document,
  its own `ui-ux-coordination.json`, and isolated presentation patches. Initial
  candidate: `studio-workspace.css` and focused UI evidence; root files stay frozen.
- Shared/high-conflict files: workspace page, global styles, package manifests,
  lockfile, shared types/client, Next/Playwright configuration and notices. Check
  both worktrees and obtain acknowledgment before integration or competing edits.
- No root checkout/index/stash/reset/commit/cherry-pick/merge operations by UI.
  Never overwrite another session's files with an older branch version.
- Each session edits only its own memory section. Re-read immediately before a
  narrow update; preserve other sections. Treat a changed snapshot as stale.

## Shared contracts

- UI consumes existing typed backend results; exact decimal strings, receipt
  lineage, explicit units, permissions and source freshness stay intact.
- DeepSeek/provider configuration and agent execution remain with WHOLE. UI may
  display actual job state but cannot manufacture progress or completed analysis.
- Keep Overview charts and first findings open in Simple and Expert modes.
- Keep account/connector controls and errors supplied by the other workstreams.
  Visual changes cannot weaken policy checks or imply live connector availability.
- Reuse bundled ECharts, native controls, Radix Select, local Manrope and existing
  test tools unless a documented need justifies a coordinated dependency change.
- New API needs must be recorded with request/response shape, owner and acceptance
  checks before UI relies on them. No new API contract is requested in slice 1.

## Integration and handoff

1. Prepare UI-only diffs and exact source hashes in the isolated worktree.
2. Publish changed paths, behavior, commands/results, screenshots and limitations
   in `UI_INTEGRATION_NOTES.md` and `UI_QA_REPORT.md`.
3. WHOLE records its accepted Phase 1 checkpoint and explicit integration window.
4. Rebase/reconcile against that checkpoint; retain PLUS2's connector functionality.
5. Run frontend checks plus affected browser journeys on the combined source.
   Isolated UI evidence cannot substitute for combined functional acceptance.
6. WHOLE owns any separately authorized release. UI does not push or deploy.

Open synchronization items: accepted Phase 1 checkpoint and combined test window.
Both sessions have acknowledged the isolated presentation-only UI lane.

UI deliverables and code currently live in the isolated worktree, not root source.
Start with `data/agent-tools/worktrees/premium-ui/UI_INTEGRATION_NOTES.md` and
`UI_QA_REPORT.md` in that same directory. The first patch changes only the existing
studio stylesheet; no new backend or API contract is requested.

Second isolated UI slice is ready: shared studio tokens/type/spacing, responsive
header, control sizing, active navigation and validation feedback. Final CSS diff
and hashes: `data/verification/2026-10-17/ui-coordination/slice2/`. Both ownership
acknowledgments are recorded; this does not open the root integration window.
Fresh 59 frontend tests, lint and production build/types pass. Browser evidence
covers eight signed-out layouts, ten CSS before/after fixtures and fifteen real
React layouts with synthetic API responses; these are not combined backend or
deployed acceptance. The UI preview server was stopped after verification.

Slice 3 is active: independent rendered chart/table/loading-state audit continues in
the isolated UI worktree. User clarified that the actual application/data live on
the VPS. UI requests Main Codex's existing restricted access procedure and current
release identifiers through `ui_session.vps_handoff_request`; share paths only,
never credentials. Read-only live inspection is separate from local synthetic
evidence. Root integration and release ownership remain with WHOLE.

Slice 3 is verified locally: single discovery cards use available grid width;
loading states use studio tokens. 59 frontend tests, lint/build/types and twenty
synthetic chart/table/loading/dialog layouts pass. Final cumulative patch/manifest:
`data/verification/2026-10-17/ui-coordination/slice3/`. Root application is unchanged.

Main Codex supplied `data/agent-memory/private-vps-handoff.md`. UI independently
checked existing control-socket access, readiness (ready; database/storage healthy)
and unauthenticated workspace HTML (200; sign-in shell present). No application
records, writes, restarts, session renewal or new tunnel. Authenticated synthetic
UI verification is requested from WHOLE; these checks are not live visual acceptance.

## User access and Docker rebuild handoff

User explicitly requested working VPS access, fresh sessions.json and a Docker
rebuild if needed to see UI changes. UI restored the existing restricted tunnel
(localhost18400/18401) and refreshed only demo1 in ignored0600 sessions.json.
Auth/readiness/web pass; other accounts are preserved. No token is recorded here.

The exact deployed web source matches commit5c48d3c across179files. UI prepared
that source plus only the reviewed studio CSS and built the uniquely tagged VPS
image `oisol-execplus/web:ui-20261017-live5c48d3c`. Production build/types and twenty
synthetic browser layouts against that actual image pass. Review manifest:
`data/verification/2026-10-17/ui-coordination/web-rebuild/candidate-manifest.json`.
Main: please coordinate activation with your release checks/backups, or include
the CSS in the next release. Keep it in the later0027/connector web build. No live
web replacement, shared image tag or deployed-source change has occurred.
