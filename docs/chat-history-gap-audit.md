> **File use case:** Audits private chat history and chat actions against the October 24 owner request.
> **What it does:** Lists what already existed, the gaps, what this slice built, and what remains.

# Chat history and chat actions — gap audit (October 24)

Owner request (paraphrased): the agent should perform actions and talk to the
user; each person's chat history is kept; they can click a past chat, see its
full history, and keep chatting in that same environment.

## What already existed (before this slice)

| Area | State before | Evidence |
| --- | --- | --- |
| Private threads | `threads`/`thread_turns` tables; owner-only (`ThreadService._thread` 404s for anyone else, including workspace admins). | `apps/api/src/execplus/application/services/threads.py` |
| Durable turns | Turns run as conversation jobs with activity, resume and cancel. | `docs/conversation-jobs.md` |
| Reopen a saved answer | `GET …/threads/{id}/turns/{turn}/answer` replays the saved receipt and rechecks current access; old replies are immutable. | `threads.py` route `historical_answer` |
| Continue a thread | `POST …/threads/{id}/jobs` / `/ask` use stored structured lineage, so “and by region?” follows the previous turn. Source/definition changes clarify (“The data revision or business definition changed. Start a new conversation.”). | `test_threads_integration.py`, `intent_router.py` |
| History list | Only **per uploaded file**, a `<select>` of creation **timestamps** (no title, no source name, no last activity, no search) hidden in a collapsed “Private conversation history” panel. | old `ask-panel.tsx` |
| Open a past chat | “Open conversation” loaded questions only; every answer needed a separate **Load saved answer** click. | old `ask-panel.tsx` |
| New chat | “New conversation” button existed. | |
| Rename / delete | **Missing.** No title or hidden state on threads. | schema `threads` |
| Chats from other files | **Missing.** Only the open file's chats were reachable. | |

## Gaps closed in this slice

1. **“Your chats” list** — `GET /workspaces/{wid}/threads?q=&limit=` returns the signed-in
   person's chats across the workspace, newest activity first (cap 50), with title
   (rename, else the first question trimmed to 80 characters, else “New chat”),
   dataset name, file name, last activity and turn count. Search covers title,
   questions, dataset and file name (LIKE-escaped). Membership is required; only
   the owner's threads are selected; each listed chat is re-authorized with the same
   per-turn checks as opening it, so a chat hidden by changed access is not listed.
2. **Open a past chat** — clicking a chat loads every turn in order and reopens the
   saved answers automatically (the 10 most recent completed turns; older ones keep
   the **Load saved answer** button). Answers come from the unchanged replay endpoint,
   so they are byte-identical to the first reopen (tested).
3. **Continue in the same chat** — the opened chat becomes the active thread; the next
   question posts to the same thread, keeping its file and structured follow-up
   context. Freshness guards are unchanged (source/definition changes clarify).
   A chat from another file switches the workspace to that file first, then opens.
4. **New chat / rename / remove** — “New chat” starts a fresh thread. Rename
   (`PATCH …/threads/{id}`, 1–120 characters) and Remove (`DELETE …/threads/{id}`,
   204) are owner-only. **Remove hides** the chat (`hidden_at`); turns, receipts and
   audit events are never deleted. Hidden chats 404 for open/continue. Both actions
   write audit events (`conversation.renamed`, `conversation.hidden`).

## Schema change (unavoidable)

Rename and remove need stored per-chat state, and no existing table can hold it
safely, so migration **0031** adds two nullable columns to `threads`: `title
VARCHAR(120)` and `hidden_at TIMESTAMPTZ`. It is additive: images built for 0030
select their own columns and keep working. Readiness now expects `0031`. Downgrade
refuses while any chat has a name or is hidden, so no owner choice is lost.
The VPS is on 0030 — a release must run alembic (the release kit already does).

## Chat actions — what exists vs. not

Reachable from chat replies today (all bounded, server-defined, no arbitrary tools):

| Action | Where in a reply | Exists |
| --- | --- | --- |
| Clickable follow-up questions | “Suggested follow-up questions” chips under verified answers | Yes |
| Clickable clarification choices | “Clarify your request” chips (D17/D14) | Yes |
| Explanation/pattern suggestions | Chips under explanations and pattern results | Yes |
| Open a tool (patterns, unusual values/anomalies, scenarios/daily what-if, forecasts, prepare/finish review, overview) | Guidance action buttons (`guidance.actions` → `onTool`) | Yes |
| Download PDF / Excel / CSV / PNG of an answer | “Download result” on eligible turns; “make a PDF of this answer” in chat | Yes |
| Save answer / question (saved library; can be added to a dashboard there) | “Save” control and “Save question” | Yes |
| Retry / resume / cancel a request | Turn buttons and activity panel | Yes |
| Pin directly to a dashboard from chat | — | **No** (save first, then pin from Saved/Studies) |
| Open a full forecast from a chat answer | Guidance “forecasts” action opens the Forecasts tool; a forecast is not *run* from chat | **Partial** |
| Arbitrary tool execution / code | — | **No, by design** |

No new action types were added in this slice; existing ones are unchanged and reach
reopened chats too (reopened answers render the same chips/buttons).

## Not done / limits

- The list rechecks every turn of every listed chat (≤ 50 chats × ≤ 100 turns);
  marked `shortcut:` in `ThreadService.list_chats` — cache access checks if it gets slow.
- Only the 10 most recent completed answers auto-load on open; older answers need one click.
- Remove is a hide only; there is no “restore hidden chat” screen and no hard delete.
- No pagination beyond the first 50 chats (search narrows the list).
- Chat-level actions such as “pin to dashboard from chat” remain future work.

## Verification

See the final report for exact commands and counts. Tests added:
`apps/api/tests/test_chat_history_integration.py` (listing/search, other members and
outsiders cannot list/open/continue/rename/hide, byte-identical reopen, continuing keeps
context, rename/hide audit, 0031 downgrade guard), `apps/web/tests/chat-history-values.test.mjs`,
and `apps/web/e2e/chat-history.spec.ts` (ask → listed → reload → open → follow-up in the
same thread → open from another file → rename → search → remove, 320/390/1440 in light/dark).
