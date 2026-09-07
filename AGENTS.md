> **File use case:** Persistent handoff and operating guide for humans and coding agents working on ExecPlus.
> **What it does:** Records current state, non-negotiable rules, commands, boundaries, and the next approved slice of work.

# ExecPlus Engineering Handoff

Read this file, `ROADMAP.md`, and `docs/decisions/architecture.md` before changing the project.

## Current state

- Phase 0: Engineering Foundation remains complete; its four exit criteria were reverified on 2026-09-07.
- The repository is a Python and TypeScript modular monorepo.
- The API has liveness and dependency-aware readiness endpoints for migrated PostgreSQL and the configured object bucket.
- Language models and vector databases are represented by provider-neutral protocols.
- No vector database vendor has been selected.
- The local-model path expects an OpenAI-compatible endpoint so Ollama, vLLM, or another server can be evaluated later.
- Runtime model selection is composed in `execplus/bootstrap.py`; routes and use cases must not branch on vendors.
- DuckDB is the planned Phase 1 compute engine for uploaded files.
- PostgreSQL is reserved for control-plane metadata, permissions, conversations, lineage, and audit records.
- MinIO provides an S3-compatible local object-store target.
- Week 1 implements local/test opaque-session identity behind an identity port; production identity remains a separate decision.
- Workspaces, roles, invitations, seat limits, retained CSV/XLSX uploads, and audit events have real PostgreSQL/MinIO integration coverage.
- Week 1 code and browser acceptance checks pass; configured Compose PostgreSQL 16 startup verification remains pending in this host session.
- Current evidence is 93 backend tests, 2 frontend tests, and 2 browser tests against PostgreSQL 14.24 and MinIO; see `docs/verification-week1.md`.
- Profiling, quality scoring, cleaning, and mapping are not implemented.
- No product feature should be represented as implemented unless tests prove it.

## Non-negotiable engineering rules

1. Never ask an LLM to calculate or supply a business number.
2. Execute validated, read-only queries and build answers from returned results.
3. Scope every resource lookup and mutation by `workspace_id`.
4. Apply permissions before query execution and before hybrid retrieval.
5. Return clarification for ambiguous requests and a supported-scope explanation for impossible requests.
6. Record model route, generated query, execution outcome, lineage, and returned answer in the audit trail.
7. Keep domain and application modules independent from web frameworks and infrastructure SDKs.
8. Add or update tests with each behavior change.
9. Update `ROADMAP.md` and this current-state section only when evidence supports the status change.
10. Do not commit datasets, secrets, model weights, generated exports, or local database volumes.
11. Put a file-level use-case and responsibility header at the top of every new file.
12. Do not add inline explanatory comments; prefer clear names, small functions, tests, and architecture documents.
13. Next.js can regenerate `next-env.d.ts`; restore its required file-purpose header before committing.

## Dependency direction

```text
presentation -> application -> domain
infrastructure -> application ports and domain
domain -> standard library only
```

Framework imports are forbidden in `execplus/domain`. Application services depend on protocols in `execplus/application/ports.py`, not concrete providers.

## Commands

```bash
make install
make check
make test
make api
make web
make dev-infra
make down
```


## Definition of done

- Acceptance criteria have automated coverage.
- Unit tests and architecture tests pass.
- Static analysis passes.
- Tenant isolation and numerical lineage are considered explicitly.
- Public contracts and configuration are documented.
- Logs contain identifiers and outcomes, not uploaded row values or secrets.
- Roadmap and handoff state reflect the tested implementation.

## Next approved slice

Finish the Week 1 operational verification against the configured Compose
PostgreSQL 16 service. Port 5432 on this host rejected development credentials;
Compose now accepts `EXECPLUS_POSTGRES_PORT` for a non-conflicting port.
See `docs/week1-api.md` for setup, supported identity flow, and test commands.

Do not start Week 2 without a new instruction. The current task explicitly
excludes profiling, quality scoring, cleaning, and mapping. Do not begin
conversational query generation until ingestion isolation and profiling
acceptance criteria pass.
