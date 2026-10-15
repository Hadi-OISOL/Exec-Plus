> **File use case:** Records the October 15 four-phase improvement request and its boundaries.
> **What it does:** Connects simpler screens and reliable data understanding to measurable delivery criteria.

# Clean experience and better understanding

The user authorized four phases, with phases one and two implemented now and the
remaining two retained for the next working session. This extends the existing
private demo. It does not change model providers, network exposure or production
acceptance requirements. The original 64 feature IDs remain the source of truth.

| Phase | Scope | Acceptance | Status |
| --- | --- | --- | --- |
| 1 — Focused experience | Separate Home, reading, definition review and conversation; retain drafts on Back; show one primary task; responsive charts, finite transitions and honest loading states. | Existing navigation and saved work remain available; desktop and narrow screens pass; keyboard/reduced-motion behavior and exact chart/table values are preserved. | In progress October 15 |
| 2 — Reliable understanding | Supply saved descriptions, meanings and units to the current model; preserve answered definitions; allow one bounded correction for invalid qualitative readings; ask for an actual missing detail; recheck source and permissions before returning. | Invalid/slow/provider failures recover safely; no invented numbers or automatic confirmation; retry respects budgets; changed context is rejected; actual hosted reading and saved replay pass. | In progress October 15 |
| 3 — Internal analytics depth | Evaluate one bounded descriptive-driver extension for 33 and explicit precedence/exclusion constraints for 59. Review scenario 57 and anomaly 58 gaps before choosing an additional method; preserve current daily what-if, grouped baselines and exact allocation. | Independent numerical fixtures, sparse/degenerate/infeasible cases, exact receipts, compatibility and owner privacy. Causal or predictive claims require separate evidence. | Planned for next session; not implemented by this release |
| 4 — Cross-feature reliability | Exercise the complete upload → meaning → question → tool → saved-result journey, build an internal failure-case evaluation set and measure a repeatable local workload. Improve specific bottlenecks only when measured. | Document failures, recovery and performance on declared fixtures; preserve source data and existing work. Representative human-labelled evaluation and sustained production acceptance remain open. | Planned after phase 3; not scheduled automatically |

## Feature mapping

- Phase 1 improves existing data reading and onboarding (18/47), chat and visual
  exploration. Production signup/login remains a separate dependency for 1/40/47.
- Phase 2 improves current explanation/planning quality and internal checks for 44.
  Fictional tests cannot close representative model-quality acceptance.
- Phase 3 addresses internal logic within Partial 33/57/58/59. None is declared
  broadly complete from a bounded method. Read the advanced analytics research
  plan before selecting the next implementation and validation contract.
- Phase 4 provides internal evidence toward 44/50, not a production-quality or
  sustained-performance certification.
- External identity, billing, SMTP, off-server recovery, monitoring destinations,
  connectors and customer integration policies are outside today's two phases.
  Fine-grained permissions (64) need a dedicated policy/architecture design.

## Reference and release contract

Public ThoughtSpot/Metabase behavior and open-source library suitability are
recorded in `clean-experience-reference-audit.md`. REA captures are observations
of accessible screens, not access to private source or backend behavior. Prefer
the existing controls where they meet the need; add a library only for a concrete
benefit after compatibility and license review.

Keep the database on 0017 and the existing API shapes compatible. Before private
release: run relevant backend/browser/static/build checks, check backups, preserve
source data and configuration fingerprints, test the hosted model and old saved
work, then record evidence and remaining limitations. All eight production gates
and the 37 Done / 16 Partial / 11 Not yet counts remain unchanged unless their
documented acceptance criteria are independently satisfied.
