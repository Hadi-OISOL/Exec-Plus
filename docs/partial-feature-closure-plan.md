> **File use case:** Plans honest closure of the seventeen remaining Partial VC features.
> **What it does:** Separates repository work from external setup and reviewed production evidence.

# Partial-feature closure plan — October 16

The maintained feature ledger has 37 Done, 17 Partial and 10 Not yet items. The
original 64 ordered IDs remain unchanged. ID 13 is now Partial for protected
saved-answer PDF export, verified locally and on the private demo under E26.
This is a bounded implementation score, not production readiness or a claim that
all exports work. Existing onboarding improvements retain IDs 18 and 47's scores. Prior research and acceptance requirements are
in [advanced analytics](advanced-analytics-research-plan.md), [ROADMAP](../ROADMAP.md)
and [production evidence](production-readiness.json).

| IDs | What remains | Dependency and acceptance |
| --- | --- | --- |
| 1, 40, 47 | Customer signup, production login and secure onboarding | Select identity provider, obtain domain/HTTPS, implement verified account/workspace creation and test authentication, session lifecycle and tenant isolation. Existing operator tokens remain private-demo only. |
| 13 | Complete PDF/Excel export scope | Verified protected PDF downloads cover completed saved calculations, exact returned tables and source-backed explanations with receipts, source/definition context and private access checks. Excel, chart images, full dashboard/report exports and pattern/forecast/scenario/diagram reports remain open; each needs exact-value, evidence, pagination/layout and authorization tests. This does not clear the separate email/report-delivery production gate. |
| 14, 45 | Commercial metering, priced model costs and spend controls | Define paid plans and approved provider pricing/caps; enforce concurrent reservations, reconciliation and idempotent usage before billing claims. |
| 24 | Real scheduled email delivery | Approved SMTP service/from address; test failure/retry, authorization, opt-out and duplicate handling. Disabled delivery is not evidence of live email. |
| 33 | Root-cause analysis beyond observed differences | Pooled/within-group comparisons now supplement descriptive drivers. Causal claims still need explicit assumptions and representative validation for each new module. |
| 42 | Complete recovery readiness | Latest-version restore drill, encrypted off-server copy, agreed retention/RPO/RTO and failure rehearsal. Current checked local VPS backups alone do not close disaster recovery. |
| 43 | Operational error monitoring | Central fixed-code collection, bounded retention, alert routing and incident drill without source values or credentials. An alert recipient/channel is required. |
| 44 | Representative AI evaluation | Approved real examples and correct-answer labels, quality/speed/cost comparison, retrieval/citation review and hosted-provider privacy approval. Fictional demo scores cannot substitute. |
| 50 | Representative performance acceptance | Agreed user/data workload, sustained rehearsal, latency/error/resource thresholds and current data parity. Eight-user functional tests are not sustained-load proof. |
| 57 | Advanced scenarios | Compound percentage drivers and explicit daily-change assumptions are deployed and verified for the private demo. Source-derived multi-measure models, uncertainty and broader constraints remain open. |
| 58 | Broader anomaly detection | Group baselines and explicit sparse/missing coverage are deployed and verified for the private demo. Seasonal, multivariate/drift candidates and representative calibration remain open. |
| 59 | Broader prescriptive recommendations | Exact allocation supports two resources, explicit prerequisites and exclusions in the verified private demo. Business modules, time precedence/scheduling, larger solvers and validated action effects remain open. |
| 62 | Customer APIs/webhooks | Scoped credentials, source permissions, signed events, retries/idempotency and delivery audit. Internal APIs alone do not complete this feature. |
| 64 | Fine-grained permissions and audit | Policy design for row/column restrictions, consistent query/planner/replay/citation enforcement, migration compatibility and independent privacy tests. |

All four bounded phases in the [clean-experience plan](clean-experience-plan.md)
are complete through October 16: focused screens, reliable saved-definition reuse,
internal analytics depth and fixed-case/workload evidence. The
[verification ledger](verification-internal-analytics-depth.md) retains limits.
Representative evaluation, sustained performance and external dependencies remain
open. The later [domain-agent tool slice](domain-agent-tools.md) adds the bounded
PDF implementation under [E26's release verification](verification-domain-agent-tools.md);
no existing Partial item becomes Done. All eight production gates remain unchanged.

Dependency order: improve the existing onboarding experience; extend tested internal analytics under
the authorized research sequence; complete exports/first controlled connectors;
implement selected commercial providers and operational controls; run reviewed
production acceptance. Broader Phase 6 remains Frozen except explicitly authorized
bounded slices. Do not activate public access or clear gates from this plan.

In easy words, external inputs mean: the website address and HTTPS; the service
users will use to log in; an email sender; the service that takes payments; and real
approved example files with answers a human has checked. Credentials belong in
private operator configuration, never this document or chat. The private demo can
continue while these inputs are pending.
