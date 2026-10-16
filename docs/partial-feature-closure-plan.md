> **File use case:** Plans honest closure of the sixteen remaining Partial VC features.
> **What it does:** Separates repository work from external setup and reviewed production evidence.

# Partial-feature closure plan — October 16

The maintained feature ledger has **39 Done, 16 Partial and 9 Not yet** items,
with the original 64 ordered IDs unchanged. Portable exports (13) and internal
incident monitoring (43) are complete for the tested private-demo contract;
advanced forecasts (56) are now Partial. Read the
[release ledger](verification-remaining-work-release.md) for scope and evidence.
This does not establish production readiness. The next local implementation
batch remains unreleased; its results must not be described as current VPS behavior.

| IDs | What remains | Dependency and acceptance |
| --- | --- | --- |
| 1, 40, 47 | Customer signup, production login and secure onboarding | Implement verified account/workspace creation and test authentication, session lifecycle and tenant isolation. An external identity provider is optional; public domain/HTTPS, verified email and independent production review remain external setup. Existing operator tokens remain private-demo only. |
| 14, 45 | Commercial metering, priced model costs and spend controls | Define paid plans and approved provider pricing/caps; enforce concurrent reservations, reconciliation and idempotent usage before billing claims. |
| 24 | Real scheduled email delivery | Approved SMTP service/from address; test failure/retry, authorization, opt-out and duplicate handling. Disabled delivery is not evidence of live email. |
| 33 | Root-cause analysis beyond observed differences | Pooled/within-group comparisons now supplement descriptive drivers. Causal claims still need explicit assumptions and representative validation for each new module. |
| 42 | Complete recovery readiness | Current-version isolated restore and encrypted operator-workstation copy now pass; see `docs/recovery-rehearsal.md`. Approved independent key custody/destination, retention and recovery objectives remain open. |
| 44 | Representative AI evaluation | Approved real examples and correct-answer labels, quality/speed/cost comparison, retrieval/citation review and hosted-provider privacy approval. Fictional demo scores cannot substitute. |
| 50 | Representative performance acceptance | Agreed user/data workload, sustained rehearsal, latency/error/resource thresholds and current data parity. Eight-user functional tests are not sustained-load proof. |
| 56 | Advanced forecasting acceptance | Delivered method selection uses chronological validation and a later holdout. External regressors, calibrated uncertainty and representative customer accuracy remain open. |
| 57 | Advanced scenarios | Compound percentage drivers and explicit daily-change assumptions are deployed and verified for the private demo. Source-derived multi-measure models, uncertainty and broader constraints remain open. |
| 58 | Broader anomaly detection | Group baselines and explicit sparse/missing coverage are deployed and verified for the private demo. Seasonal, multivariate/drift candidates and representative calibration remain open. |
| 59 | Broader prescriptive recommendations | Exact allocation supports two resources, explicit prerequisites and exclusions in the verified private demo. Business modules, time precedence/scheduling, larger solvers and validated action effects remain open. |
| 62 | Customer APIs/webhooks | Scoped credentials, source permissions, signed events, retries/idempotency and delivery audit. Internal APIs alone do not complete this feature. |
| 64 | Fine-grained permissions and audit | Versioned row/column grants and consistent profile/planner/query/replay/export enforcement are deployed and tested, including revocation races. Regulated-customer audit and independent production privacy acceptance remain open. |

All four bounded phases in the [clean-experience plan](clean-experience-plan.md)
are complete through October 16: focused screens, reliable saved-definition reuse,
internal analytics depth and fixed-case/workload evidence. The
[verification ledger](verification-internal-analytics-depth.md) retains limits.
Representative evaluation, sustained performance and external dependencies remain
open. The later [domain-agent tool slice](domain-agent-tools.md) adds the bounded
PDF implementation under [E26's release verification](verification-domain-agent-tools.md);
the later portable-export release closes the full supported export scope. All eight
production gates remain unchanged.

Dependency order: improve the existing onboarding experience; extend tested internal analytics under
the authorized research sequence; complete exports/first controlled connectors;
implement selected commercial providers and operational controls; run reviewed
production acceptance. The October16 remaining-work instruction now authorizes
independent implementations beyond the older bounded slices; see
`docs/remaining-work-execution.md`. Do not activate public access or clear gates
from this plan.

In easy words, external inputs mean: the website address and HTTPS; the service
users will use to log in; an email sender; the service that takes payments; and real
approved example files with answers a human has checked. Credentials belong in
private operator configuration, never this document or chat. The private demo can
continue while these inputs are pending.
