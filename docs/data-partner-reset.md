> **File use case:** Turns the October 2 product feedback into a testable usability release.
> **What it does:** Records the observed gaps, new default journey and honest capability boundaries.

# Upload first, explore together

The October 2 request changes the immediate priority: a person should upload a
file and receive useful, calculated findings before entering a business-definition
questionnaire. The private demo remains the delivery target. This slice precedes
the remaining 4C–4E work; it does not represent their completion.

## Gap audit

The September 30 system could calculate supported queries, preserve evidence,
explain selected columns and save studies, but that did not establish a usable
first-run experience. Inspection on October 2 found:

- A first-time user encountered workspace/dataset setup before uploading.
- Uploading while an existing dataset was selected could put an unrelated file in
  that dataset. Optional domain/goal inputs competed with the basic task.
- The default overview put a large business-definition form and schema diagram
  before conversation. Real columns numbered in the hundreds made this especially
  costly. Several automatically mounted panels issued redundant queries.
- Automatic observations chiefly described file quality. There was no concise
  briefing showing useful calculated extremes, averages and category counts.
- Conversational clarification did not retain the unresolved original question.
  Metadata questions routed through the model could hit the numerical confirmation
  guard even when no calculation was requested.
- Real public banking/retail data exposed semicolon-separated CSVs and CamelCase
  identifiers. The frozen comma parser and profile-v1 rules require compatibility
  work, not a silent reinterpretation of historical evidence.

## Acceptance for this release

1. An authenticated new user can upload a supported file directly. The application
   supplies an editable file-based dataset name and a personal workspace when
   needed. Optional metadata stays optional. New files default to new datasets;
   adding a version to an existing dataset is deliberate.
2. Upload selects the new source and shows an automatic discovery briefing. Its
   observed shape, quality warnings, calculated findings and next questions use
   that actual source. No generated business meanings are silently confirmed.
3. Every numerical finding has an executed query and immutable replay receipt.
   Saved definitions, filters, units, source changes and current permissions apply.
   One unsuitable measure does not remove valid findings from other columns.
4. Ordinary conversation can explain structure/quality, suggest relevant next
   questions and continue a clarification using its private, version-bound context.
   Model claims never become authoritative business definitions or numbers.
5. Advanced setup, studies, source preparation, refresh and sharing remain usable
   through explicit navigation/disclosures. Desktop/mobile and keyboard flows work.
6. Evaluation uses licensed public real-world data with source provenance and
   independently computed expectations, alongside adversarial and compatibility
   tests. Ordered subsets and file conversions are disclosed. Public source rows,
   generated reports and session credentials stay outside version control.

## Automatic discovery contract

`GET /workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/discovery`
returns `discovery-v1` with dataset name, summary, shape, definition state, immutable
source references, quality observations, findings, suggestions and limitations.

The bounded selector examines at most two suitable numerical columns plus one
small category group. It executes at most seven read-only queries using the existing
executor. Unconfirmed name-based identifiers, calendar coordinates and ordinal
ratings are excluded from automatic numerical recommendations. Confirmed roles
take precedence. Ordinary numerical columns get minimum, maximum and arithmetic
mean; configured metrics use their confirmed aggregation and filters. No arbitrary
total is relabeled as revenue, no currency is guessed, and no field multiplication
is assumed to define business revenue.

Each finding contains an ordinary query response with its lineage/receipt. Category
counts include a missing-value group, and ties are identified. Decimal values keep
the existing string contract. Mean rounding remains twelve decimal places. Findings
are rendered from results, without a model. There is no persistent discovery cache;
opening a briefing parses one authorized snapshot and reuses it for the bounded
queries. Initial parsing and the final source check run outside the async event
loop. The final check verifies the original bytes and checks current permissions,
revision and definition both before and after that read, without reparsing. No
parsed table is retained across requests. Saved unconfirmed/stale definitions retain profile help and explicit
calculation limitations. The briefing never overwrites a human correction.

