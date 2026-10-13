> **File use case:** Records evidence for the October 10 bounded anomaly and decision delivery.
> **What it does:** Separates verified private-demo behavior, retained failures and unfinished broader analytics.

# Decision-analysis verification

Status: Complete for the explicitly authorized bounded local/test and private-demo
extension. Migration **0016** is deployed. VC 58 and 59 are **Partial**, because
broader calibrated detectors and business decision models remain absent. VC 60's
basic private approval/rejection/reopening workflow is **Done**. This does not
complete Phase 6, commercial readiness or production acceptance.

Read [the preimplementation audit](decision-analysis-plan.md),
[method/API contracts](decision-analysis.md) and [ADR 0010](decisions/0010-bounded-decision-analysis.md).
The existing demo was reconnected and eight sessions privately renewed/verified
before implementation. Credentials and generated data are not repository artifacts.

## Local results

- **927 distinct backend/architecture cases pass:** the final full suite passed
  **922** in **829.34 seconds**, then the final 24-case integration group passed
  in **40.11 seconds**. Nineteen of those integration cases overlap the full run;
  five were added afterward. The new delivery adds **58 cases**: 34 domain cases
  and 24 real PostgreSQL/MinIO integration cases. No count is inflated by repeats.
- Domain tests compare weighted statistics with independently expanded median/
  quartile calculations and allocation with exhaustive enumeration over thirty
  seeded small problems. Tests cover degenerate baselines, repeated/constant/small
  samples, materiality, unsafe/invalid numbers, exact decimals, ties, mandatory
  minimums, infeasibility and bounded work. Statistical ratios remain labelled
  approximations; findings are not confirmed errors or calibrated probabilities.
- Integration covers full typed receipt/result replay, required population filters,
  private owners including workspace admins, query-receipt privacy, revocation
  during calculation, stale meaning and ineffective approval, concurrent optimistic
  reviews, tampered request/result/units/meaning/receipt, corrupted object bytes,
  missing values, source/result caps and composite database source constraints.
  Corrupted bytes return the existing `503 storage_integrity` refusal, not an answer.
- Migration tests retain prior metadata and exercise current readiness and old
  0014/0015 preservation contracts. Existing query, forecast, study, support and
  conversation checks remain passing.
- Ruff, mypy over **154 files**, TypeScript, ESLint, **17 frontend tests**, local
  production build and VPS candidate builds pass. Generated `next-env.d.ts` changes
  were restored; unrelated formatting was not retained.
- **30 distinct real-service browser journeys pass.** The full offline attempt
  passed 28, failed one model-dependent average and skipped the live mixed-chat
  case. Both passed in the live DeepSeek rerun. The new journey also passed after
  the final analysis-focus improvement, including exact decimal display, private
  saved history, finding feedback, approve/reopen, source replay and 1440/390/320
  widths. It uses real infrastructure, not mocked numerical answers.
- A clean non-root candidate image passed **eight concurrent users / 32 exact
  query executions and replays**, independently expected values and deterministic
  method reconstruction. Network was disabled; NumPy, pandas, SciPy, statsmodels
  and Prophet were absent. This is a functional bounded-compute check, not a benchmark.

## Private VPS release

Before mutation, all **207 existing runtime/source files** matched the Git baseline.
Rollback source lives under `releases/pre-decisions-20261010/source`; API/web images
retain tag `pre-decisions-20261010`. Checked pre-release backup
**20261010T175603Z** verified the database dump and object archive SHA-256 values,
stopping API/jobs before storage and restarting previously running services.

Candidate API/web images were built separately and clean-tested before activation.
Activation held `/run/lock/execplus-maintenance.lock`, stopped writers, captured
table fingerprints, copied the candidate source, migrated and restarted API/web/jobs.
Migration **0016** preserved hashes/counts for **all 44 prior data tables** and added
only `analysis_runs` and `analysis_reviews`. API dependency readiness, web HTTP 200
and the jobs service pass. Models, secrets and loopback exposure were unchanged.

The separate **Decision walkthrough · fictional only** workspace has one confirmed
fictional cost/benefit source shared with the existing eight demo accounts. Its
definition explicitly labels per-unit, additive toy assumptions. Existing uploads,
meanings, workspaces and saved results were not replaced.

Eight concurrent deployed browsers passed in **64.245 seconds**:

| Check | Passing evidence |
| --- | ---: |
| Users | 8 / 8 |
| Private anomaly/allocation runs | 16 |
| Finding feedback / recommendation reviews | 16 |
| Immutable saved-run reopenings | 16 |
| Independently typed source-receipt replays | 16 |
| Cross-user run/review/receipt access denials | 448 |
| Desktop / 390 / 320 layouts | 24 |
| Browser errors | 0 |

