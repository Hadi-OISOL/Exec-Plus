> **File use case:** Preserves researched delivery planning for VC features 57, 58, 59 and 63.
> **What it does:** Defines dependencies, method choices, data contracts, evaluation and release criteria without changing implementation status.

# Advanced analytics and embedded dashboard delivery plan

Planning date: October 13, 2026. Implementation baseline observed: `phase2` at
`639e28c`, with the bounded private-demo decision extension on migration 0016.
The subsequent user request authorized starting implementation; the bounded
scenario slice is verified on 0017 in [its ledger](verification-scenario-planning.md).
The retained October 10 table below is historical; VC 57 is now Partial. This does
not authorize activating all of Phase 6 or
evidence that new features are implemented. The existing eight production gates
remain mandatory. No application or VPS change is part of this planning slice.

ExecPlus should connect supported analyses through one governed evidence lifecycle:
confirmed data meaning, an explicit question, an eligible versioned method,
reproducible computation, an inspectable result and a human decision. Methods can
expand independently; a single detector or solver must not be advertised as
working for every dataset or business problem.

## Verified feature baseline from October 10

The supplied Desktop `ExecPlus_VC_Feature_Report_2026-10-10.docx` has 64 feature IDs.
Its entries agree with `product-feature-audit.json`; there is no feature 69.
Do not map 69 to 60 without the user's correction. Approval feature 60 is included
below because it is a dependency of recommendations, not an assumed renumbering.

| VC ID | Feature | Current status | Remaining product scope |
| --- | --- | --- | --- |
| 57 | Scenario planning | Not yet | Versioned what-if assumptions, scenario computation and comparison |
| 58 | Anomaly detection | Partial | Seasonal, segmented and multivariate methods, calibration and drift evaluation |
| 59 | Prescriptive recommendations | Partial | Multiple constraints, business modules and validated effect assumptions |
| 60 | Recommendation approval | Done for basic private scope | Separately designed team review and external-action authorization |
| 63 | Embedded dashboards | Not yet | Host authentication, restricted views, origin controls and customer isolation |

Existing reusable components include `DecisionAnalysisService`, `ForecastService`,
`StudyService`, source reconstruction, exact query receipts, confirmed meanings,
staged refresh, monitoring, durable conversation jobs and private audit.
Current detectors use weighted MAD/IQR; the allocation solver supports one
declared integer budget. Existing analysis HTTP execution is not a durable job.
The latest method-only recheck passed 34 tests; it does not validate any proposed
extension. See [current acceptance evidence](verification-decision-analysis.md).

The teammate's separate `/home/administrator/abm/Exec-Plus` upload review changes
are an independent, unverified dependency candidate. Audit its API payloads,
meaning confirmation, private-note handling and source-change behavior before
integration. Do not overwrite the deployed source with that checkout.

## Dependencies and delivery order

| Slice | Dependency | Concrete delivery | Acceptance boundary |
| --- | --- | --- | --- |
| A | Existing 0016 contracts | Common versioned analysis inputs, source bindings and evaluation fixtures | Existing receipts, numerical strings and private results remain compatible |
| B | A | Feature 57 deterministic scenario engine and comparison UI | Conditional estimates with saved assumptions; no invented demand response |
| C | A | Feature 58 segmented and calendar-aware anomaly trials, then selected runtime methods | Measured alert quality and chronological evaluation for eligible datasets |
| D | B and A | Feature 59 multiple-resource decisions and explicit scenario inputs | Independently checked feasibility, objectives and solver status |
| E | B–D | Governed chat dispatch, durable analysis jobs and explicit refresh subscriptions | Idempotency, cancellation, scope and current-source checks pass |
| F | Identity and scoped access foundations from Phase 5 | Feature 63 private embedding prototype, followed by reviewed external embedding | Host-origin, token lifecycle, browser and cross-tenant security tests pass |

B and C can later be developed independently after A, but each release needs its
own evidence. Public embedding and commercial decision claims depend on Phase 5.
Phase 4D exports and 4E connectors remain separate unfinished work; these features
must initially operate on retained CSV/XLSX snapshots rather than promise live
connectivity. Broader Phase 6 activation remains Frozen in the canonical roadmap.
No calendar completion promise follows from this sequence. Re-estimate each slice
after its gap audit, fixture review and bounded prototype.

## Common analysis and evidence contracts

Every proposed run binds workspace, dataset, owner, original upload/revision,
confirmed understanding, required filters, units, method and implementation version.
Inputs distinguish observed values, user-declared assumptions, fitted estimates and
business constraints. The output retains exact query receipts, parameters,
result checksum, numerical representation, coverage and limitations.

