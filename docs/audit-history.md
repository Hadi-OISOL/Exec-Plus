> **File use case:** Defines the user-visible activity history and its privacy boundary.
> **What it does:** Documents bounded metadata search, current access checks and legacy compatibility.

# Workspace audit history

The audit view contains recorded server actions, their time, actor ID and resource ID.
It contains no source rows, filenames, questions, private goals, model prompts or
credentials. It records an action, not a claim that every operation succeeded.
Its action name distinguishes events such as creation, completion and failure.

Every request checks current workspace membership. Members see their own events
and explicit shared operational events for datasets, uploads, preparation, business
definitions, refresh and monitoring. Workspace owners/admins also see team-management
metadata. Study/version, dashboard, document and saved-item events from someone else
are visible only while the resource is currently shared. Unsharing or deleting that
resource removes those events from another member's next history request.

Private conversation, query, job, forecast, report, alert, preference and dismissal
events remain visible only to their actor, including when the reader is an admin.
An organization never grants access to a department's history. Source facts are not
returned by resolving the resource IDs. Opening any linked resource must apply its
normal authorization independently.

The server uses an explicit shared-action allowlist. Generic resource types are
insufficient: a private preference can refer to a dataset, and private alert events
use the same `refresh` type as shared refresh operations. New action types therefore
remain actor-only unless explicitly classified or backed by a currently shared
resource. Owners cannot use text search or a forged page cursor to bypass visibility.

## API

`GET /workspaces/{workspace_id}/audit-history` returns:

```json
{
  "events": [],
  "next_cursor": null,
  "limit": 50
}
```

Each event has `id`, `workspace_id`, `actor_id`, `action`, `resource_type`,
`resource_id` and `created_at`. Results are newest first, with UUID ordering to
break timestamp ties. An opaque `next_cursor` advances to older records; inserts
after the first request do not duplicate records on later pages. A changed sharing
decision can remove previously visible history. Refresh starts a new first page.

| Parameter | Contract |
| --- | --- |
| `limit` | Integer 1–100; default 50 |
| `cursor` | Returned opaque cursor, at most 200 characters |
| `q` | At most 80 characters; literal case-insensitive match on action/type/IDs |
| `action` | Exact action, at most 50 characters |
| `resource_type` | Exact type, at most 30 characters |
| `since`, `until` | Inclusive ISO timestamps with explicit timezone; start cannot exceed end |

Visibility and all filters run in PostgreSQL before fetching at most `limit + 1`
records. There are no hidden-resource totals or queries against uploaded values.
Missing membership returns 404; unauthenticated requests return 401. Invalid
filters/cursors return safe 422 errors. All responses remain `Cache-Control: no-store`.

The historical `GET /audit-events` endpoint keeps its list-shaped response and
owner/admin requirement. It now applies the same resource-privacy filter instead of
disclosing every other member's private event identifiers. Internal usage aggregation
retains its existing identifier-only event input and does not expose private event lists.

This slice does not add export, tamper-evident audit retention, regulated-customer
permission controls or production security approval.
