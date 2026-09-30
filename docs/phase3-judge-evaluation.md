> **File use case:** Runs and preserves the final optional-judge evaluation.
> **What it does:** Binds human labels to reviewed content and distinguishes rejection from completion.

# Final judge evaluation workflow

The private demo continues with the existing planner, deterministic execution and
checked source citations. The advisory judge remains disabled. A failed optional
candidate may be rejected; it does not have to be made reliable to finish its
assessment. Phase 3D is now Complete after the human-approved fixture assessment;
the final reviewed trial confirmed the do-not-adopt decision.

The repository user approved all twelve proposed labels on 2026-09-30 after
opening the review sheet. The recorded message was “done, approvedlabels”.
The original presented sheet is retained in ignored evaluation evidence; only
its approval-status introduction changed. Case facts, labels and scoring rules
were unchanged. The reviewed run and final status are recorded in
[Phase 3D verification](verification-phase3d.md).

## Reviewed run

The reviewer reads [the twelve examples and frozen rubric](phase3-judge-review.md).
An approval record in ignored `data/phase3-evaluation/` must contain:

- `scope`: `synthetic-judge-label-review`.
- `reviewer`: the actual human reviewer's name or accountable session identity.
- `reviewed_on`: ISO date, not in the future.
- `approved_case_ids`: all twelve IDs in their frozen order.
- `cases_sha256`: the hash of the canonical questions, facts and labels.
- `rubric_sha256`: the hash of the reviewed document.

Obtain the current fingerprints without invoking a provider:

```bash
PYTHONPATH=scripts python3 -c 'from evaluate_advisory_judge import evidence_identity; import json; print(json.dumps(evidence_identity(), indent=2))'
```

The completed reviewed run used:

```bash
python3 scripts/evaluate_advisory_judge.py --review data/phase3-evaluation/judge-review.json --output data/phase3-evaluation/judge-reviewed-001.json
```

The script refuses a stale, incomplete, wrong-scope, malformed or future-dated
review before any model request. Changing a label or fact changes its fingerprint;
a review of the old set does not authorize the new set. Hashes prove content
identity, not that the human's review was correct. The operator must preserve the
actual approval separately; the agent must never manufacture it.

## Explicit preliminary run

A run without human review must be labeled preliminary:

```bash
python3 scripts/evaluate_advisory_judge.py --preliminary --output data/phase3-evaluation/judge-preliminary-002.json
```

`--review` and `--preliminary` are mutually exclusive. Every run needs a new output
path; existing evidence cannot be overwritten. One provider call is allowed per
case, with a ten-second timeout and no retries. Only canonical fictional case IDs
can enter the evaluator. There is no runtime-history or arbitrary-document input.
The configured provider must be the already approved demo model; no real data is
transmitted by this workflow.

Reports include case/rubric/evaluator hashes, observation timestamp, actual returned
model identifiers, reported tokens and explicit rejection reasons. Missing token
usage remains unknown and billing cost is not invented. Cases must be complete
and unique, and recorded verdicts must match the frozen labels and scoring rule.
The report never enables a judge or changes a product answer or production gate.

## September 30 final engineering check

The existing twelve observations were rescored without new inference, preserving
`judge.json` and writing a separate ignored `judge-final-audit.json`. The outcome
remains `do_not_adopt`: human review missing, one issue-label disagreement, three
timeouts, p95 above five seconds, incomplete usage, and no approved judge budget.
See [ADR 0007](decisions/0007-representation-and-judge-trials.md) for measurements.
The rescored report is not a new model trial or a human-reviewed benchmark.

Nineteen added tests cover review-to-label binding, stale or malformed approvals,
report preservation, missing/duplicated/altered observations and timeout handling.
The evaluation/architecture subset passed **34 tests**. Ruff, mypy (100 files),
Python compilation and whitespace checks passed. The previous complete application
release remains the 376-backend-test/8-browser release with 5/5 live unified checks
and 8/8 concurrent VPS sessions. This change only hardens the offline evaluator;
it does not require an application migration, a changed runtime model, or a rebuild
of the deployed web/API application.

Commands executed for this continuation:

```bash
python3 -m ruff format scripts/evaluate_advisory_judge.py apps/api/tests/test_phase3_evaluations.py
python3 -m pytest apps/api/tests/test_phase3_evaluations.py tests/test_architecture.py --tb=short
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts deploy/vps
python3 -m mypy
python3 -m compileall -q scripts/evaluate_advisory_judge.py
git diff --check
ssh -S /tmp/execplus-phase3-ssh -o BatchMode=yes -o ConnectTimeout=10 administrator@173.208.151.137 'curl -fsS http://127.0.0.1:18401/health/ready'
```

The reviewed model result and its approval are documented in
[Phase 3D verification](verification-phase3d.md). The current 34-test rerun also
passed after approval; the preliminary evidence above remains historical.

One initial timeout-test failure was a Python 3.10 test-fixture mismatch between
built-in `TimeoutError` and `asyncio.TimeoutError`; the fixture now uses the same
exception as the actual async operation. The production handling was unchanged.

The final evaluator/tests and handoff were synchronized to VPS source after preserving
`releases/pre-phase3d-evaluator-source`. Runtime containers were not rebuilt or
restarted for this offline-only change. The API readiness check passed. The
production preflight still blocks all eight gates; its manifest is unchanged.
