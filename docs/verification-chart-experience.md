> **File use case:** Records evidence for the requested chart and data-presentation enhancement.
> **What it does:** Separates measured checks, retained failures, source preservation and deployment status.

# Chart experience verification

Scope follows [the contract](chart-experience.md) and
[the reference audit](chart-experience-reference-audit.md). This is a web-only
change over existing deterministic results, saved evidence and permissions.
Initial web release `879d90f` is deployed; final live checks identify a dashboard
layout issue that is being corrected. Schema remains 0018, with no API,
jobs, provider or numerical-method change.

## Implementation and reference evidence

The shared answer view has Bars, Dots and eligible Line/observed-point views,
readable scales, exact focus/hover details and the existing table/expand/drill
controls. Dot stems use the same zero baseline and returned rows as bars; nulls
have no mark and true zero stays at zero. Axis labels use the existing string
formatter for digit grouping and insignificant trailing zeros. Raw strings remain
in titles, inspection and tables; no Number-based label rounding is introduced.
Geometry remains approximate, including values too close to plot distinctly.

Dashboard cards have a clear reading order, actual units where returned, source
details and a calculated-state badge only after content arrives. Forecasts retain
unconnected observed/estimated markers, uncertainty and missing values. Named
regions, selected periods and recorded/forecast values make the chart readable;
forecast tick labels are explicitly approximate. Pattern cards expose their real
scatter data and pooled/group comparisons without inventing stronger findings.

Five project-local coding skills now include the unmodified pinned Lieflat
package. All 146 installed files match the reviewed source/reference. Its prior
partial scanner findings are retained; installation is not a new safety audit.
No upstream template, token file or executable HTML is copied into the product.
oneDAL remains a reviewed source, not a deployed ML engine. See the reference audit
for the distinct use of all seven repositories.

## Local checks and retained failures

- The first expanded visualization journey passes in 14.1 seconds, including
  signed/extreme values, null/zero, Dots, exact tables and real filtered drill-down.
  Visual review then applies existing exact string formatting to axis labels and
  removes a repeated chart subtitle. The original raw inspector/table is retained.
- The selected twelve-journey run has ten passes and two failures in 2.7 minutes.
  Forecast pointer entry can replace the chosen period when a control scrolls
  into view. This is a real new interaction bug: explicit period/record selection
  is now separate from hover preview, scrolling does not select a point, and
  leaving the plot restores selection. The same behavior is applied to scatter
  inspection. The original failed assertion remains; additional checks cover
  hover followed by explicit navigation.
- The second failure is an outdated study-chart assertion: two transparent hit
  targets plus two visible marks are counted as four SVG circles. The corrected
  assertion counts two semantic observation targets and still requires no lines.
- Initial unit checks pass 37 cases; focused forecast/pattern rendering checks
  pass 16, including missing intervals, precision and empty prediction rows.
  Five architecture checks pass. A lint invocation from the repository root fails
  to locate the workspace config; normal workspace lint is required below.

The six affected browser journeys pass in 1.1 minutes after recovery. Across the
selected run and reruns, all twelve distinct journeys have passing executions;
this is not a claim of one clean twelve-case run. After the final readable forecast-highlight adjustment, frontend tests pass all
38 cases without skips; the 17 focused forecast/pattern cases are included in that
total. A final basic-forecast browser rerun passes in 19.2 seconds. Normal workspace
ESLint/TypeScript pass. The relevant
new checks cover hover followed by explicit navigation, 375-pixel and landscape
layouts, increased root font size, reduced motion and original exact values.
Desktop/narrow screenshots are inspected; current copies are retained in the
release folder even where older test helpers use historical screenshot paths.

The first local production build passes. After the live layout review, the
scoped KPI grid/font and pattern picker repairs pass their two browser checks in
22.3 seconds at desktop and narrow widths. The new large-value KPI case raises
the local total to **13 distinct browser journeys with passing executions**. It
checks full numeric text, one-line normal values, card widths and no overflow;
the pattern check requires a 44–60 pixel picker that fits its parent. Final
static/build and private-release evidence follow below.
No full backend or model-quality evaluation is claimed for this presentation work.
Private logs and screenshots remain in
`data/verification/2026-10-16/chart-experience/`.

## Private demo

Before-release browser inspection covers three fictional-source journeys and
eighteen layouts with unchanged source bytes/profile/definitions/history and no
page errors. Its initial helper incorrectly blocks seven automatic data-brief
requests. This failed helper result is retained. Source review establishes that
the matching confirmed definition returns before model/sampling/audit; the helper
now permits only that exact confirmed-source route. No production source,
definition or memory writes are permitted by the helper.

Initial deployment builds and activates the web image successfully, with backend
container IDs/images/start times and environment checksum unchanged. Readiness
and the workspace recover after the expected initial connection-refused startup
retry. All five reported-source artifacts remain unchanged. A direct artifact
copy cannot traverse the root-owned ops directory; the same evidence is retrieved
through the established administrator sudo channel. The first live dashboard
screenshot reveals an actual CSS precedence bug: inherited grid rules squeeze
large KPI values into narrow cards. This is retained as a release failure pending
a scoped repair and new browser/build/release checks. The first expanded live
helper also stops on an overly strict forecast-picker selector after nine layouts;
the semantic combobox selector is corrected without changing expectations. The
retry passes three journeys and 27 layouts in 55.199 seconds, with both fictional
sources unchanged and no page errors or prohibited writes. Visual inspection
still rejects the KPI layout and a 145-pixel-tall pattern record picker caused
by inherited label direction. Both get scoped CSS repairs. The added KPI browser
case initially times out on “Revenue” versus the existing “Total revenue” label;
the frozen corrected selector is used in the final rerun. Other three cases in
that run pass; these failures are not removed from the record.

The checked pre-release backup is `20261016T075401Z`; database and objects archive
checksums pass and services restart healthy. Fresh snapshots of the user's
reported source are retained separately for the release comparison. This is
archive-integrity evidence, not a restore drill. The prior existing-tab mismatch
remains unverified; no successful fresh-browser check alone diagnoses its cause.

All 64 original feature IDs, 37 Done / 16 Partial / 11 Not yet and eight blocked
production gates remain unchanged.
