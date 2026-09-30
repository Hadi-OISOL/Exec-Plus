> **File use case:** Records Phase 3 implementation evidence and open release gates.
> **What it does:** Distinguishes tested local behavior from unevaluated production capabilities.

# Phase 3 verification — 2026-09-17

Status: **In progress**. Implementation follows the Phase 2 audit on local branch
`phase2`; no Phase 4 work has started.

Implemented:

- Three reproducible ranked profile observations with revision references.
- Exact replay-backed scalar comparisons with evidence IDs, zero-baseline handling
  and explicit absence of causal conclusions.
- Fixed-category feedback carrying server release/workspace/actor metadata, with
  arbitrary text rejected; manager-only aggregate usage and event-derived onboarding.
- Self-subscribed report schedules, durable delivery claims, original-analysis replay,
  authorization immediately before delivery, unsubscribe and sanitized failure audits.
- Immutable TXT/Markdown objects, stable chunk offsets/checksums, private/shared
  visibility, authorization before ranking, verified result candidates and citations.
- Bounded lexical/hashed-vector reference retrieval and an offline evaluation command.
- Workspace UI for observations, feedback, reference documents/search/citations,
  saved analyses and daily subscription/unsubscribe.

Evidence:

- The full `make check` passes 286 backend tests, 2 frontend tests, Ruff, mypy,
  frontend lint/types and the production build. Tests use real PostgreSQL/MinIO.
- Five browser tests pass, including the combined analytics/Phase 3 journey and
  existing narrow-screen/user-activation journeys.
- Phase 3 tests cover foreign tenants, private source filtering before ranking,
  revocation before citation access, malicious ranker output, malformed/oversize
  documents, source tampering, non-sensitive telemetry, report repeat claims,
  unsubscribe, disabled/failing mail providers and revocation during replay.
- Additional transaction/concurrency regressions verify compensation after document
  metadata commit failure and cancellation when a saved analysis is deleted during
  report replay. All 17 Phase 3 tests pass in the targeted run.
- No real email was sent; capture adapters exercise delivery. No source document was
  transmitted to a local or hosted language model during evaluation.

Commands in addition to the [Phase 2 check commands](verification-phase2.md):

```bash
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55433/execplus python3 -m pytest apps/api/tests/test_phase2_hardening.py apps/api/tests/test_phase3_integration.py -q
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55433/execplus python3 -m pytest apps/api/tests/test_phase3_integration.py -q
python3 scripts/evaluate_phase3.py
python3 -m ruff check apps/api migrations scripts
python3 -m mypy
```

Synthetic reference evaluation: three fictional questions, hit-rate@3 1.0,
MRR@3 1.0, zero external requests. One observed run had median 0.295 ms and maximum
0.404 ms on this machine. Tiny fixture timings vary and are not production latency
or customer relevance evidence. The output explicitly declines production selection.

Open gates before Phase 3 can be Complete:

1. Approved representative customer documents and relevance judgments.
2. An agreed retrieval relevance threshold, including negative/ambiguous cases.
3. Learned embedding-provider evaluation and a production vector-provider comparison
   covering isolation, filtering, deletion, backup/restore, latency, operations and cost.
4. Measured local and hosted model quality, latency, privacy and cost. No approved
   model endpoint/name or representative corpus was supplied.
5. Operational SMTP configuration and worker scheduling in the target environment;
   external delivery behavior still needs deployment rehearsal. Uncertain SMTP
   outcomes/abandoned claims require operator inspection, not automatic duplicate sends.

See [contracts and limits](phase3-activation-knowledge.md) and
[the provisional retrieval ADR](decisions/0006-retrieval-evaluation.md).

Final evidence: `make check` passed **286 backend tests**, 2 frontend tests, all
static checks and the production build. The narrative-retention follow-up test also
passes: repeated comparisons append receipts rather than replacing prior commentary.
The required Next.js file-purpose header was restored after build generation.

## Approved demo and DeepSeek verification — 2026-09-17

The user approved fictional documents and hosted DeepSeek V4 Pro for this iteration.
Representative-customer and comparative provider reviews are now mandatory Phase 5
production gates, not prerequisites to generating demo material. The earlier open-gate
list remains historical context; see the current
[demo/release guide](phase3-demo-and-production-gates.md).

- Six fictional Markdown policy documents and twenty question/answer cases were
  generated under ignored `data/phase3-demo-v1/`. The checked-in generator preserves
  edited files and source checksums; the human answer sheet is `questions.md`.
- Offline retrieval found the expected source in the top three for all 16 answerable
  questions (hit-rate@3 1.0, MRR@3 0.9375). Unsupported/ambiguous cases are evaluated
  separately; these are tiny synthetic fixtures, not a customer relevance claim.
- Hosted DeepSeek V4 Pro passed **20/20** evidence-selection/classification cases:
  16 supported, two unsupported and two ambiguous. Median observed latency was
  3469.36 ms; provider-reported input/output usage was 11486/374 tokens for this run.
  Actual cost reconciliation and local-model comparison remain open production gates.
- An initial smoke passed 1/2; the first full run passed only 2/20 because responses
  failed the strict structured-output contract. Explicit JSON response mode fixed
  the integration; expected answers and strict server validation were unchanged.
  Both failed and passing reports remain locally available. These are single-run
  observations, not statistical production reliability measurements.
- A separate live pipeline smoke routed a fictional revenue question through
  DeepSeek, executed the proposed plan in DuckDB, obtained exactly
  `0.300000000000`, and verified the selected summary evidence. Raw source values
  were not sent for model calculation.
- **292 backend tests pass**, including six new demo/provider/release-gate tests.
  Ruff and mypy (83 files) pass. The existing frontend/browser evidence above
  remains applicable; this change did not modify the frontend.
- `make production-preflight` intentionally exits nonzero with all eight gates open.
  Production startup also rejects missing/invalid evidence before initializing
  infrastructure. API credentials were never printed or added to Git.

Commands for this iteration:

```bash
make demo-corpus
make evaluate-demo
python3 scripts/evaluate_demo_model.py --limit 2 --output data/phase3-demo-v1/model-smoke.json
python3 scripts/evaluate_demo_model.py --output data/phase3-demo-v1/model-evaluation.json
python3 -m pytest apps/api/tests/test_demo_readiness.py apps/api/tests/test_provider_contracts.py apps/api/tests/test_bootstrap.py tests/test_architecture.py -q
EXECPLUS_TEST_DATABASE_URL=postgresql+psycopg://execplus:execplus@localhost:55433/execplus python3 -m pytest
python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts
python3 -m mypy
make production-preflight
git diff --check
```

Demo validation is verified. Production acceptance remains blocked by the explicit
release ledger; these results do not select a production vector database or approve
customer-document transmission to a hosted provider.

## Private VPS follow-up (2026-09-28)

The user subsequently authorized a private eight-user demo with a supplied VPS.
Deployment, 298 backend tests, concurrent API/browser checks, Qwen quantization
comparison and backup restoration are recorded in [VPS verification](verification-vps-demo.md).
Qwen Q4 scored 19/20 on the fictional evidence test; this does not supersede the
open production-quality gates or the historical DeepSeek evaluation above.
