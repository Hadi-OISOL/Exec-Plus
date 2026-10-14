> **File use case:** Plans honest closure of the sixteen remaining Partial VC features.
> **What it does:** Separates repository work from external setup and reviewed production evidence.

# Partial-feature closure plan — October 14

The maintained report has 37 Done, 16 Partial and 11 Not yet items. These counts
refer to bounded private-demo features, not production readiness. The teammate
onboarding integration improves 18 and 47 without inflating their scores. The
original 64 IDs remain unchanged. Prior research and acceptance requirements are
in [advanced analytics](advanced-analytics-research-plan.md), [ROADMAP](../ROADMAP.md)
and [production evidence](production-readiness.json).

| IDs | What remains | Dependency and acceptance |
| --- | --- | --- |
| 1, 40, 47 | Customer signup, production login and secure onboarding | Select identity provider, obtain domain/HTTPS, implement verified account/workspace creation and test authentication, session lifecycle and tenant isolation. Existing operator tokens remain private-demo only. |
| 14, 45 | Commercial metering, priced model costs and spend controls | Define paid plans and approved provider pricing/caps; enforce concurrent reservations, reconciliation and idempotent usage before billing claims. |
| 24 | Real scheduled email delivery | Approved SMTP service/from address; test failure/retry, authorization, opt-out and duplicate handling. Disabled delivery is not evidence of live email. |
| 33 | Root-cause analysis beyond observed differences | Separate descriptive drivers from causal claims; explicit assumptions and representative validation for each new module. |
| 42 | Complete recovery readiness | Latest-version restore drill, encrypted off-server copy, agreed retention/RPO/RTO and failure rehearsal. Current checked local VPS backups alone do not close disaster recovery. |
| 43 | Operational error monitoring | Central fixed-code collection, bounded retention, alert routing and incident drill without source values or credentials. An alert recipient/channel is required. |
| 44 | Representative AI evaluation | Approved real examples and correct-answer labels, quality/speed/cost comparison, retrieval/citation review and hosted-provider privacy approval. Fictional demo scores cannot substitute. |
| 50 | Representative performance acceptance | Agreed user/data workload, sustained rehearsal, latency/error/resource thresholds and current data parity. Eight-user functional tests are not sustained-load proof. |
| 57 | Advanced scenarios | Local/test compound percentage drivers extend bounded what-if comparisons. Deploy and verify this slice; source-derived multi-measure models, uncertainty and broader constraints remain open. |
| 58 | Broader anomaly detection | Local/test group baselines and explicit sparse/missing coverage are verified. Deploy and verify this slice; seasonal, multivariate/drift candidates and representative calibration remain open. |
| 59 | Broader prescriptive recommendations | Local/test exact allocation supports two resources under bounded enumeration. Deploy and verify this slice; business modules, precedence/exclusions, larger solvers and validated assumptions remain open. |
| 62 | Customer APIs/webhooks | Scoped credentials, source permissions, signed events, retries/idempotency and delivery audit. Internal APIs alone do not complete this feature. |
| 64 | Fine-grained permissions and audit | Policy design for row/column restrictions, consistent query/planner/replay/citation enforcement, migration compatibility and independent privacy tests. |

Dependency order: finish onboarding release; extend tested internal analytics under
the authorized research sequence; complete exports/first controlled connectors;
implement selected commercial providers and operational controls; run reviewed
production acceptance. Broader Phase 6 remains Frozen except explicitly authorized
bounded slices. Do not activate public access or clear gates from this plan.

In easy words, external inputs mean: the website address and HTTPS; the service
users will use to log in; an email sender; the service that takes payments; and real
approved example files with answers a human has checked. Credentials belong in
private operator configuration, never this document or chat. The private demo can
continue while these inputs are pending.
