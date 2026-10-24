> **File use case:** Documents the model-written data reading that opens after an upload.
> **What it does:** Explains the flow, the endpoint, what the model sees and how confirmed answers become context.

# Data reading

After a CSV or XLSX upload is selected, Syntelio asks the configured language model what the
file appears to contain and what it is unsure about. The owner confirms or corrects that
reading one question at a time. Confirmed answers become the dataset's shared meaning, so
the planner already receives them as saved definitions on later questions.

## Flow

1. The reading opens at the top of Overview when an upload is added or selected and has no
   confirmed meaning. It shows a short "Reading your data" state while the model runs.
   While it is loading or open, **Ask Syntelio**, the home question box and the insight
   canvas are hidden, so the owner confirms meaning before asking questions. Skip for now
   always releases them. If the reading cannot load, nothing is hidden.
2. Cards ask, in order: what the data is about, what one row represents, each column the model
   was unsure about, every remaining source column, and up to three whole-data
   questions. Each card offers Yes, edit, Skip and Back.
3. The review step saves on request. A new review with skipped fields or unknown row meaning
   stays a draft; reviewing a subset cannot confirm the entire file. **Save as context** writes the confirmed definition
   through `POST .../understanding`. Free-text answers are kept as one private Markdown
   note through `POST .../documents`; sharing the note is an explicit checkbox.
4. **Skip for now** hides it only until the page is reloaded or the owner signs in again; it
   returns for every unconfirmed upload when the data is uploaded, selected or the page is
   reloaded. Finishing the review (Continue to my insights) stores a per-browser marker so it
   is not shown again for that upload. A confirmed upload never opens it automatically.
5. **Check what Syntelio understood** reopens it at any time, from Overview and from the
   Prepare data panel. For an already confirmed upload it asks only about missing meanings or units, retaining
   all other answers. A complete definition says it is already confirmed.

If the model is disabled, unavailable or returns an unverifiable reply, or the request fails,
the reading does not open and the existing **Guided data review** opens exactly as before.

## Endpoint

`POST /workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/data-brief`

Authenticated members only. The call saves nothing except a private audit event
`data_brief.drafted`. `?review_missing=true` resumes missing details from saved definitions without another
model call when the saved version belongs to this revision. The response carries `source` (`model` or `profile`), `summary`,
`grain`, `columns` (name, type, role, meaning, unit, `uncertain`, `question`), `questions`,
`model_route`, `notice`, and the current `revision_id`, `version`, `state`, `can_edit` and
`definition` needed to save through the existing understanding endpoint.
`already_confirmed: true` returns without calling the model.

## What the model sees and may say

- Input is profile metadata (column names, types, missing and distinct counts, date ranges,
  row and column counts, suggested roles). It never receives a private goal.
- **Sampling.** With `EXECPLUS_DATA_BRIEF_SAMPLE_VALUES` above zero (default `0`, off), the
  model also receives up to that many of the most frequent values per column and the first
  three rows, each cut to 40 characters. This is what lets it notice short codes such as
  `P`, `R`, `C` and ask what they mean. Identifier columns and columns whose names suggest
  personal data (name, email, phone, address, account, card and similar) are sent as
  `(withheld)`. The screen says when a sample was used. Sending values to a hosted provider
  is a privacy decision: leave it off until the provider is approved for that data.
- Replies are strict JSON. Unknown or repeated columns, extra fields, over-long text and any
  number not present in the supplied metadata or sample are rejected. Rejection falls back
  to the profile reading rather than showing unverified text.
- Whole-data questions that repeat a column question or ask what one row represents are
  dropped, since those already have cards.
- Statements are suggestions. Only what the owner confirms is saved. Nothing the model writes
  is a calculated value, and numerical answers still come from validated queries.

## Wide files

The model is shown up to 80 columns and asked to describe at most 20: every column it is unsure
about first, then the most important. The reading uses its own output limit,
`EXECPLUS_DATA_BRIEF_MAX_OUTPUT_TOKENS` (default 4096), because the general chat limit of 1024
tokens truncates a reply about many columns and the adapter rejects a truncated reply. When a
configured model still fails, the screen says why and the standard guided review opens.

## Permissions and limits

- Only the dataset creator or a workspace owner/admin can change the shared meaning; other
  members keep their answers as private notes.
- Saving a fully reviewed definition confirms it for new calculations. Incomplete reviews
  remain drafts with their answers retained. Unknown units remain explicit gaps; they do not
  become invented units. Previously confirmed definitions stay editable.
- One model call is made per unconfirmed upload when it is first shown, with the large tier
  and the configured output limit. Reading time depends on the provider.
- Planning now receives up to three integrity-checked passages from accessible reading
  notes for the selected upload, newest first, plus the caller's private saved goal.
  These are untrusted context and cannot override confirmed definitions or permissions.
  Other supporting documents continue through explicit evidence retrieval.
- Chat explains confirmed descriptions and can open forecast, anomaly, scenario or allocation
  setup with an explicitly named measure. Setup still requires any missing user declarations.
- No migration; existing exact receipts and the guided-review fallback remain supported.
