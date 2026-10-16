> **File use case:** Defines the independent company-consolidation implementation.
> **What it does:** Separates exact worksheet arithmetic from source permissions and accounting decisions that require explicit user inputs.

# Company consolidation worksheet

Status: planned under the October 16 remaining-work instruction. No consolidation
endpoint or saved run is delivered by this document.

The first complete workflow will combine prepared account balances from two to
eight companies in an organization. Each company has one declared source,
reporting period, currency and account mapping. The actor must retain current
access to every source; owning the organization alone does not give data access.
Runs and their evidence are private to their creator.

## Inputs and calculations

- Use confirmed account, signed amount and optional counterparty fields. Preserve
  source receipts and account-level exact amounts. Reject missing account codes,
  invalid amounts and incomplete populations instead of silently omitting rows.
- Require the same explicitly confirmed reporting period and sign convention for
  every company. Different periods must be prepared first; never align them by
  row position or silently carry balances forward.
- Map every source account to a named group account and declared rate basis.
  Exchange rates are explicit positive inputs with a retained reference and date.
  Same-currency rates must be one. Never fetch or invent an exchange rate.
- Keep closing, transaction/average and historical rate choices separate. They
  are user decisions, not inferred accounting policy. Show translated totals and
  any resulting imbalance; never silently insert a balancing entry.
- Elimination journals reference declared companies, group accounts and reciprocal
  counterparties. Entries must balance exactly, use existing internal balances
  and cannot remove more than the available amount or erase an external balance.
  An unmatched or currency-difference amount requires review and remains visible.
- Display each company's contribution, combined balance, explicit eliminations
  and final consolidated amount. Export all four layers with source and rate
  evidence. Reopening checks the original arithmetic and current permissions.

The worksheet does not infer control, acquisition accounting, goodwill,
non-controlling interests, tax effects or statutory compliance. Those depend on
the user's accounting facts and approved policies. This boundary must be visible
before confirmation, rather than hidden behind a successful calculation.

## Evidence and implementation order

1. Pure bounded Decimal arithmetic with independent Fraction oracles, signed and
   large values, invalid/missing mappings, period mismatches, rate errors,
   balanced/unbalanced and repeated elimination entries.
2. Governed source projection and immutable private run persistence. Lock multiple
   workspaces in a stable order only for final checks, with no object/model I/O
   inside those locks. Recheck all source policy epochs, memberships and versions.
3. A guided selection, mapping and review interface with explicit confirmation,
   retryable drafts, complete exact tables and protected exports.
4. Real multi-workspace denial/revocation/source-change tests, compatibility,
   desktop/mobile browser journeys and private-demo verification on fictional
   companies. Preserve existing sources and accounting definitions.

## Primary reference review

IFRS 10 describes consolidation of comparable items and elimination of internal
group balances and transactions. That informs the explicit mapping and elimination
controls; it does not establish that a generic worksheet satisfies the standard.
[IFRS Foundation, IFRS 10](https://www.ifrs.org/content/dam/ifrs/publications/pdf-standards/english/2022/issued/part-a/ifrs-10-consolidated-financial-statements.pdf?bypass=on)

IAS 21 distinguishes rate choices and the treatment of exchange differences.
The published standard and its supporting material reinforce keeping rate
assumptions and unresolved differences visible. No accounting certification or
current-standard compliance is claimed.
[IFRS Foundation, IAS 21](https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/),
[IFRS Foundation, intragroup exchange differences](https://www.ifrs.org/content/dam/ifrs/meetings/2025/september/ifric/ap2-classification-intragroup-exchange.pdf)
