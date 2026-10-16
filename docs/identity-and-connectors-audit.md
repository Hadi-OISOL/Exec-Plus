> **File use case:** Distinguishes unfinished identity/connectors code from external setup.
> **What it does:** Records the next independently testable implementation and the remaining production boundaries.

# Identity and source connectors

This audit covers original feature IDs 1, 40, 47 and 52–55. It does not promote
production gates or imply that a private demo is a production login system.

| Area | Existing behavior | Independent code work | External acceptance/setup |
| --- | --- | --- | --- |
| 1 / 40: registration and login | Operator-issued expiring tokens; `LocalSessionIdentity` rejects staging/production and bootstrap always chooses it | Verified account creation/login, bounded one-use challenges, session rotation/revocation, non-enumerating responses and abuse limits, tenant-isolation tests | Verified email delivery or an explicitly configured identity provider, public HTTPS/domain and independent security/privacy review |
| 47: onboarding | Guided meaning review and explicit private preferences already work | Link verified signup and workspace creation to the existing first-file journey; preserve optional preferences and explicit shared confirmation | Email/identity setup above; paid onboarding depends on real commercial entitlements |
| 52 / 53: accounting systems | Supported exported files can be uploaded; no vendor authentication/synchronization exists | Shared source lifecycle, exact snapshot ingestion, schema-drift/revocation handling; later provider adapters need their own tested contracts | Customer authorization, tenant/company selection, provider app registration and API access; no credentials are requested automatically |
| 54: Google Sheets | No remote Sheets adapter; refresh accepts explicitly staged files | Provider adapter, bounded range/type handling and staged snapshots can be tested with fixtures | Authorized spreadsheet access and explicit OAuth/service-account setup |
| 55: PostgreSQL / BigQuery | A bounded read-only PostgreSQL source adapter, versioned registry, private import history and owner Sources screen pass local acceptance | Private release acceptance; BigQuery still needs a separate adapter and cost/permission controls | Approved customer endpoint/read-only credentials and TLS setup; BigQuery project/dataset authorization and billing configuration |

Source evidence: [identity adapter](../apps/api/src/execplus/infrastructure/identity.py),
[composition](../apps/api/src/execplus/bootstrap.py),
[email delivery](../apps/api/src/execplus/infrastructure/email.py),
[refresh service](../apps/api/src/execplus/application/services/refresh.py), and
[source-adapter architecture](decisions/architecture.md).

The PostgreSQL slice is a complete bounded snapshot import, not live SQL in
chat. Operators register approved source/table/column metadata and private secret
references. Browser/model input cannot choose arbitrary DSNs, endpoints or SQL.
A complete read enters existing immutable upload/staged-refresh review; it never
silently changes saved meanings or activates a changed source. A separate local
DB proves read-only behavior, exact values, limits, failures and source-policy
rechecks without accessing a customer's database. The actual application's
control-plane database is never an eligible source.
See [approved PostgreSQL snapshots](postgres-source-import.md) for the implemented
limits, explicit retry/recovery and owner import/staged-refresh workflow.

Identity code remains required after this slice. A delivery adapter or a passing
mock does not establish real email delivery, production authentication safety or
customer acceptance. No default passwords, automatic email sending, public listener
or production identity-provider change is authorized by this implementation.
