> **File use case:** Closes the reviewed Phase 3D assessment and private-demo Phase 3 milestone.
> **What it does:** Records human approval, measured judge rejection and unchanged production gates.

# Phase 3D verification — 2026-09-30

**Phase 3D is Complete as an assessment with a do-not-adopt decision.**
All four Phase 3 feature/evaluation slices are now Complete for the approved
local/test and private-demo scope. This closes the missing human-review criterion;
it does not approve a runtime judge or any production deployment. Phase 4 remains
Planned and has not started.

## Human review and frozen evidence

After opening `docs/phase3-judge-review.md`, the repository user explicitly wrote
“done, approvedlabels” in this conversation on September 30. This approves all
twelve labels from the preceding review request. The reviewer is recorded as
**Repository user in this Codex conversation**, without inventing a personal name
or independent reviewer. This is product-owner review, not external certification.

The table, questions, expected labels, scoring rules and adoption thresholds were
unchanged. The review sheet's introductory status was updated before recording its
hash. The original sheet as presented is retained separately. The approval record
was validated against both the exact cases and the annotated rubric before inference.

| Artifact | SHA-256 |
| --- | --- |
| Original presented review sheet | `40f044437d8ffa2ac4da23ef70a65e8207b9ba94919bd09a081eb4ff2d33dd8f` |
| Canonical cases/facts/labels | `66ec30aa69dfe36a77ebfa9864615ca6d0f3c4161c5b101d8a6bed2d10ec0309` |
| Rubric with approval-status annotation | `5e8e5e268d6564075840e5fb4e0952b3d58ade3f11fef77cadc8f9cbb1d47e28` |
| Human approval record | `a4a92b386d10337da8655a5c3f9b1beb6153accebaa8f12472a85dd6e1753437` |
| Evaluator source | `f93da7a6cc2cccaafc2a910f2b8703cdf1266935f335ae1403b544a0db866dcd` |
| Reviewed result | `a16a8349bd7e575151679ad0901195172946118d0b0b58ebb2b7240fbbcb3b46` |

Generated evidence is retained under ignored `data/phase3-evaluation/` as
`judge-review.json`, `judge-reviewed-001.json` and
`judge-rubric-as-presented-v1.md`. The earlier preliminary result and final audit
remain intact. No generated corpus, credentials, weights or private user data
enter version control.

## Reviewed trial

The run completed at **2026-09-30 12:30:16 UTC** using the configured hosted
`deepseek-v4-pro`; that same model identifier was returned on completed calls.
There was one call per canonical fictional case, no retries, a ten-second deadline,
JSON output mode, reasoning disabled and a 256-output-token limit. The trial runs
locally against the approved hosted API; it is not a new eight-user VPS load test.

| Case | Expected | Observed | Exact match |
| --- | --- | --- | --- |
| city-missing | missing_filter | Timed out | No |
| city-correct | pass | pass | Yes |
| period-wrong | wrong_period | Timed out | No |
| period-correct | pass | Timed out | No |
| meaning-wrong | wrong_meaning | missing_filter | No |
| meaning-correct | pass | Timed out | No |
| claim-unsupported | unsupported_claim | Timed out | No |
| claim-correct | pass | pass | Yes |
| mixed-incomplete | incomplete_answer | incomplete_answer | Yes |
| mixed-complete | pass | Timed out | No |
| partial-honest | pass | pass | Yes |
| injection | missing_filter | missing_filter | Yes |

- Strict label matches: **5/12**; unavailable feedback: **6/12**.
- Three defects produced no alert because their requests timed out; one additional
  defect was detected but assigned the wrong issue label.
- False alerts on completed acceptable cases: **0**. Timed-out acceptable cases
  remain failures and are not counted as correct passes.
- Added p95 latency: **10,012.89 ms**, above the frozen 5,000 ms limit.
- Reported completed-call usage: **959 input / 82 output tokens**. Timed-out calls
  may incur additional usage. Total usage and billing cost are unknown.
- Runtime answer changes: **0**. Runtime judge enabled: **No**.

