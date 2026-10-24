> **File use case:** Security policy and implementation baseline.
> **What it does:** Documents reporting guidance and the controls expected before production use.

# Security

Syntelio is pre-alpha and must not process production customer data yet.

Report suspected vulnerabilities privately to the repository owner. Do not include secrets, personal data, or exploitable production details in public issues.

Required controls include workspace-scoped authorization, defense-in-depth row-level security, encrypted transport and storage, secret-manager integration, read-only analytical queries, bounded execution, file validation, dependency scanning, audit logging, least-privilege service identities, backup restoration tests, and log redaction.

Any change touching authentication, authorization, upload parsing, query validation, model data sharing, or export access requires security-focused tests and explicit review.