The original source profile/understanding metadata stayed unchanged. The result
`110.200000000000` is an independently expected conditional benefit for a fictional
budget of `2`; it is not a customer outcome. Review never executed an external action.
This short functional rehearsal does not establish sustained eight-user capacity.

Four older profile-v1/v2 receipts passed independent typed-checksum replay both
before and after release. A retained private forecast and its actual comparison
reopened with identical complete-response hashes. These six compatibility controls
are separate from new analysis checks.

Checked post-release backup **20261010T180215Z** includes the new run/review data.
It stopped API/jobs before storage, verified both archive checksums and restarted
storage/API/jobs with healthy readiness. Refresh and backup timers remain active.
Preserve new metadata before rollback; old images expect 0015 and an older backup
must not overwrite subsequently saved work.

## Commands and retained attempts

Local integration/browser runs used disposable PostgreSQL on loopback **15433**
and MinIO on **19000** with `EXECPLUS_TEST_DATABASE_URL` and
`EXECPLUS_TEST_OBJECT_STORE_ENDPOINT`. Other applications and their ports were
left alone. The substantive commands executed were:

```bash
python3 -m pytest apps/api/tests/test_decision_analysis.py tests/test_architecture.py -q
python3 -m pytest apps/api/tests/test_decision_analysis_integration.py -q -x
python3 -m pytest -q
python3 -m pytest -o addopts='' -q
python3 -m pytest apps/api/tests/test_decision_analysis_integration.py -o addopts='' -q
python3 -m pytest apps/api/tests/test_operations_persistence.py::test_0015_preserves_all_0014_tables_forecasts_receipts_and_jobs apps/api/tests/test_workspace_integration.py::test_real_readiness_and_migration_roundtrip -o addopts='' -q
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
npm run typecheck:web
npm run lint:web
npm run test:web
npm run build:web
python3 scripts/check_browser.py decisions.spec.ts
python3 scripts/check_browser.py
EXECPLUS_BROWSER_LIVE_MODEL=1 python3 scripts/check_browser.py workspace.spec.ts --grep 'first file needs no setup|combined data and document chat'
python3 scripts/create_decision_demo.py
python3 scripts/check_production_gates.py
```

On the VPS, candidate builds used the existing compose file with a separate image
override. Clean computation used `docker run --network none --read-only` and the
candidate API image. The private deploy script ran under the maintenance lock with
`python -m alembic upgrade head`, source/table fingerprints and compatible image
promotion. Pre/post backup used `sudo bash deploy/vps/backup.sh`. The private
eight-user script and legacy/forecast probes retain their exact commands, outputs,
IDs, hashes and screenshots under ignored `data/vps-private/decision-analysis-20261010/`.
No password or session token is recorded here. No commit, push or merge occurred.

Retained failures include the initial query-lineage field-length error, an allocation
receipt precheck omitting `matched_records`, exact-scale and required-filter fixture
expectations, old migration-head/table-list assumptions, and the source-integrity
test expecting a different error status. These were corrected and verified; unsafe
answers were never substituted. The new browser's first two failures were an
ambiguous label selector and an integer fixture expecting decimal scale. An SSH
administration control stream stalled while candidate images built; a fresh
connection verified completed images and healthy demo access. Root-private table
fingerprints required sudo reads, and the report builder correctly refused a
missing verification document before regeneration. Failed logs remain separate.

## Remaining boundaries

- Seasonal/time-series, multivariate, drift and calibrated anomaly methods;
  representative labels, segment validation and repeated-testing controls.
- More decision modules, causal effects, nonlinear/multiple-resource constraints,
  scenarios, team approval stages and separately authorized external execution.
- Natural-language dispatch into these methods, durable analysis jobs, automatic
  refresh/alert integration, archival and pagination beyond the bounded private limits.
- Phase 4D exports, Phase 4E first connectors, remaining Phase 5 commercialization
  and representative performance/recovery/privacy/identity acceptance.

All **eight production gates remain blocked**. The VC report preserves the original
64 IDs and now counts **37 Done / 15 Partial / 12 Not yet**. Competitor review remains
dated October 5; this delivery makes no percentage-parity or performance claim.

The updated October 10 DOCX and PDF are published on the Desktop, with the older
named report copies synchronized and their prior contents backed up under ignored
`data/reports/2026-10-10/desktop-backups/`. Validation preserves all 64 original IDs
and labels, checks referenced evidence files, and confirms the ten-page PDF.
Pages 6 and 9 were visually checked for table overflow. The initial report checker
mistook the summary count for a feature ID; selecting only feature tables corrected
the checker without changing report content. A final local production web build
also passes after the analysis-focus change.
