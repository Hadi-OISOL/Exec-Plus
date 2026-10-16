> **File use case:** Defines the requested chart and data-presentation enhancement.
> **What it does:** Connects the user's visual references to bounded original ExecPlus implementation and verification.

# Chart experience

The October 16 follow-up explicitly asks for the supplied chart skill and other
repositories to affect the product's actual data display. Downloading references
does not satisfy that request. This work changes the dashboard, shared calculated
answer charts, measured-pattern cards and forecast results. Local implementation
is verified; private-demo release checks are in progress. See the
[verification ledger](verification-chart-experience.md) for actual results.

## Presentation contract

- Lead with the real question or measure, then readable figures and source context.
- Use existing returned data only. Original React/SVG presents values; it does not
  invent totals, percentage changes, rankings, forecasts or causal explanations.
- Preserve signed values, true zero, missing values, numeric strings, table order,
  filtered drill-down, exact tables and immutable source receipts.
- Keep observed and estimated values visually distinct. Uncertainty and missing
  observations remain visible; a line must not bridge absent observations.
- Show useful focus/touch details as well as hover. Keep controls keyboard usable,
  support narrow screens and reduced motion, and avoid decorative simulated data.
- Compose existing dashboard cards and figures with calm spacing and clear reading
  order. Do not mistake file consistency or a saved definition for analysis readiness.

## Repository use

The supplied UI/UX and chart guidance inform the coding workflow. The general EDA
and SQL examples inform the inspect → compare → investigate reading order. The
skill scanner checks development tools. oneDAL requires a justified numerical
adapter and independent evaluation before runtime adoption; installing it merely
to restyle charts would not implement a useful model. No new backend method,
provider, permissions or schema is part of this presentation change.

Lieflat's pinned skill is available locally as requested. Its template
license and the separate permissive licenses of chart engines are distinct. The
product changes use independently written components, without copying upstream
templates, token files or executable HTML. The source/reference audit records
exact installation and observable design evidence.

## Acceptance

Relevant existing journeys must still pass exact-value, gap, source-filter,
replay, keyboard, reduced-motion and narrow-screen checks. Add meaningful
coverage for new interactions. Inspect screenshots of real returned results,
then build and activate the web image with a rollback checkpoint and preserved
user data. Record initial failures as well as passing reruns. The user's earlier
open-tab mismatch remains unverified until their refreshed screen is observed.
