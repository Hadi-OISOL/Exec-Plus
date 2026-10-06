> **File use case:** Explains internal administration, private support and product reporting.
> **What it does:** Defines staff access, customer-visible workflows and honest usage/performance boundaries.

# Internal operations and product reporting

This is the October 6 private-demo operations slice pulled forward from Phase 5.
Release acceptance is recorded in [verification](verification-operations.md); this
contract does not complete commercial readiness. The eight production gates,
billing, public identity and external delivery setup remain separate work.

## Staff access and administration

Workspace owner/admin/member roles retain their existing meaning. Internal staff
grants are a separate, revocable record: `admin` can open operational workspace
metadata and product reports, while `support` can handle support requests. Neither
grant confers membership or access to a customer's rows, documents, conversations,
private forecasts or query receipts through ordinary APIs.

Only an operator CLI can grant/revoke staff access for an existing account:

```bash
python3 -m execplus.manage grant-staff --email staff@example.test --role admin
python3 -m execplus.manage grant-staff --email support@example.test --role support
python3 -m execplus.manage revoke-staff --email staff@example.test
```

There is no browser self-grant endpoint, implicit grant from an email domain, or
fallback grant to a workspace owner. Each privileged operation checks the current
grant. Access already in a transaction completes under its locked grant; revocation
blocks later privileged requests. CLI changes and staff reads/mutations retain
identifier-only staff audit records. Ordinary workspace audit does not reveal
another person's private support request or its text.

The **Admin console** shows bounded workspace/customer metadata, seats, resource
counts, aggregate job states and the support queue. Own-job support diagnostics
provide fixed failure categories and timestamps when explicitly linked. The plan is
explicitly `private_demo`, with billing `unconfigured`. It cannot change paid plans,
impersonate a user, expose source values, or bypass existing team-management rules.
Workspace managers continue to use **Team & settings** for their own workspace.

## Customer support

Every current workspace member can open **Support**, create a request and read
their own requests. The form explains that submitted text is shared with authorized
support staff. It asks users to leave out credentials and confidential source rows.
It does not silently attach source files, prompts, conversation history or server logs.
There are no automatic external emails, help-desk integrations or attachments.

Requests capture a subject, description, feature and category. Existing own feedback
and own-job IDs can be linked; the server checks both tenant and owner. Job
diagnostics contain operational identifiers, fixed status/stage/failure categories
and timestamps only. They do not permit reading the underlying conversation.

The requester and staff share a public reply/status timeline. Staff can triage,
assign an active staff member, set normal/high priority, mark work in progress,
wait for the customer, escalate and resolve. Resolved requests require explicit
reopening before further edits. Team owners/admins cannot browse another member's
private request unless separately granted staff access.

Each change includes `expected_version`. Conflicting edits return 409 and ask the
client to reload; they do not overwrite another person's reply or decision. Ticket
and timeline publication are transactional and workspace-bound. Subjects are
limited to 120 characters; descriptions/replies to 4,000; a ticket to 200 timeline
events; each requester to fifty unresolved tickets per workspace. Lists have at
most 100 rows with stable cursors. Limits are technical bounds, not paid-plan quotas.

| API | Purpose |
| --- | --- |
| `GET /admin/access` | Current staff role or null |
| `GET /admin/workspaces` | Admin-only bounded workspace metadata |
| `GET /admin/workspaces/{wid}` | Admin-only operational workspace overview |
| `GET /admin/staff` | Active staff eligible for support assignment |
| `GET /admin/support-tickets` | Staff queue with status/priority/search filters |
| `GET/POST /workspaces/{wid}/support-tickets` | List own requests or create one |
| `GET /workspaces/{wid}/support-tickets/{tid}` | Own request and bounded timeline |
| `POST /workspaces/{wid}/support-tickets/{tid}/messages` | Reply with expected version |
| `POST /workspaces/{wid}/support-tickets/{tid}/reopen` | Explicitly reopen a resolved request |
| `/admin/workspaces/{wid}/support-tickets/{tid}` | Scoped staff detail/PATCH and corresponding message/reopen endpoints |

Ticket bodies and replies are stored for the support purpose explicitly chosen by
the requester. General audit, usage, performance reports and logs contain no such
text. Production support retention/privacy policies, independent access review and
external incident-response processes remain Phase 5 requirements.

