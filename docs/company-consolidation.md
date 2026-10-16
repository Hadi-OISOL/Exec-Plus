> **File use case:** Describes the implemented private company worksheet contract.
> **What it does:** Records explicit accounting inputs, source authorization, exact evidence and practical limits separately from deployment acceptance.

# Private company worksheet

Status: implemented in the working tree on additive **0024**, after connector
**0023**. Local guided browser checks pass; combined release acceptance remains in progress. This is
not deployed by this document. The [plan](company-consolidation-plan.md) records the
approved accounting boundary.

A person can combine complete prepared ledgers from two to eight company
workspaces grouped in one organization. Organization ownership gives no data
rights. The person must have current full access to each chosen source. Restricted
row or column views cannot stand in for a complete company ledger.

The three-step Team interface asks for company files, account mappings and declared
rates, then optional internal adjustments and explicit confirmation. Back keeps
drafts. A failed save keeps the inputs; a successful save followed by a failed
history read retains the result and reports that only the list failed to reload.
No original file, meaning or accounting entry is changed.

## Complete and explicit inputs

Each company supplies a confirmed account field, fixed-currency signed amount
field and optional counterparty field. The selected company currency must exactly
match the confirmed amount unit. Missing accounts or amounts, nonexact numerical
types, unknown fields and measure-specific required row exclusions are refused.
Every source row is included, with a bound of 10,000 rows per company. The actor
explicitly confirms that the file is a prepared ledger for the declared period;
calendar dates never silently filter the file or infer account balances.

All companies use one explicitly declared period and sign convention. Every
source account maps once to a group account and one declared rate key. Up to 256
accounts and 256 named rates are supported per company. Closing, transaction/
average and historical rates remain separate user choices. Every positive exact
rate has a date and retained reference. Same-currency rates must be exactly one.
No exchange-rate provider is called.

Counterparty names are preserved exactly in private source rows and receipts.
Only an explicit raw-name-to-company mapping makes a row internal. Unmapped names,
including strings that happen to look like company UUIDs, remain external. The
calculation receives no internal company ID for those rows.

An optional elimination journal names exact signed adjustments in the reporting
currency. Each entry refers to a source account and declared other company.
Entries must oppose available translated internal balances, cannot over-remove
cumulatively, and must balance both per journal and per reciprocal company pair.
There are at most 100 journals and 64 entries per journal. An externally mapped or
unmatched balance cannot be erased. No balancing entry is invented.

## Results and source protection

The result separates each company contribution, translated source balances,
combined group balances, declared eliminations, final consolidated balances and
remaining internal balances. Exact totals and unresolved imbalances stay visible.
Arithmetic uses exact fractions derived from bounded decimals, without browser or
model calculations. This worksheet does not infer ownership/control, acquisition
accounting, goodwill, non-controlling interests, tax or statutory compliance.

Each complete projection has an owner-private `aggregation="analysis"` receipt.
The immutable saved run retains input/result checksums, query IDs, exact source
versions, confirmed definitions, membership epochs and organization links. Raw
source rows and raw counterparty names are available on reopening and in exports.
A source's parsing scale can differ from CSV formatting; the receipt's exact typed
number, rather than a rounded browser float, is preserved.

File listing collects metadata outside workspace locks and rechecks all included
company links, memberships and dataset policy epochs before returning it. Creation
performs source reads and computation outside workspace locks. Final
checks lock company workspaces in stable UUID order and recheck every membership,
full-access policy, organization link, retained source, confirmed definition and
accepted refresh source. Reopening reconstructs the original projections and
compares every receipt and the complete calculated result. A newer source or
meaning marks the saved worksheet historical; it does not replace the old result.
Changed policy or membership epochs invalidate access. Runs are creator-private,
including from organization/workspace administrators.

PDF, Excel, CSV bundles and PNG are explicit protected downloads of the saved
worksheet. They include all calculation layers, source rows, mappings, rate
references and evidence. Rendering happens outside locks; full replay and ordered
access checks run again before returning bytes. The standard export size/cell/page
limits remain explicit: an oversized export is refused rather than truncated.
PNG metadata includes exact values and evidence; its visual panel shows the
consolidated balance chart.

## API and lifecycle

The route root is `/organizations/{organization_id}/consolidations`:

- `GET /options`: accessible company workspaces and full-access files.
- `POST /source-options`: current confirmed field and currency choices.
- `POST /preview-company`: complete account/counterparty choices and a private
  projection receipt; it does not save a worksheet.
- `POST` at the root: calculate and save explicit companies plus worksheet inputs.
- `GET` at the root and `GET /{run_id}`: private history and verified reopening.
- `GET /{run_id}/export.{pdf|xlsx|csv|png}`: protected complete delivery.

Up to fifty saved runs per organization/person are retained. Final insertion uses
one transaction-scoped organization/person lock, so simultaneous requests with
different company sets cannot exceed that limit. Migration 0024 adds
only `consolidation_runs`; downgrade refuses while any worksheet remains. Existing
source files, definitions, receipts and other features are preserved. Real company
accounting facts and rate choices are still user inputs, not automatic assumptions.
