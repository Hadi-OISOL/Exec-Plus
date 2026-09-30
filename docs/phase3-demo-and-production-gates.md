> **File use case:** Records the approved demo setup and non-waivable production follow-up.
> **What it does:** Explains fictional documents, DeepSeek configuration, evaluation and release blockers.

# Phase 3 demo setup

Update 2026-09-28: a private VPS demo now runs Qwen3-4B for eight users. Local
development can still use the DeepSeek configuration below. See the
[VPS runbook](vps-demo-runbook.md) and [measured limitations](verification-vps-demo.md).
The private deployment does not clear the production gates in this document.

On 2026-09-17 the user approved fictional documents and known answers for current
development, selected hosted DeepSeek V4 Pro, and deferred representative-customer
validation until before production. This replaces the earlier request to supply
customer documents and local GPU hardware now. It does not certify production readiness.
The API and databases still run locally; DeepSeek performs hosted model inference.

## Demo documents

Run `make demo-corpus`. The generated folder is `data/phase3-demo-v1/` under the
repository, ignored by Git. The reproducible source is `scripts/create_demo_corpus.py`.
It refuses to overwrite changed files and labels every document as fictional.

Six documents cover refunds, expenses, leave, inventory, workspace access and reports
for fictional Cedar Demo Company. `evaluation.json` contains source checksums and
20 questions with expected answers: 16 answerable, two unsupported, two ambiguous.
The generator source is versioned; generated documents/results are not committed.

Upload the six policy `.md` files through `/workspace` → Reference documents.
Read `questions.md` for the human-readable answers. Do not upload that answer sheet,
`evaluation.json` or the generated README. Documents remain private
unless you explicitly check sharing in the UI.

`make evaluate-demo` checks retrieval of the 16 answerable questions with the reference
ranker. Ambiguous/unsupported examples are evaluated separately, not silently scored
as answered. The reference vectors remain deterministic hashed tokens, not learned
semantic embeddings or a selected production vector database.

## Hosted model

DeepSeek's [API introduction](https://api-docs.deepseek.com/) lists the base URL
`https://api.deepseek.com` and model `deepseek-v4-pro`. Its
[chat contract](https://api-docs.deepseek.com/api/create-chat-completion/) supports
`reasoning_effort=none` and `max_tokens`; these keep structured demo requests bounded.
Configuration was verified against the official documentation on 2026-09-17.

Use the ignored `.env` file:

```dotenv
EXECPLUS_LLM_MODE=hosted
EXECPLUS_LLM_BASE_URL=https://api.deepseek.com
EXECPLUS_LLM_API_KEY=<your local secret>
EXECPLUS_LLM_SMALL_MODEL=deepseek-v4-pro
EXECPLUS_LLM_LARGE_MODEL=deepseek-v4-pro
EXECPLUS_LLM_JSON_MODE=true
EXECPLUS_LLM_MAX_OUTPUT_TOKENS=1024
EXECPLUS_LLM_REASONING_EFFORT=none
```

The two tier names currently route to the same approved model. JSON output mode
is enabled because the application requests structured plans and evidence IDs. Routes and use cases
remain provider-neutral. A response truncated by the token limit is rejected.
Restart `make api` after changing environment settings. `.env.example` keeps models
disabled until a developer supplies credentials and explicitly enables hosted mode.

`make evaluate-demo-model` makes up to 20 hosted requests (with bounded transient
retries) and writes `data/phase3-demo-v1/model-evaluation.json`. It transmits only the
canonical fictional evidence after verifying every generated file. Edited/custom
corpora are refused by this command. The output contains case IDs, pass/fail, selected
fictional evidence IDs, latency and token usage; never API keys or raw prompt dumps.

This benchmark tests evidence selection: the model selects sentence IDs and the
server supplies the known source statements. It does not ask the model to calculate
business numbers. It is separate from the application search path, which returns
authorized source passages. Live smoke/evaluation results are recorded in
[Phase 3 verification](verification-phase3.md), including failed cases.

## Mandatory production follow-up

[production-readiness.json](production-readiness.json) is the machine-readable open
ledger. Every item must pass before production or externally accessible customer alpha:

| Gate | Required evidence |
| --- | --- |
| Representative corpus | Approved customer-like documents, human answer/relevance labels |
| Retrieval quality | Agreed thresholds, missing/ambiguous cases, source/citation correctness |
| Vector provider | Selection with tenant isolation, filtering, deletion, latency and cost tests |
| Backup/restore | Successful restore of database metadata, source objects and selected search index |
| Model comparison | Measured local/hosted quality, latency, token usage and actual cost |
| Provider privacy | Approved handling/retention/residency, secrets and hosted-data boundary |
| Report delivery | Real SMTP/worker rehearsal, revocation/unsubscribe and uncertain-delivery recovery |
| Identity/security | Production authentication and complete tenant-isolation review |

Run `make production-preflight`. Its nonzero result is expected while these are open.
Production runtime construction also refuses startup without validated evidence via
`EXECPLUS_PRODUCTION_EVIDENCE_PATH`. This is independent of model selection; changing
a model name or marking Phase 3 demo work complete cannot bypass the evidence check.

For each gate the release owner supplies status `passed`, a named reviewer, an ISO
review date, an evidence file inside the release bundle, and its SHA-256 checksum.
The manifest must have `scope: production`. Missing/changed evidence, demo scope or
future review dates are rejected. Artifact hashes prove integrity, not whether a
human review was correct; the release owner must ensure evidence is genuine and
applicable to the deployed version. All entries currently remain open.

These follow-ups belong to Phase 5 commercial readiness and must finish before the
first external customer deployment even if the team develops Phase 4 features sooner.
