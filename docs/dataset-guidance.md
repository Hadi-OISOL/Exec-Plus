> **File use case:** Documents dataset and column explanations in private chat.
> **What it does:** Defines observed facts, tentative meanings, definition precedence and private follow-up evidence.

# Dataset explanations in chat

The September 30 repair addresses column-meaning questions that previously reached
a fixed overview menu or an empty document search. Questions such as “what does
attock erp mean?” now resolve against actual column names, including spaces versus
underscores and case. Longer matching column names take precedence over prefixes.

The explanation separates:

- File observations from the deterministic profile, such as type and layout.
- Saved, confirmed business definitions and units, quoted as workspace definitions.
- Inferences from names or paired columns, explicitly described as tentative.
- General business terminology, explicitly distinguished from this file's definition.
- Remaining questions the dataset owner should answer before interpreting a measure.

For example, an ERP field paired with a corresponding `_value` column may suggest
a quantity/value pair. The system does not infer a currency, claim it is stock or
sales, or assert a formula. A confirmed meaning takes precedence over these hints.
Draft meanings are labelled unconfirmed; rejected/stale meanings are not treated
as current definitions. Guidance does not save or approve a business definition.

Whole-dataset help uses actual row/column metadata, identifiers, dimensions,
repeated measure/value pairs and available date types. Suggestions refer to
existing columns. “??” after a column explanation keeps the topic and gives a
shorter explanation. A related-value follow-up selects the actual paired column.
These English patterns are bounded conveniences, not unrestricted conversation or
automatic understanding of arbitrary company terminology.

Clear guidance requests do not require a model call. For other phrasings, the
provider-neutral planner can return `overview` with up to three validated `columns`.
Its prose is ignored; the server builds the explanation. Explicit document requests
retain retrieval, and totals/averages/record questions retain validated query execution.
An unconfirmed definition may be inspected without enabling a blocked calculation.

## Wire and history

The existing ask routes retain `kind: overview` and add:

```json
{
  "guidance": {
    "columns": ["attock_erp"],
    "suggestions": ["What does attock_erp_value mean?"],
    "definition_state": "inferred"
  },
  "sources": [{"dataset_id": "...", "upload_id": "...", "revision_id": "...",
               "source_checksum": "...", "output_checksum": "..."}]
}
```

`message` and `model_route` remain present. Sources add `understanding_id` when a
saved definition is part of the context. The browser renders paragraphs, related
questions and a source-details disclosure; inferred explanations do not receive
the numerical Verified badge.

Private turn evidence retains a `dataset-guidance-v1` payload and immutable source
references in the existing JSON evidence field. No migration is needed. Reopening
reauthorizes the conversation owner, dataset, source bytes, revision and definition.
Changed current definitions do not rewrite an old explanation. Missing source bytes
block reopening. Follow-ups detect changed context; explicitly naming the column
again uses the current version. Only selected column names enter later model context,
not arbitrary old explanation prose or uploaded rows. General audit events retain
identifiers/outcomes without copying definitions or values.

Keep profile-v1 and numerical receipt behavior intact. No source data, shared meaning,
model/provider choice, public exposure or production gate is changed by this repair.
See [verification](verification-dataset-guidance.md).