DuckDB intake validates/coerces referenced columns as before, then passes bounded
JSON column arrays with explicit SQL types. Decimal values use fixed-point strings,
dates use ISO strings, and nulls remain nulls. This avoids costly per-cell optional
library import checks in a minimal Python runtime. It adds no dependency, persistent
representation or cache; isolated connections, parameter binding, projection, query
timeouts, precision checks and replay contracts remain unchanged.

The UI groups related numerical results into a readable card and exposes the exact
queries through evidence controls. Larger dashboard computations run only when the
user opens them. Existing studies and alerts still have their governed setup rules.
Briefing requests wait for visible, settled file selection; switching away cancels
the browser request. The API stops remaining discovery queries after disconnect and
retains a failed receipt for an interrupted execution. Completed receipts survive.
Chat uses the briefing's suggested questions instead of parsing the file again through
the legacy suggestions endpoint. This does not create a cross-user result cache.

## Real-file compatibility

New CSV ingestion recognizes comma, semicolon and tab-delimited UTF-8 tables, in
that header-detection priority. Strict quoting, width, formula and resource checks
remain. The retained upload format records `csv`, `csv;s` or `csv;t`; reconstruction
validates using that stored dialect. Existing single-column comma files containing
semicolons are not silently reinterpreted. This is not arbitrary encoding detection.

New ordinary uploads use **profile-v2**. It recognizes label-based identifiers such
as `CustomerID`, `StockCode` and `InvoiceNo` as text dimensions, preserving leading
zeros, cancellation prefixes and missing values. Whole valid numeric day/month/year
components become integer dimensions rather than invalid complete dates. Other
inference remains unchanged; these heuristics do not establish business meaning.

`profile-v1`, its synthetic samples and existing lazy-profile uploads remain frozen.
Cleaning inherits its parent profile version; staged refresh inherits the feed's
source version. Original files and checksum reconstruction do not change. Receipts
continue to replay their own original profiles. Existing v1 files are not upgraded
in place; importing a new upload uses the new interpretation. Timestamp text still
requires a separately supported date representation for time-based analysis.

The FileParser protocol adds optional `stored_format` to validation so source readers
do not redetect a historical dialect. No database migration is necessary; readiness
stays on 0012. An older application image cannot read new v2 revisions: rollback must
preserve new user metadata and account for this compatibility boundary.

## Public-data rehearsal

`scripts/evaluate_data_partner.py` downloads and retains attributed originals under
ignored `data/realdata-evaluation/`, with retrieval timestamps and SHA-256 hashes.
It runs against disposable PostgreSQL schemas and object buckets. Independent
standard-library Decimal references verify totals, averages, groups and filters;
group comparisons explicitly apply the executor's established text-trimming rule.

- [UCI Bank Marketing](https://archive.ics.uci.edu/dataset/222/bank+marketing),
  Moro, Rita and Cortez (2014), CC BY 4.0: the publisher's 4,521-row sample,
  using the original semicolon-delimited CSV bytes.
- [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail),
  Chen (2015), CC BY 4.0: the first 10,000 original rows, preserving values,
  negative quantities and missing identifiers. The full workbook exceeds current
  intake limits. This ordered subset is not representative population sampling.

The live mode uses the configured real model. Failed reports are preserved and new
runs use new output paths. The separate `scripts/check_data_partner_vps.mjs` exercises
eight private browser sessions using these public sources and independent expected
answers supplied in an ignored target file. Neither rehearsal is a sustained-load
benchmark or a production-quality gate.

## Limits that remain real

This release is descriptive exploration, not universal data-scientist replacement.
Unknown company abbreviations, causal conclusions, statistical inference and new
business formulas cannot be known from column labels alone. Focused clarification
is appropriate when the requested answer depends on such a meaning. CSV/single-sheet
XLSX size/structure bounds still apply; document ingestion has its separate contract.
Arbitrary formats, automatic joins and external-system actions are not added here.

Basic forecasts, exports and the initial connectors remain separate 4C–4E work.
The user deferred public-deployment work; the existing private identity and network
boundary remain. Neither public datasets nor a nicer interface clear production
gates. The verification ledger records actual passes, failures and deployment status.