Add new result kinds or versions rather than changing `decision-analysis-v1`.
Introduce a domain-owned eligibility contract describing supported grain, types,
required history, units, completeness and resource limits. The server validates
eligibility; model suggestions cannot bypass it. The browser displays a reason
and a focused correction when a method is unavailable.

Keep domain computation standard-library-only. Optional scientific libraries and
solvers belong in infrastructure adapters behind application ports, preferably
isolated bounded workers. Pin candidate packages in an evaluation environment
first. Adopt a runtime dependency only after image, numerical, operational and
license review; the research below selects no production package.

Decimal amounts remain exact strings. Approximate statistical scores, forecasts
and solver tolerances receive separate labels and recorded precision policies.
Float conversion must never alter retained amounts or accounting constraints.
Derived arrays need explicit column order, row identity, missingness policy,
transformation version, training boundaries and byte checksums. Embeddings remain
evidence-discovery representations, not substitutes for numerical records.

New runs remain creator-private by default. Workspace/staff admins do not gain
access. Collaboration requires a new explicit permission model rather than an
exception in existing private-run endpoints. Recheck permission and source bindings
before execution, publication, reopening, sharing and review. Changes invalidate
current approval; preserve historical evidence when still authorized.

## Feature 57 scenario planning

Scenario planning answers a conditional question: what follows if declared inputs
change? Scenario forecasting examines plausible alternatives, including extremes;
an alternative is not necessarily the likely outcome. [Forecasting Principles and
Practice, scenario forecasting](https://otexts.com/fpp3/judgmental.html#scenario-forecasting).

Start with a bounded deterministic calculation module: at most five alternatives
per comparison and ten declared assumptions per alternative, proposed limits to
verify against fixtures and load before finalizing. Bind all alternatives to one
baseline and comparable units, coverage and grain. The source is never rewritten.

Allow server-owned typed operations such as setting an eligible input, changing it
by a declared percentage, or replacing an allocation budget. Formula templates
are bounded named operations over confirmed inputs. Do not execute user formulas,
SQL, Python or model-generated expressions. A declared price increase changes
revenue only under an explicit quantity assumption; estimating how price changes
demand requires a separately evaluated response model. Stock snapshots cannot be
summed across time as transaction flows.

Save immutable scenario versions with creator, baseline evidence, assumptions,
method, comparison group and checksum. Compare baseline and alternatives using
exact deltas; percentage differences are unavailable when their baseline is zero.
Incompatible currencies or periods refuse comparison. Sensitivity charts show
conditional outputs over a bounded grid; ranges must not masquerade as confidence
intervals. Reopening recalculates source queries and scenario outputs. Source
refresh offers a new version and preserves the original.

The UI should ask one question at a time: objective, eligible inputs, assumptions,
then alternatives. Show an editable assumption summary and baseline before Run.
Offer side-by-side tables and sensitivity plots, with exact table values and
approximate plot coordinates. Chat may draft a known scenario, but the user must
confirm its assumptions and the server must calculate.

Acceptance includes independent Decimal fixtures, zero/negative values, mixed
units, rounding boundaries, percentages, incompatible periods, invalid templates,
stale meanings, tampered assumptions, original-byte changes and cross-user denials.
An independent calculator must agree with every supported fixture. A new version
must reproduce after process restart without changing the old run.

## Feature 58 anomaly detection

Use a method registry based on confirmed data shape:

| Data shape | First candidate | Evaluation requirement |
| --- | --- | --- |
| One numerical snapshot | Retain weighted MAD/IQR v1 | Preserve duplicate frequencies, materiality and degenerate baseline semantics |
| Comparable categories | Per-segment robust checks | Explicit minimum support and segment coverage; no silent global fallback |
| Complete regular calendar series | Seasonal-naive residual baseline, then robust STL trial | Score new periods using earlier history; missing periods remain explicit |
| Multiple numerical features | Isolation Forest trial; LOF as a comparator | Versioned scaling, row identity and held-out labeled evaluation |
| Distribution changing over refreshes | Separate drift-assessment trial | Distinguish population change from unusual individual records |

STL supports a robust fitting option, but that does not itself establish calibrated
anomaly thresholds. [statsmodels STL documentation](https://www.statsmodels.org/stable/generated/statsmodels.tsa.seasonal.STL.html).
Isolation Forest and LOF are candidates, not default replacements. Outlier detection
and novelty detection have different training assumptions; contamination affects
threshold selection and is not a learned probability that a record is wrong.
[scikit-learn outlier and novelty detection](https://scikit-learn.org/stable/modules/outlier_detection.html).

For calendar methods, distinguish retrospective decomposition from prospective
monitoring. A decomposition using the complete series cannot supply a leakage-free
historical alert evaluation. Fit and select thresholds on earlier training and
validation windows, then score untouched later observations. Rolling-origin
evaluation uses only observations preceding each test point.
[Forecasting Principles and Practice, time series cross validation](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation).

Retain a stable record reference for new row-level findings; current v1 distribution
findings identify distinct values and counts, not individual rows. Protect identifiers
and reauthorize any record drill. Retain reason, observed value, baseline, score,
threshold, materiality, coverage and method; never claim a causal explanation from
an unsupervised score. Multivariate attribution is an explanatory approximation
unless separately validated.

Build disjoint evaluation sets for stable values, legitimate seasonal peaks,
trend changes, isolated spikes, duplicate-heavy populations, sparse segments,
missing periods and unit changes. Known injections are synthetic evidence; genuine
reviewed business labels are needed for customer claims. Keep tuning and test labels
separate, and measure precision/recall where labels support them, false alerts per
period, coverage, latency and reviewer workload. Segment and repeated-search
effects require a recorded multiple-testing policy; do not cherry-pick discoveries.

Release thresholds must be agreed for each use case before opening the final test
set. Without reviewed labels, release only an exploratory unusualness view with
clear limitations. Human dismissal/investigation is feedback, not automatic truth
or retraining. Review any retrained method as a new version.

## Feature 59 prescriptive recommendations

Broaden the existing allocation contract through explicit decision modules. Each
module requires an objective, candidate actions, quantity domains, costs, resource
constraints, benefit assumptions, baseline and a separately versioned effect model
when effects are estimated. A sales or margin column is not automatically the
benefit caused by taking an action.

First extend declared linear allocation to multiple resources, minimum/maximum
quantities, exclusions and precedence. Compare candidate CP-SAT against exhaustive
small cases and the existing single-budget dynamic program. CP-SAT uses integer
constraints and distinguishes optimal, feasible, infeasible, invalid and unknown
statuses. [Google OR-Tools CP-SAT documentation](https://developers.google.com/optimization/cp/cp_solver).

Represent all decimal coefficients by exact declared integer scales, proving that
conversion fits the solver's supported integer range. Refuse scale overflow rather
than round a budget or cost. After solving, independently recalculate every resource,
objective and constraint with Decimal from original inputs. Any failed verification
withholds the recommendation. A timeout with a feasible incumbent is not optimal;
record the bound and gap when available. Preserve the actual selected quantities
and solver result rather than assume repeated runs choose the same tied optimum.

Then evaluate separately approved modules such as inventory replenishment or
workforce scheduling. Each needs its own units, coverage, lead-time/capacity rules,
effect assumptions and infeasible fixtures. For example, reorder advice needs
stock, lead time and justified demand assumptions; incomplete inputs must not
produce a plausible-looking recommendation. Nonlinear, stochastic and causal
methods remain later modules rather than hidden changes to linear allocation.

Scenario comparisons may feed decisions only when their inputs and assumptions are
compatible. Always show do-nothing/current-policy baseline, objective, constrained
resources, estimated benefit and limitations. Describe which constraints bind;
do not turn a solver sensitivity or association into a causal root-cause claim.

Reuse private review for the first extension. Team approval needs a distinct grant
model with named approvers, immutable role snapshots, optimistic transitions and
current-source checks. Approval records a decision; external execution requires a
separate capability, request, authorization, idempotency and audit design.

Acceptance requires exhaustive oracle parity for small cases, exact constraint
checks, budget/scale extremes, ties, incompatible units, infeasibility, timeouts,
invalid models, cancellation, result tampering, concurrent review and stale approval.
Estimated action effects require an agreed external validation protocol before
business-effect claims; solver correctness alone does not establish those effects.

## Chat jobs and refresh integration

Extend the existing server-owned typed plan vocabulary with eligible scenarios,
anomaly methods and decision modules. The primary model interprets intent; advisory
routing never grants execution authority. Ambiguous objectives, inputs or constraints
produce focused clarification. No model supplies calculations or private data from
another workspace. Activity shows real actions, not model chain-of-thought.

Reuse the job lifecycle deliberately: immutable requested method/parameters, current
source verification, fenced publication, cancellation cleanup, limits and owner-only
events. Add explicit retry semantics for analysis work; current conversation retry
rules are not automatically safe for every solver. Keep canceled or stale output
unpublished while retaining identifier/outcome audit.

Automatic refresh is opt-in per method and source. An accepted refresh creates a
new observation/run, never rewrites an old result or approval. Schema/meaning drift,
insufficient history and rejected candidates pause the subscription. Reuse private
alert authorization and cooldown rules after qualifying an event; do not send every
statistical flag. Measure eight-user concurrency and a representative sustained
workload separately. Set latency/RSS and queue-age budgets after a recorded baseline.

## Feature 63 embedded dashboards

Start with read-only boards containing explicitly shareable studies. Private anomaly,
scenario and decision runs cannot be embedded through an admin shortcut. They need
an explicit sharing design first. Host identity must map to an authorized customer
principal and resource grant; the host page cannot choose arbitrary workspace IDs.
ThoughtSpot exposes dedicated embedding authentication patterns, including trusted
authentication. This is a design reference, not a dependency or integration claim.
[ThoughtSpot embedding authentication](https://developers.thoughtspot.com/docs/embed-auth).

Prototype a server-issued, narrowly scoped embed grant with audience, host origin,
workspace, resource/version, principal, expiry and revocation identifier. Prefer an
opaque short-lived bootstrap grant exchanged once for a restricted view session.
Keep tokens out of URLs, browser storage and logs. Every view request rechecks
current grant, user access and resource sharing. Expiry and revocation must stop
subsequent data access; previously downloaded data cannot be recalled.

Render a dedicated embed route with no upload, admin, editing or broader navigation
capability. Apply a response-header `frame-ancestors` policy for the permitted hosts;
CORS alone does not control framing. This directive does not inherit `default-src`
and is not supported in a meta element. [MDN frame ancestors](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors).

If resize/filter events use `postMessage`, validate sender origin, source window,
event type, schema and bounds; send to an exact target origin rather than `*`.
[MDN postMessage security guidance](https://developer.mozilla.org/en-US/docs/Web/API/Window/postMessage).
Server-side filter validation still governs execution. Cache keys and retrieval
must include principal/grant/resource scope, with no cross-tenant reuse.

Exercise Chrome, Firefox and Safari behavior under third-party-cookie blocking.
Select the exchange/session transport only after that prototype; do not promise
SSO compatibility from a desktop iframe test. Test nested frames, origin spoofing,
token replay, expiry, revocation, unsharing, source loss, navigation, accessibility,
responsive charts and exact exported labels. Public release additionally requires
domain/TLS, production identity/privacy and Phase 5 acceptance.

## Verification and private VPS release

Before implementation, inventory current source and preserve the teammate checkout
and all unrelated work. Allocate migrations only after inspecting the then-current
head. Proposed new entities include scenario groups/versions, evaluation metadata,
versioned method artifacts and embed grants; avoid speculative general-purpose DAG
tables or duplicate receipt stores.

For each delivered slice, run domain/architecture tests, real PostgreSQL/MinIO
integration, static checks, frontend checks and meaningful browser journeys. Include
exact old profile-v1/v2 receipts, forecasts, existing analysis reviews and all eight
users' authorized controls alongside cross-user denials. Scientific/solver adoption
also requires bounded clean non-root image tests without unnecessary network access.

Before deployment, save source/image checkpoints and a maintenance-coordinated
checked backup. Record existing table counts/hashes, apply additive migrations,
build candidate images and independently verify source/image identity. Release only
the accepted slice under the existing maintenance lock. Verify readiness, jobs,
model reachability and relevant browser flows through the private tunnel. Complete
a checked post-release backup and preserve new metadata through rollback.

Update `product-feature-audit.json` and the DOCX/PDF only after verified behavior;
preserve all 64 IDs, previous report copies and the October 5 competitor audit.
Keep broad 58/59 Partial until their advertised scope passes agreed evaluation.
Do not clear any production gate from synthetic data or short eight-user rehearsals.

## Handoff and unresolved decisions

The next implementation proposal should name one bounded slice, its fixtures,
required inputs and completion evidence. Suggested first slice is deterministic
scenario planning B after common-contract audit A. The subsequent user authorization starts this sequence; A and the bounded B
delivery are now verified. C remains the next evaluated extension, with external
embedding still subject to Phase 5 identity and security acceptance.

Resolve feature 69's intended name, representative evaluation datasets/labels,
anomaly alert budgets, initial decision domain and host embedding/identity setup
before claiming those capabilities. Customer data and labels can be provided later;
initial fixtures remain fictional and cannot clear production acceptance.

Primary references above were checked October 13, 2026. Method/library APIs must be
rechecked at adoption time. The proposed limits, architecture and delivery sequence
are ExecPlus design choices; the linked sources establish the specific method and
browser/security facts cited, not product acceptance or universal coverage.
