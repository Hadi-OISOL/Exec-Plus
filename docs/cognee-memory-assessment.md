# Cognee memory assessment — October 18, 2026

**Decision: retain Cognee as a reviewed research reference; defer Syntelio runtime integration.** Its graph and semantic document retrieval could help a future multi-document question-answering workload. Current work needs private preferences and exact, authorized earlier-result recall. Existing ThreadService, receipt replay and the bounded Trellis-derived tokenizer fit that requirement without a second durable memory system.

This is an engineering fit decision, not a claim that Cognee is unsafe or ineffective. No Cognee package, model, service or skill was installed or imported. No customer data, credentials, provider calls or runtime benchmark were used. No product dependencies, schema or global configuration changed.

## Source and license

Reviewed [official repository at commit 37f788bd287750e10d7610173e5332b3843f6ebd](https://github.com/topoteretes/cognee/tree/37f788bd287750e10d7610173e5332b3843f6ebd), package version **1.6.5**. Local ignored checkout: `data/agent-tools/references/cognee`. Initial GitHub DNS failure was followed by a successful shallow clone; its working tree is clean. Pin checks and hashes of reviewed sources are in `data/verification/2026-10-18/cognee/source-review.json`.

The package declares **Apache-2.0**, with `LICENSE` and `NOTICE.md`; preserve both for redistribution. Individual dependencies and downloaded models require their own license review. The source explicitly distinguishes its open-source GLiNER demo extractor from a separately licensed enterprise implementation. Do not claim enterprise parity. `SECURITY.md` provides private vulnerability reporting and supports the latest release only; that is a maintenance policy, not verification of security.

## What the code actually provides

| Need | Cognee implementation observed | Fit for Syntelio |
| --- | --- | --- |
| Semantic document retrieval | Graph/vector storage, multiple retrieval modes, optional references, graph extraction and embedding configuration | Potential future benefit for related facts spread across documents; benefit unmeasured here |
| Tenant and dataset permissions | Read-authorized dataset resolution; user, child-agent, tenant and role grants; selected-tenant filtering; per-dataset database contexts | Real controls, but separate identity and grant semantics need explicit mapping; not a substitute for Syntelio row/field policies |
| Private memory | User/session identities and separate memory lifecycle storage | A second durable store introduces consent, retention and forget obligations |
| Source-backed numerical answers | Retrieval context and generated completion, with optional references | Does not establish Syntelio exact arithmetic, confirmed units or immutable calculation receipts |
| Deletion | Dataset delete authorization, per-dataset pipeline locks, provenance-aware graph/vector cleanup, raw-file reference counting and session invalidation | Useful design, but requires failure-injection and race tests before an Syntelio forget guarantee |
| Current source and consent | Session invalidation exists; search history is recorded | No reviewed bridge to Syntelio revision, meaning, permission and explicit-memory versions at publication |

Permission details come from `cognee/modules/data/methods/get_authorized_existing_datasets.py`, `modules/users/permissions/methods/get_all_user_permission_datasets.py`, `modules/search/methods/search.py` and `context_global_variables.py`. Omitting dataset selection searches accessible datasets; omitting a user in SDK APIs can resolve the default user. An adapter must always supply explicit identities and dataset IDs. Backend access control defaults according to whether the selected graph/vector providers support it and can be disabled by environment configuration. Require and verify it explicitly in any multi-user experiment; do not infer isolation merely from a dataset argument.

Deletion details come from [datasets.py at the reviewed commit](https://github.com/topoteretes/cognee/blob/37f788bd287750e10d7610173e5332b3843f6ebd/cognee/api/v1/datasets/datasets.py) and `modules/data/methods/delete_dataset.py`. Delete operations take the dataset lock used by pipelines and remove attributable graph content. Both session invalidation helpers catch exceptions and log a nonfatal warning, allowing deletion to continue. Graph/vector and relational changes occur across separate operations rather than one demonstrated cross-store transaction. These are specific integration concerns, not proof of a data leak. A successful delete response alone cannot be accepted as proof that every derived session stopped using forgotten content. Upstream has tenant/deletion tests; they were inspected by location, not executed here.

## Local operation and security boundaries

The reviewed `pyproject.toml` contains **54 core dependency entries**, including SQLAlchemy, LanceDB, Ladybug, FastEmbed/ONNX, LiteLLM/OpenAI, FastAPI, pandas, ingestion and model tooling. This is substantially more than a text tokenizer. No dependency resolution or vulnerability scan was performed for this assessment.

Local operation is supported, but “no API key” does not mean no downloads or installation. `modules/cognify/config.py` selects the local GLiNER demo when usable LLM credentials are absent; `gliner_auto_install` defaults to **true**. Its installer can install torch from the PyTorch CPU index and the remaining GLiNER dependencies into the running environment. Embeddings have local fallback behavior; local model artifacts still need download, license, disk and memory review. With provider credentials, configured LLM/embedding paths can use external services. No current Syntelio provider should be reused implicitly.

[Telemetry code](https://github.com/topoteretes/cognee/blob/37f788bd287750e10d7610173e5332b3843f6ebd/cognee/shared/utils.py) exits when `TELEMETRY_DISABLED` is set, or in test/dev mode. Otherwise it can send operation metadata and stable pseudonymous machine/key tracking identifiers; its sanitization is not equivalent to disabling telemetry. Search spans include up to 500 query characters. `base_config.py` permits Langfuse credentials to enable tracing unless explicitly disabled. Search also records local query/completion history. For any future experiment set `TELEMETRY_DISABLED=1`, `COGNEE_TRACING_ENABLED=false`, `GLINER_AUTO_INSTALL=false`, use an empty credential environment and isolated HOME/storage, and review all logging/history retention. These settings are prerequisites, not a complete security certification.

## Comparison with the current design and Trellis

Syntelio `application/services/threads.py` authorizes candidate turns before retrieval, resolves receipt evidence for reuse, and checks private memory context. Publication retains source and permission freshness checks. `domain/context_retrieval.py` handles explicit requests for earlier answers within bounded candidate/text budgets, requires a unique match, and clarifies ambiguity. `domain/agent_memory.py` stores deliberately saved actor/workspace preferences; those preferences guide wording and suggestions, never numerical facts, units or permissions.

The current Trellis adoption is narrow: an attributed MIT tokenizer from commit `104ee0b03d30569e9ba36971dd343e4e507a5f4a`, with an ExecPlus-specific authorized retrieval adapter. It does not install Trellis's vault, MCP server or automatic write hooks. See `docs/intelligence-reference-adoption.md`. Trellis graph expansion and Cognee graph extraction both remain distinct from verified receipt replay. Neither should silently save agent-inferred personal facts or turn agricultural associations into causal claims.

## Concrete reconsideration gate

Revisit Cognee when users demonstrate relevant facts distributed across documents that existing authorized retrieval misses. First create a disposable, credential-free synthetic corpus and measure a baseline. Suggested fixed workload: 30 questions across 20 documents, two tenants, duplicate names, contradicting revisions, revoked access and explicit forget cases. Compare source recall, unsupported assertions, latency, peak memory, storage and deletion behavior against the existing retriever.

An experiment must pass every cross-tenant/revocation/forget negative case, demonstrate a meaningful retrieval improvement on that fixed corpus, and preserve exact source IDs and revision checks before any answer is published. Test deletion failure and concurrent ingestion/search explicitly. Record model artifacts and dependency locks; do not allow runtime installation. Start with retrieval-only output and a fixed result/time budget, with no autonomous tools or memory writes.

Only then consider a separately scoped adapter that returns candidate source references to Syntelio. Syntelio remains responsible for consent, row/field projection, permissions, current-source checks, numeric tools and evidence. A future runtime integration needs its own reviewed dependency/storage/provider decision; this assessment does not authorize it.

Current usable outcome: the pinned source, concrete risks and evaluation criteria are retained for future work. The intended private earlier-result recall continues through the existing governed implementation. No performance, accuracy or production-readiness claim is made for Cognee.
