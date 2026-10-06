> **File use case:** Primary onboarding guide for developers and operators.
> **What it does:** Explains ExecPlus, the repository layout, and the shortest path to a working local environment.

# ExecPlus

ExecPlus is a self-serve analytics platform that turns structured business data into traceable answers and charts. Numerical output is computed by a query engine; language models may plan, explain, and summarize, but never invent business figures.

## Current status

The October 6 operations update adds **Support** for private requests and replies,
**Usage & retention** for workspace owners/admins, and an **Admin console** for
explicitly granted internal staff. Staff can inspect operational metadata and handle
support requests without acquiring access to private customer analyses. Usage reports
show deliberate activity and completed-week return cohorts with their definitions.
See the [operations contract](docs/operations-console-support.md) and
[verification ledger](docs/verification-operations.md). Run migration **0015** after
pulling. Staff grants are operator-only; ordinary workspace ownership does not grant
platform administration. Billing and public production readiness remain unfinished.

Phase 4C is complete for the approved local/test and private-demo scope as of
October 6, and is deployed to the VPS. Open
**Forecasts** to estimate complete daily or monthly periods, inspect historical
test errors and compare later actual data with a saved forecast. Source actuals
remain exact; estimates and heuristic ranges are clearly labelled. Grounded
commentary explains measured differences without claiming their cause. **Audit
history** now exposes searchable activity under each person's current permissions.
The forecasting slice introduced migration **0014**. See the
[forecasting contract and model trial](docs/phase4-forecasting.md),
[audit visibility contract](docs/audit-history.md) and
[release verification](docs/verification-phase4c.md) for acceptance evidence,
including the successful eight-user functional rehearsal.

The October 4 foundation extension is verified locally and deployed to the private
VPS demo. It adds durable private
chat requests with recorded execution activity, cancellation and resume; optional
Expert views expose existing evidence plus authorized artifact and quality
descriptions. It introduced migration 0013; keep `make jobs` alongside the API/web app.
See the [implementation plan](docs/platform-foundation-plan.md),
[conversation job contract](docs/conversation-jobs.md) and
[bounded compute contract](docs/compute-broker.md),
[artifact and quality contract](docs/platform-artifacts-quality.md) and
[acceptance record](docs/verification-platform-foundation.md). These conversation
and evidence contracts remain compatible with the forecasting extension.

The October 2 workspace starts with a file: sign in, choose a CSV or single-sheet
XLSX, and upload. First-time users get an automatic workspace and file-named dataset.
Calculated starting points, data checks and relevant questions appear beside chat;
definitions and advanced controls stay optional until a request needs them.
New uploads handle semicolon/tab CSVs, mixed identifier codes and numeric calendar
components with versioned reconstruction. Read the
[data-partner guide](docs/data-partner-reset.md) and
[verification record](docs/verification-data-partner.md).

Phases 0 and 1 remain verified for local/test operation. The teammate's Phase 2
branch has been audited and hardened: verified DuckDB analytics, KPI dashboards,
filters, drill-down, conversational planning, private threads, saved analyses and
workspace sharing are implemented. Phase 3 adds observations, feedback, checklists,
scheduled report delivery and authorized document search; its production provider
and representative-corpus evaluation gates remain open.

Phase 3A adds editable, versioned business definitions under **Data understanding**,
private goals, reviewed relationships and definition-aware query/replay safeguards.
It requires migration 0009. See [the data-understanding guide](docs/phase3-data-understanding.md).
Unified data/document conversation, private history and catalog discovery now
require migration 0010. Offline representation and judge trials are documented;
Phase 3D completed its human-reviewed assessment with a do-not-adopt decision;
no judge is enabled. Phase 3 is complete for the private-demo scope.

