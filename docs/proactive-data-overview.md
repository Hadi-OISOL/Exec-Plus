# Proactive data overview

The overview now appears on upload/load alongside the existing meaning review. Users can
see authorized data before completing optional review, and can enter the conversation
without dismissing that review. Saved definitions that need review still block calculations
in the existing server rules; this change does not confirm meanings automatically.

The existing discovery response adds a structural map, reusing the same diagram builder
and permission-scoped snapshot as other analytical work. Maps include at most 80 visible
fields; wider files receive an explicit selected-field instruction instead of a partial map.
Lines show file membership, never causal effects. Calculated ranges, category charts,
eligible measured relationships and quality checks retain their existing receipts and limits.
This is a bounded starting overview, not an exhaustive search of every possible finding.

Up to three suggested what-if measures come from confirmed, complete, fixed-unit numerical
fields. Explicit sum/average rules are retained; otherwise the starting calculation is average.
Other declared aggregations and varying units do not get this shortcut. The existing scenario
service still validates scope, completeness, units, source freshness and assumptions at execution.
A percentage change alters the selected aggregate only; it does not predict an effect on another
field, crop growth or future outcomes. Price/quantity/cost models remain separately available
with explicit source mappings and assumptions.

The scenario screen adds explicit percentage buttons, exact server-returned baseline/result
cards and a clear distinction between saved results and the edited form. Editing assumptions
requires confirmation again. A successful save remains visible if the subsequent history read
fails; confirmation is consumed so this does not automatically repeat the write. Failed replay
clears the prior result. Internal evidence, SQL, source references and optional history/population
controls start closed. Relevant limitations and assumptions remain visible.

No new model provider, runtime dependency, schema migration or automatic source modification
is introduced. Existing data-reading questions, pattern calculations, diagrams and scenario
services are reused. Three collaborating agents handled overview, scenarios and independent QA;
the root integrated source metadata, navigation and final verification.

Verification and deployment status: see `docs/verification-proactive-data-overview.md`.