## Usage and retention definitions

**Usage & retention** is available to workspace owners/admins for their own
workspace. Internal admins can open the same aggregate report through their audited
console. Support-only staff cannot use the internal product-report endpoint.

`GET /workspaces/{wid}/product-usage?weeks=8` and the staff-admin equivalent
`GET /admin/workspaces/{wid}/product-usage?weeks=8` return `usage-v1` reports.
Windows contain one to twelve UTC Monday weeks, including the unfinished current
week. The report includes its upper observation time, counts, definitions and limits.
Its aggregates share one PostgreSQL statement snapshot. Integers outside
JavaScript's exact range travel as decimal strings; unfinished-cohort flags stay booleans.

| Measure | Definition |
| --- | --- |
| Active users | Distinct historical people with qualifying deliberate actions in the displayed window |
| Active members | The subset still belonging to this workspace |
| Activated members | Current members with a successful conversation, saved analysis, study or forecast in retained history |
| Never active members | Current members without a recorded qualifying deliberate action |
| Inactive for 14 days | Previously active current members whose last qualifying action is older than fourteen days |
| Feature adoption | Qualifying action count and distinct people for each recorded feature |
| Cohort | The week of a person's first qualifying action in this workspace, looking before the displayed window too |
| Weekly retention | Cohort members active in that specific completed week divided by its original size |

The versioned allowlist in `domain/product_usage.py` includes upload, preparation,
question submission, saved analysis, study/dashboard/forecast actions, knowledge
actions and report scheduling. Background query completions, refresh/observation
workers, staff/support activity and sign-ins do not independently establish active
use or retention. Reopening evidence and deliberate fictional sample uploads may
count. Counts describe recorded actions rather than unique visits or browser sessions.

Cohort cells for unfinished or future weeks return `eligible: false` and null
counts/rates. A mature week with no return activity is zero. Removed members remain
in historical cohort denominators; current membership cards use current members.
Percentage strings use two decimal places. Inactivity is an explicit follow-up
rule, not predicted churn or a diagnosis of why a customer stopped using the app.

Period usage includes uploads, retained-byte events, completed/failed query events
and created forecasts. Background computations can contribute to query counts;
they cannot thereby create human retention. These are not billing entitlements,
payment/customer retention or comprehensive telemetry for uninstrumented legacy
queries, passive views and activity outside ExecPlus. No per-person activity
history, source values, questions or private ticket text are returned in the report.

## Performance and compatibility

New reports and onboarding use PostgreSQL aggregates, transferring bounded summary
rows rather than whole audit/usage histories. Legacy `/usage-analytics` preserves its
historical all-action semantics and response shape. The new view uses the explicit
`usage-v1` definition. Legacy `/usage` still returns its existing event list for
compatibility; only its resource-total calculation replaces the per-dataset upload
loop. Do not describe that legacy response as newly bounded.

Optional browser views are loaded on demand; invitations load when Team is opened.
Existing discovery debounce/cancellation, query budgets, model routes, numerical
contracts and original evidence replay remain unchanged. The benchmark uses
disposable fictional data and independently checks result parity. Its warm local
repository timings exclude HTTP/browser/network overhead and are not representative
production capacity. See the release ledger for measured outcomes and remaining work.

## Maintaining the VC report

`docs/product-feature-audit.json` retains the original 64 feature IDs and evidence.
After a verified delivery, update affected statuses/notes, evidence references and
report prose together, then regenerate with `scripts/build_feature_report.py`.
The original competitor comparison retains its October 5 research date until a
separate review is performed. The report generator requires optional `python-docx`
only when generating a file; it is not an application dependency.

The current local tooling invocation is:

```bash
PYTHONPATH=data/report-tools python3 scripts/build_feature_report.py \
  --output /home/it-admin/Desktop/ExecPlus_VC_Feature_Report_2026-10-06.docx
```

Preserve previous DOCX versions before replacing a copy, verify all 64 rows/counts,
and render/inspect pagination. Generated DOCX/PDFs and backups stay local/ignored;
the audit and generator are versioned. Report completion means tested scope, not
automatic production acceptance.
