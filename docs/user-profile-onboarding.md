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

## Per-file follow-up questions (`dataset-focus-v1`, no migration)

After any upload, `GET /workspaces/{wid}/uploads/{uid}/dataset-purpose` adds `follow_up`
`{version, questions, answers, status}`. The 3–5 questions are deterministic templates from that
file's own columns (`domain/dataset_focus.py`):

- Ordinary files: `measure` (which number matters most; measure candidates), `segment` (which
  group; category candidates), `time` (Day/Week/Month/Quarter/Year by …, No time view; only when
  a date exists), `decision` (short text with suggestions), `relation` (how you are connected).
- Ranking files (scores + descriptive text, e.g. leads): `persona` (trade or main skills, text with
  the work kinds found in the rows as chips), `level`, `want`, `measure` (which score), `segment`.

`PUT /workspaces/{wid}/uploads/{uid}/dataset-focus` `{answers, status: completed|skipped}` saves
them after validating each answer against the current questions (422 `invalid_focus`). Answers
live in one private object per workspace, dataset and member
(`workspaces/{wid}/private/dataset-focus/{dataset_id}/{user_id}.json`), the same pattern as
hypothesis feedback; only that member's own requests read it. Answers given to the chat's
"about you" questions (`persona`, `level`, `want`) are merged into the same object.

How answers are used: the chosen measure and group sort first in measure/category candidates
(insights, hypotheses, discovery), the first suggested question uses them, the auto dashboard
is rebuilt with the deterministic pick (route `deterministic:auto-dashboard-focus-v1`), bonuses
for the chosen measure/group, the chosen time view as the trend grain, and only a checksum of
the answers in its payload. The chat planner receives only the chosen column names and the fixed
time-view label as "choice" context; free text (decision, persona) never reaches the planner, and
answers never become filters, numbers, permissions or meanings. Without answers nothing changes.

## Persona ranking asks first

"Which leads are the best fit for me?" now asks, one at a time with clickable answers, what you
do (skipped when the question names a role, saved answers or My memory role exist), your
experience level and what you want (a job, clients, partners). The state travels in the
clarification question as `[about me: persona=…; level=…; want=…]`. Matching is whole-word with
plain inflections only ("engine" never matches "engineer"); when no record mentions the person's
work, the reply says so plainly and names the kinds of work the records do mention, instead of a
ranking. Level and goal shape the wording only.

Language options for the profile now also include Arabic, Spanish, French, Chinese, Hindi and
Another language; earlier answers stay valid.
