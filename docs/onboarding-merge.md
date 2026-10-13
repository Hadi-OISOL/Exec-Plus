> **File use case:** Explains the integrated teammate onboarding experience.
> **What it does:** Defines optional guided review, private notes and explicit shared-meaning drafts.

# Guided data review

The October 13 integration recovers the question cards and styling from the teammate's
`/home/administrator/abm/Exec-Plus` checkout. Its old page was not substituted for
the current application: three frontend inputs were merged with the 0017 code.
The original checkout and unrelated work remain intact.

After uploading CSV/Excel, observed findings remain visible and a guided review offers
Yes, explain, Back and Skip. Existing uploads can use **Review this upload step by
step** in the overview. The flow focuses on grain and at most ten columns, discloses
that limit and never confirms the entire schema automatically.

The final preview offers separate actions:

- **Save my data notes** saves user-reported interpretation privately by default.
  Explicit sharing makes the note available under ordinary workspace permissions.
  Notes are not verified calculations and do not confirm shared definitions.
- **Save draft meanings** writes explicit structured corrections through the existing
  optimistic understanding API, only when the actor has edit permission. The result
  remains `needs_review`. Personal notes are not inserted into shared meanings.
- **Review and confirm full meanings** opens the complete existing editor. Its source,
  permission, required-field and confirmation guards remain authoritative.
- **Continue to my insights** closes the flow without saving unsaved answers.

Save outcomes are independent. A failed or stale draft does not erase a saved note;
a failed request does not display success. Pending operations prevent double clicks.
Source/account changes abort obsolete client reads and discard local answers. A
network interruption can leave server completion uncertain; inspect history before
retrying. This is not an exactly-once write guarantee.

Untouched metrics, relationships and column fields are preserved. Currency/per-row
unit policies require full review rather than a quick unit override. Numerical
profiling and queries continue to use the existing deterministic backend, exact
wire formats, permissions and source evidence.

This is a frontend-only private-demo improvement on migration 0017. It changes no
model, email delivery, identity provider or public network exposure. VC 18 remains
Done for its bounded guided-upload scope; VC 47 remains Partial because customer
self-signup and paid-plan onboarding are still absent. See the
[gap audit](onboarding-merge-gap-audit.md) and
[verification ledger](verification-onboarding-merge.md).
