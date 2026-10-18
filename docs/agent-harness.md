# Bounded conversational agent harness

Implementation contract, October 18, 2026. Release acceptance and measured results are recorded separately in `agent-harness-implementation.md`; this document alone does not establish a deployment.

The application owns authorization, planning contracts, execution and publication. Models interpret language and select presentations of already verified facts. They cannot run arbitrary SQL, shell commands, plugins, network requests or filesystem operations.

## Turn lifecycle

1. Bind the private thread to its actor, workspace, upload, current revision and access policy.
2. Reconstruct bounded relevant task context, pending clarification and authorized result references. Keep saved personal preferences separate from analytical filters.
3. Offer the existing typed capability catalogue and validate the proposed operation and all fields, conditions and units.
4. Execute one supported operation, or at most two independent governed data queries when compound orchestration is enabled. Stop on cancellation, stale context, missing authorization, unsupported dependencies or exhausted budgets.
5. Reuse the ordinary analytical services and their immutable receipts. The language model does not calculate the answer.
6. Optionally construct a bounded factual presentation packet from authorized results and the definitions used by their receipts. Ask the main model to select wording variants and ordering; validate every selected statement and evidence reference.
7. Recheck permissions and versions before publishing the answer. Persist the exact selected presentation with the original evidence.
8. Reopen the receipt and reconstruct its authorized facts before serving a historical presentation. Reject altered text, missing facts, wrong evidence IDs or forbidden source access.

The recorded activity stages describe application operations, not private model reasoning or an invented debate among autonomous agents.

## Feature switches and compatibility

| Setting | Default | Effect |
| --- | --- | --- |
| `EXECPLUS_AGENT_CONTEXT_ENABLED` | `false` | Bounded verified-result context and follow-up handling. |
| `EXECPLUS_AGENT_ORCHESTRATION_ENABLED` | `false` | Two independently validated data-query steps within the existing job budget. |
| `EXECPLUS_AGENT_SYNTHESIS_ENABLED` | `false` | Saved, evidence-checked wording selection with deterministic fallback. |
| `EXECPLUS_AGENT_RETRIEVAL_EXPANSION_ENABLED` | `false` | Conservative English synonym hints for document candidate discovery. |

No migration is required. These switches govern new work; historical answers retain their original receipts. A compound result keeps the existing `mixed` answer kind, uses `coverage=data`, retains the first calculation in `data`, and adds the second in `additional_data`. It does not imply a document search occurred. PDF, Excel and CSV exports include both calculations and original source evidence.

The private VPS composition explicitly opts in through `deploy/vps/agent-harness.env`. It loads the existing private `app.env` afterward, so an operator can persistently override individual switches there without editing credentials or replacing compatible readers. General application and `.env.example` defaults remain off. Activating this composition still requires the recorded release gates.

Turning flags off is an operational fallback for new requests. Already saved compound answers and narratives require the compatible new reader; do not roll back to an older reader that silently omits their second result. Prefer disabling the new paths while retaining the compatible images. Never restore an earlier database over newer user work.

## Facts, language and privacy

Narrative selection is intentionally constrained: the model chooses among application-authored factual variants. It cannot invent a new explanation, change a value or unit, remove a mandatory limitation, add a cause, or perform arithmetic between results. Unsupported, oversized or timed-out presentations retain the exact typed renderer or deterministic wording. A fallback is recorded separately from a successful model selection.

Packets include authorized computed facts, units, scope and evidence IDs. Table follow-up context contains field names, counts, scope and receipt references, not individual record cells. Scalar result context can include its verified scalar value. Document quotations and some grouped result labels can still be sensitive; authorized model context is not anonymization.

Missing fixed units remain explicit. A historical USD result cannot be relabeled EUR by a later definition edit. Counts of records remain distinct from counts of nonmissing values. Extrema retain ties within the existing record limit. Observed cohort differences do not establish causes or intervention effects.

## Boundaries

- The two-step plan supports independent calculations. Result-dependent arithmetic, implicit joins, arbitrary multi-step loops and causal prescriptions remain unsupported.
- Existing forecast, anomaly, scenario and decision panels retain their governed services and prerequisites. This change does not make every panel operation autonomously executable from chat.
- The main provider and local selector remain separately configured; model names are not changed by this implementation. Hosted task correctness and selector usefulness require actual synthetic measurements.
- Document expansion improves candidate discovery for a small explicit synonym set. It does not rename columns, establish equivalence, or turn a candidate passage into evidence without the existing quotation checks.
- Operational diagnostics retain fixed outcome codes, route attribution and evidence references. General logs must not contain raw questions, model replies, credentials or uploaded records.
- Private-VPS acceptance is distinct from independent production security, scale and availability acceptance.