Phase 4 has started with **Studies & dashboards**: goal-aware suggestions, exact
descriptive studies and immutable versions, ordered survey views, six-pin private
or shared dashboards, and separate department workspaces grouped by organization.
The private demo now also includes **Refresh & alerts**: validated staged-file
replacement/append/merge, schedules, replayable observations, exact segment drivers
and private KPI notifications. That slice introduced migration 0012; the current
application requires **0014**. See the
[4A guide](docs/phase4-studies.md), [4B guide](docs/phase4-refresh-monitoring.md) and
[4B verification](docs/verification-phase4b.md). Schedules process files staged in
ExecPlus. Forecast comparisons can use an accepted refresh without changing the
original forecast. Exports remain Phase 4D and live connectors remain Phase 4E.
All eight production gates remain blocked; private-demo evidence does not clear them.

For a guided trial, choose **Try forecasting sample** in Data library, review its
date/measure meanings and units, then choose **Predictive · basic forecasts** under Analysis
focus or open **Forecasts**. Confirm the complete daily coverage before creating
a forecast. The fictional sample contains ninety days; older samples are unchanged.
Descriptive and all-supported views remain available. Prescriptive analysis is
labelled planned and cannot execute.

Forecasting compares last-value, recent-mean and linear-trend methods, with an
optional declared seasonal baseline. Separate validation and test windows expose
MAE, RMSE, WAPE and MAPE, including zero-value limitations and a last-value test
benchmark. Ranges are heuristic, not calibrated confidence intervals. This path
does not call language models or automatically retrain. ARIMA and Prophet were
evaluated separately and are not runtime dependencies.

Use `/workspace` for the application. See [Phase 2 contracts](docs/phase2-analytics.md),
[the interactive explorer and hybrid chat](docs/conversational-explorer.md),
[Phase 2 verification](docs/verification-phase2.md),
[Phase 3 contracts and limitations](docs/phase3-activation-knowledge.md), and
[local setup](docs/week1-api.md). After pulling this branch, run `make install` and
`make migrate` before restarting the API and web app. Models and email remain
configuration-dependent; deterministic dashboards do not require a model.

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

In a third terminal, start the conversation worker:

```bash
make jobs
```

Keep the worker running while using chat. Questions are stored in PostgreSQL so
closing a browser tab does not lose the request; reopen private conversation
history to resume its activity. **Cancel request** explicitly asks the worker to
stop. API-only installations retain the older synchronous `/ask` endpoint.

The API is served at `http://localhost:8000`, its documentation at `http://localhost:8000/docs`, and the web application at `http://localhost:3000`.

## Quality checks

```bash
make check
```

The command runs backend linting, type checks, tests, and frontend checks. Individual commands are documented in the `Makefile`.

## Product invariants

- Every request is scoped to an authenticated workspace.
- Observed numerical values come from successful execution against authorized data; statistical estimates are labelled separately and retain their source evidence.
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

## Phase 3 demo

For the private eight-user VPS deployment, individual SSH tunnel keys, session
renewal, backup operations and expansion checklist, read the
[VPS demo runbook](docs/vps-demo-runbook.md). DeepSeek handles primary query planning;
the optional Qwen helper suggests routes/columns and selects executed evidence.
The earlier standalone Qwen trial is recorded in [VPS verification](docs/verification-vps-demo.md).

Run `make demo-corpus` to create six fictional policy files and twenty known-answer
questions in `data/phase3-demo-v1/`. Run `make evaluate-demo` for offline retrieval;
`make evaluate-demo-model` uses the configured hosted model and incurs API usage.
The approved current model is DeepSeek V4 Pro. See
[setup and mandatory production gates](docs/phase3-demo-and-production-gates.md).
`make production-preflight` deliberately fails until real release evidence is reviewed.

Unified chat and catalog discovery are described in
[the Phase 3 conversation contract](docs/phase3-unified-conversation.md).
The [verification ledger](docs/verification-phase3b-c.md) distinguishes local and
deployed checks. [Candidate trials](docs/decisions/0007-representation-and-judge-trials.md)
do not enable a runtime judge, learned search provider or Parquet cache.
The [reviewed Phase 3D assessment](docs/verification-phase3d.md) closes the private-demo
phase. All production gates remain open in Phase 5.

For the optional judge assessment, use the [final evaluation workflow](docs/phase3-judge-evaluation.md).
