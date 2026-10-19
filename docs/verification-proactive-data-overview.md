# Proactive data overview verification

Status: implemented, locally verified and verified on the private VPS release
074a5821f55d2aff / schema 0029 (runtime c5b0b4a).

Evidence: `data/verification/2026-10-19/proactive-overview/` (private, ignored).

- Frontend: 72 unit tests pass.
- Initial backend run encountered stopped local test PostgreSQL/storage containers. Its failures
  are retained in `backend.log`; only the two task-owned containers were started for a fresh run.
- Initial browser fixture incorrectly expected a scenario shortcut for an incomplete measure.
  The implementation conservatively requires complete values; the fixture was corrected.
- Independent review found a moved-review wrapper could hide both chat and review; corrected
  before acceptance. A failed discovery retry could redisplay older data; its saved state now clears.
- Focused backend: 77 passes; expanded new overview cases: 10 passes (four overlap the
  77-case run); existing diagram/scenario/pattern regression: 134 passes. Together these
  cover 217 distinct tests, not 221. One existing Starlette/httpx deprecation warning remains.
- Ruff, mypy (269 source files), frontend TypeScript and ESLint pass. Both VPS production
  images build; restricted image computation checks pass.
- Five distinct browser cases have passing latest runs: four in `browser-recheck.log`,
  remaining overview case in `browser-overview-combobox-final.log` (14.8 seconds).
  This is combined evidence, not a single clean run. It covers source switching/403/retry,
  original proactive receipts/theme stability, aggregate/source scenarios, early chat with
  unavailable AI reading, automatic map, Simple/Expert disclosures, six layouts, exact
  average 20 → 25 under +25%, unchanged source bytes and exactly one successful save even
  when its history refresh returns 503. Root inspected desktop dark/mobile light captures.
  Earlier incomplete-data fixture, missing re-login, nested-summary/select selectors,
  desktop-hidden CTA and interrupted-run failures remain retained. The helper now permits
  overview and optional review to be visible together.
- Browser review also found the unavailable-reading fallback could activate a focused
  guide and hide the overview. Checkpoint c5b0b4a clears that automatic fallback state;
  explicit manual review still works. Earlier candidate e89859035c9d6599 was never activated.
- Candidate 074a5821f55d2aff, source c5b0b4a, activated on unchanged 0029 after checked
  pre-release backup 20261019T142919Z. Final post-release checker passes.
- Four live hosted API cases pass with selected factual narratives and both owned fictional
  accounts disabled/revoked. Two checker mount-permission failures occurred before account
  creation; they are retained separately from application checks.
- Initial live browser completed the overview, exact average scenario, compound answer,
  three responsive layouts, outcome clarification and social reply checks. It failed solely
  because navigating away cancelled a decision-analysis GET that its old allowlist lacked. A second run similarly recorded
  an intentional discovery GET cancellation.
  Source cleanup and observed AbortSignal events confirm that cancellation. The checker now
  accepts only matching observed GET aborts for these panels; the initial report is retained.
  An intervening checker-only regex syntax error and a fail-closed post-release check
  against the rejected browser report are retained. Fifteen cancellation classifier checks
  pass, including refusal without observed abort, wrong stage, POST or real network failure.
  The fresh browser run passes in 58.658 seconds (`live-browser-accepted.json`),
  with six overview layouts, exact average 2 → 2.5, default closed disclosures in both
  modes, existing compound/narrative/clarification/social journeys, zero page/network
  errors and verified own-account cleanup. Four live API tasks pass in 35.094 seconds.
  All five fictional accounts across live API and three browser runs are disabled/revoked;
  existing real sessions are unchanged.

No exhaustive analytical discovery, causal recommendations, universal language accuracy or
production-readiness claim is made. Feature requirement counts and external gates are unchanged.

Final release checks pass (`post-release-final.json`). Checked backups: before
20261019T142919Z, after 20261019T143504Z UTC. All 77 original table projections,
stored objects and configuration are preserved. Five services, six loopback listeners,
readiness/web, model/timers and exact running images pass. No restore, schema/provider
change, public exposure or push occurred. Existing real sessions remain unchanged.

Try it at the existing private tunnel: http://localhost:18400/workspace. Refresh the page,
load a source and use Overview. Review meanings/units where requested; an eligible
What-if shortcut opens an explicit assumption form. Confirm and calculate to save a
conditional result. Evidence and internal details expand on request.
