> **File use case:** Contract for the per-user "get to know you" questionnaire shown to new accounts.
> **What it does:** States the questions, API, storage, privacy, how answers shape replies and what they never do.

# User profile onboarding (`user_profiles`, migration 0035)

When a self-service account (password or Google) signs in and has neither completed nor
skipped the questionnaire, the workspace shows a full-screen, one-question-per-screen flow
before the normal shell (`apps/web/src/app/workspace/onboarding/`). Operator-provisioned
local/test sessions never see it. Every question is skippable; "Skip for now" saves whatever
was answered and does not ask again. "Redo the questions" lives in **My memory** and
**Team & settings**.

## Questions (fixed in `domain/user_profile.py`)

18 questions: `preferred_name` (text), `role`, `industry`, `company_size`, `data_comfort`,
`goals` (multi), `data_sources` (multi), `typical_questions` (multi), `decision_frequency`,
`time_horizon`, `answer_style`, `detail_level`, `language`, `number_format`,
`chart_preference`, `next_steps`, `regions_currency` (text), `anything_else` (text).
Options are stored exactly as shown (plain labels). Text answers are at most 120 characters
with no control characters; unknown ids or unlisted options are rejected (422
`invalid_profile`).

## API (owner only, versioned)

- `GET /me/profile` → `{user_id, version, preferred_name, answers, completed_at, skipped_at,
  updated_at, status: pending|completed|skipped, questionnaire}`.
- `PUT /me/profile` `{expected_version, preferred_name, answers, status: completed|skipped}`
  → saved profile; 409 `profile_conflict` when the version moved.
- `DELETE /me/profile?expected_version=n` → forgets answers (status back to `pending`).
- Account events `profile.completed|skipped|forgotten` record identifiers and outcome only.

## How answers are used

The repository attaches the profile to every `AgentMemory` read (`repo.agent_memory`), so the
same private context that already feeds dataset readings, data briefs, purpose and social
replies gains a nested `profile` block (`preferred_name`, `role`, `industry`, `goals`,
`answer_style`, `detail_level`, `language`, `number_format`). `MEMORY_PROMPT` tells the model
to greet by the preferred name and adapt depth, language and format. The deterministic
offline greeting also uses the name. Memory references in saved turns carry
`profile_version`, so later profile changes are visible in evidence; saved answers stay
immutable and reopen unchanged.

## What it never does

- Never supplies numbers, units, filters, plans, permissions or confirmed business meanings.
- Never rewrites saved replies, shared definitions or workspace memory.
- Never leaks to other users: profiles are keyed by `user_id` and only `/me/profile` reads them.
