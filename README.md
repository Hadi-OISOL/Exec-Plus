> **File use case:** Primary onboarding guide for developers and operators.
> **What it does:** Explains ExecPlus, the repository layout, and the shortest path to a working local environment.

# ExecPlus

ExecPlus is a self-serve analytics platform that turns structured business data into traceable answers and charts. Numerical output is computed by a query engine; language models may plan, explain, and summarize, but never invent business figures.

## Current status

Phases 0 and 1 are verified for local/test operation. `/workspace` provides sign-in,
workspaces, invitations, seats, isolated CSV/XLSX uploads, deterministic profiles,
quality scores, previewable/reversible cleaning and column mapping, synthetic
finance/sales/inventory samples, guided onboarding and workspace usage counts.
PostgreSQL 16.10 and MinIO integration and browser acceptance checks pass.

Conversational analytics and KPI dashboards remain Phase 2 scope. See
[Phase 1 verification](docs/verification-phase1.md),
[data preparation guide](docs/phase1-data-preparation.md), and
[local setup and workspace API](docs/week1-api.md).

See [ROADMAP.md](ROADMAP.md) for delivery phases and [AGENTS.md](AGENTS.md) for the live engineering handoff.

## Architecture at a glance

```text
apps/web -> apps/api -> application services -> domain
                         |       |       |
                      query     LLM    retrieval
                         |       |       |
                      DuckDB  local/   future vector store
                              hosted
```

The backend starts as a modular monolith. Its ports keep compute, language-model, identity, storage, and retrieval implementations replaceable without distributing the system prematurely.

## Prerequisites

- Python 3.10 or newer
- Node.js 20 or newer
- Docker with Compose for PostgreSQL and object storage

## Local setup

```bash
cp .env.example .env
make install
make dev-infra
make migrate
make init-storage
python3 -m execplus.manage provision-user --email owner@example.test
make api
```

The provisioning command prints an eight-hour session token. Enter it on `/workspace`; keep it private. Provision each invited email through the same local operator command. This identity provider is disabled outside local/test. If port 5432 is occupied, follow the alternate-port instructions in [the setup guide](docs/week1-api.md).

In another terminal:

```bash
make web
```

The API is served at `http://localhost:8000`, its documentation at `http://localhost:8000/docs`, and the web application at `http://localhost:3000`.

## Quality checks

```bash
make check
```

The command runs backend linting, type checks, tests, and frontend checks. Individual commands are documented in the `Makefile`.

## Product invariants

- Every request is scoped to an authenticated workspace.
- Numerical values reach users only after successful execution against the selected dataset.
- Generated SQL is read-only, bounded, validated, and recorded before execution.
- Ambiguous metrics trigger clarification rather than a guessed query.
- Every answer includes lineage and an audit event.
- Local and hosted language models are selected through configuration.
- Vector retrieval is optional and accessed only through a provider-neutral port.
- Uploaded data remains inside the configured deployment boundary.

## Repository layout

```text
apps/api          Python API and application core
apps/web          Next.js user interface
docs              Architecture and engineering decisions
infra             Container and deployment foundations
tests             Cross-cutting architecture tests
```

## Configuration

Configuration is environment-driven. Copy `.env.example` locally and never commit secrets. Production deployments must supply secrets through the cloud provider's secret manager.