The passive no-judge fixture baseline has six missed defects, zero false alerts and
zero added model calls. This does not claim the existing application would accept
those hypothetical invalid plans: deterministic guards already enforce many of
these constraints. No incremental production-quality benefit over those guards
has been established by this small assessment.

**Decision: do not adopt.** Exact-label recall, reliable completion and latency
failed the frozen thresholds. Usage is incomplete and no judge spending budget
has been approved. The human-label gate is now satisfied. Budget approval is not
needed to reject the candidate; it would be required for future adoption. A rejected
optional candidate satisfies the assessment's decision criterion. The thresholds
were not weakened, failed cases were not removed, and the judge was not enabled.

## Verification and changes

The existing evaluation/architecture subset passed **34 tests**, one dependency
warning, in 0.45 seconds. Ruff, mypy (100 files), Python compilation and whitespace
checks passed. No new test or runtime behavior was needed for this approval/run;
existing tests cover stale/malformed reviews, label binding, incomplete observations,
report preservation, malformed judge output, prompt injection, private-context
rejection and timeout handling.

The unchanged application release retains its prior **376 backend tests, 2 frontend
tests, 8 browser journeys, 5/5 deployed unified checks and 8/8 concurrent deployed
browser sessions**. Those were not rerun or relabeled as new evidence for this
small evaluation/documentation closeout. The VPS readiness and migration were
checked again: PostgreSQL/object storage healthy, **0010**.

Updated files: `ROADMAP.md`, `AGENTS.md`, `README.md`, review-sheet approval status,
judge workflow, ADR 0007, architecture, the VPS runbook, the earlier 3B–3C ledger's
follow-up note, and this verification record. The current branch remains `phase2`;
existing work is preserved, with no commit, merge or push in this continuation.

Commands executed:

```bash
git status --short
git branch --show-current
python3 scripts/evaluate_advisory_judge.py --review data/phase3-evaluation/judge-review.json --output data/phase3-evaluation/judge-reviewed-001.json
python3 -m pytest apps/api/tests/test_phase3_evaluations.py tests/test_architecture.py --tb=short
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
python3 -m compileall -q scripts/evaluate_advisory_judge.py
git diff --check
make production-preflight
```

The model report was redirected to `/tmp/execplus-judge-reviewed-001.log`. A local
Python step wrote the review record exclusively after verifying that all twelve
Markdown verdicts matched the canonical cases and the configured provider was the
approved demo model. No key was printed. `make production-preflight` returned the
expected failure: all eight production gates remain blocked. Its manifest remains
unchanged at SHA-256
`8f2b92715756aab3b6c969b1001b1bc2f461176b9600cf29464342e5f24dcef9`.

## VPS evidence retention

Documentation was synchronized to the VPS source. The previous source was preserved
at `releases/pre-phase3-close-source`; the five reviewed artifacts are retained
with mode-restricted access at
`/sdb-disk/OISOL_ExecPLUS/ops/phase3d-reviewed-001`. All five SHA-256 checks passed.
The runtime API/web/model containers were not rebuilt, restarted or reconfigured.
A final readiness check passed after synchronization.

An initial archive-filename mismatch stopped extraction before source changes;
resuming with the actual uploaded filenames succeeded. The corrected VPS commands
were run from `/sdb-disk/OISOL_ExecPLUS`:

```bash
tar -xzf ops/execplus-phase3-close-source.tar.gz -C source
mkdir -m 700 ops/phase3d-reviewed-001
tar -xzf ops/execplus-phase3-reviewed-evidence.tar.gz -C ops/phase3d-reviewed-001
chmod -R go-rwx ops/phase3d-reviewed-001
cd ops/phase3d-reviewed-001
sha256sum -c SHA256SUMS
curl -fsS http://127.0.0.1:18401/health/ready
```

## Remaining work

Phase 4's adaptive studies/dashboard work, refresh/alerts, forecasts, exports and
first connectors remain Planned. All previously deferred Phase 5 reviews remain
mandatory before external customer deployment. Parquet serving/caching and the
learned retrieval candidate were not adopted; these remain explicitly documented
optimization decisions. A future judge requires a new tested adoption policy,
representative evidence and an approved operating budget. No more label approval
is needed for this completed twelve-case assessment.
